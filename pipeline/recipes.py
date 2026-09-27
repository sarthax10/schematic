"""Scene recipes: hand-staged, tested compositions that a small LLM fills in.

Designing a scene from scratch (placing a dozen actors, timing beats, moving the camera) is
beyond a 7-14B local model; shown an example, it copies the example. Filling a small form is
not. So each recipe owns the craft — layout inside the safe area, sizes, depth, camera moves,
motion, the order things happen — and exposes only a few slots: who is involved, which
objects, which short labels, and which words of the narration trigger each step.

Slot schemas are JSON Schemas with enums drawn from the runtime's own catalogs, so with
structured output the model cannot name a prop or icon that doesn't exist. Cue phrases that
aren't in the narration are repaired here (nearest matching word, else a word at the right
point in the sentence) instead of failing the scene.

    python -m pipeline.recipes --gallery      # every recipe with its sample slots → out/recipe_gallery/
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import plan as plan_mod
from .timeline import _norm_tokens

PROPS = sorted(plan_mod.PROP_HEIGHTS)
CONTAINERS = ["jar", "bucket", "box", "database", "server", "cup", "conveyor"]  # props that visibly hold things
ICONS = sorted(plan_mod.ICONS)
SHIRTS = ["sky", "coral", "mint", "amber", "lav", "sand"]
TONE = ["ok", "fail", "signal", "sky", "lavender"]
STOP = set("a an the of to and or is are was be it its in on at for with that this so as by then they them their "
           "you your we our i he she his her there here".split())


# ---- cues ------------------------------------------------------------------------------------
class Cues:
    """Makes sure every cue names words that are actually spoken in this scene."""

    def __init__(self, narration: str):
        self.raw = narration.split()
        self.norm = [" ".join(_norm_tokens(w)) for w in self.raw]
        self.text = " ".join(_norm_tokens(narration))
        self.repaired: list[str] = []

    def _at_fraction(self, frac: float) -> str:
        n = len(self.raw)
        i = max(0, min(n - 1, int(frac * n)))
        # Prefer a content word near that point so the phrase is distinctive.
        for j in list(range(i, n)) + list(range(i - 1, -1, -1)):
            if self.norm[j] and self.norm[j] not in STOP and len(self.norm[j]) > 2:
                return " ".join(x for x in self.norm[j:j + 2] if x)
        return self.norm[i]

    def get(self, phrase: str | None, frac: float) -> str:
        if phrase:
            p = " ".join(_norm_tokens(phrase))
            if p and re.search(rf"(^| ){re.escape(p)}", self.text):
                return phrase
            # Longest content word of the phrase that is spoken in the scene.
            for w in sorted(_norm_tokens(phrase), key=len, reverse=True):
                if w not in STOP and len(w) > 2 and re.search(rf"(^| ){re.escape(w)}", self.text):
                    self.repaired.append(f"{phrase!r} → {w!r}")
                    return w
        fallback = self._at_fraction(frac)
        self.repaired.append(f"{phrase!r} → {fallback!r} (not spoken; placed by position)")
        return fallback


# ---- shared slot schemas ----------------------------------------------------------------------
def _str(max_len: int, desc: str = "") -> dict:
    d = {"type": "string", "maxLength": max_len}
    if desc:
        d["description"] = desc
    return d


CUE = {"type": "string", "description": "2-4 words copied exactly from the narration"}
PARTY = {
    "type": "object",
    "description": "a participant: a person (real-life analogy), a device/system (tech), or an object",
    "properties": {
        "kind": {"enum": ["person", "device", "object"]},
        "label": _str(14, "short name shown on screen"),
        "icon": {"enum": ICONS, "description": "for kind=device"},
        "prop": {"enum": PROPS, "description": "for kind=object"},
        "shirt": {"enum": SHIRTS, "description": "for kind=person"},
    },
    "required": ["kind", "label"],
}
ITEM = {"enum": ["packet"] + PROPS, "description": "what travels: 'packet' for data, or a real object"}


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


# ---- actor helpers ------------------------------------------------------------------------------
def _height(kind: str, size: float, prop: str | None = None) -> float:
    if kind == "person":
        return size * 1.6
    if kind == "device":
        return size * 0.8
    return size * plan_mod.PROP_HEIGHTS.get(prop or "box", 200) / 200


def party(aid: str, spec: dict, x: float, y_feet: float, *, size: float | None = None, face: str | None = None,
          idx: int = 0, name_label: bool = True) -> tuple[list[dict], dict]:
    """Actors for one participant standing on y_feet. Returns (actors, info) where info has
    the main actor id, centre and top (for bubbles, labels and camera framing)."""
    kind = spec.get("kind") if spec.get("kind") in ("person", "device", "object") else "device"
    size = size or {"person": 2.3, "device": 2.5, "object": 2.3}[kind]
    prop = spec.get("prop") if spec.get("prop") in plan_mod.PROP_HEIGHTS else "box"
    h = _height(kind, size, prop)
    cy = round(y_feet - h / 2, 3)
    label = (spec.get("label") or "").strip()[:14]
    actors: list[dict] = []
    if kind == "person":
        a = {"id": aid, "type": "character", "at": [x, cy], "size": size,
             "look": {"shirt": spec.get("shirt") if spec.get("shirt") in SHIRTS else SHIRTS[idx % len(SHIRTS)]}}
        if face:
            a["face"] = face
        actors.append(a)
    elif kind == "device":
        icon = spec.get("icon") if spec.get("icon") in plan_mod.ICONS else "server"
        actors.append({"id": aid, "type": "node", "icon": icon, "label": label or icon, "at": [x, cy], "size": size})
        name_label = False  # the node card carries its own label
    else:
        actors.append({"id": aid, "type": "prop", "prop": prop, "at": [x, cy], "size": size})
    if name_label and label:
        actors.append({"id": f"{aid}_name", "type": "text", "style": "label", "text": label, "attached": aid,
                       "at": [x, round(y_feet + 0.55, 3)], "size": max(2.6, size + 0.6)})
    return actors, {"id": aid, "kind": kind, "x": x, "cy": cy, "top": cy - h / 2, "h": h}


def ground(y: float) -> dict:
    return {"id": "floor", "type": "shape", "shape": "ground", "at": [6, y]}


def headline(text: str | None, y: float = 2.85) -> list[dict]:
    if not text:
        return []
    text = text.strip()
    text = text[:1].upper() + text[1:]  # sentence case, even when the model writes "tcp handshake"
    return [{"id": "headline", "type": "text", "style": "title", "text": text[:44], "at": [6, y], "size": 10.2, "screen": True}]


def react(actor: dict, cue: str | None, good: bool, after: float | None = None) -> list[dict]:
    """A reaction that reads on any kind of actor: people pose, things glow."""
    b0 = {"at": cue} if cue and after is None else {"after": after or 0.1}
    if actor["kind"] == "person":
        return [{**b0, "do": "state", "actor": actor["id"], "state": {"pose": "cheer" if good else "sad", "expression": "smile" if good else "frown"}},
                {"after": 0.1, "do": "emit", "actor": actor["id"], "kind": "check" if good else "question"}]
    return [{**b0, "do": "highlight", "actor": actor["id"], "tone": "ok" if good else "fail", "hold": 1.8},
            {"after": 0.1, "do": "emit", "actor": actor["id"], "kind": "check" if good else "cross"}]


# ---- recipes ----------------------------------------------------------------------------------
@dataclass
class Recipe:
    name: str
    use_when: str
    schema: dict
    build: Callable[[dict, Cues], dict]
    sample: dict  # (narration, slots) used by the gallery and tests — never shown to the model


def build_exchange(s: dict, c: Cues) -> dict:
    """Two parties trade a sequence of messages; each message leaves its label in a central
    ledger, so the whole protocol is readable at the end."""
    msgs = (s.get("messages") or [])[:4]
    people = any((s.get(k) or {}).get("kind") == "person" for k in ("left", "right"))
    feet = 10.9
    big = {"person": 2.6, "device": 2.9, "object": 2.6}
    L, li = party("left", s.get("left") or {}, 2.6, feet, face="right", idx=0, size=big.get((s.get("left") or {}).get("kind"), 2.8))
    R, ri = party("right", s.get("right") or {}, 9.4, feet, face="left", idx=1, size=big.get((s.get("right") or {}).get("kind"), 2.8))
    actors = ([ground(feet)] if people else []) + headline(s.get("headline")) + L + R
    beats1, beats2, beats3 = [], [], []
    n = max(len(msgs), 1)
    for k, m in enumerate(msgs):
        frm, to = (li, ri) if m.get("from", "left") == "left" else (ri, li)
        arrow = "→" if frm is li else "←"
        tid = f"msg{k}"
        actors.append({"id": tid, "type": "text", "style": "mono", "text": f"{arrow} {m.get('label', '')[:18]}".strip(),
                       "tone": m.get("tone") if m.get("tone") in TONE else "signal", "at": [6, round(4.5 + k * 0.95, 2)], "size": 6.4})
        cue = c.get(m.get("cue"), (k + 0.5) / (n + 1))
        target = beats1 if k < 2 else beats2
        item = m.get("item") if m.get("item") in ITEM["enum"] else "packet"
        target += [
            {"at": cue, "do": "send", "from": frm["id"], "to": to["id"], "item": item, "dur": 0.9, "arc": 1.6,
             "size": 0.45 if item == "packet" else 1.0},
            {"at": cue, "do": "enter", "actor": tid, "style": "type"},
        ]
        if frm["kind"] == "person":
            target.append({"at": cue, "do": "state", "actor": frm["id"], "state": {"pose": "reach"}})
            target.append({"after": 1.0, "do": "state", "actor": frm["id"], "state": {"pose": "idle"}})
    out_cue = c.get(s.get("outcome_cue"), 0.9)
    beats3 += react(li, out_cue, s.get("outcome_good", True)) + react(ri, None, s.get("outcome_good", True), after=0.12)
    if s.get("outcome_label"):
        beats3.append({"after": 0.1, "do": "label", "actor": "right", "text": s["outcome_label"][:14], "tone": "ok" if s.get("outcome_good", True) else "fail"})
    shots = [{"camera": {"focus": [6, 7.3], "zoom": 1.0}, "beats": beats1}]
    if beats2:
        shots.append({"at": beats2[0]["at"], "camera": {"focus": [6, 7.2], "zoom": 1.1}, "beats": beats2})
    shots.append({"at": out_cue, "camera": {"focus": [6, 7.8], "zoom": 1.06}, "beats": beats3})
    return {"actors": actors, "shots": shots}


def build_flow(s: dict, c: Cues) -> dict:
    """Something travels through a chain of 2-4 components; each lights up as it passes; it
    may fail at one step (the error travels back)."""
    stages = (s.get("stages") or [])[:4]
    n = len(stages)
    if n <= 3:
        xs = {1: [6], 2: [3.2, 8.8], 3: [2.3, 6, 9.7]}[max(n, 1)]
        pos = [(x, 8.4) for x in xs[:n]]
    else:
        pos = [(3.4 if k % 2 == 0 else 8.6, 4.8 + k * 2.0) for k in range(n)]
    actors = headline(s.get("headline"))
    for k, (st, (x, y)) in enumerate(zip(stages, pos)):
        icon = st.get("icon") if st.get("icon") in plan_mod.ICONS else "server"
        actors.append({"id": f"st{k}", "type": "node", "icon": icon, "label": (st.get("label") or icon)[:12], "at": [x, y], "size": 2.4 if n <= 3 else 2.2})
    for k in range(n - 1):
        actors.append({"id": f"w{k}", "type": "connector", "from": f"st{k}", "to": f"st{k + 1}", "curve": "arc", "bend": 0.6 if n > 3 else -0.8})
    fail_at = s.get("fail_at")
    fail_at = fail_at if isinstance(fail_at, int) and 0 < fail_at < n else None
    item = s.get("item") if s.get("item") in ITEM["enum"] else "packet"
    b1, b2 = [], []
    last = (fail_at if fail_at is not None else n - 1)
    for k in range(n):
        cue = c.get(stages[k].get("cue"), (k + 0.5) / (n + 1))
        tgt = b1 if k < 2 else b2
        if 0 < k <= last:
            tgt.append({"at": cue, "do": "send", "via": f"w{k - 1}", "to": f"st{k}", "item": item, "dur": 0.8, "size": 0.45 if item == "packet" else 0.9})
        tgt.append({"at": cue, "do": "highlight", "actor": f"st{k}", "tone": "signal", "hold": 1.2})
    end_cue = c.get(s.get("result_cue"), 0.9)
    b3 = []
    if fail_at is not None:
        b3 += [{"at": end_cue, "do": "shake", "actor": f"st{fail_at}"},
               {"at": end_cue, "do": "highlight", "actor": f"st{fail_at}", "tone": "fail", "hold": 2.0},
               {"at": end_cue, "do": "send", "via": f"w{fail_at - 1}", "reverse": True, "to": f"st{fail_at - 1}", "item": "packet", "tone": "fail", "dur": 0.8}]
        if s.get("result_label"):
            b3.append({"after": 0.1, "do": "label", "actor": f"st{fail_at}", "text": s["result_label"][:14], "tone": "fail"})
    else:
        b3 += [{"at": end_cue, "do": "highlight", "actor": f"st{n - 1}", "tone": "ok", "hold": 2.0},
               {"after": 0.1, "do": "emit", "actor": f"st{n - 1}", "kind": "check"}]
        if s.get("result_label"):
            b3.append({"after": 0.1, "do": "label", "actor": f"st{n - 1}", "text": s["result_label"][:14], "tone": "ok"})
    mid = pos[min(1, n - 1)]
    shots = [{"camera": {"focus": [6, 7.6 if n > 3 else 7.9], "zoom": 1.0 if n <= 3 else 0.95}, "beats": b1}]
    if b2:
        shots.append({"at": b2[0]["at"], "camera": {"focus": [6, pos[2][1] - 1.0], "zoom": 1.1}, "beats": b2})
    shots.append({"at": end_cue, "camera": {"focus": [mid[0] if fail_at else 6, 7.6], "zoom": 1.05 if n <= 3 else 0.95}, "beats": b3})
    return {"actors": actors, "shots": shots}


def build_queue(s: dict, c: Cues) -> dict:
    """A line of people at a counter: the first few are served, the rest wait."""
    count = max(3, min(8, int(s.get("people") or 6)))
    served = max(1, min(count - 1, int(s.get("served") or 3)))
    item = s.get("item") if s.get("item") in plan_mod.PROP_HEIGHTS else "ticket"
    server_prop = s.get("server_prop") if s.get("server_prop") in plan_mod.PROP_HEIGHTS else "bell"
    actors = [ground(7.9), {"id": "counter", "type": "prop", "prop": "shop-counter", "at": [9.35, 6.2], "size": 3.6, "allowOverlap": ["server", "p0", "p1"]}]
    sh = plan_mod.PROP_HEIGHTS[server_prop] / 200 * 1.6
    actors.append({"id": "server", "type": "prop", "prop": server_prop, "at": [9.45, round(5.46 - sh / 2, 3)], "size": 1.6})
    if s.get("server_label"):
        actors.append({"id": "server_name", "type": "text", "style": "label", "text": s["server_label"][:14], "at": [9.45, 2.9], "size": 3.6})
    for k in range(count):
        t = k / max(count - 1, 1)
        size = round(1.45 + 0.7 * t, 2)
        x, y = round(8.1 - 7.2 * t, 2), round(6.6 + 3.4 * t, 2)
        actors.append({"id": f"p{k}", "type": "character", "at": [x, y], "size": size, "look": {"shirt": SHIRTS[k % len(SHIRTS)]},
                       "allowOverlap": [f"p{k - 1}", f"p{k + 1}", "counter"]})
    arrive, serve, wait = c.get(s.get("arrive_cue"), 0.1), c.get(s.get("serve_cue"), 0.4), c.get(s.get("wait_cue"), 0.75)
    b1 = [{"at": arrive, "do": "enter", "actor": "p0", "style": "slide-right"}] + [
        {"after": 0.08, "do": "enter", "actor": f"p{k}", "style": "slide-right"} for k in range(1, count)]
    for k in range(served):
        b1.append({"at": serve, "do": "send", "from": "server", "to": f"p{k}", "item": item, "dur": 0.5 + 0.06 * k, "arc": 1.0 + 0.2 * k} if k == 0
                  else {"after": 0.12, "do": "send", "from": "server", "to": f"p{k}", "item": item, "dur": 0.5 + 0.06 * k, "arc": 1.0 + 0.2 * k})
    b1.append({"after": 0.4, "do": "state", "actor": "p0", "state": {"pose": "cheer"}})
    b1 += [{"after": 0.06, "do": "state", "actor": f"p{k}", "state": {"pose": "cheer"}} for k in range(1, served)]
    b2 = [{"at": wait, "do": "state", "actor": f"p{count - 1}", "state": {"pose": "sad", "expression": "frown"}},
          {"after": 0.08, "do": "state", "actor": f"p{count - 2}", "state": {"pose": "sad", "expression": "frown"}} if count - 2 >= served else None,
          {"after": 0.1, "do": "emit", "actor": f"p{count - 1}", "kind": "zzz"}]
    b2 = [b for b in b2 if b]
    if s.get("wait_label"):
        b2.append({"after": 0.1, "do": "label", "actor": "server", "text": s["wait_label"][:14], "tone": "fail"})
    shots = [{"camera": {"focus": [5.6, 7.7], "zoom": 0.94}, "beats": b1},
             {"at": wait, "camera": {"focus": [1.9, 8.6], "zoom": 1.45}, "beats": b2}]
    return {"actors": actors, "shots": shots}


def build_fill(s: dict, c: Cues) -> dict:
    """A container fills one item at a time until full; the next one overflows."""
    cap = max(2, min(6, int(s.get("capacity") or 4)))
    container = s.get("container") if s.get("container") in CONTAINERS else "jar"
    item = s.get("item") if s.get("item") in plan_mod.PROP_HEIGHTS else "ticket"
    src, si = party("source", s.get("source") or {"kind": "person", "label": ""}, 2.5, 10.0, size=2.5)
    ch = plan_mod.PROP_HEIGHTS[container] / 200 * 3.0
    actors = [ground(10.0)] + headline(s.get("headline")) + src
    cont = {"id": "box", "type": "prop", "prop": container, "at": [7.4, round(10.0 - ch / 2, 3)], "size": 3.0}
    if container == "jar":
        cont["state"] = {"count": 0}
    actors.append(cont)
    actors.append({"id": "level", "type": "meter", "value": 0, "at": [7.4, round(10.0 - ch - 0.9, 3)], "size": 3.4, "tone": "signal"})
    fill_cue, full_cue, over_cue = c.get(s.get("fill_cue"), 0.15), c.get(s.get("full_cue"), 0.55), c.get(s.get("overflow_cue"), 0.8)
    b1 = []
    shown = min(cap, 4)
    for k in range(shown):
        first = {"at": fill_cue} if k == 0 else {"after": 0.25}
        b1.append({**first, "do": "send", "from": "source", "to": "box", "item": item, "dur": 0.6, "arc": 1.5})
        v = (k + 1) / cap if k < shown - 1 else (cap - 1) / cap
        b1.append({"after": 0.6, "do": "state", "actor": "level", "state": {"value": round(v, 3)}})
        if container == "jar":
            b1.append({"after": 0.0, "do": "state", "actor": "box", "state": {"count": round(v * 6)}})
    if si["kind"] == "person":
        b1.insert(0, {"at": fill_cue, "do": "state", "actor": "source", "state": {"pose": "reach"}})
    b2 = [{"at": full_cue, "do": "send", "from": "source", "to": "box", "item": item, "dur": 0.5, "arc": 1.2},
          {"after": 0.5, "do": "state", "actor": "level", "state": {"value": 1}},
          {"after": 0.0, "do": "label", "actor": "box", "text": (s.get("full_label") or "Full")[:14], "tone": "ok"}]
    if container == "jar":
        b2.insert(2, {"after": 0.0, "do": "state", "actor": "box", "state": {"count": 6}})
    b2 += [{"at": over_cue, "do": "send", "from": "source", "to": [11.2, 12.8], "item": item, "dur": 1.1, "arc": 3.0, "spin": True, "impact": False},
           {"at": over_cue, "do": "shake", "actor": "box"},
           {"after": 0.3, "do": "label", "actor": "box", "text": (s.get("overflow_label") or "Dropped")[:14], "tone": "fail"}]
    if si["kind"] == "person":
        b2.append({"at": over_cue, "do": "state", "actor": "source", "state": {"pose": "shrug", "expression": "open"}})
    shots = [{"camera": {"focus": [5.6, 7.6], "zoom": 1.0}, "beats": b1},
             {"at": full_cue, "camera": {"focus": [7.2, 7.4], "zoom": 1.3}, "beats": b2}]
    return {"actors": actors, "shots": shots}


def build_compare(s: dict, c: Cues) -> dict:
    """Two options side by side; the better one wins. Text stays in ink (readable on every mood);
    colour lives on the hero and the verdict, not the words."""
    actors = headline(s.get("headline"))
    sides = []
    for side, x in (("left", 3.4), ("right", 8.6)):
        d = s.get(side) or {}
        title = (d.get("title") or side)[:14]
        if d.get("icon") in plan_mod.ICONS and not d.get("prop"):
            acts, info = party(side, {"kind": "device", "icon": d["icon"], "label": title}, x, 7.4, size=2.7, name_label=False)
        else:
            acts, info = party(side, {"kind": "object", "prop": d.get("prop"), "label": title}, x, 7.4, size=2.3, name_label=True)
        actors += acts
        for k, pt in enumerate((d.get("points") or [])[:2]):
            actors.append({"id": f"{side}_p{k}", "type": "text", "style": "label", "text": pt[:32], "attached": side,
                           "at": [x, round(8.6 + k * 1.25, 2)], "size": 4.0})
        sides.append((side, c.get(d.get("cue"), 0.1 if side == "left" else 0.5)))
    winner = s.get("winner") if s.get("winner") in ("left", "right") else "right"
    loser = "left" if winner == "right" else "right"
    (_, lcue), (_, rcue) = sides
    right_ids = [a["id"] for a in actors if a["id"] == "right" or a["id"].startswith("right_")]
    b1 = [{"at": lcue, "do": "pulse", "actor": "left"}] + [
        {"after": 0.3, "do": "enter", "actor": a["id"], "style": "rise"} for a in actors if a["id"].startswith("left_p")]
    b2 = [{"at": rcue, "do": "enter", "actor": "right", "style": "pop"}] + [
        {"after": 0.25, "do": "enter", "actor": i, "style": "rise"} for i in right_ids if i != "right"]
    v = c.get(s.get("verdict_cue"), 0.85)
    b3 = [{"at": v, "do": "dim", "actors": [a["id"] for a in actors if a["id"] == loser or a["id"].startswith(f"{loser}_")]},
          {"at": v, "do": "highlight", "actor": winner, "tone": "ok", "hold": 2.5},
          {"after": 0.1, "do": "emit", "actor": winner, "kind": "check"}]
    # Right side waits off set until named; the left side is there from the first frame.
    return {"actors": actors, "shots": [
        {"camera": {"focus": [5.7, 7.2], "zoom": 1.08}, "beats": b1},
        {"at": rcue, "camera": {"focus": [6.3, 7.2], "zoom": 1.08}, "beats": b2},
        {"at": v, "camera": {"focus": [6, 7.3], "zoom": 1.0}, "beats": b3}]}


def build_stat(s: dict, c: Cues) -> dict:
    """One big number that counts up, a plain label, and optional comparison bars."""
    actors = [{"id": "num", "type": "counter", "value": 0, "unit": (s.get("unit") or "")[:10], "style": "display",
               "tone": s.get("tone") if s.get("tone") in TONE else "signal", "at": [6, 4.4], "size": 8}]
    actors.append({"id": "what", "type": "text", "style": "label", "text": (s.get("label") or "")[:32], "at": [6, 6.0], "size": 9})
    comp = (s.get("compare") or [])[:3]
    hero = s.get("hero_prop") if s.get("hero_prop") in plan_mod.PROP_HEIGHTS else None
    if comp:
        actors.append({"id": "bars", "type": "bars", "at": [6, 9.3], "size": 9.6, "items": [
            {"label": (i.get("label") or "")[:18], "value": float(i.get("value") or 0), "display": (i.get("display") or str(i.get("value")))[:12],
             "tone": i.get("tone") if i.get("tone") in TONE else "ink2"} for i in comp]})
    elif hero:
        actors.append({"id": "hero", "type": "prop", "prop": hero, "at": [6, 9.2], "size": 2.6})
    cue = c.get(s.get("cue"), 0.2)
    b1 = [{"at": cue, "do": "enter", "actor": "num", "style": "pop"},
          {"at": cue, "do": "count", "actor": "num", "to": float(s.get("value") or 0), "dur": 1.4},
          {"after": 0.3, "do": "pulse", "actor": "what"}]
    shots = [{"camera": {"focus": [6, 5.6], "zoom": 1.1}, "beats": b1}]
    if comp:
        cc = c.get(s.get("compare_cue"), 0.6)
        shots.append({"at": cc, "camera": {"focus": [6, 7.4], "zoom": 1.0}, "beats": [{"at": cc, "do": "enter", "actor": "bars", "style": "fade"}]})
    elif hero:
        cc = c.get(s.get("compare_cue"), 0.6)
        shots.append({"at": cc, "camera": {"focus": [6, 7.2], "zoom": 1.0}, "beats": [{"at": cc, "do": "enter", "actor": "hero", "style": "drop"},
                                                                                      {"after": 0.7, "do": "emit", "actor": "hero", "kind": "sparkle"}]})
    return {"actors": actors, "shots": shots}


SETTINGS = {  # backdrop props for real-life scenes
    "shop": [{"id": "set0", "type": "prop", "prop": "shop", "at": [6, 5.6], "size": 5.2}],
    "counter": [{"id": "set0", "type": "prop", "prop": "shop-counter", "at": [6, 9.4], "size": 3.4}],
    "office": [{"id": "set0", "type": "prop", "prop": "shop-counter", "at": [6, 9.5], "size": 3.2},
               {"id": "set1", "type": "prop", "prop": "laptop", "at": [6, 8.2], "size": 1.8}],
    "library": [{"id": "set0", "type": "prop", "prop": "shelf", "at": [6, 5.4], "size": 3.4}],
    "street": [{"id": "set0", "type": "prop", "prop": "house", "at": [3.0, 4.6], "size": 2.4},
               {"id": "set1", "type": "prop", "prop": "house", "at": [9.0, 4.4], "size": 2.8},
               {"id": "set2", "type": "prop", "prop": "traffic-light", "at": [6, 4.6], "size": 1.1}],
    "post office": [{"id": "set0", "type": "prop", "prop": "shop", "at": [6, 5.6], "size": 5.0},
                    {"id": "set1", "type": "prop", "prop": "envelope", "at": [6, 3.0], "size": 1.4}],
    "none": [],
}


def build_story(s: dict, c: Cues) -> dict:
    """A real-life moment: one or two people act it out in a setting (give, walk, say, react)."""
    setting = s.get("setting") if s.get("setting") in SETTINGS else "none"
    feet = 11.0
    A, ai = party("a", s.get("person_a") or {"kind": "person", "label": ""}, 2.6, feet, size=2.5, face="right", idx=2)
    pieces = [x["id"] for x in SETTINGS[setting]]
    actors = [ground(feet)] + [dict(x, allowOverlap=["a", "b"] + pieces) for x in SETTINGS[setting]] + A
    infos = {"a": ai}
    if s.get("person_b"):
        B, bi = party("b", s["person_b"], 9.4, feet, size=2.5, face="left", idx=4)
        actors += B
        infos["b"] = bi
    acts = (s.get("actions") or [])[:4]
    beats = []
    for k, act in enumerate(acts):
        who = act.get("who") if act.get("who") in infos else "a"
        other = "b" if who == "a" and "b" in infos else "a"
        cue = c.get(act.get("cue"), (k + 0.5) / (len(acts) + 1))
        d = act.get("do")
        if d == "give":
            item = act.get("item") if act.get("item") in plan_mod.PROP_HEIGHTS else "box"
            beats += [{"at": cue, "do": "state", "actor": who, "state": {"pose": "reach"}},
                      {"at": cue, "do": "send", "from": who, "to": other, "item": item, "dur": 0.9, "arc": 1.6},
                      {"after": 1.0, "do": "state", "actor": who, "state": {"pose": "idle"}}]
        elif d == "walk":
            tx = 5.0 if who == "a" else 7.0
            beats.append({"at": cue, "do": "move", "actor": who, "to": [tx, infos[who]["cy"]], "walk": True, "dur": 1.2})
        elif d == "say":
            beats.append({"at": cue, "do": "say", "actor": who, "text": (act.get("text") or "")[:38]})
        elif d == "point":
            beats.append({"at": cue, "do": "state", "actor": who, "state": {"pose": "point"}})
        else:  # react
            mood = act.get("feeling") or "happy"
            pose, expr, fx = {"happy": ("cheer", "smile", "sparkle"), "confused": ("think", "neutral", "question"),
                              "sad": ("sad", "frown", "zzz"), "surprised": ("shrug", "open", "exclaim")}.get(mood, ("cheer", "smile", "sparkle"))
            beats += [{"at": cue, "do": "state", "actor": who, "state": {"pose": pose, "expression": expr}},
                      {"after": 0.1, "do": "emit", "actor": who, "kind": fx}]
    half = max(1, len(beats) // 2)
    first, second = beats[:half], beats[half:]
    shots = [{"camera": {"focus": [6, 7.4], "zoom": 1.0}, "beats": first}]
    if second:
        shot_cue = next((b["at"] for b in second if b.get("at")), None) or c.get(None, 0.6)
        shots.append({"at": shot_cue, "camera": {"focus": [6, 8.3], "zoom": 1.18}, "beats": second})
    return {"actors": actors, "shots": shots}


def build_reveal(s: dict, c: Cues) -> dict:
    """The analogy turns into the tech: each everyday thing maps to its technical name."""
    pairs = (s.get("pairs") or [])[:3]
    actors = headline(s.get("headline"))
    rows = [5.3, 7.9, 10.5][:len(pairs)] if len(pairs) == 3 else [6.2, 9.4][:len(pairs)] if len(pairs) == 2 else [7.6]
    shots_b = []
    for k, (p, y) in enumerate(zip(pairs, rows)):
        prop = p.get("prop") if p.get("prop") in plan_mod.PROP_HEIGHTS else "box"
        icon = p.get("icon") if p.get("icon") in plan_mod.ICONS else "server"
        ph = plan_mod.PROP_HEIGHTS[prop] / 200 * 1.9
        actors += [{"id": f"real{k}", "type": "prop", "prop": prop, "at": [2.6, y], "size": min(1.9, 1.9 * 1.9 / max(ph, 1.9))},
                   {"id": f"tech{k}", "type": "node", "icon": icon, "label": (p.get("tech") or "")[:12], "at": [9.2, y], "size": 2.3},
                   {"id": f"map{k}", "type": "connector", "from": f"real{k}", "to": f"tech{k}", "style": "arrow"}]
        cue = c.get(p.get("cue"), (k + 0.4) / (len(pairs) + 0.6))
        # The everyday objects are on set from the first frame, waiting to be translated;
        # each one pulses when named, then its technical counterpart appears.
        shots_b.append([{"at": cue, "do": "pulse", "actor": f"real{k}"},
                        {"after": 0.25, "do": "enter", "actor": f"map{k}"},
                        {"after": 0.35, "do": "enter", "actor": f"tech{k}", "style": "pop"},
                        {"after": 0.3, "do": "send", "via": f"map{k}", "to": f"tech{k}", "item": "packet", "dur": 0.6}])
    shots = [{"camera": {"focus": [6, 7.6], "zoom": 1.0}, "beats": [b for bb in shots_b[:2] for b in bb]}]
    if len(shots_b) > 2:
        shots.append({"at": shots_b[2][0]["at"], "camera": {"focus": [6, 8.0], "zoom": 1.08}, "beats": shots_b[2]})
    else:
        last = pairs[-1] if pairs else {}
        shots.append({"at": c.get(s.get("closing_cue"), 0.85), "camera": {"focus": [6.6, rows[-1] - 0.5], "zoom": 1.2},
                      "beats": [{"at": c.get(s.get("closing_cue"), 0.85), "do": "highlight", "actor": f"tech{len(pairs) - 1}", "tone": "signal", "hold": 2}]})
    return {"actors": actors, "shots": shots}


def build_code(s: dict, c: Cues) -> dict:
    lines = [l[:34] for l in (s.get("lines") or [])[:8]]
    actors = headline(s.get("headline")) + [{"id": "code", "type": "code", "file": (s.get("file") or "")[:36], "code": lines,
                                               "at": [6, round(7.4 + (0.3 if s.get("headline") else 0), 2)], "size": 10.2}]
    hl = (s.get("highlights") or [])[:3]
    beats = [{"do": "enter", "actor": "code", "style": "rise"}]
    shots = [{"camera": {"focus": [6, 7.4], "zoom": 1.0}, "beats": beats}]
    for k, h in enumerate(hl):
        a, b = (h.get("lines") or [1, 1])[:2] if len(h.get("lines") or []) >= 2 else ((h.get("lines") or [1])[0],) * 2
        a, b = max(1, min(len(lines), int(a))), max(1, min(len(lines), int(b)))
        cue = c.get(h.get("cue"), (k + 1) / (len(hl) + 1))
        beat = {"at": cue, "do": "highlight-lines", "actor": "code", "lines": [min(a, b), max(a, b)]}
        if k == 1:
            shots.append({"at": cue, "camera": {"focus": [6, 7.4 + (min(a, b) - len(lines) / 2) * 0.35], "zoom": 1.08}, "beats": [beat]})
        else:
            shots[-1]["beats"].append(beat)
    return {"actors": actors, "shots": shots}


def build_recap(s: dict, c: Cues) -> dict:
    items = (s.get("items") or [])[:3]
    hero = s.get("hero_prop") if s.get("hero_prop") in plan_mod.PROP_HEIGHTS else "lightbulb"
    actors = [{"id": "hero", "type": "prop", "prop": hero, "at": [6, 3.9], "size": 2.0},
              {"id": "points", "type": "list", "at": [6, 8.4], "size": 9.4, "items": [
                  {"text": (i.get("text") or "")[:30], "tone": i.get("tone") if i.get("tone") in ("ok", "fail", "signal", "sky") else "ok"} for i in items]}]
    b1 = [{"at": c.get(items[0].get("cue") if items else None, 0.05), "do": "enter", "actor": "points", "style": "fade"}]
    cues = [c.get(i.get("cue"), (k + 0.3) / (len(items) + 0.5)) for k, i in enumerate(items)]
    b1 += [{"at": cues[k], "do": "reveal", "actor": "points", "index": k} for k in range(min(2, len(items)))]
    shots = [{"camera": {"focus": [6, 6.8], "zoom": 1.0}, "beats": b1}]
    if len(items) > 2:
        shots.append({"at": cues[2], "camera": {"focus": [6, 7.6], "zoom": 1.05}, "beats": [
            {"at": cues[2], "do": "reveal", "actor": "points", "index": 2},
            {"after": 0.6, "do": "emit", "actor": "hero", "kind": "sparkle"}]})
    return {"actors": actors, "shots": shots}


def build_hook(s: dict, c: Cues) -> dict:
    """The opening problem: a headline question over a hero object that visibly has the problem."""
    hero = s.get("hero_prop") if s.get("hero_prop") in plan_mod.PROP_HEIGHTS else "phone"
    hh = plan_mod.PROP_HEIGHTS[hero] / 200 * 3.0
    actors = headline(s.get("headline"), 3.0) + [ground(10.9), {"id": "hero", "type": "prop", "prop": hero, "at": [7.0, round(10.9 - hh / 2, 3)], "size": 3.0}]
    person = s.get("with_person", True)
    if person:
        actors.append({"id": "viewer", "type": "character", "at": [2.8, round(10.9 - 2.3 * 1.6 / 2, 3)], "size": 2.3, "face": "right", "look": {"shirt": "sky"}})
    prob = c.get(s.get("problem_cue"), 0.45)
    b1 = [{"at": c.get(s.get("headline_cue"), 0.02), "do": "enter", "actor": "headline", "style": "words"}] if s.get("headline") else []
    b2 = [{"at": prob, "do": "shake", "actor": "hero"}, {"at": prob, "do": "label", "actor": "hero", "text": (s.get("problem_label") or "Error")[:14], "tone": "fail"},
          {"at": prob, "do": "flash", "tone": "fail"}]
    if person:
        b2 += [{"after": 0.2, "do": "state", "actor": "viewer", "state": {"pose": "think", "expression": "frown"}},
               {"after": 0.1, "do": "emit", "actor": "viewer", "kind": "question"}]
    return {"actors": actors, "shots": [{"camera": {"focus": [6, 7.6], "zoom": 1.0}, "beats": b1},
                                        {"at": prob, "camera": {"focus": [6.4, 8.2], "zoom": 1.25}, "beats": b2}]}


def _party_example(kind: str) -> dict:
    return {"kind": kind, "label": "<short name>"}


RECIPES: dict[str, Recipe] = {}


def _r(name, use_when, props, required, build, sample):
    RECIPES[name] = Recipe(name, use_when, _schema(props, required), build, sample)


_r("hook", "the opening problem the viewer has hit (an error, a slow page, a failure)",
   {"headline": _str(40, "a short question or statement"), "headline_cue": CUE, "hero_prop": {"enum": PROPS},
    "problem_label": _str(14, "what goes wrong, e.g. an error code"), "problem_cue": CUE, "with_person": {"type": "boolean"}},
   ["headline", "hero_prop", "problem_label", "problem_cue"], build_hook,
   ("Ever opened a page that just spins forever? Here's why it happens.",
    {"headline": "Why does it hang?", "headline_cue": "Ever opened", "hero_prop": "phone", "problem_label": "Timeout", "problem_cue": "spins forever", "with_person": True}))
_r("story", "a real-life analogy moment acted out by one or two people (give, walk, say, point, react)",
   {"setting": {"enum": list(SETTINGS)}, "person_a": PARTY, "person_b": PARTY,
    "actions": {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": {
        "who": {"enum": ["a", "b"]}, "do": {"enum": ["give", "walk", "say", "point", "react"]}, "item": {"enum": PROPS},
        "text": _str(38, "for say"), "feeling": {"enum": ["happy", "confused", "sad", "surprised"]}, "cue": CUE},
        "required": ["who", "do", "cue"]}}},
   ["setting", "person_a", "actions"], build_story,
   ("Maya walks up to the post office counter and hands over a letter. The clerk smiles and says it will arrive tomorrow.",
    {"setting": "post office", "person_a": {"kind": "person", "label": "Maya", "shirt": "coral"}, "person_b": {"kind": "person", "label": "Clerk", "shirt": "mint"},
     "actions": [{"who": "a", "do": "walk", "cue": "walks up"}, {"who": "a", "do": "give", "item": "envelope", "cue": "hands over"},
                 {"who": "b", "do": "react", "feeling": "happy", "cue": "clerk smiles"}, {"who": "b", "do": "say", "text": "Tomorrow!", "cue": "arrive tomorrow"}]}))
_r("exchange", "two parties trade a sequence of 1-4 messages (a protocol, a request and response, a handshake)",
   {"headline": _str(40), "left": PARTY, "right": PARTY,
    "messages": {"type": "array", "minItems": 1, "maxItems": 4, "items": {"type": "object", "properties": {
        "from": {"enum": ["left", "right"]}, "label": _str(18, "the message name"), "item": ITEM, "tone": {"enum": TONE}, "cue": CUE},
        "required": ["from", "label", "cue"]}},
    "outcome_good": {"type": "boolean"}, "outcome_label": _str(14), "outcome_cue": CUE},
   ["left", "right", "messages", "outcome_cue"], build_exchange,
   ("The browser asks for the page. The server replies with the HTML. Then the browser asks for the images, and the page is ready.",
    {"headline": "Request and response", "left": {"kind": "device", "icon": "browser", "label": "Browser"}, "right": {"kind": "device", "icon": "server", "label": "Server"},
     "messages": [{"from": "left", "label": "GET /page", "cue": "asks for the page"}, {"from": "right", "label": "200 HTML", "item": "doc", "tone": "ok", "cue": "replies"},
                  {"from": "left", "label": "GET /img", "cue": "asks for the images"}], "outcome_good": True, "outcome_label": "Loaded", "outcome_cue": "page is ready"}))
_r("flow", "a request or item passes through a chain of 2-4 components (an architecture path); optionally fails at one",
   {"headline": _str(40), "item": ITEM, "stages": {"type": "array", "minItems": 2, "maxItems": 4, "items": {"type": "object", "properties": {
        "icon": {"enum": ICONS}, "label": _str(12), "cue": CUE}, "required": ["icon", "label", "cue"]}},
    "fail_at": {"type": "integer", "description": "index of the stage where it fails, or omit"}, "result_label": _str(14), "result_cue": CUE},
   ["stages", "result_cue"], build_flow,
   ("Your request hits the CDN first, then the load balancer, then an app server, and finally the database answers.",
    {"headline": "One request's journey", "item": "packet", "stages": [{"icon": "cdn", "label": "CDN", "cue": "CDN first"}, {"icon": "load_balancer", "label": "Balancer", "cue": "load balancer"},
     {"icon": "server", "label": "App", "cue": "app server"}, {"icon": "database", "label": "Database", "cue": "the database"}], "result_label": "Done", "result_cue": "answers"}))
_r("queue", "people line up for a limited resource; the first few are served, the rest wait (queues, limits, contention)",
   {"server_prop": {"enum": PROPS}, "server_label": _str(14), "item": {"enum": PROPS}, "people": {"type": "integer", "minimum": 3, "maximum": 8},
    "served": {"type": "integer", "minimum": 1, "maximum": 6}, "arrive_cue": CUE, "serve_cue": CUE, "wait_cue": CUE, "wait_label": _str(14)},
   ["server_prop", "item", "people", "served", "arrive_cue", "serve_cue", "wait_cue"], build_queue,
   ("A crowd arrives at the kitchen. The chef can cook three meals at once. Everyone else waits their turn.",
    {"server_prop": "bell", "server_label": "Kitchen", "item": "cup", "people": 7, "served": 3, "arrive_cue": "crowd arrives", "serve_cue": "three meals",
     "wait_cue": "waits their turn", "wait_label": "Busy"}))
_r("fill", "a container fills up one item at a time until full, then the next one overflows (buffers, caches, memory, limits)",
   {"headline": _str(40), "source": PARTY, "container": {"enum": CONTAINERS}, "item": {"enum": PROPS}, "capacity": {"type": "integer", "minimum": 2, "maximum": 6},
    "fill_cue": CUE, "full_cue": CUE, "full_label": _str(14), "overflow_cue": CUE, "overflow_label": _str(14)},
   ["container", "item", "fill_cue", "full_cue", "overflow_cue"], build_fill,
   ("Every new message goes into the mailbox. It holds four, and when it's full the next one is simply lost.",
    {"headline": "A buffer has a limit", "source": {"kind": "person", "label": "Sender", "shirt": "amber"}, "container": "box", "item": "envelope", "capacity": 4,
     "fill_cue": "goes into the mailbox", "full_cue": "it's full", "full_label": "Full", "overflow_cue": "simply lost", "overflow_label": "Lost"}))
_r("compare", "two options side by side with 1-2 short points each, then one wins (trade-offs, before/after)",
   {"headline": _str(40), "left": {"type": "object", "properties": {"title": _str(16), "icon": {"enum": ICONS}, "prop": {"enum": PROPS}, "points": {"type": "array", "maxItems": 2, "items": _str(32)}, "tone": {"enum": TONE}, "cue": CUE}, "required": ["title", "points", "cue"]},
    "right": {"type": "object", "properties": {"title": _str(16), "icon": {"enum": ICONS}, "prop": {"enum": PROPS}, "points": {"type": "array", "maxItems": 2, "items": _str(32)}, "tone": {"enum": TONE}, "cue": CUE}, "required": ["title", "points", "cue"]},
    "winner": {"enum": ["left", "right"]}, "verdict_cue": CUE},
   ["left", "right", "winner", "verdict_cue"], build_compare,
   ("Polling asks the server every few seconds, wasting requests. A WebSocket keeps one connection open and gets updates instantly. For live data, the socket wins.",
    {"headline": "Polling vs WebSocket", "left": {"title": "Polling", "icon": "clock", "points": ["asks every few seconds", "mostly wasted requests"], "tone": "fail", "cue": "Polling asks"},
     "right": {"title": "WebSocket", "icon": "api", "points": ["one open connection", "instant updates"], "tone": "ok", "cue": "A WebSocket"}, "winner": "right", "verdict_cue": "socket wins"}))
_r("stat", "one striking number (latency, size, count), optionally compared with 2-3 others",
   {"value": {"type": "number"}, "unit": _str(10), "label": _str(32, "what the number measures"), "tone": {"enum": TONE}, "cue": CUE,
    "hero_prop": {"enum": PROPS}, "compare": {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {
        "label": _str(18), "value": {"type": "number"}, "display": _str(12), "tone": {"enum": TONE}}, "required": ["label", "value"]}}, "compare_cue": CUE},
   ["value", "label", "cue"], build_stat,
   ("Reading from memory takes about a hundred nanoseconds. From an SSD it's around a hundred microseconds, a thousand times slower.",
    {"value": 100, "unit": "ns", "label": "one read from memory", "tone": "ok", "cue": "hundred nanoseconds", "compare": [
        {"label": "Memory", "value": 0.1, "display": "100 ns", "tone": "ok"}, {"label": "SSD", "value": 100, "display": "100 µs", "tone": "ink2"}], "compare_cue": "From an SSD"}))
_r("reveal", "name the concept: each everyday thing from the analogy maps to its technical counterpart (1-3 pairs)",
   {"headline": _str(40, "the concept's name; wrap the key term in **double asterisks**"), "pairs": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "object", "properties": {
        "prop": {"enum": PROPS, "description": "the everyday object"}, "tech": _str(12, "its technical name"), "icon": {"enum": ICONS}, "cue": CUE},
        "required": ["prop", "tech", "icon", "cue"]}}, "closing_cue": CUE},
   ["headline", "pairs"], build_reveal,
   ("That's a message queue. The mailbox is the queue, each letter is a message, and the post office is the broker.",
    {"headline": "A **message queue**", "pairs": [{"prop": "box", "tech": "Queue", "icon": "queue", "cue": "mailbox is the queue"},
     {"prop": "envelope", "tech": "Message", "icon": "info", "cue": "letter is a message"}, {"prop": "shop", "tech": "Broker", "icon": "server", "cue": "is the broker"}]}))
_r("code", "real code, config or headers, with lines highlighted as they are mentioned",
   {"headline": _str(40), "file": _str(36), "lines": {"type": "array", "minItems": 1, "maxItems": 8, "items": _str(34)}, "cue": CUE,
    "highlights": {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {
        "lines": {"type": "array", "minItems": 1, "maxItems": 2, "items": {"type": "integer", "minimum": 1}}, "cue": CUE}, "required": ["lines", "cue"]}}},
   ["lines", "highlights"], build_code,
   ("Here's the config. The max connections line sets the pool size, and the timeout decides how long a request waits.",
    {"file": "pool.yaml", "lines": ["pool:", "  max_connections: 20", "  timeout_ms: 500", "  idle_ms: 30000"], "cue": "the config",
     "highlights": [{"lines": [2, 2], "cue": "max connections"}, {"lines": [3, 3], "cue": "the timeout"}]}))
_r("recap", "the closing summary: up to 3 short rules revealed one by one",
   {"hero_prop": {"enum": PROPS}, "items": {"type": "array", "minItems": 2, "maxItems": 3, "items": {"type": "object", "properties": {
        "text": _str(30), "tone": {"enum": ["ok", "fail", "signal", "sky"]}, "cue": CUE}, "required": ["text", "cue"]}}},
   ["items"], build_recap,
   ("So: cache what's read often, set an expiry, and never cache secrets.",
    {"hero_prop": "lightbulb", "items": [{"text": "Cache what's read often", "tone": "ok", "cue": "cache what's"},
     {"text": "Always set an expiry", "tone": "sky", "cue": "set an expiry"}, {"text": "Never cache secrets", "tone": "fail", "cue": "never cache"}]}))


# ---- data-structure recipes ---------------------------------------------------------------------
# The hero is a stateful structure actor (runtime/actors/structures.js) driven by `op` beats;
# the recipe only times the operations to the narration and moves the camera.
def _op_beats(actor: str, ops: list[dict], c: Cues, keys: tuple[str, ...], gap: float = 0.9) -> list[dict]:
    beats = []
    for k, o in enumerate(ops):
        b = {"do": "op", "actor": actor, "op": o.get("op")}
        for key in keys:
            if o.get(key) not in (None, ""):
                b[key] = o[key]
        if o.get("cue"):
            b["at"] = c.get(o["cue"], (k + 0.5) / (len(ops) + 1))
        else:
            b["after"] = gap if beats else 0.3
        beats.append(b)
    return beats


def _split_shots(beats: list[dict], wide: dict, close: dict) -> list[dict]:
    """First half of the operations in a wide shot, the rest in a push-in on the first cued
    beat of the second half (every shot after the first needs a spoken cue)."""
    # Split at a *cued* beat at or after the middle, so the second shot starts exactly on
    # that beat and every uncued beat stays chained to the one before it, in order.
    half = max(1, (len(beats) + 1) // 2)
    split = next((i for i in range(half, len(beats)) if beats[i].get("at")), None)
    if split is None:
        return [{"camera": wide, "beats": beats}]
    return [{"camera": wide, "beats": beats[:split]},
            {"at": beats[split]["at"], "camera": close, "beats": beats[split:]}]


def build_ring(s: dict, c: Cues) -> dict:
    """A ring buffer: slots in a circle, a write pointer chasing a read pointer; when full,
    the next write overwrites the oldest value."""
    slots = max(4, min(12, int(s.get("slots") or 8)))
    values = [str(v)[:5] for v in (s.get("values") or [])][:slots]
    raw_ops = [o for o in (s.get("ops") or [])[:10] if o.get("op") in ("write", "read")]
    if not values and len(raw_ops) < 4:
        # A nearly empty ring shows nothing happening; start it partly full so writes,
        # reads and the wrap-around are all visible within the scene.
        values = [chr(ord("A") + i) for i in range(max(2, slots // 2))]
    count, kept = len(values), []
    for o in raw_ops:
        if o["op"] == "read" and count == 0:
            continue  # a read on an empty buffer changes nothing on screen
        count = max(0, count - 1) if o["op"] == "read" else min(slots, count + 1)
        kept.append(o)
    actors = headline(s.get("headline")) + [{
        "id": "ring", "type": "ring", "slots": slots, "values": values,
        "writeLabel": (s.get("write_label") or "write")[:8], "readLabel": (s.get("read_label") or "read")[:8],
        "at": [6, 8.2], "size": 7.4}]
    ops = [{**o, "value": str(o.get("value", ""))[:5]} for o in kept]
    beats = _op_beats("ring", ops, c, ("value",))
    return {"actors": actors, "shots": _split_shots(beats, {"focus": [6, 7.7], "zoom": 1.0}, {"focus": [6, 8.0], "zoom": 1.06})}


def build_array(s: dict, c: Cues) -> dict:
    """An array with named pointers, highlighted ranges, swaps and eliminated halves
    (binary search, two pointers, sliding window, sorting steps)."""
    vals = [str(v)[:5] for v in (s.get("values") or [])][:9] or ["?"]
    actors = headline(s.get("headline")) + [{"id": "arr", "type": "array", "values": vals, "at": [6, 7.4], "size": 9.4}]
    if s.get("caption"):
        actors.append({"id": "cap", "type": "text", "style": "label", "text": s["caption"][:28], "tone": "signal", "at": [6, 4.6], "size": 9})
    ops = [o for o in (s.get("ops") or [])[:12] if o.get("op") in ("pointer", "set", "swap", "highlight", "dim", "found")]
    beats = _op_beats("arr", ops, c, ("name", "index", "from", "to", "i", "j", "value", "tone"), gap=0.8)
    return {"actors": actors, "shots": _split_shots(beats, {"focus": [6, 7.4], "zoom": 1.0}, {"focus": [6, 7.6], "zoom": 1.08})}


def build_stack(s: dict, c: Cues) -> dict:
    """A stack (last in, first out) or a queue (first in, first out), pushed and popped."""
    queue = s.get("kind") == "queue"
    ops = [o for o in (s.get("ops") or [])[:10] if o.get("op") in (("enqueue", "dequeue") if queue else ("push", "pop"))]
    # Accept the other family's verbs rather than dropping the model's intent.
    if not ops:
        mapping = {"push": "enqueue", "pop": "dequeue"} if queue else {"enqueue": "push", "dequeue": "pop"}
        ops = [{**o, "op": mapping[o["op"]]} for o in (s.get("ops") or [])[:10] if o.get("op") in mapping]
    cap = max(3, min(7, int(s.get("capacity") or 5)))
    act = {"id": "st", "type": "stack", "kind": "queue" if queue else "stack", "capacity": cap,
           "values": [str(v)[:6] for v in (s.get("values") or [])][:cap]}
    act.update({"at": [6, 7.6], "size": 10.2} if queue else {"at": [6, 7.9], "size": 5.4})
    actors = headline(s.get("headline")) + [act]
    beats = _op_beats("st", [{**o, "value": str(o.get("value", ""))[:6]} for o in ops], c, ("value",))
    close = {"focus": [6, 7.6], "zoom": 1.1} if queue else {"focus": [6, 7.2], "zoom": 1.12}
    return {"actors": actors, "shots": _split_shots(beats, {"focus": [6, 7.6], "zoom": 1.0}, close)}


def build_tree(s: dict, c: Cues) -> dict:
    """A binary search tree: a cursor walks down comparing at each node; inserts grow a new
    branch, searches end found (green) or missing (red)."""
    vals = [str(v)[:4] for v in (s.get("values") or [])][:8]
    ops = [{**o, "value": str(o.get("value", ""))[:4]} for o in (s.get("ops") or [])[:5] if o.get("op") in ("insert", "search")]
    actors = headline(s.get("headline")) + [{"id": "bst", "type": "tree", "values": vals, "at": [6, 8.4], "size": 9.0}]
    beats = _op_beats("bst", ops, c, ("value",), gap=2.0)
    return {"actors": actors, "shots": _split_shots(beats, {"focus": [6, 7.8], "zoom": 1.0}, {"focus": [6, 8.2], "zoom": 1.04})}


def build_hashmap(s: dict, c: Cues) -> dict:
    """A hash map: keys go through the hash function into buckets; collisions chain."""
    buckets = max(3, min(8, int(s.get("buckets") or 5)))
    ops = []
    for o in (s.get("ops") or [])[:8]:
        if o.get("op") in ("put", "get") and o.get("key"):
            o = {**o, "key": str(o["key"])[:8]}
            if o.get("bucket") is not None:
                try:
                    o["bucket"] = max(0, min(buckets - 1, int(o["bucket"])))
                except (TypeError, ValueError):
                    o.pop("bucket")
            ops.append(o)
    actors = headline(s.get("headline")) + [{"id": "map", "type": "hashmap", "buckets": buckets, "at": [6, 8.35], "size": 8.8}]
    beats = _op_beats("map", ops, c, ("key", "bucket"), gap=1.4)
    return {"actors": actors, "shots": _split_shots(beats, {"focus": [6, 7.8], "zoom": 1.0}, {"focus": [6, 8.3], "zoom": 1.04})}


VAL = _str(5, "a short value: a number, letter or tiny word")
_r("ring", "a ring buffer / circular buffer: fixed slots in a circle, writes chase reads and wrap around, overwriting when full",
   {"headline": _str(40), "slots": {"type": "integer", "minimum": 4, "maximum": 12}, "values": {"type": "array", "maxItems": 12, "items": VAL},
    "write_label": _str(8), "read_label": _str(8),
    "ops": {"type": "array", "minItems": 1, "maxItems": 10, "items": {"type": "object", "properties": {
        "op": {"enum": ["write", "read"]}, "value": VAL, "cue": CUE}, "required": ["op"]}}},
   ["slots", "ops"], build_ring,
   ("A circular buffer has eight slots. New log lines go in one after another, the reader takes the oldest, and when it's full the newest line overwrites the oldest.",
    {"headline": "A ring of eight slots", "slots": 8, "values": ["A", "B", "C", "D", "E", "F"],
     "ops": [{"op": "write", "value": "G", "cue": "New log lines"}, {"op": "write", "value": "H"}, {"op": "read", "cue": "takes the oldest"},
             {"op": "write", "value": "I", "cue": "when it's full"}, {"op": "write", "value": "J", "cue": "newest line overwrites"}]}))
_r("array", "an array of values with pointers and ranges: binary search, two pointers, sliding window, or sorting steps",
   {"headline": _str(40), "caption": _str(28, "e.g. 'find 42'"), "values": {"type": "array", "minItems": 3, "maxItems": 9, "items": VAL},
    "ops": {"type": "array", "minItems": 1, "maxItems": 12, "items": {"type": "object", "properties": {
        "op": {"enum": ["pointer", "set", "swap", "highlight", "dim", "found"]},
        "name": _str(5, "pointer name, e.g. lo, mid, hi, i, j"), "index": {"type": "integer", "minimum": 0},
        "from": {"type": "integer", "minimum": 0}, "to": {"type": "integer", "minimum": 0}, "i": {"type": "integer"}, "j": {"type": "integer"},
        "value": VAL, "tone": {"enum": TONE}, "cue": CUE}, "required": ["op"]}}},
   ["values", "ops"], build_array,
   ("Binary search checks the middle. Forty-two is bigger, so the whole left half is thrown away. Check the middle again, and there it is.",
    {"headline": "Binary search", "caption": "find 42", "values": ["3", "8", "15", "21", "30", "42", "57", "64", "80"],
     "ops": [{"op": "pointer", "name": "lo", "index": 0}, {"op": "pointer", "name": "hi", "index": 8},
             {"op": "pointer", "name": "mid", "index": 4, "cue": "checks the middle"}, {"op": "dim", "from": 0, "to": 4, "cue": "thrown away"},
             {"op": "pointer", "name": "lo", "index": 5}, {"op": "pointer", "name": "mid", "index": 6, "cue": "middle again"},
             {"op": "pointer", "name": "mid", "index": 5}, {"op": "found", "index": 5, "cue": "there it is"}]}))
_r("stack", "a stack (last in, first out: undo, call stack) or a queue (first in, first out: print jobs, task queues)",
   {"headline": _str(40), "kind": {"enum": ["stack", "queue"]}, "capacity": {"type": "integer", "minimum": 3, "maximum": 7},
    "values": {"type": "array", "maxItems": 5, "items": _str(6)},
    "ops": {"type": "array", "minItems": 1, "maxItems": 10, "items": {"type": "object", "properties": {
        "op": {"enum": ["push", "pop", "enqueue", "dequeue"]}, "value": _str(6), "cue": CUE}, "required": ["op"]}}},
   ["kind", "ops"], build_stack,
   ("Every time you type, the change is pushed onto the undo stack. Press undo, and the last change pops off first.",
    {"headline": "The undo stack", "kind": "stack", "capacity": 5, "values": ["type H"],
     "ops": [{"op": "push", "value": "type i", "cue": "Every time you type"}, {"op": "push", "value": "bold"},
             {"op": "push", "value": "delete", "cue": "pushed onto"}, {"op": "pop", "cue": "Press undo"}, {"op": "pop", "cue": "pops off first"}]}))
_r("tree", "a binary search tree (or any sorted tree index): inserting or searching by walking down, left if smaller, right if bigger",
   {"headline": _str(40), "values": {"type": "array", "minItems": 1, "maxItems": 8, "items": _str(4)},
    "ops": {"type": "array", "minItems": 1, "maxItems": 4, "items": {"type": "object", "properties": {
        "op": {"enum": ["insert", "search"]}, "value": _str(4), "cue": CUE}, "required": ["op", "value"]}}},
   ["values", "ops"], build_tree,
   ("To find thirty-seven, start at the root. It's bigger than fifty? No, go left. Bigger than twenty-five, go right, and there it is. Adding forty just grows a new leaf.",
    {"headline": "Searching a sorted tree", "values": ["50", "25", "75", "12", "37", "62", "90"],
     "ops": [{"op": "search", "value": "37", "cue": "start at the root"}, {"op": "insert", "value": "40", "cue": "Adding forty"}]}))
_r("hashmap", "a hash map / hash table / dictionary: keys hashed into buckets, lookups jump straight to the bucket, collisions chain",
   {"headline": _str(40), "buckets": {"type": "integer", "minimum": 3, "maximum": 8},
    "ops": {"type": "array", "minItems": 1, "maxItems": 8, "items": {"type": "object", "properties": {
        "op": {"enum": ["put", "get"]}, "key": _str(8), "bucket": {"type": "integer", "minimum": 0, "description": "optional: force a bucket to show a collision"},
        "cue": CUE}, "required": ["op", "key"]}}},
   ["buckets", "ops"], build_hashmap,
   ("Each name is hashed to a bucket number. Alice lands in bucket two, Bob in bucket four. Carol also hashes to two, so she's chained right after Alice. Looking up Carol jumps straight to bucket two.",
    {"headline": "How a hash map finds things", "buckets": 5,
     "ops": [{"op": "put", "key": "alice", "bucket": 2, "cue": "Alice lands"}, {"op": "put", "key": "bob", "bucket": 4, "cue": "Bob in bucket"},
             {"op": "put", "key": "carol", "bucket": 2, "cue": "Carol also hashes"}, {"op": "get", "key": "carol", "bucket": 2, "cue": "Looking up Carol"}]}))



def build_scene(recipe_name: str, slots: dict, narration: str) -> tuple[dict, list[str]]:
    """Recipe + slots → DSL scene (without id/mood/transition). Returns (scene, notes)."""
    r = RECIPES.get(recipe_name) or RECIPES["story"]
    cues = Cues(narration)
    scene = r.build(slots, cues)
    scene["narration"] = narration
    scene["recipe"] = r.name
    return scene, cues.repaired


def menu() -> str:
    return "\n".join(f"- {r.name}: {r.use_when}" for r in RECIPES.values())


# ---- gallery: every recipe with its sample slots, for visual QA and tests ---------------------------
def gallery_plan() -> dict:
    moods = ["night", "day", "dusk", "night", "day", "night", "signal", "night", "dusk", "night", "day"]
    trans = ["cut", "dissolve", "pan", "zoom-out", "iris", "dissolve", "zoom-out", "pan", "dissolve", "pan", "dissolve"]
    scenes = []
    for i, r in enumerate(RECIPES.values()):
        narration, slots = r.sample
        sc, _ = build_scene(r.name, json.loads(json.dumps(slots)), narration)
        sc.update({"id": r.name, "mood": moods[i % len(moods)], "transition": {"type": trans[i % len(trans)], "dir": "right"}})
        scenes.append(sc)
    return {"title": "Recipe gallery", "scenes": scenes}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gallery", action="store_true")
    args = ap.parse_args()
    if args.gallery:
        out = Path(__file__).resolve().parent.parent / "out" / "recipe_gallery"
        out.mkdir(parents=True, exist_ok=True)
        (out / "plan.json").write_text(json.dumps(gallery_plan(), indent=1, ensure_ascii=False), encoding="utf-8")
        print(out / "plan.json")

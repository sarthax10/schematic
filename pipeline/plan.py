"""Scene plan (v2): the contract between the scene designer (LLM or human) and the runtime.

A plan is a list of scenes; each scene is a set (mood + actors) seen through shots (camera
framings) whose beats (verbs) land on words of that scene's narration. Everything is a
closed vocabulary. Validation splits problems into:
  - errors: the scene can't be rendered as intended (unknown actor referenced, missing
    narration, bad type) — sent back to the designer for repair;
  - warnings: repaired here with a documented default (unknown icon → "server", size
    clamped into range) — logged, never silently invented.

Catalogs (prop names, icons, poses) are parsed from the runtime's own JS so there is one
source of truth: the validator can never accept something the engine can't draw.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent.parent / "runtime"


def _keys(file: str, pattern: str) -> dict[str, str]:
    src = (RUNTIME / file).read_text(encoding="utf-8")
    return {m.group(1).strip('"'): m.group(2) for m in re.finditer(pattern, src, re.M)}


PROP_HEIGHTS = {k: int(v) for k, v in _keys("props.js", r'^\s{2}("?[\w-]+"?): \{\s*\n?\s*h: (\d+)').items()}
ICONS = set(_keys("icons.js", r"^\s{2}(\w+): '()").keys())
POSES = set(_keys("actors/character.js", r"^\s{2}(\w+): \[()").keys())

ACTOR_TYPES = {"text", "prop", "node", "icon", "shape", "counter", "meter", "bars", "list", "code", "character", "connector",
               "ring", "array", "stack", "tree", "hashmap"}
STRUCTURE_OPS = {"ring": {"write", "read"}, "array": {"pointer", "set", "swap", "highlight", "dim", "found"},
                 "stack": {"push", "pop", "enqueue", "dequeue"}, "tree": {"insert", "search"}, "hashmap": {"put", "get"}}
VERBS = {
    "enter", "exit", "move", "scale", "rotate", "pulse", "shake", "hop", "wiggle", "spin", "highlight", "dim", "undim",
    "label", "say", "emit", "send", "morph", "state", "count", "reveal", "highlight-lines", "flash", "op",
}
ENTER_STYLES = {"pop", "grow", "rise", "drop", "slide-left", "slide-right", "fade", "draw", "words", "type"}
EXIT_STYLES = {"fade", "pop", "sink", "slide-left", "slide-right"}
MOODS = {"night", "day", "dusk", "signal"}
TRANSITIONS = {"cut", "dissolve", "pan", "zoom-in", "zoom-out", "iris"}
PAN_DIRS = {"left", "right", "up", "down"}
TONES = {"signal", "ok", "fail", "sky", "lavender", "ink2"}
TEXT_STYLES = {"display", "title", "body", "label", "mono", "number"}
SHAPES = {"rect", "circle", "ring", "pill", "ground", "zone"}
FX = {"sparkle", "question", "exclaim", "zzz", "sweat", "check", "cross", "dust"}
EXPRESSIONS = {"smile", "neutral", "open", "frown"}
HAIR = {"short", "long", "bun", "curly"}
SHIRTS = {"amber", "mint", "coral", "sky", "lav", "sand", "slate"}

DEFAULT_VOICE = "en-US-AndrewNeural"
DEFAULT_RATE = "+4%"

# Longest text that still reads at each style's size inside the safe area.
TEXT_LIMITS = {"display": 14, "number": 8, "title": 48, "body": 90, "label": 32, "mono": 60}


class PlanError(ValueError):
    pass


def load(path: str | Path) -> tuple[dict, list[str]]:
    return validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _num(v, lo, hi, default):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def apply_layouts(scene: dict) -> None:
    """Resolve layout helpers into concrete `at` positions (so designers can say "these four
    in a row at y=8" instead of computing coordinates)."""
    actors = {a["id"]: a for a in scene.get("actors", [])}
    for lay in scene.get("layouts", []) or []:
        ids = [i for i in lay.get("actors", []) if i in actors]
        if not ids:
            continue
        kind = lay.get("kind", "row")
        cx, cy = float(lay.get("x", 6)), float(lay.get("y", 7.6))
        gap = float(lay.get("gap", 0.7))
        if kind == "row":
            widths = [float(actors[i].get("size", 2.5)) for i in ids]
            total = sum(widths) + gap * (len(ids) - 1)
            x = cx - total / 2
            for i, w in zip(ids, widths):
                actors[i]["at"] = [round(x + w / 2, 3), cy]
                x += w + gap
        elif kind == "column":
            step = float(lay.get("step", 2.6))
            y0 = cy - step * (len(ids) - 1) / 2
            for k, i in enumerate(ids):
                actors[i]["at"] = [cx, round(y0 + k * step, 3)]
        elif kind == "grid":
            cols = int(lay.get("cols", 3))
            step = float(lay.get("step", 2.6))
            rows = -(-len(ids) // cols)
            for k, i in enumerate(ids):
                r, c = divmod(k, cols)
                actors[i]["at"] = [round(cx + (c - (cols - 1) / 2) * step, 3), round(cy + (r - (rows - 1) / 2) * step, 3)]
        elif kind == "queue":  # people waiting in line, overlapping slightly, receding
            step = float(lay.get("step", 1.3))
            for k, i in enumerate(ids):
                actors[i]["at"] = [round(cx + k * step * (1 if lay.get("dir", "right") == "right" else -1), 3), cy]


def validate_scene(raw: dict, index: int, prev_ids: set[str]) -> tuple[dict, list[str], list[str]]:
    """Returns (clean scene, errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    where = f"scene {raw.get('id') or index + 1}"
    sc = {k: v for k, v in raw.items()}
    sc["id"] = str(raw.get("id") or f"s{index + 1}")
    sc["narration"] = (raw.get("narration") or "").strip()
    if not sc["narration"]:
        errors.append(f"{where}: narration is empty")
    if sc.get("mood") not in MOODS:
        warnings.append(f"{where}: mood {sc.get('mood')!r} → 'night'")
        sc["mood"] = "night"

    apply_layouts(sc)
    ids: set[str] = set()
    actors = []
    for a in raw.get("actors", []) or []:
        a = dict(a)
        aid = a.get("id")
        if not aid or aid in ids:
            errors.append(f"{where}: actor with missing or duplicate id {aid!r}")
            continue
        if a.get("type") not in ACTOR_TYPES:
            errors.append(f"{where}: actor {aid!r} has unknown type {a.get('type')!r} (valid: {sorted(ACTOR_TYPES)})")
            continue
        ids.add(aid)
        t = a["type"]
        if t != "connector":
            at = a.get("at")
            if not (isinstance(at, list) and len(at) == 2):
                errors.append(f"{where}: actor {aid!r} needs at:[x, y] (grid units) or a layout")
                continue
            a["at"] = [_num(at[0], -6, 18, 6), _num(at[1], -4, 24, 7.6)]
            a["size"] = _num(a.get("size", 9 if t in ("text", "list", "code", "bars", "ring", "array", "stack", "tree", "hashmap") else 3), 0.3, 12, 3)
        if t == "prop" and a.get("prop") not in PROP_HEIGHTS:
            warnings.append(f"{where}: prop {a.get('prop')!r} unknown → 'box'")
            a["prop"] = "box"
        if t in ("node", "icon") and a.get("icon") not in ICONS:
            warnings.append(f"{where}: icon {a.get('icon')!r} unknown → 'server'")
            a["icon"] = "server"
        if t == "text":
            if a.get("style") not in TEXT_STYLES:
                a["style"] = "title"
            limit = TEXT_LIMITS[a["style"]]
            plain = re.sub(r"\*\*", "", str(a.get("text", "")))
            if not plain:
                errors.append(f"{where}: text actor {aid!r} is empty")
            elif len(plain) > limit:
                errors.append(f"{where}: text {aid!r} is {len(plain)} chars; style {a['style']} allows {limit} — shorten it (captions already carry the narration)")
        if t == "shape" and a.get("shape") not in SHAPES:
            a["shape"] = "rect"
        if t == "character":
            if a.get("pose", "idle") not in POSES:
                a["pose"] = "idle"
            look = a.get("look") or {}
            if look.get("hair") not in HAIR:
                look.pop("hair", None)
            if look.get("shirt") not in SHIRTS:
                look.pop("shirt", None)
            a["look"] = look
        if t == "connector":
            if a.get("from") not in ids | {x.get("id") for x in raw.get("actors", [])} or a.get("to") not in {x.get("id") for x in raw.get("actors", [])}:
                errors.append(f"{where}: connector {aid!r} must join two actors of this scene (from/to)")
        if a.get("tone") and a["tone"] not in TONES:
            warnings.append(f"{where}: tone {a['tone']!r} → 'signal'")
            a["tone"] = "signal"
        if a.get("carry") and a["carry"] not in prev_ids:
            warnings.append(f"{where}: carry {a['carry']!r} not in previous scene; dropped")
            a.pop("carry")
        actors.append(a)
    sc["actors"] = actors
    sc.pop("layouts", None)

    tr = raw.get("transition") or {"type": "cut" if index == 0 else "dissolve"}
    if tr.get("type") not in TRANSITIONS:
        warnings.append(f"{where}: transition {tr.get('type')!r} → 'dissolve'")
        tr = {"type": "dissolve"}
    if tr["type"] == "pan" and tr.get("dir") not in PAN_DIRS:
        tr["dir"] = "right"
    if any(a.get("carry") for a in actors) and tr["type"] != "dissolve":
        warnings.append(f"{where}: carried actor present → transition forced to 'dissolve'")
        tr = {"type": "dissolve"}
    sc["transition"] = tr

    shots = raw.get("shots") or []
    if not shots:
        errors.append(f"{where}: needs at least one shot")
    for si, shot in enumerate(shots):
        cam = shot.get("camera") or {}
        focus = cam.get("focus")
        if isinstance(focus, str) and focus not in ids:
            warnings.append(f"{where} shot {si + 1}: camera focus {focus!r} unknown → centre")
            cam["focus"] = [6, 7.6]
        cam["zoom"] = _num(cam.get("zoom", 1), 0.5, 3.5, 1)
        shot["camera"] = cam
        clean_beats = []
        for b in shot.get("beats", []) or []:
            verb = b.get("do")
            if verb not in VERBS:
                errors.append(f"{where}: beat verb {verb!r} unknown (valid: {sorted(VERBS)})")
                continue
            refs = [b.get("actor")] if b.get("actor") else []
            refs += [b.get(k) for k in ("from", "to") if isinstance(b.get(k), str) and verb in ("send", "morph")]
            if verb == "move" and isinstance(b.get("to"), str):
                refs.append(b["to"])
            refs += list(b.get("actors") or [])
            bad = [r for r in refs if r not in ids]
            if bad:
                errors.append(f"{where}: beat {verb!r} references unknown actor(s) {bad}")
                continue
            if verb == "op":
                kind = next((a.get("type") for a in actors if a.get("id") == b.get("actor")), None)
                if kind not in STRUCTURE_OPS or b.get("op") not in STRUCTURE_OPS[kind]:
                    errors.append(f"{where}: op {b.get('op')!r} is not valid for actor {b.get('actor')!r} ({kind}); "
                                  f"valid: {sorted(STRUCTURE_OPS.get(kind, []))}")
                    continue
            if verb == "enter" and b.get("style") and b["style"] not in ENTER_STYLES:
                b["style"] = "pop"
            if verb == "exit" and b.get("style") and b["style"] not in EXIT_STYLES:
                b["style"] = "fade"
            if verb == "emit" and b.get("kind") not in FX:
                b["kind"] = "sparkle"
            if verb == "state" and "pose" in (b.get("state") or {}) and b["state"]["pose"] not in POSES:
                b["state"]["pose"] = "idle"
            if verb == "state" and "expression" in (b.get("state") or {}) and b["state"]["expression"] not in EXPRESSIONS:
                b["state"]["expression"] = "smile"
            if b.get("tone") and b["tone"] not in TONES:
                b["tone"] = "signal"
            if verb == "send" and b.get("item") not in (None, "packet") and b["item"] not in PROP_HEIGHTS:
                b["item"] = "packet"
            clean_beats.append(b)
        shot["beats"] = clean_beats
    sc["shots"] = shots
    return sc, errors, warnings


def validate(plan: dict) -> tuple[dict, list[str]]:
    """Whole-plan validation for rendering: raises PlanError on any error."""
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise PlanError("plan has no scenes")
    out, warnings, errors = [], [], []
    prev_ids: set[str] = set()
    for i, raw in enumerate(scenes):
        sc, errs, warns = validate_scene(raw, i, prev_ids)
        errors += errs
        warnings += warns
        out.append(sc)
        prev_ids = {a["id"] for a in sc["actors"]}
    if errors:
        raise PlanError("; ".join(errors))
    return {
        "title": plan.get("title") or "Untitled",
        "voice": plan.get("voice") or DEFAULT_VOICE,
        "rate": plan.get("rate") or DEFAULT_RATE,
        "scenes": out,
    }, warnings

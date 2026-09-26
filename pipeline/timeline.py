"""Validated plan + per-scene narration → the resolved timeline the runtime plays.

Every shot and beat that names an `at` phrase is placed on the exact spoken word (from the
TTS engine's own word boundaries). Beats without `at` chain off the previous beat with
`after` seconds (default: a short stagger), so a designer can say "the jar pops in when
'jar' is said, then the lid bounces 0.4 s later".
"""
from __future__ import annotations

import re

LEAD_IN = 0.45  # speech starts after the scene's transition has mostly landed
TAIL = 0.5
CUE_ANTICIPATION = 0.1  # visuals land a hair before the word: perceived as in sync
MIN_SCENE = 3.0
CAPTION_MAX_CHARS = 42


def _norm_tokens(phrase: str) -> list[str]:
    return [w for w in re.sub(r"[^a-z0-9 ]", " ", str(phrase).lower()).split() if w]


def find_phrase(words: list[dict], phrase: str, start_idx: int = 0) -> int | None:
    target = _norm_tokens(phrase)
    if not target:
        return None
    stream = [(wi, tok) for wi, w in enumerate(words) for tok in w["norm"].split()]
    for si in range(len(stream)):
        if stream[si][0] < start_idx:
            continue
        toks = [tok for _, tok in stream[si:si + len(target)]]
        if len(toks) == len(target) and toks[:-1] == target[:-1] and toks[-1].startswith(target[-1]):
            return stream[si][0]
    return None


class _Cues:
    """Resolves `at` phrases in reading order, falling back to a search from the start."""

    def __init__(self, words, label, warnings):
        self.words, self.label, self.warnings, self.cursor = words, label, warnings, 0

    def time(self, phrase: str) -> float | None:
        wi = find_phrase(self.words, phrase, self.cursor)
        if wi is None:
            wi = find_phrase(self.words, phrase, 0)
        if wi is None:
            self.warnings.append(f"{self.label}: cue {phrase!r} not found in narration")
            return None
        self.cursor = wi
        return LEAD_IN + self.words[wi]["start"] - CUE_ANTICIPATION


def _resolve_scene(scene: dict, words: list[dict], duration: float, warnings: list[str]) -> tuple[list, list]:
    cues = _Cues(words, f"scene {scene['id']}", warnings)
    shots_out, beats_out = [], []
    n = len(scene["shots"])
    last_beat = 0.3
    for si, shot in enumerate(scene["shots"]):
        if si == 0:
            t_shot = 0.0
        elif shot.get("at"):
            t_shot = cues.time(shot["at"])
            if t_shot is None:
                t_shot = duration * si / n
        else:
            t_shot = max(last_beat + 0.3, duration * si / n)
        t_shot = max(0.0, min(t_shot, duration - 0.6))
        shots_out.append({"t": round(t_shot, 3), "camera": shot.get("camera", {})})
        prev = t_shot + (0.35 if si == 0 else 0.25)
        for k, b in enumerate(shot.get("beats", [])):
            b = dict(b)
            t = cues.time(b.pop("at")) if b.get("at") else None
            if t is None:
                t = prev + float(b.pop("after", 0.18 if k else 0.0))
            b.pop("after", None)
            t = max(0.0, min(t + float(b.pop("delay", 0)), duration - 0.25))
            b["t"] = round(t, 3)
            prev = b["t"]
            last_beat = max(last_beat, prev)
            beats_out.append(b)
    # Shots must be in time order even if cues were said out of order.
    for i in range(1, len(shots_out)):
        shots_out[i]["t"] = max(shots_out[i]["t"], shots_out[i - 1]["t"] + 0.5)
    return shots_out, beats_out


# ---- captions --------------------------------------------------------------------------------
def _text_len(ws):
    return len(" ".join(w["text"] for w in ws))


def _split_balanced(phrase):
    if _text_len(phrase) <= CAPTION_MAX_CHARS or len(phrase) < 2:
        return [phrase]
    best = min(range(1, len(phrase)), key=lambda k: max(_text_len(phrase[:k]), _text_len(phrase[k:])))
    return _split_balanced(phrase[:best]) + _split_balanced(phrase[best:])


def _captions(words, offset, scene_end):
    phrases = [[]]
    for w in words:
        phrases[-1].append(w)
        if re.search(r"[.!?;:,—]$", w["text"]):
            phrases.append([])
    phrases = [p for p in phrases if p]
    merged = []
    for p in phrases:
        if merged and (_text_len(merged[-1]) < 12 or _text_len(p) < 8) and _text_len(merged[-1] + p) <= CAPTION_MAX_CHARS:
            merged[-1] = merged[-1] + p
        else:
            merged.append(p)
    chunks = [line for p in merged for line in _split_balanced(p)]
    out = []
    for i, c in enumerate(chunks):
        start = offset + c[0]["start"]
        end = offset + chunks[i + 1][0]["start"] if i + 1 < len(chunks) else min(offset + c[-1]["end"] + 0.35, scene_end)
        out.append({"text": " ".join(x["text"] for x in c), "start": round(start, 3), "end": round(end, 3)})
    return out


def build(plan: dict, narration: list[dict], fps: int = 30) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    scenes, captions = [], []
    t = 0.0
    for i, (scene, nar) in enumerate(zip(plan["scenes"], narration)):
        dur = max(LEAD_IN + nar["duration"] + TAIL, MIN_SCENE)
        dur = round(round(dur * fps) / fps, 4)
        shots, beats = _resolve_scene(scene, nar["words"], dur, warnings)
        scenes.append({
            "id": scene["id"], "index": i, "start": round(t, 4), "duration": dur,
            "mood": scene["mood"], "transition": scene["transition"] if i else {"type": "cut"},
            "actors": scene["actors"], "shots": shots, "beats": beats,
        })
        captions += _captions(nar["words"], t + LEAD_IN, t + dur)
        t += dur
    return {
        "title": plan["title"], "fps": fps, "duration": round(t, 4), "audio": "narration.m4a",
        "scenes": scenes, "captions": captions,
    }, warnings

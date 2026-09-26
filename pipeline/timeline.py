"""Turns a validated plan + per-scene narration into the resolved timeline the runtime plays:
absolute scene start/duration, every step's `at` phrase resolved to a time on the actual
spoken word, and caption chunks. Nothing here guesses timing from text length — every
time comes from the TTS engine's own word boundaries.
"""
from __future__ import annotations

import re

LEAD_IN = 0.4  # speech starts this long after a scene's visual starts (lets it land first)
TAIL = 0.45  # hold after the last word before cutting
CUE_ANTICIPATION = 0.12  # visuals land a hair before the word: perceived as in sync
MIN_DURATION = {"title": 2.6}

CAPTION_MAX_CHARS = 42


def _norm_tokens(phrase: str) -> list[str]:
    return [w for w in re.sub(r"[^a-z0-9 ]", " ", phrase.lower()).split() if w]


def _find_phrase(words: list[dict], phrase: str, start_idx: int) -> int | None:
    target = _norm_tokens(phrase)
    if not target:
        return None
    # A boundary can hold several tokens ("40 ms"), so match on a flattened token stream.
    stream = [(wi, tok) for wi, w in enumerate(words) for tok in w["norm"].split()]
    for si in range(len(stream)):
        if stream[si][0] < start_idx:
            continue
        toks = [tok for _, tok in stream[si:si + len(target)]]
        # Prefix match on the last token so "cache" also catches "cached"/"caches".
        if len(toks) == len(target) and toks[:-1] == target[:-1] and toks[-1].startswith(target[-1]):
            return stream[si][0]
    return None


def _resolve_steps(scene: dict, words: list[dict], warnings: list[str], label: str) -> list[dict]:
    resolved = []
    cursor = 0
    last_t = LEAD_IN
    for step in scene["steps"]:
        s = {k: v for k, v in step.items() if k != "at"}
        if "t" in step:
            t = float(step["t"])
        elif "at" in step:
            wi = _find_phrase(words, step["at"], cursor)
            if wi is None:
                wi = _find_phrase(words, step["at"], 0)
            if wi is None:
                t = last_t + 0.6
                warnings.append(f"{label}: cue {step['at']!r} not found in narration; placed at {t:.2f}s")
            else:
                cursor = wi
                t = LEAD_IN + words[wi]["start"] - CUE_ANTICIPATION
        else:
            t = last_t
        t += float(step.get("delay", 0))
        s["t"] = round(max(0.0, t), 3)
        last_t = s["t"]
        resolved.append(s)
    return resolved


def _text_len(ws: list[dict]) -> int:
    return len(" ".join(w["text"] for w in ws))


def _split_balanced(phrase: list[dict]) -> list[list[dict]]:
    """Splits an over-long phrase into the fewest near-equal-length lines."""
    if _text_len(phrase) <= CAPTION_MAX_CHARS or len(phrase) < 2:
        return [phrase]
    best = min(range(1, len(phrase)), key=lambda k: max(_text_len(phrase[:k]), _text_len(phrase[k:])))
    return _split_balanced(phrase[:best]) + _split_balanced(phrase[best:])


def _captions(words: list[dict], offset: float, scene_end: float) -> list[dict]:
    # Break at clause punctuation first, so a caption never ends mid-thought
    # ("Your database is the / bottleneck.") — then balance any clause that's too long,
    # and merge fragments too short to read on their own into their neighbour.
    phrases: list[list[dict]] = [[]]
    for w in words:
        phrases[-1].append(w)
        if re.search(r"[.!?;:,—]$", w["text"]):
            phrases.append([])
    phrases = [p for p in phrases if p]
    merged: list[list[dict]] = []
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
        dur = LEAD_IN + nar["duration"] + TAIL
        dur = max(dur, MIN_DURATION.get(scene["type"], 0))
        dur = round(round(dur * fps) / fps, 4)  # whole frames, so cuts never drift
        steps = _resolve_steps(scene, nar["words"], warnings, f"scene {i + 1}")
        scenes.append({**scene, "index": i, "start": round(t, 4), "duration": dur, "steps": steps})
        captions += _captions(nar["words"], t + LEAD_IN, t + dur)
        t += dur
    return {
        "title": plan["title"],
        "fps": fps,
        "duration": round(t, 4),
        "audio": "narration.m4a",
        "scenes": scenes,
        "captions": captions,
    }, warnings

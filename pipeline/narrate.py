"""Narration: one edge-tts clip per scene, with real word-level timestamps from the TTS
engine itself (WordBoundary events) — so scene length is the true spoken length and every
animation cue can land on the exact word, without a separate transcription pass.

Boundary words come back without punctuation ("40 ms" as one unit, "time" not "time!"),
so each one is located back in the source narration and given its original surrounding
text — captions then keep the author's punctuation.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from pathlib import Path

import edge_tts

from . import media

TICKS = 10_000_000  # edge-tts offsets are in 100ns units


def _align(text: str, boundaries: list[dict]) -> list[dict]:
    lower = text.lower()
    cursor = 0
    starts: list[int | None] = []
    for b in boundaries:
        idx = lower.find(b["text"].lower(), cursor)
        if idx == -1:
            starts.append(None)
        else:
            starts.append(idx)
            cursor = idx + len(b["text"])
    words = []
    for i, b in enumerate(boundaries):
        s = starts[i]
        if s is None:
            display = b["text"]
        else:
            nxt = next((x for x in starts[i + 1:] if x is not None), len(text))
            display = text[s:nxt].strip()
        words.append({
            "text": display,
            "norm": re.sub(r"[^a-z0-9 ]", "", b["text"].lower()),
            "start": round(b["offset"] / TICKS, 3),
            "end": round((b["offset"] + b["duration"]) / TICKS, 3),
        })
    return words


async def _synth(text: str, voice: str, rate: str, mp3: Path) -> list[dict]:
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    boundaries = []
    with mp3.open("wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                boundaries.append({"text": chunk["text"], "offset": chunk["offset"], "duration": chunk["duration"]})
    return _align(text, boundaries)


async def narrate_scene(i: int, text: str, voice: str, rate: str, out_dir: Path, sem: asyncio.Semaphore) -> dict:
    key = hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()[:12]
    mp3 = out_dir / f"scene_{i:02d}_{key}.mp3"
    meta = mp3.with_suffix(".json")
    if mp3.exists() and meta.exists():  # cached: iterate on visuals without re-synthesizing
        return json.loads(meta.read_text(encoding="utf-8"))
    async with sem:
        for attempt in range(3):
            try:
                words = await _synth(text, voice, rate, mp3)
                break
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(1.5 * (attempt + 1))
    result = {"audio": mp3.name, "duration": media.duration(mp3), "words": words}
    meta.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def narrate(plan: dict, out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)

    async def run():
        sem = asyncio.Semaphore(4)
        return await asyncio.gather(*[
            narrate_scene(i, s["narration"], plan["voice"], plan["rate"], out_dir, sem)
            for i, s in enumerate(plan["scenes"])
        ])

    return asyncio.run(run())

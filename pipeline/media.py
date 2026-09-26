"""ffmpeg helpers. Uses imageio-ffmpeg's bundled static binary, so there's no system
ffmpeg to install on a dev machine or server."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def run(args: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run([FFMPEG, "-hide_banner", "-y", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}):\n{proc.stderr[-3000:]}")
    return proc


def duration(path: Path) -> float:
    """Exact decoded duration (decodes the file rather than trusting container headers,
    which are unreliable for streamed MP3)."""
    proc = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True)
    times = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", proc.stderr)
    if not times:
        raise RuntimeError(f"could not read duration of {path}")
    h, m, s = times[-1]
    return round(int(h) * 3600 + int(m) * 60 + float(s), 3)


def build_narration(clips: list[Path], leads: list[float], durations: list[float], out: Path) -> None:
    """Lays each scene's clip at its lead-in offset, pads it to the scene's exact length,
    concatenates, and loudness-normalizes — one ffmpeg call, sample-accurate."""
    args: list[str] = []
    for c in clips:
        args += ["-i", str(c)]
    chains = []
    for i, (lead, dur) in enumerate(zip(leads, durations)):
        chains.append(
            f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,adelay={int(lead * 1000)}:all=1,"
            f"apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}[a{i}]"
        )
    joined = "".join(f"[a{i}]" for i in range(len(clips)))
    graph = ";".join(chains) + f";{joined}concat=n={len(clips)}:v=0:a=1,loudnorm=I=-15:TP=-1.5:LRA=9[out]"
    run([*args, "-filter_complex", graph, "-map", "[out]", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(out)])

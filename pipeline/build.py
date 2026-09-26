"""Plan JSON → finished MP4.

    python -m pipeline.build examples/cache_aside.json            # full render
    python -m pipeline.build examples/cache_aside.json --preview  # live browser preview
    python -m pipeline.build examples/cache_aside.json --stills 2,9.5,20

Output lands in out/<plan-name>/: narration audio, timeline.json, video.mp4.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from . import media, narrate, plan as plan_mod, render, timeline

ROOT = Path(__file__).resolve().parent.parent


def prepare(plan_path: Path, out_dir: Path, fps: int) -> dict:
    plan, warnings = plan_mod.load(plan_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[1/3] narration ({len(plan['scenes'])} scenes, voice {plan['voice']})")
    nar = narrate.narrate(plan, out_dir / "audio")
    tl, tl_warnings = timeline.build(plan, nar, fps=fps)
    for w in warnings + tl_warnings:
        print(f"  warning: {w}")
    media.build_narration(
        [out_dir / "audio" / n["audio"] for n in nar],
        [timeline.LEAD_IN] * len(nar),
        [s["duration"] for s in tl["scenes"]],
        out_dir / "narration.m4a",
    )
    (out_dir / "timeline.json").write_text(json.dumps(tl, indent=1), encoding="utf-8")
    print(f"  timeline: {tl['duration']:.1f}s, {len(tl['captions'])} caption chunks")
    return tl


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--preview", action="store_true", help="serve a live preview instead of rendering")
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--stills", help="comma-separated times to snapshot as PNGs instead of rendering")
    args = ap.parse_args(argv)

    out_dir = args.out or ROOT / "out" / args.plan.stem
    started = time.time()
    try:
        tl = prepare(args.plan, out_dir, args.fps)
    except plan_mod.PlanError as e:
        print(f"plan error: {e}", file=sys.stderr)
        return 2

    if args.preview:
        server, port = render.serve(out_dir, args.port)
        print(f"preview: http://127.0.0.1:{port}/index.html?timeline=/job/timeline.json&mode=preview")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0

    if args.stills:
        times = [float(x) for x in args.stills.split(",")]
        paths = asyncio.run(render.snapshot(out_dir, times, out_dir))
        print("\n".join(str(p) for p in paths))
        return 0

    print(f"[2/3] rendering {round(tl['duration'] * args.fps)} frames with {args.workers} workers")
    render.render(out_dir, out_dir / "video.mp4", args.fps, tl["duration"], args.workers)
    print(f"[3/3] done in {time.time() - started:.0f}s: {out_dir / 'video.mp4'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

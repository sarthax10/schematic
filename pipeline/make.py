"""End to end: pick a new topic → teach it in a script → fact-check → storyboard → design every
scene → narrate → lint the real rendered layout and repair → render the MP4.

    python -m pipeline.make                         # fresh topic, any category
    python -m pipeline.make --category databases
    python -m pipeline.make --topic "how DNS resolution works"   # replaced if already made
    python -m pipeline.make --resume out/<slug>     # continue an interrupted run

Every stage's output is saved in out/<slug>/ (topic.json, script.json, review.json,
storyboard.json, scenes/NN.json, plan.json) and reused on resume, so a failure late in the
run never throws away the LLM work before it. Rendering and linting need no LLM.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from . import build, library, render, stages
from .llm import LLM

ROOT = Path(__file__).resolve().parent.parent


def _cached(path: Path, make):
    if path.exists():
        print(f"  (reusing {path.name})")
        return json.loads(path.read_text(encoding="utf-8"))
    out = make()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topic")
    ap.add_argument("--category")
    ap.add_argument("--resume", type=Path)
    ap.add_argument("--no-render", action="store_true", help="stop after the plan passes lint")
    ap.add_argument("--lint-rounds", type=int, default=2)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)

    llm = LLM()
    ok, msg = llm.health()
    print(f"LLM {llm}: {msg}")
    if not ok:
        return 2
    started = time.time()

    # 1. topic (reserved in the library immediately, so parallel runs never collide)
    if args.resume:
        out = args.resume
        topic = json.loads((out / "topic.json").read_text(encoding="utf-8"))
        slug = out.name
    else:
        print("[1/7] choosing a topic that hasn't been made")
        topic = stages.choose_topic(llm, args.topic, args.category)
        slug = library.add(topic["topic"], category=topic.get("category", ""), keywords=topic.get("keywords", []),
                           embedding=llm.embed(topic["topic"]), status="planned")
        out = ROOT / "out" / slug
        out.mkdir(parents=True, exist_ok=True)
        (out / "topic.json").write_text(json.dumps(topic, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  topic: {topic['topic']}  ->  {out}")
    stages.FAILED_DIR = out / "failed"

    # 2-3. script + independent accuracy review (one revision round if anything serious)
    print("[2/7] writing the script")
    script = _cached(out / "script.json", lambda: stages.write_script(llm, topic))
    print("[3/7] reviewing technical accuracy")
    review_path = out / "review.json"
    if review_path.exists():
        review = json.loads(review_path.read_text(encoding="utf-8"))
    else:
        review = stages.review_script(llm, script)
        serious = [i for i in review["issues"] if i.get("severity") in ("high", "medium")]
        if serious:
            print(f"  {len(serious)} issue(s) flagged; revising the script")
            fixes = [f"{i.get('quote', '')!r}: {i.get('problem', '')} → {i.get('fix', '')}" for i in serious]
            script = stages.write_script(llm, topic, feedback=fixes)
            (out / "script.json").write_text(json.dumps(script, indent=1, ensure_ascii=False), encoding="utf-8")
            review = {"first_pass": review, "second_pass": stages.review_script(llm, script)}
        review_path.write_text(json.dumps(review, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  {len(stages.script_text(script).split())} words: {script.get('title')}")

    # 4. storyboard
    print("[4/7] storyboarding")
    sb = _cached(out / "storyboard.json", lambda: stages.storyboard(llm, script))
    print(f"  {len(sb['scenes'])} scenes: " + " → ".join(f"{s['id']}({s['mood']})" for s in sb["scenes"]))

    # 5. design each scene, in order, each seeing the one before it (continuity, carries)
    print("[5/7] designing scenes")
    scenes = []
    for i in range(len(sb["scenes"])):
        prev = scenes[-1] if scenes else None
        sc = _cached(out / "scenes" / f"{i:02d}.json", lambda i=i, prev=prev: stages.design_scene(llm, script, sb, i, prev))
        scenes.append(sc)
        print(f"  scene {i + 1}: {len(sc.get('actors', []))} actors, {len(sc.get('shots', []))} shots")

    def save_plan():
        plan = {"title": script.get("title"), "topic": topic["topic"], "scenes": scenes}
        (out / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
        return out / "plan.json"

    # 6. narrate + render-time layout lint, repairing only the scenes that failed
    print("[6/7] narrating and checking every shot's real layout")
    for round_ in range(args.lint_rounds + 1):
        tl = build.prepare(save_plan(), out, 30)
        issues = asyncio.run(render.lint(out, render.settle_times(tl)))
        errs = [i for i in issues if i.get("kind") == "runtime_error"]
        if errs:
            print(f"  runtime error: {errs[0]['detail']}")
            return 3
        by_scene = defaultdict(list)
        starts = {s["id"]: s["start"] for s in tl["scenes"]}
        for i in issues:
            by_scene[i["scene"]].append(stages.describe_lint(i, starts[i["scene"]]))
        print(f"  lint round {round_ + 1}: {len(issues)} issue(s) in {len(by_scene)} scene(s)")
        if not issues or round_ == args.lint_rounds:
            break
        for i, sc in enumerate(scenes):
            if sc["id"] in by_scene:
                scenes[i] = stages.design_scene(llm, script, sb, i, scenes[i - 1] if i else None,
                                                lint_notes=by_scene[sc["id"]], current=sc)
                (out / "scenes" / f"{i:02d}.json").write_text(json.dumps(scenes[i], indent=1, ensure_ascii=False), encoding="utf-8")

    if args.no_render:
        library.set_status(slug, "planned", out_dir=str(out))
        print(f"plan ready: {out / 'plan.json'} ({llm.calls} LLM calls, {time.time() - started:.0f}s)")
        return 0

    # 7. render
    print(f"[7/7] rendering {round(tl['duration'] * 30)} frames")
    render.render(out, out / "video.mp4", 30, tl["duration"], args.workers)
    library.set_status(slug, "rendered", title=script.get("title", ""), out_dir=str(out))
    print(f"done in {time.time() - started:.0f}s ({llm.calls} LLM calls): {out / 'video.mp4'}")
    print("  review.json lists what the accuracy pass flagged; 'nothing flagged' is not proof — watch it before publishing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

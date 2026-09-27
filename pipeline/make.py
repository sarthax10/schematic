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
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

from . import build, library, render, review, stages
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


def _save(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")


def accuracy_pass(llm, topic: dict, script: dict, out: Path) -> dict:
    """Independent accuracy review with up to two revision rounds, each re-checked by a fresh
    pass. Revisions edit the current script (so a human's edits survive). Whatever is still
    flagged is recorded in review.json for the human reviewer. Returns the final script."""
    passes = [stages.review_script(llm, script)]
    for round_ in range(2):
        serious = [i for i in passes[-1]["issues"] if i.get("severity") in ("high", "medium")]
        if not serious:
            break
        print(f"  review round {round_ + 1}: {len(serious)} issue(s) flagged; revising the script")
        fixes = [f"{i.get('quote', '')!r}: {i.get('problem', '')} -> {i.get('fix', '')}" for i in serious]
        script = stages.write_script(llm, topic, feedback=fixes, current=script)
        _save(out / "script.json", script)
        passes.append(stages.review_script(llm, script))
    remaining = [i for i in passes[-1]["issues"] if i.get("severity") in ("high", "medium")]
    if remaining:
        print(f"  {len(remaining)} issue(s) still flagged; left for the human reviewer")
    _save(out / "review.json", {"passes": passes, "unresolved": remaining})
    return script


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topic")
    ap.add_argument("--category")
    ap.add_argument("--resume", type=Path)
    ap.add_argument("--no-render", action="store_true", help="stop after the plan passes lint")
    ap.add_argument("--lint-rounds", type=int, default=2)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--auto-approve", action="store_true",
                    help="skip the human script review (unattended runs; the review step exists for a reason)")
    ap.add_argument("--freeform", action="store_true", help="let the model write raw scene DSL instead of filling recipes (needs a strong model)")
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

    # 2-3. script + independent accuracy review
    print("[2/7] writing the script")
    script = _cached(out / "script.json", lambda: stages.write_script(llm, topic))
    print("[3/7] reviewing technical accuracy")
    if not (out / "review.json").exists():
        script = accuracy_pass(llm, topic, script, out)

    # 3b. human review: nothing slow runs until a person approves this exact script
    status = review.gate(out, script)
    if status == "changes_requested":
        notes = review.state(out).get("notes", [])
        print(f"  revising the script with {len(notes)} reviewer note(s)")
        script = stages.write_script(llm, topic, feedback=notes, current=script)
        _save(out / "script.json", script)
        script = accuracy_pass(llm, topic, script, out)
        (out / "approval.json").unlink(missing_ok=True)
        status = "pending"
    if status != "approved":
        if args.auto_approve:
            review.approve(out, by="auto (--auto-approve)")
        else:
            library.set_status(slug, "awaiting_review", title=script.get("title", ""), out_dir=str(out))
            print(f"  {len(stages.script_text(script).split())} words: {script.get('title')}")
            print(f"  waiting for human review:  python -m pipeline.review {out}")
            print(f"  then continue with:        python -m pipeline.make --resume {out}")
            return 0
    print(f"  approved script, {len(stages.script_text(script).split())} words: {script.get('title')}")

    # 4. storyboard (rebuilt, with its scenes, if the approved script isn't the one it was made from)
    print("[4/7] storyboarding")
    sha = review.script_sha(script)
    sb_path = out / "storyboard.json"
    made_from = json.loads(sb_path.read_text(encoding="utf-8")).get("script_sha") if sb_path.exists() else None
    if made_from and made_from != sha:
        print("  the script changed after this storyboard was made; rebuilding storyboard and scenes")
        sb_path.unlink()
        shutil.rmtree(out / "scenes", ignore_errors=True)
    sb = _cached(sb_path, lambda: {**stages.storyboard(llm, script), "script_sha": sha})
    print(f"  {len(sb['scenes'])} scenes: " + " → ".join(f"{s['id']}({s['mood']})" for s in sb["scenes"]))

    # 5. design each scene, in order, each seeing the one before it (continuity, carries)
    print("[5/7] designing scenes")
    scenes = []
    def direct(i, prev, notes=None, current=None):
        if args.freeform:
            return stages.design_scene(llm, script, sb, i, prev, lint_notes=notes, current=current)
        return stages.direct_scene(llm, script, sb, i, prev, [x.get("recipe", "") for x in scenes[:i]], notes=notes)

    for i in range(len(sb["scenes"])):
        prev = scenes[-1] if scenes else None
        sc = _cached(out / "scenes" / f"{i:02d}.json", lambda i=i, prev=prev: direct(i, prev))
        scenes.append(sc)
        print(f"  scene {i + 1}: {sc.get('recipe', 'freeform')}, {len(sc.get('actors', []))} actors, {len(sc.get('shots', []))} shots")

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
                scenes[i] = direct(i, scenes[i - 1] if i else None, notes=by_scene[sc["id"]], current=sc)
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

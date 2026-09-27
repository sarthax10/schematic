"""The writing and directing stages: topic → script → accuracy review → storyboard → scenes.

Every stage follows the same loop: prompt with a skill (design/*.md) plus a worked example,
validate the reply against hard rules in code, and on failure send the exact violations back
for a repair attempt. Small local models are unreliable on first try; they are much better at
fixing a specific, named problem — so the rules live here, not only in the prompt.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from . import library, plan as plan_mod, recipes
from .llm import LLM, LLMError
from .timeline import _norm_tokens

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design"
EXAMPLE = ROOT / "examples" / "token_bucket"

CATEGORIES = [
    "system design", "networking", "databases", "distributed systems", "operating systems", "security",
    "web & APIs", "data structures & algorithms", "cloud & devops", "concurrency", "caching & performance",
]
SCRIPT_PARTS = ["hook", "analogy", "reveal", "mechanism", "example", "insight", "recap"]
BANNED = ["in this video", "basically", "essentially", "it's important to note", "let's dive", "delve"]


class StageError(RuntimeError):
    pass


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _log(msg: str) -> None:
    print(f"  {msg}", flush=True)


FAILED_DIR: Path | None = None  # set by make.py so failed attempts are kept for diagnosis


def _loop(llm: LLM, system: str, user: str, check, *, attempts: int = 3, temperature: float = 0.6,
          max_tokens: int = 4096, label: str = "stage", fix=None, schema: dict | None = None) -> dict:
    """Ask, apply deterministic `fix(out)` (things code can repair better than a model),
    validate with `check(out) -> list[str]`, and repair until clean."""
    prompt = user
    out, problems = None, []
    for i in range(attempts):
        started = time.time()
        try:
            out = llm.json(system, prompt, schema=schema, temperature=temperature, max_tokens=max_tokens)
        except LLMError as e:
            problems = [str(e)]
            _log(f"{label}: attempt {i + 1} failed: {e}")
            continue
        if fix:
            out = fix(out)
        problems = check(out)
        took = time.time() - started
        if not problems:
            _log(f"{label}: ok on attempt {i + 1} ({took:.0f}s)")
            return out
        if i == attempts - 1 and all(pr.startswith("(soft)") for pr in problems):
            # Style issues only: accept rather than throw away a long run; keep them visible.
            _log(f"{label}: accepted on attempt {i + 1} with {len(problems)} style warning(s)")
            out["_warnings"] = problems
            return out
        _log(f"{label}: attempt {i + 1} ({took:.0f}s) had {len(problems)} problem(s): {problems[0][:160]}")
        if FAILED_DIR:
            FAILED_DIR.mkdir(parents=True, exist_ok=True)
            (FAILED_DIR / f"{re.sub(r'[^a-z0-9]+', '_', label.lower())}_attempt{i + 1}.json").write_text(
                json.dumps({"problems": problems, "output": out}, indent=1, ensure_ascii=False), encoding="utf-8")
        prompt = (f"{user}\n\nYour previous answer:\n{json.dumps(out, ensure_ascii=False)}\n\n"
                  "It has these problems — fix ALL of them and return the complete corrected JSON:\n- "
                  + "\n- ".join(problems[:12]))
        temperature = max(0.2, temperature - 0.15)
    raise StageError(f"{label} failed after {attempts} attempts: {problems[:5]}")


# ---- 1. topic -----------------------------------------------------------------------------------
def choose_topic(llm: LLM, requested: str | None = None, category: str | None = None) -> dict:
    """Pick a topic no existing video covers. A requested topic that's already been made is
    reported and replaced by a fresh one (the pipeline never remakes a video)."""
    if requested:
        dup = library.find_duplicate(requested, [], llm.embed(requested))
        if not dup:
            return {"topic": requested, "category": category or "", "keywords": [], "angle": "", "analogy": "", "real_example": ""}
        _log(f"topic {requested!r} already made as {dup[0]['slug']!r} ({dup[2]}, {dup[1]}); choosing another")

    existing = [v["title"] or v["topic"] for v in library.all_videos()][:80]
    system = ("You choose topics for 60-90 second animated explainer videos about software engineering. "
              "Reply with JSON only.")
    rejected: list[str] = []
    for round_ in range(3):
        user = f"""Suggest 6 candidate topics{f' in the category "{category}"' if category else ' across these categories: ' + ', '.join(CATEGORIES)}.

Each topic must:
- be ONE concrete mechanism, narrow enough to explain in 90 seconds (good: "how a token bucket rate limiter works"; too broad: "microservices");
- be explainable with an everyday real-life analogy (a shop, post office, kitchen, traffic, library...);
- teach a beginner something AND give a working engineer a trade-off or real number they'd value;
- have a real, verifiable technical example (a product, protocol, status code, header, or config).

Already made — do NOT suggest these or close variants:
{json.dumps(existing + rejected, ensure_ascii=False)}

Example of one candidate:
{_read(EXAMPLE / "topic.json")}

Reply: {{"candidates": [{{"topic", "category", "angle", "analogy", "real_example", "keywords": [5-8 lowercase terms]}}]}}"""
        out = llm.json(system, user, temperature=0.9)
        for c in out.get("candidates", []):
            t = (c.get("topic") or "").strip()
            if not t:
                continue
            dup = library.find_duplicate(t, c.get("keywords", []), llm.embed(t))
            if dup:
                _log(f"skip {t!r}: too close to {dup[0]['slug']!r} ({dup[2]} {dup[1]})")
                rejected.append(t)
                continue
            return c
        _log(f"round {round_ + 1}: every candidate was a duplicate; asking again")
    raise StageError("could not find a topic that hasn't been made already")


# ---- 2. script ------------------------------------------------------------------------------------
def split_sentences(text: str) -> list[str]:
    # A sentence may end inside a closing quote: "...send me a reply.' If..." splits after the quote.
    parts = re.split(r"""(?:(?<=[.!?])|(?<=[.!?]['"’”]))\s+(?=[A-Z"'‘“])""", text.strip())
    return [s.strip() for s in parts if s.strip()]


MAX_SENTENCE_WORDS = 26
_JOINS = [", and ", ", but ", ", so ", "; ", ", which ", ", then ", ", while ", " — "]


def split_long(sentence: str) -> list[str]:
    """Splits an over-long spoken sentence at the clause joint nearest its middle, repeatedly.
    Deterministic, so a small model never has to be asked twice to shorten a sentence."""
    words = sentence.split()
    if len(words) <= MAX_SENTENCE_WORDS:
        return [sentence]
    mid = len(sentence) / 2
    best = None
    for j in _JOINS:
        for m in re.finditer(re.escape(j), sentence):
            if best is None or abs(m.start() - mid) < abs(best[0] - mid):
                best = (m.start(), j)
    if best is None:
        return [sentence]
    at, j = best
    left = sentence[:at].rstrip(" ,;—") + "."
    right = sentence[at + len(j):].strip()
    if j.strip(", ;—") in ("and", "but", "so", "then", "while"):
        right = j.strip(", ;—").capitalize() + " " + right
    elif j.strip(", ;—") == "which":
        right = "That " + right
    else:
        right = right[:1].upper() + right[1:]
    return split_long(left) + split_long(right)


def script_text(script: dict) -> str:
    return " ".join(s["text"].strip() for s in script["sections"])


def spoken(text: str) -> str:
    """Narration is read aloud: turn "SYN (synchronize)" into "SYN, synchronize," and drop other
    written-only marks, deterministically — no need to spend an LLM round on punctuation."""
    text = re.sub(r"\s*\(([^()]*)\)", r", \1,", text)
    text = re.sub(r"\s*\[([^\[\]]*)\]", r", \1,", text)
    text = text.replace("(", "").replace(")", "").replace("[", "").replace("]", "")
    text = re.sub(r",\s*([,.!?:;])", r"\1", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r"\s{2,}", " ", text).replace("*", "").replace("`", "")
    return text.strip()


def fix_script(s: dict) -> dict:
    for sec in s.get("sections") or []:
        if isinstance(sec, dict) and isinstance(sec.get("text"), str):
            text = spoken(sec["text"])
            sec["text"] = " ".join(part for sent in split_sentences(text) for part in split_long(sent))
    return s


def check_script(s: dict) -> list[str]:
    p = []
    secs = s.get("sections") or []
    parts = [x.get("part") for x in secs]
    for need in ("hook", "analogy", "reveal", "example", "insight", "recap"):
        if need not in parts:
            p.append(f"missing a '{need}' section")
    if parts and parts[0] != "hook":
        p.append("the first section must be the hook")
    if parts and parts[-1] != "recap":
        p.append("the last section must be the recap")
    text = " ".join(x.get("text", "") for x in secs)
    n = len(text.split())
    if n < 160:
        p.append(f"script is {n} words; it must be 160-250 (60-90 seconds). Expand the analogy and mechanism.")
    if n > 255:
        p.append(f"script is {n} words; it must be 160-250. Cut the least essential sentences.")
    for sent in split_sentences(text):
        if len(sent.split()) > MAX_SENTENCE_WORDS:
            p.append(f"(soft) sentence too long for narration ({len(sent.split())} words): {sent[:80]!r}")
    for b in BANNED:
        if b in text.lower():
            p.append(f"(soft) remove the filler phrase {b!r}")
    for sent in split_sentences(text):
        if re.search(r"[()\[\]]", sent):
            p.append(f"no parentheses or brackets — this is read aloud: {sent[:100]!r}")
    if not (s.get("analogy") or {}).get("mapping"):
        p.append("analogy.mapping must map each everyday part to its technical counterpart")
    if not s.get("claims"):
        p.append("list every factual claim in 'claims' so it can be fact-checked")
    return p


def write_script(llm: LLM, topic: dict, feedback: list[str] | None = None) -> dict:
    system = "You write narration scripts for animated engineering explainers. Reply with JSON only.\n\n" + _read(DESIGN / "TEACHING_SCRIPT_SKILL.md")
    user = f"""Topic:
{json.dumps(topic, ensure_ascii=False, indent=1)}

A finished script for a different topic, showing the exact JSON shape and the level of plain-spoken teaching expected:
{_read(EXAMPLE / "script.json")}

Write the script for the topic above. Sections in order: {", ".join(SCRIPT_PARTS)} ("mechanism" may be merged into "reveal" if short).
{"Reviewer corrections you MUST apply:" + chr(10) + chr(10).join("- " + f for f in feedback) if feedback else ""}"""
    return _loop(llm, system, user, check_script, label="script", temperature=0.7, fix=fix_script)


# ---- 3. accuracy review ----------------------------------------------------------------------------
def review_script(llm: LLM, script: dict) -> dict:
    """A second, independent pass that hunts for wrong or overstated claims. Like Antiquary's
    fact-check: 'nothing flagged' is not proof of accuracy — the human review stays load-bearing."""
    system = ("You are a senior software engineer reviewing an educational script for technical accuracy. "
              "Be strict about numbers, product behaviour, protocol details and overgeneralisation. Reply with JSON only.")
    user = f"""Script:
{script_text(script)}

Claims the writer listed:
{json.dumps(script.get("claims", []), ensure_ascii=False)}

Check every factual statement (including ones not in the list). Also flag analogies that would teach something false.
Reply: {{"issues": [{{"quote": "exact words", "problem": "what is wrong or unverifiable", "severity": "high|medium|low", "fix": "corrected wording"}}], "verdict": "ok|revise"}}"""
    out = llm.json(system, user, temperature=0.2)
    out.setdefault("issues", [])
    return out


# ---- 4. storyboard ---------------------------------------------------------------------------------
def check_storyboard(sb: dict, n_sent: int) -> list[str]:
    p = []
    scenes = sb.get("scenes") or []
    if not 5 <= len(scenes) <= 11:
        p.append(f"{len(scenes)} scenes; use 6-10")
    expect = 0
    for i, s in enumerate(scenes):
        rng = s.get("sentences")
        if not (isinstance(rng, list) and len(rng) == 2 and all(isinstance(x, int) for x in rng)):
            p.append(f"scene {i + 1}: 'sentences' must be [first, last] sentence numbers")
            continue
        if rng[0] != expect:
            p.append(f"scene {i + 1} starts at sentence {rng[0]} but must start at {expect} — every sentence, in order, exactly once")
        if rng[1] < rng[0]:
            p.append(f"scene {i + 1}: last sentence before first")
        expect = rng[1] + 1
        if rng[1] - rng[0] > 3:
            p.append(f"scene {i + 1} covers {rng[1] - rng[0] + 1} sentences; max 4 — split it")
        if s.get("mood") not in plan_mod.MOODS:
            p.append(f"scene {i + 1}: mood must be one of {sorted(plan_mod.MOODS)}")
        if len(s.get("shots") or []) < (1 if i == len(scenes) - 1 else 2):
            p.append(f"scene {i + 1}: plan 2-4 shots (camera framings) so it is a scene, not a slide")
    if expect != n_sent:
        p.append(f"scenes cover sentences 0..{expect - 1} but the script has {n_sent} (0..{n_sent - 1})")
    moods = [s.get("mood") for s in scenes]
    for i in range(2, len(moods)):
        if moods[i] == moods[i - 1] == moods[i - 2]:
            p.append(f"scenes {i - 1}-{i + 1} all use mood {moods[i]!r}; never 3 in a row")
    if moods.count("signal") > 1:
        p.append("use the 'signal' mood at most once (the key insight)")
    if sum(m in ("day", "dusk") for m in moods) < 0.35 * max(len(moods), 1):
        p.append("at least 40% of scenes should be real-world analogy scenes (mood day or dusk)")
    trans = [(s.get("transition") or {}).get("type") for s in scenes[1:]]
    for i in range(2, len(trans)):
        if trans[i] == trans[i - 1] == trans[i - 2]:
            p.append(f"transition {trans[i]!r} used 3 times in a row; vary them")
    return p


def fix_storyboard(sb: dict) -> dict:
    """Deterministic repairs: a full list of sentence numbers becomes [first, last]; three
    analogy scenes in a row alternate day/dusk (same meaning, visible variety)."""
    for sc in sb.get("scenes") or []:
        rng = sc.get("sentences")
        if isinstance(rng, list) and len(rng) != 2 and rng and all(isinstance(x, int) for x in rng):
            sc["sentences"] = [min(rng), max(rng)]
        elif isinstance(rng, list) and len(rng) == 1 and isinstance(rng[0], int):
            sc["sentences"] = [rng[0], rng[0]]
    scenes = sb.get("scenes") or []
    for i in range(2, len(scenes)):
        m = [scenes[k].get("mood") for k in (i - 2, i - 1, i)]
        if m[0] == m[1] == m[2] and m[1] in ("day", "dusk"):
            scenes[i - 1]["mood"] = "dusk" if m[1] == "day" else "day"
    return sb


def storyboard(llm: LLM, script: dict) -> dict:
    sents = split_sentences(script_text(script))
    system = ("You are the director of an animated explainer. You break a narration into scenes and plan each "
              "scene's shots. Reply with JSON only.\n\n" + _read(DESIGN / "SCENE_DESIGN_SKILL.md"))
    numbered = "\n".join(f"{i}: {s}" for i, s in enumerate(sents))
    ex_script = split_sentences(script_text(json.loads(_read(EXAMPLE / "script.json"))))
    user = f"""Narration, one numbered sentence per line:
{numbered}

The analogy and its mapping: {json.dumps(script.get("analogy"), ensure_ascii=False)}

Group consecutive sentences into 6-10 scenes (1-4 sentences each, every sentence exactly once, in order).
For each scene decide mood, transition from the previous scene, the setting, what visibly HAPPENS, and 2-4 shots.

Worked example (for its own {len(ex_script)}-sentence script):
{_read(EXAMPLE / "storyboard.json")}

Reply with the same JSON shape: {{"scenes": [{{"id", "sentences": [first, last], "purpose", "mood", "transition", "setting", "visual", "shots": [...], "carry": [...]}}]}}"""
    sb = _loop(llm, system, user, lambda o: check_storyboard(o, len(sents)), label="storyboard", temperature=0.6,
               fix=fix_storyboard)
    for s in sb["scenes"]:
        a, b = s["sentences"]
        s["narration"] = " ".join(sents[a:b + 1])
    return sb


# ---- 5. scene design --------------------------------------------------------------------------------
def dsl_reference() -> str:
    return (_read(DESIGN / "SCENE_DSL.md")
            .replace("{PROPS}", ", ".join(sorted(plan_mod.PROP_HEIGHTS)))
            .replace("{ICONS}", ", ".join(sorted(plan_mod.ICONS)))
            .replace("{POSES}", ", ".join(sorted(plan_mod.POSES))))


def check_scene(scene: dict, sb_scene: dict, index: int, prev_ids: set[str], last: bool) -> list[str]:
    scene = json.loads(json.dumps(scene))  # validate a copy
    scene["narration"] = sb_scene["narration"]
    _, errors, _ = plan_mod.validate_scene(scene, index, prev_ids)
    p = list(errors)
    narr = " ".join(_norm_tokens(sb_scene["narration"]))
    shots = scene.get("shots") or []
    if len(shots) < 2 and len(sb_scene["narration"].split()) > 14:
        p.append("use 2-4 shots with different camera framings (focus/zoom) — one static framing is a slide")
    verbs = [b.get("do") for s in shots for b in s.get("beats", [])]
    if not set(verbs) & {"send", "move", "morph", "state", "count", "reveal", "highlight-lines", "emit", "say", "op"}:
        p.append("nothing HAPPENS: add actions (send, move, morph, state, count, emit, say) that act out the narration")
    for s in shots:
        for b in [s] + s.get("beats", []):
            if b.get("at") and " ".join(_norm_tokens(b["at"])) not in narr:
                p.append(f"'at' phrase {b['at']!r} is not in the narration — copy words exactly")
    for s in shots[1:]:
        if not s.get("at"):
            p.append("every shot after the first needs an 'at' phrase saying when the camera moves")
    texts = [a for a in scene.get("actors", []) if a.get("type") == "text"]
    if len(texts) > 3 and not scene.get("recipe"):  # recipes use deliberate, length-capped labels
        p.append(f"{len(texts)} text actors; max 3 per scene — the captions already carry the narration")
    if len(scene.get("actors", [])) > 12:
        p.append("more than 12 actors; simplify")
    return p


def design_scene(llm: LLM, script: dict, sb: dict, i: int, prev_scene: dict | None, lint_notes: list[str] | None = None,
                 current: dict | None = None) -> dict:
    s = sb["scenes"][i]
    example = json.loads(_read(EXAMPLE / "plan.json"))["scenes"]
    ex = [e for e in example if e["id"] in ("shop", "reveal")]
    system = ("You design ONE scene of an animated vertical explainer video as JSON in the Scene DSL. "
              "You are a motion designer: stage real action, not slides. Reply with JSON only.\n\n"
              + _read(DESIGN / "SCENE_DESIGN_SKILL.md") + "\n\n" + dsl_reference())
    prev = ""
    if prev_scene:
        prev = "Previous scene (you may `carry` its actors by id, or use its actors as zoom-in/iris origin):\n" + json.dumps(
            {"id": prev_scene["id"], "mood": prev_scene["mood"],
             "actors": [{k: a.get(k) for k in ("id", "type", "prop", "icon", "at", "size") if a.get(k) is not None} for a in prev_scene["actors"]]},
            ensure_ascii=False)
    overview = "\n".join(f"{k + 1}. [{x['mood']}] {x['purpose']}: {x['visual']}" for k, x in enumerate(sb["scenes"]))
    user = f"""Video: {script.get("title")}
Analogy mapping: {json.dumps(script.get("analogy"), ensure_ascii=False)}

All scenes (you are designing #{i + 1}):
{overview}

{prev}

Scene #{i + 1} brief:
{json.dumps({k: s.get(k) for k in ("id", "purpose", "mood", "transition", "setting", "visual", "shots", "carry")}, ensure_ascii=False, indent=1)}

Narration for this scene (copy `at` phrases from it exactly):
"{s["narration"]}"

Two finished scenes from another video, for the level of staging expected:
{json.dumps(ex, ensure_ascii=False)}
{"" if not current else chr(10) + "Your current design of this scene:" + chr(10) + json.dumps(current, ensure_ascii=False)}
{"" if not lint_notes else chr(10) + "The rendered frames showed these layout problems — fix them:" + chr(10) + chr(10).join("- " + n for n in lint_notes)}
Reply with the scene JSON: {{"id", "mood", "transition", "actors", "layouts"?, "shots"}} (narration is added for you)."""
    prev_ids = {a["id"] for a in prev_scene["actors"]} if prev_scene else set()
    out = _loop(llm, system, user, lambda o: check_scene(o, s, i, prev_ids, i == len(sb["scenes"]) - 1),
                label=f"scene {i + 1}", temperature=0.55, max_tokens=6000)
    out["narration"] = s["narration"]
    out.setdefault("id", s.get("id") or f"s{i + 1}")
    out.setdefault("mood", s.get("mood", "night"))
    if i and not out.get("transition"):
        out["transition"] = s.get("transition") or {"type": "dissolve"}
    return out


def describe_lint(issue: dict, scene_start: float) -> str:
    t = round(issue.get("t", 0) - scene_start, 1)
    k = issue["kind"]
    if k == "outside_safe_area":
        return f"at {t}s, actor {issue['actor']!r} sticks {issue['px']}px outside the safe area (x 1-11, y 2.6-12.6): move it inward or make it smaller"
    if k == "overlap":
        return f"at {t}s, actors {issue['actors']} overlap ({int(issue['frac'] * 100)}% of the smaller one): separate them, or list each other in allowOverlap if intentional (e.g. a person in front of a counter)"
    if k == "text_too_small":
        return f"at {t}s, text {issue['actor']!r} renders at {issue['px']}px — too small to read on a phone; use a bigger style or camera zoom"
    if k == "crowded":
        return f"at {t}s, {issue['count']} separate things are on screen; keep it to 7 or fewer"
    if k == "empty_frame":
        return f"at {t}s the frame is empty — something should be on screen for the whole scene"
    return json.dumps(issue)



# ---- 5b. scene direction with recipes (default) ------------------------------------------------------
DIRECTOR = ("You direct scenes of an animated vertical explainer video for software engineers and beginners. "
            "Each scene is built from a proven recipe; you choose the recipe and fill its form. Reply with JSON only.")


def _main_actor(scene: dict) -> str | None:
    for a in scene.get("actors", []):
        if a.get("type") not in ("shape", "text", "connector") and not a.get("screen"):
            return a["id"]
    return None


def check_slots(recipe: str, slots: dict) -> list[str]:
    p = []
    for req in recipes.RECIPES[recipe].schema.get("required", []):
        if slots.get(req) in (None, "", [], {}):
            p.append(f"field {req!r} is required for recipe {recipe!r}")
    for key in ("messages", "stages", "pairs", "items", "actions", "lines"):
        if key in slots and not isinstance(slots[key], list):
            p.append(f"{key!r} must be a list")
    if recipe == "code" and isinstance(slots.get("lines"), list):
        # Real code/config/headers have syntax; narration sentences dressed up as code don't.
        prose = [l for l in slots["lines"] if isinstance(l, str) and len(l.split()) >= 4 and not re.search(r"[=:{}()\[\]<>/;#$]", l)]
        if prose:
            p.append(f"code lines must be real code, config or protocol headers, not sentences: {prose[0]!r}. "
                     "If this scene has no real code to show, it should not use the code recipe.")
    return p


# The amber 'signal' mood swallows amber props (bulbs, bells, boxes, tickets); keep it for
# recipes that are mostly nodes, numbers and text.
SIGNAL_SAFE = {"compare", "stat", "flow", "code"}


def _short_fields(schema: dict) -> str:
    """The form's fields for the prompt, with long catalogue enums elided (the structured
    output schema still enforces them)."""
    fields = json.dumps(schema["properties"], ensure_ascii=False)
    return re.sub(r'\{"enum": \[[^\]]{200,}\]', '{"enum": [...catalogue...]', fields)


def direct_scene(llm: LLM, script: dict, sb: dict, i: int, prev_scene: dict | None, recent: list[str],
                 notes: list[str] | None = None) -> dict:
    """Choose a recipe for storyboard scene i and fill its form (two small structured calls)."""
    s = sb["scenes"][i]
    n = len(sb["scenes"])
    names = list(recipes.RECIPES)
    if len(recent) >= 2 and recent[-1] == recent[-2] and recent[-1] in names:
        names.remove(recent[-1])  # never the same recipe three scenes running
    if i == 0:
        hint = " This is the OPENING scene: 'hook' is usually right."
    elif i == n - 1:
        hint = " This is the LAST scene: 'recap' is usually right."
    else:
        hint = ""
    mapping = json.dumps(script.get("analogy", {}).get("mapping", []), ensure_ascii=False)
    context = "\n".join([
        f"Video: {script.get('title')}",
        f"Analogy mapping: {mapping}",
        f"Scene {i + 1} of {n}. Purpose: {s.get('purpose')}. Planned visual: {s.get('visual')}",
        f'Narration of this scene: "{s["narration"]}"',
    ])
    choose_schema = {"type": "object", "properties": {"recipe": {"enum": names}, "why": {"type": "string", "maxLength": 160}},
                     "required": ["recipe"]}
    choose_prompt = "\n".join([
        context, "", "Recipes:", recipes.menu(), "",
        f"Previous scenes used: {recent[-3:] or 'none'}.{hint}",
        "Pick the recipe whose on-screen ACTION best shows what this narration says.",
        f'Reply: {{"recipe": one of {names}, "why": "one short sentence"}}',
    ])
    choice = llm.json(DIRECTOR, choose_prompt, schema=choose_schema, temperature=0.3)
    name = choice.get("recipe") if choice.get("recipe") in names else names[0]
    r = recipes.RECIPES[name]
    rules = [
        '- Every "cue" field: 2-4 consecutive words copied EXACTLY from the narration above, in the order they are spoken.',
        "- Labels are short (a few words), sentence case, and name things from this topic, not from any other example.",
        '- Use people (kind "person") for real-life analogy roles, devices (kind "device") for technical systems.',
        "- Pick props and icons a viewer would instantly recognise as the thing being described.",
    ]
    if notes:
        rules.append("Fix these problems found in the rendered frames:")
        rules += [f"- {x}" for x in notes]
    fill_prompt = "\n".join([
        context, "",
        f"Recipe: {name} - {r.use_when}",
        f"Form fields: {_short_fields(r.schema)}", "",
        "Fill the form for THIS scene of THIS video:",
        *rules,
        "Reply with the filled form as JSON.",
    ])
    slots = _loop(llm, DIRECTOR, fill_prompt, lambda o: check_slots(name, o), schema=r.schema,
                  label=f"scene {i + 1} ({name})", temperature=0.4, max_tokens=1500)
    scene, repaired = recipes.build_scene(name, slots, s["narration"])
    for note in repaired:
        _log(f"scene {i + 1}: cue repaired {note}")
    scene["id"] = re.sub(r"[^a-z0-9_]+", "_", (s.get("id") or f"s{i + 1}").lower())[:24] or f"s{i + 1}"
    scene["mood"] = s.get("mood") if s.get("mood") in plan_mod.MOODS else "night"
    if scene["mood"] == "signal" and name not in SIGNAL_SAFE:
        prev_mood = (prev_scene or {}).get("mood")
        scene["mood"] = "dusk" if prev_mood != "dusk" else "night"
        _log(f"scene {i + 1}: {name} on the amber mood would hide its props; using {scene['mood']}")
    tr = dict(s.get("transition") or {"type": "dissolve"}) if i else {"type": "cut"}
    if tr.get("type") in ("zoom-in", "iris"):
        prev_ids = {a["id"] for a in (prev_scene or {}).get("actors", [])}
        if tr.get("actor") not in prev_ids:
            tr["actor"] = _main_actor(prev_scene or {})
    scene["transition"] = tr
    scene["slots"] = slots
    scene["why"] = choice.get("why", "")
    return scene

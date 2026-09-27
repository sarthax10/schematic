# Schematic

Animated, narrated 9:16 engineering explainers (system design, networking, databases, APIs...),
60–90 seconds each, generated end to end: the app picks a topic it hasn't covered, writes a
teaching script with a real-life analogy and a real-world example, fact-checks it, storyboards
it into scenes, designs every scene as animation (characters, props, camera moves, transitions),
narrates it, checks the real rendered layout, and renders the MP4.

Sibling of Antiquary: same idea (short, human-reviewed educational videos), but every visual is
designed motion graphics rendered from HTML/CSS/JS, never sourced footage or generated images.

## Pipeline

```
topic ──► library check (never remake a video: keyword + embedding similarity)
      ──► script        design/TEACHING_SCRIPT_SKILL.md  (hook → analogy → reveal → mechanism → example → insight → recap)
      ──► review        independent accuracy pass; up to two automatic revisions
      ──► HUMAN REVIEW  the pipeline pauses: a person edits, listens, approves or requests changes
      ──► storyboard    sentences grouped into 6–10 scenes, each with mood, transition, 2–4 shots
      ──► design        one scene at a time in the Scene DSL, guarded by design/SCENE_DESIGN_SKILL.md
      ──► narrate       edge-tts per scene, word-level timestamps
      ──► lint          headless Chromium renders every shot; overlaps / off-safe-area / tiny text → redesign that scene
      ──► render        Chromium seeks every frame (pure function of t) → ffmpeg → out/<slug>/video.mp4
```

Every LLM stage validates the reply in code and sends named violations back for repair; every
stage's output is cached in `out/<slug>/`, so `--resume` never repeats finished work.

## Run

```bash
python -m venv .venv && .venv/Scripts/activate        # or: source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

# LLM: local Ollama by default (GPU if present, CPU otherwise, automatically)
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text        # optional: meaning-based duplicate-topic detection
python -m pipeline.llm              # check the backend answers

python -m pipeline.make                          # new topic, end to end
python -m pipeline.make --category databases
python -m pipeline.make --topic "how DNS works"  # replaced with a fresh topic if already made
python -m pipeline.make --resume out/<slug>

# The run pauses after the script. Review it (edit, listen, approve or request changes):
python -m pipeline.review                        # what's waiting
python -m pipeline.review out/<slug>             # opens the review page
# "Approve and continue" on the page resumes the pipeline; or run make --resume yourself.
# Unattended runs can skip the checkpoint with --auto-approve (not recommended).

# Rendering a plan directly (no LLM needed)
python -m pipeline.build examples/token_bucket/plan.json            # MP4
python -m pipeline.build examples/token_bucket/plan.json --preview  # live browser preview
python -m pipeline.build examples/token_bucket/plan.json --shots    # one still per shot
python -m pipeline.build examples/token_bucket/plan.json --lint     # layout check

python -m pipeline.library list
```

Any OpenAI-compatible server works instead of Ollama: `SCHEMATIC_LLM=openai:<model>` plus
`SCHEMATIC_LLM_BASE_URL` / `SCHEMATIC_LLM_API_KEY` (see `pipeline/llm.py`).

## The scene engine (runtime/)

A scene is a **set** (a mood background + actors in world space) seen through its own
**camera**, which glides between the scene's **shots**. Designers write verbs (enter, move,
send, morph, say, emit, count...) timed to words of the narration; the engine supplies the
craft: anticipation and follow-through on moves, arcs on throws, springs on arrivals, idle
breathing/blinking/drift on everything, eased camera moves with a slow push, parallax
backgrounds. Scene changes are real transitions (pan with motion blur, zoom-through into an
object, iris wipe, dissolve) and actors can be **carried** across a cut (the jar flies into
the next scene and morphs into a bucket).

- `engine.js` actors, tracks, camera, sends, bubbles, fx, morph · `main.js` transitions,
  carries, captions, preview, `lint()` · `props.js` 33 flat illustrations · `actors/character.js`
  posable people · `moods.js` night / day / dusk / signal
- Every property is computed from `t`, so rendering is frame-exact on any machine speed.
- The full vocabulary is in `design/SCENE_DSL.md`; `pipeline/plan.py` validates against
  catalogs parsed from the runtime itself.

`examples/token_bucket/` is a complete reference run (topic, script, storyboard, plan) and
the few-shot example every LLM stage is shown.

## Honest limitations

- The fact-check pass is another LLM reading the script, not a web search. "Nothing flagged"
  is not proof; watch every video before publishing.
- Small local models (7–8B) follow the DSL imperfectly; the validate → repair → lint loop
  catches structural and layout problems, not taste. Larger models design noticeably better.
- No publish step, no web app/review desk yet.

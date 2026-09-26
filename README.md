# Schematic

Animated, narrated 9:16 engineering explainers (system design, data structures, protocols),
rendered from a structured **scene plan**. A sibling of Antiquary: same idea (short,
reviewed educational videos), but the visuals are designed motion graphics, not sourced
footage.

```
plan.json ──► narrate (edge-tts, per scene, word timestamps)
          ──► timeline (cues resolved to spoken words, captions)
          ──► runtime/ (HTML/CSS/JS, every frame a pure function of t)
          ──► headless Chromium: seek(n/fps) + screenshot, 4 pages in parallel
          ──► ffmpeg ──► out/<plan>/video.mp4
```

## Run

```bash
python -m venv .venv && .venv/Scripts/activate      # or source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

python -m pipeline.build examples/cache_aside.json             # render MP4
python -m pipeline.build examples/cache_aside.json --preview   # live preview in a browser
python -m pipeline.build examples/cache_aside.json --stills 5,12.5
```

Narration is cached per scene (keyed on voice/rate/text), so iterating on visuals doesn't
re-synthesize audio.

## Scene vocabulary

The plan never contains pixel positions or animation code: only a closed vocabulary that
`pipeline/plan.py` validates (unknown icons/tones/actions are repaired with a warning;
unknown scene types are errors). Step `at` is a phrase from that scene's narration; the
step fires on the exact spoken word.

| type | data | step actions |
|---|---|---|
| `title` | `kicker`, `title`, `icons[]` | — |
| `architecture` | `nodes[{id, kind, label}]`, `edges[{from, to, label?}]`, `carry` | `reveal`, `highlight`, `fail`, `packet {path[]}`, `label {text}` |
| `code` | `file`, `code[]` | `highlight {lines:[a,b]}` |
| `stat` | `value`, `unit`, `label`, `bars[{label, value, tone}]` | `bars` |
| `takeaway` | `items[{text, tone}]` | `reveal {index}` |
| `compare` | `left/right {name, icon, points[], tone}` | `reveal {side}` |

Tones: `signal` (amber: look here), `ok` (mint), `fail` (coral), `ink2` (neutral).
Icons: see `runtime/icons.js` (mirrored in `pipeline/plan.py`).

## Design rules

- One signal colour (amber) that always means "look here / data in motion".
- Every property is computed from `t`: no CSS transitions, timers or rAF deltas. That is
  what makes rendering frame-exact at any machine speed.
- Motion is eased or sprung, never linear; nothing pops out of existence.
- Captions are plain clause-broken phrases (no karaoke), drawn by the runtime itself.
- Fonts (Bricolage Grotesque, JetBrains Mono; both OFL) are vendored in `runtime/fonts/`.

## Not built yet

LLM writer (topic → plan), technical-accuracy check pass, web app / review desk, music bed.

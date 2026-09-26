# Scene DSL reference

You write ONE scene as JSON. The engine does all easing, springs, arcs, idle motion and
camera smoothing; you only choose what exists, where, and which verbs happen on which words.

## Coordinates
Grid units, 1 unit = 90 px. The frame at zoom 1 is 12 wide × 21.3 tall; the camera focus point
lands at the centre of the safe area. Important content: x 1–11, y 2.6–12.6. Captions live at
y 13–15 — never put anything there. `at` is an actor's CENTRE (except `ground`: its top edge).
`size` is an actor's WIDTH in units (height follows its shape).

## Scene
```
{"id": "short-id", "mood": "night|day|dusk|signal",
 "transition": {"type": "cut|dissolve|pan|zoom-in|zoom-out|iris", "dir": "left|right|up|down (pan)", "actor": "id in PREVIOUS scene (zoom-in / iris origin)"},
 "narration": "<copied exactly>",
 "actors": [ ... ], "layouts": [ ... optional ... ],
 "shots": [ {"at": "phrase", "camera": {"focus": [x,y] | "actorId", "zoom": 0.9-2.2}, "beats": [ ... ]} ]}
```
The first shot has no `at`. Later shots start on their `at` phrase; the camera glides there.

## Actors (all need "id", "type", and "at" + "size" unless noted)
- `character` — a person. `look`: {"shirt": amber|mint|coral|sky|lav|sand|slate, "hair": short|long|bun|curly, "skin": 0-3}, `face`: "left"|"right", `pose`: one of {POSES}. Size 1.5–3 (height = 1.6 × size).
- `prop` — illustration: `prop` one of {PROPS}. Optional `state` (jar: {"count": 0-6}; door: {"open": true}; lock: {"open": true}; clock: {"fast": true}; traffic-light: {"light": "red|amber|green"}).
- `node` — tech component card: `icon` one of {ICONS}, `label` (≤ 12 chars). Size 2–3.
- `icon` — bare glyph: `icon`, `tone`.
- `text` — `text` (use **double asterisks** around ONE key term to underline it), `style`: display (≤14 chars, huge) | title (≤48) | label (≤32) | body (≤90) | mono (≤60, code/headers). `tone` optional. `screen: true` pins it to the screen so camera moves don't crop it — use for headlines.
- `counter` — animated number: `value`, `unit`, `style` (display|number), `tone`.
- `meter` — fill gauge: `value` 0–1, `label`, `tone`.
- `bars` — comparison: `items`: [{"label", "value", "display", "tone"}].
- `list` — key points: `items`: [{"text", "tone", "icon"}]; reveal with `reveal` beats.
- `code` — `file`, `code`: [lines] (≤ 34 chars each, ≤ 8 lines); highlight with `highlight-lines`.
- `shape` — `shape`: ground (a floor; `at` y = floor top; characters' feet stand on it) | rect | circle | ring | pill | zone (dashed container with `label`), `tone`.
- `connector` — NO `at`: `from`, `to` (actor ids), `style`: arrow|line|dashed, `curve`: straight|arc, `bend`: -1..1, `label`.
Common optional fields: `tone` (signal|ok|fail|sky|lavender|ink2), `carry`: "<id in previous scene>" (the actor flies from its old place to this one across the cut), `allowOverlap`: [ids] (intentional overlap: a person in front of a counter), `screen`: true.
Actors without an `enter` beat are on set from the start. Draw order = list order (later = in front).

## Layout helpers (optional; they set `at` for you)
`{"kind": "row", "actors": [ids], "x": 6, "y": 8, "gap": 0.7}` · `{"kind": "column", "actors": [...], "x": 6, "y": 7, "step": 2.6}` · `{"kind": "grid", "cols": 3, "step": 2.6, ...}` · `{"kind": "queue", "actors": [...], "x": 2, "y": 9.5, "step": 1.2}`

## Beats: {"at": "exact phrase from narration" OR "after": seconds after previous beat, "do": verb, ...}
- `enter` {actor, style: pop|grow|rise|drop|slide-left|slide-right|fade|draw|words|type}
- `exit` {actor, style: fade|pop|sink|slide-left|slide-right}
- `move` {actor, to: [x,y] | "actorId", walk: true (characters), arc: true|units, dur, face: left|right}
- `send` {from: id|[x,y], to: id|[x,y], item: "packet" or a prop name, count, stagger, dur, arc: units|false, tone, via: connectorId, reverse: true, spin: true, size}
- `morph` {from, to} — one actor transforms into another (analogy → tech)
- `state` {actor, state: {pose, expression: smile|neutral|open|frown, count, open, light, tone, text, label}}
- `count` {actor (counter), to, dur}
- `reveal` {actor (list), index}
- `highlight-lines` {actor (code), lines: [from, to]}
- `highlight` {actor, tone, hold} · `dim` {actors: [...]} · `undim` {actors: [...]}
- `label` {actor, text (≤ 14 chars), tone} — a badge on the actor
- `say` {actor (character), text (≤ 40 chars)} — speech bubble
- `emit` {actor, kind: sparkle|question|exclaim|zzz|sweat|check|cross|dust}
- `pulse` · `shake` · `hop` · `wiggle` · `spin` {actor}
- `scale` {actor, to} · `rotate` {actor, to} · `flash` {tone}

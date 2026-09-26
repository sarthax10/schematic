# Scene design skill: animated engineering explainers

This is the design guardrail every scene designer (human or LLM) follows. It is injected into
the scene-design prompt verbatim, so it is written as rules, not inspiration. Sources it
synthesizes: Anthropic's frontend-design and canvas-design skills (intentional aesthetics,
restraint, spatial communication over text), Remotion's agent-skill motion rules (never linear,
springs, sequenced transitions), Disney's 12 principles of animation as applied to motion
graphics (anticipation, follow-through, arcs, staging, secondary action, timing), Mayer's
multimedia-learning principles (coherence, signaling, redundancy, temporal contiguity), and
cross-platform vertical-video safe zones (Shorts/Reels/TikTok).

## 1. It is a film, not a deck

- A **scene** is a place and a moment. A **shot** is one camera framing inside it. Every
  scene has 2–4 shots; the camera moves between them (push in on the detail being said, pull
  back to reveal context, pan to follow the action). A scene with one static framing is a slide.
- Things **happen** on screen: objects travel, characters act, containers fill and empty,
  states change colour. If the narration describes a process, the process plays out visibly.
  If a shot only fades text in, redesign it.
- Something is always moving, but only one thing is the subject. The engine adds idle life
  (breathing characters, drifting props, camera float); you direct the one action the
  viewer must watch.
- Continuity beats cuts: carry an actor from one scene into the next (`carry`) whenever the
  story continues with it (the jar becomes the bucket; the request packet becomes the envelope).

## 2. Teach with pictures (Mayer)

- **Temporal contiguity:** a visual lands on the exact word that names it. Every beat has an
  `at` phrase copied from the narration.
- **Redundancy:** never put the narration on screen as text; captions already carry it. On-screen
  text is limited to labels, numbers, a key term, or one short title (≤ 6 words).
- **Coherence:** no decoration that doesn't carry meaning. Every actor in a shot must be
  something the narration refers to or the metaphor needs.
- **Signaling:** at most one highlighted thing per moment. Dim what doesn't matter.
- **Concrete first:** introduce the real-world analogy with characters and objects before the
  technical diagram, then morph the analogy into the tech (match the parts one-to-one).
- One idea per shot. If a shot needs two labels and an arrow to be understood, split it.

## 3. Composition (portrait 1080×1920, grid unit = 90px, frame = 12 × 21.3 units)

- **Safe area:** anything important stays inside x 1–11, y 2.6–12.6 units. Captions own
  y 12.9–14.8. Below 14.8 the platform UI covers the frame; only background may go there.
- Compose around a **focal point**, not the centre line: rule of thirds (x ≈ 4 or 8,
  y ≈ 5.5 or 9.5) for subjects; centre only for a single hero object or a big number.
- Scale contrast: one dominant element (4–7 units wide), supporting elements at half size or
  less. Five equal-size things in a row is a slide.
- Leave air: ≥ 0.6 units between actors; never overlap two actors unless one is carried by /
  sits inside the other (a ticket inside a jar, a label on a node).
- Characters stand on a `ground` line; things that rest, rest on something.
- Max 7 visible actors per shot. Max 2 text actors per shot.

## 4. Motion (the 12 principles, applied)

- Never linear. The engine eases everything; you choose the verb and the style.
- **Anticipation → action → follow-through:** big moves use `move` (the engine winds up and
  settles); arrivals get a `pulse`; impacts get a `shake`.
- **Arcs:** things thrown or delivered travel on arcs (`send` with `arc: true`).
- **Staging:** introduce elements in reading order of importance, staggered 0.1–0.2 s, never
  all at once. Exits are as designed as entrances.
- **Secondary action:** reactions sell the idea: a character `emit`s `question` when confused,
  `sparkle` on success, `sweat` when overloaded.
- **Timing:** ~0.4–0.6 s for small actions, 0.8–1.2 s for camera moves and big travels. Leave
  0.5–1 s of stillness after an important reveal so it registers.
- **Exaggeration:** when something is "too many", show many (8–12 packets, a queue of people),
  not two with a label.

## 5. Variety rules (anti-monotony, enforced across the video)

- Alternate moods: the same mood never runs more than 2 scenes in a row. Analogy scenes live in
  `day` or `dusk`; system scenes in `night`; use `signal` once, for the key insight.
- Alternate transitions: no transition type more than twice in a row. `cut` only for a punch.
- Alternate shot scale: follow a wide shot with a closer one (zoom ≥ 1.5) and vice versa.
- Every scene introduces at least one new visual element or a new state of an old one.
- At least 40% of scenes feature a character or a real-world prop, not only tech nodes.

## 6. Colour and type

- Colour carries meaning, consistently: `signal` (amber) = look here / in motion; `ok` (mint) =
  success, allowed, hit; `fail` (coral) = error, rejected, miss; `sky` = data at rest, info;
  `lavender` = secondary category. Don't use a tone for decoration.
- Text styles: `display` for one huge word/number per video section, `title` for a short
  headline, `label` for naming things, `mono` for code/headers/values. Sentence case. No
  all-caps words except true acronyms (API, HTTP, 429).
- Numbers are shown, not said twice: a counter that counts, a gauge that fills.

## 7. Real-world examples

- Every abstract concept gets a physical analogy from everyday life (a coffee shop, a post
  office, a library, traffic, a restaurant kitchen) AND one real technical example (a real
  product, protocol, status code, or header). The analogy is animated with characters and
  props; the real example is shown concretely (a real header, a real number).
- Map analogy to tech explicitly: morph or carry each analogy part into its technical
  counterpart and label it once.

## 8. Self-check before returning a scene

1. Could this shot be a static slide? Then add the action the narration describes.
2. Does every beat land on a word from the narration?
3. Is anything important outside x 1–11, y 2.6–12.6, or overlapping?
4. Is there exactly one focal point per shot?
5. Does it differ from the previous scene in mood, transition, or shot scale?

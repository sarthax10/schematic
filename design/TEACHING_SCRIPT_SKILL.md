# Teaching script skill

Rules for the script writer. The narration is the spine of the video: every scene, shot and
beat hangs off its exact words.

## Audience

Two viewers at once: a beginner who has never heard the term, and a working engineer who
knows it. The beginner must be able to follow every sentence; the professional must learn
one thing they didn't know or hadn't thought about (a trade-off, a real number, a failure
mode, how a real system does it).

## Length and pace

- 160–250 words (≈ 60–90 seconds spoken). Sentences of 6–18 words. Spoken, not written:
  contractions, second person ("you"), no parentheses, no lists read aloud.
- Numbers spoken the way a person says them ("five thousand requests an hour", "four
  twenty-nine").

## Structure (always this arc)

1. **Hook (1–2 sentences):** a concrete situation or question the viewer has hit. Never
   "In this video we will…".
2. **Real-life analogy (3–5 sentences):** an everyday place with people and objects that
   works exactly like the concept. Let it play out: normal case, then the interesting case.
3. **The reveal (1–2 sentences):** name the concept and map every part of the analogy to its
   technical counterpart, one-to-one.
4. **How it really works (2–4 sentences):** the mechanism in plain words, one step at a time.
   Define every term the moment it's used.
5. **Real-world example (1–3 sentences):** a real product, protocol, number, header, or
   incident. Must be accurate and verifiable; if unsure of a number, don't use one.
6. **The professional's insight (1–2 sentences):** the trade-off, the knob to tune, or the
   common mistake.
7. **Recap (1 sentence):** the whole idea in one line.

## Rules

- The analogy must play out EVERY step of the real mechanism, in the same order and the same
  number of steps (a three-step protocol gets three letters, not two). Check the mapping
  one-to-one before writing the reveal.
- The mechanism section must NOT retell the analogy. Name what the system really does:
  the actual messages, fields, numbers, states or data structures, in order.
- The insight must be something a working engineer might not know or might get wrong: a
  cost (latency, memory, round trips), a failure mode, a tuning knob, or why a newer design
  exists. "It's important for reliability" is not an insight.
- The hook names a concrete moment the viewer has lived through (a page that hangs, an error
  they've seen, a bill that spiked), and the question the video answers.
- Explain, don't name-drop. Every piece of jargon gets a plain-words definition right away.
- One analogy for the whole video. Don't mix metaphors.
- Show-able sentences: each sentence should describe something that can be drawn happening.
- No hedging filler ("basically", "essentially", "it's important to note").
- Accuracy over drama: never invent statistics, company internals, or history.

// Scene engine. A video is a sequence of scenes; each scene is a *set* (mood background +
// actors in world space) seen through its own *camera*, which moves between the scene's
// shots. Directors (human or LLM) write verbs — enter, move, send, morph, say, emit — and the
// engine turns them into motion with the craft built in: anticipation and follow-through on
// moves, arcs on throws, springs on arrivals, idle life on everything, eased camera moves.
// Every value is a pure function of t, so any frame can be rendered exactly.
import { clamp, css, ease, el, envelope, hash01, latest, lerp, prog, rgb, spring, svg, tone, TONES } from "./core.js";
import { applyMood, mood } from "./moods.js";
import * as basic from "./actors/basic.js";
import * as character from "./actors/character.js";
import { PROPS } from "./props.js";

export const U = 90; // one grid unit in px
export const FW = 1080, FH = 1920;
export const ANCHOR = [540, 690]; // screen point the camera's focus lands on (safe-area centre)
export const TRANS = { pre: 0.35, post: 0.55 }; // transition window around a scene boundary

const FACTORIES = {
  text: basic.text, prop: basic.prop, node: basic.node, icon: basic.glyph, shape: basic.shape,
  counter: basic.counter, meter: basic.meter, bars: basic.bars, list: basic.list, code: basic.code,
  character: character.create,
};

// ---- keyframe tracks -------------------------------------------------------------------------
// A track is a list of {t, dur, to, ease}; each key eases from the previous key's target.
function evalTrack(keys, t, initial) {
  let v = initial;
  for (const k of keys) {
    if (t < k.t) break;
    const from = k.from ?? v;
    v = lerp(from, k.to, (k.ease || ease.inOutCubic)(clamp((t - k.t) / Math.max(k.dur, 1e-6))));
  }
  return v;
}

const ENTER = {
  pop: (tr, t) => { tr.s.push({ t, dur: 0.7, from: 0.4, to: 1, ease: ease.spring }); tr.o.push({ t, dur: 0.2, from: 0, to: 1 }); },
  grow: (tr, t) => { tr.s.push({ t, dur: 0.8, from: 0, to: 1, ease: ease.spring }); tr.o.push({ t, dur: 0.12, from: 0, to: 1 }); },
  rise: (tr, t) => { tr.dy.push({ t, dur: 0.65, from: 80, to: 0, ease: ease.outCubic }); tr.o.push({ t, dur: 0.35, from: 0, to: 1 }); },
  drop: (tr, t) => { tr.dy.push({ t, dur: 0.8, from: -320, to: 0, ease: ease.outBack }); tr.o.push({ t, dur: 0.15, from: 0, to: 1 }); },
  "slide-left": (tr, t) => { tr.dx.push({ t, dur: 0.85, from: 560, to: 0, ease: ease.outCubic }); tr.o.push({ t, dur: 0.3, from: 0, to: 1 }); },
  "slide-right": (tr, t) => { tr.dx.push({ t, dur: 0.85, from: -560, to: 0, ease: ease.outCubic }); tr.o.push({ t, dur: 0.3, from: 0, to: 1 }); },
  fade: (tr, t) => { tr.o.push({ t, dur: 0.5, from: 0, to: 1 }); },
  draw: (tr, t) => { tr.o.push({ t, dur: 0.3, from: 0, to: 1 }); tr.s.push({ t, dur: 0.5, from: 0.94, to: 1, ease: ease.outCubic }); },
  words: (tr, t) => { tr.o.push({ t, dur: 0.01, from: 0, to: 1 }); },
  type: (tr, t) => { tr.o.push({ t, dur: 0.01, from: 0, to: 1 }); },
};
const EXIT = {
  fade: (tr, t) => tr.o.push({ t, dur: 0.4, to: 0 }),
  pop: (tr, t) => { tr.s.push({ t, dur: 0.35, to: 0.2, ease: ease.inCubic }); tr.o.push({ t: t + 0.1, dur: 0.25, to: 0 }); },
  sink: (tr, t) => { tr.dy.push({ t, dur: 0.5, to: 120, ease: ease.inCubic }); tr.o.push({ t, dur: 0.45, to: 0 }); },
  "slide-left": (tr, t) => { tr.dx.push({ t, dur: 0.6, to: -700, ease: ease.inCubic }); tr.o.push({ t: t + 0.3, dur: 0.3, to: 0 }); },
  "slide-right": (tr, t) => { tr.dx.push({ t, dur: 0.6, to: 700, ease: ease.inCubic }); tr.o.push({ t: t + 0.3, dur: 0.3, to: 0 }); },
};

// ---- scene construction ---------------------------------------------------------------------
export function buildScene(scene, host) {
  const S = { scene, actors: new Map(), connectors: [], sends: [], bubbles: [], fx: [], flashes: [] };
  S.el = el("div", "scene", host);
  S.bg = el("div", "scene-bg", S.el);
  S.pattern = el("div", "scene-pattern", S.el);
  S.world = el("div", "world", S.el);
  S.wires = svg("svg", { class: "wires", width: 8000, height: 8000, viewBox: "-2000 -2000 8000 8000", style: "left:-2000px;top:-2000px" }, S.world);
  S.actorLayer = el("div", "actor-layer", S.world);
  S.fxLayer = el("div", "fx-layer", S.world);
  S.screen = el("div", "screen-layer", S.el);
  applyMood(S.el, S.bg, S.pattern, scene.mood);
  S.mood = mood(scene.mood);

  const beats = [...(scene.beats || [])].sort((a, b) => a.t - b.t);
  const byActor = (id) => beats.filter((b) => b.actor === id);

  // First pass: fold actor-internal events (state/pose/count/reveal) into each spec.
  for (const spec of scene.actors || []) {
    if (spec.type === "connector") continue;
    const mine = byActor(spec.id);
    spec._states = mine.filter((b) => ["state", "count", "reveal", "highlight-lines"].includes(b.do)).map((b) => {
      const s = { t: b.t, ...(b.state || {}) };
      if (b.do === "count") { s.to = b.to; s.dur = b.dur; }
      if (b.do === "reveal") s.index = b.index;
      if (b.do === "highlight-lines") s.lines = b.lines;
      if (b.text != null && b.do === "state") s.text = b.text;
      return s;
    });
    spec._poses = mine.filter((b) => b.do === "state" && b.state?.pose).map((b) => ({ t: b.t, pose: b.state.pose }));
    spec._faces = mine.filter((b) => b.do === "state" && b.state?.expression).map((b) => ({ t: b.t, face: b.state.expression }));
    // A walking move implies a walk pose for its duration, then back to what it was.
    for (const b of mine.filter((b) => b.do === "move" && b.walk)) {
      const before = latest([{ t: -1, pose: spec.pose || "idle" }, ...spec._poses.sort((a, c) => a.t - c.t)], b.t);
      spec._poses.push({ t: b.t, pose: "walk" }, { t: b.t + (b.dur || 1.2), pose: before?.pose || "idle" });
      if (b.face) spec._faceDir = spec._faceDir || [];
    }
    const enter = mine.find((b) => b.do === "enter");
    spec._enterT = enter ? enter.t : -1;
    spec._enterStyle = enter?.style;
  }

  // Build actors.
  for (const spec of scene.actors || []) {
    if (spec.type === "connector") continue;
    const make = FACTORIES[spec.type];
    if (!make) continue;
    const impl = make(spec);
    const wrap = el("div", `actor a-${spec.type}`, spec.screen ? S.screen : S.actorLayer);
    const inner = el("div", "inner", wrap);
    inner.appendChild(impl.el);
    const isGround = spec.type === "shape" && spec.shape === "ground";
    const w = isGround ? 44 * U : (spec.size || (spec.type === "text" ? spec.width || 9 : 3)) * U;
    css(wrap, { width: `${w}px` });
    if (isGround) css(wrap, { height: `${16 * U}px` });
    else if (impl.aspect) css(wrap, { height: `${w * impl.aspect}px` });
    if (spec.face === "left") css(inner, { transform: "scaleX(-1)" });
    const [ax, ay] = spec.at || [6, 7.6];
    const A = {
      spec, impl, wrap, inner, w, bx: ax * U, by: ay * U,
      tr: { dx: [], dy: [], s: [], r: [], o: [], arc: [] },
      ev: { pulse: [], shake: [], hop: [], wiggle: [], spin: [], hl: [], dim: [], labels: [] },
      idle: spec.idle ?? (["prop", "node", "icon"].includes(spec.type) ? 1 : 0),
      phase: hash01(spec.id) * 6.28,
    };
    A.h = isGround ? 16 * U : impl.aspect ? w * impl.aspect : null;
    if (isGround) A.by += A.h / 2; // `at` names the floor's top edge
    S.actors.set(spec.id, A);
  }
  // Heights of auto-sized actors (text, code, lists) once laid out. The scene is hidden
  // (display:none) outside its time window, so measure while it is briefly displayed.
  S.el.style.display = "block";
  for (const A of S.actors.values()) {
    if (A.h == null) A.h = A.wrap.offsetHeight || U;
  }
  S.el.style.display = "";
  for (const A of S.actors.values()) {
    css(A.wrap, { left: `${(A.bx - A.w / 2).toFixed(1)}px`, top: `${(A.by - A.h / 2).toFixed(1)}px` });
  }

  // Connectors (drawn as SVG, endpoints follow their actors every frame).
  for (const spec of scene.actors || []) {
    if (spec.type !== "connector") continue;
    const path = svg("path", { fill: "none", "stroke-width": 6, "stroke-linecap": "round" }, S.wires);
    if (spec.style === "dashed") path.setAttribute("stroke-dasharray", "4 16");
    const head = spec.style === "line" || spec.style === "dashed" ? null : svg("path", { fill: "none", "stroke-width": 6, "stroke-linecap": "round", "stroke-linejoin": "round" }, S.wires);
    const label = spec.label ? svg("text", { class: "wire-label", "text-anchor": "middle" }, S.wires) : null;
    if (label) label.textContent = spec.label;
    const enter = byActor(spec.id).find((b) => b.do === "enter");
    const exit = byActor(spec.id).find((b) => b.do === "exit");
    S.connectors.push({ spec, path, head, label, enterT: enter ? enter.t : -1, exitT: exit ? exit.t : Infinity, heat: [] });
  }

  // Second pass: engine-level verbs → tracks and events.
  for (const b of beats) {
    const A = S.actors.get(b.actor);
    const tr = A?.tr;
    switch (b.do) {
      case "enter": if (A) (ENTER[b.style] || (A.spec.type === "text" ? ENTER.words : ENTER.pop))(tr, b.t); break;
      case "exit": if (A) (EXIT[b.style] || EXIT.fade)(tr, b.t); break;
      case "move": {
        if (!A) break;
        const target = moveTarget(S, A, b);
        const dur = b.dur || (b.walk ? 1.2 : 0.9);
        const e = b.walk ? ease.inOutSine : ease.inOutBack;
        tr.dx.push({ t: b.t, dur, to: target[0] - A.bx, ease: e });
        tr.dy.push({ t: b.t, dur, to: target[1] - A.by, ease: e });
        if (b.arc) tr.arc.push({ t: b.t, dur, h: typeof b.arc === "number" ? b.arc * U : 1.6 * U });
        if (b.face) A.faceKeys = [...(A.faceKeys || []), { t: b.t, face: b.face }];
        break;
      }
      case "scale": if (A) tr.s.push({ t: b.t, dur: b.dur || 0.6, to: b.to ?? 1.2, ease: ease.spring }); break;
      case "rotate": if (A) tr.r.push({ t: b.t, dur: b.dur || 0.6, to: b.to ?? 0, ease: ease.inOutBack }); break;
      case "pulse": case "shake": case "hop": case "wiggle": case "spin": if (A) A.ev[b.do].push(b.t); break;
      case "highlight": if (A) A.ev.hl.push({ t: b.t, tone: b.tone || "signal", hold: b.hold ?? 1.6 }); break;
      case "dim": for (const id of b.actors || [b.actor]) S.actors.get(id)?.ev.dim.push({ t: b.t, on: true }); break;
      case "undim": for (const id of b.actors || [b.actor]) S.actors.get(id)?.ev.dim.push({ t: b.t, on: false }); break;
      case "label": if (A) A.ev.labels.push({ t: b.t, text: b.text, tone: b.tone || "signal", hold: b.hold ?? Infinity }); break;
      case "say": if (A) S.bubbles.push(makeBubble(S, A, b)); break;
      case "emit": if (A) S.fx.push(...makeFx(S, A, b)); break;
      case "send": S.sends.push(...makeSends(S, b)); break;
      case "morph": morph(S, b); break;
      case "flash": S.flashes.push({ t: b.t, tone: b.tone || "signal" }); break;
    }
  }
  for (const A of S.actors.values()) {
    for (const k of Object.values(A.tr)) k.sort((a, b) => a.t - b.t);
    A.ev.hl.sort((a, b) => a.t - b.t).forEach((h, i, all) => { h.end = Math.min(h.t + h.hold, all[i + 1]?.t ?? Infinity); });
    A.ev.labels.sort((a, b) => a.t - b.t);
    A.ev.dim.sort((a, b) => a.t - b.t);
    if (A.ev.labels.length) {
      A.badge = el("div", "badge", A.wrap);
    }
    // Actors never entered are on set from the start; entered ones are hidden until then.
    A.initialO = A.spec._enterT >= 0 || A.spec.carry ? 0 : 1;
    if (A.spec.carry) A.initialO = 1;
  }

  // Sends: travelling heats its connector; each arrival ripples its target.
  for (const sd of S.sends) {
    const via = sd.b.via && S.connectors.find((c) => c.spec.id === sd.b.via);
    if (via) via.heat.push({ t0: sd.t0, t1: sd.t0 + sd.dur });
    const T = typeof sd.b.to === "string" && S.actors.get(sd.b.to);
    if (T && sd.b.impact !== false) T.ev.pulse.push(sd.t0 + sd.dur);
  }

  // Camera shots: resolve each shot's framing.
  S.shots = (scene.shots || [{ t: 0 }]).map((sh) => ({ ...sh, ...resolveFraming(S, sh) }));
  S.flashEl = el("div", "flash", S.el);
  return S;
}

function moveTarget(S, A, b) {
  if (typeof b.to === "string") {
    const T = S.actors.get(b.to);
    if (T) return [T.bx + (b.offset?.[0] || 0) * U, T.by + (b.offset?.[1] || 0) * U];
  }
  if (Array.isArray(b.to)) return [b.to[0] * U, b.to[1] * U];
  if (Array.isArray(b.by)) return [A.bx + b.by[0] * U, A.by + b.by[1] * U];
  return [A.bx, A.by];
}

function resolveFraming(S, sh) {
  const cam = sh.camera || {};
  let f = cam.focus;
  if (typeof f === "string") {
    const A = S.actors.get(f);
    f = A ? [A.bx / U, A.by / U] : null;
  }
  if (Array.isArray(f) && Array.isArray(f[0])) {
    // A list of actor ids/points to frame together: centre of their bounds.
    f = [f.reduce((a, p) => a + p[0], 0) / f.length, f.reduce((a, p) => a + p[1], 0) / f.length];
  }
  return { fx: (f?.[0] ?? 6) * U, fy: (f?.[1] ?? 7.67) * U, zoom: cam.zoom || 1, cdur: cam.dur ?? 1.0, cut: !!cam.cut };
}

// ---- per-actor current world state -----------------------------------------------------------
export function actorState(A, t) {
  const tr = A.tr;
  let x = A.bx + evalTrack(tr.dx, t, 0);
  let y = A.by + evalTrack(tr.dy, t, 0);
  let s = evalTrack(tr.s, t, 1);
  let r = evalTrack(tr.r, t, 0);
  let o = evalTrack(tr.o, t, A.initialO);
  for (const a of tr.arc) {
    const p = (t - a.t) / a.dur;
    if (p > 0 && p < 1) y -= a.h * Math.sin(Math.PI * ease.inOutSine(p));
  }
  if (A.idle) {
    y += Math.sin(t * 1.6 + A.phase) * 4 * A.idle;
    r += Math.sin(t * 1.1 + A.phase) * 0.6 * A.idle;
  }
  for (const p0 of A.ev.pulse) { const d = t - p0; if (d > 0 && d < 0.45) s *= 1 + 0.14 * Math.sin((Math.PI * d) / 0.45); }
  for (const p0 of A.ev.shake) { const d = t - p0; if (d > 0 && d < 0.5) x += Math.sin(d * 55) * 16 * (1 - d / 0.5); }
  for (const p0 of A.ev.hop) { const d = t - p0; if (d > 0 && d < 0.5) { y -= 70 * Math.sin((Math.PI * d) / 0.5); s *= 1 + 0.05 * Math.sin((Math.PI * d) / 0.5); } }
  for (const p0 of A.ev.wiggle) { const d = t - p0; if (d > 0 && d < 0.7) r += 9 * Math.sin(d * 28) * (1 - d / 0.7); }
  for (const p0 of A.ev.spin) { const d = t - p0; if (d > 0) r += 360 * ease.inOutBack(clamp(d / 0.8)); }
  const dimE = latest(A.ev.dim, t);
  if (dimE) {
    const k = prog(t, dimE.t, 0.4);
    o *= dimE.on ? 1 - 0.72 * k : 0.28 + 0.72 * k;
  }
  if (A.carryOverride) {
    const c = A.carryOverride(t);
    if (c) { x = c.x; y = c.y; s *= c.s; o = 1; }
  }
  return { x, y, s, r, o };
}

// ---- camera ---------------------------------------------------------------------------------
export function cameraAt(S, lt) {
  const shots = S.shots;
  let i = 0;
  while (i + 1 < shots.length && shots[i + 1].t <= lt) i++;
  const cur = shots[i], prev = shots[i - 1];
  let fx = cur.fx, fy = cur.fy, zoom = cur.zoom;
  if (prev && !cur.cut) {
    const p = ease.inOutCubic(clamp((lt - cur.t) / cur.cdur));
    fx = lerp(prev.fx, cur.fx, p); fy = lerp(prev.fy, cur.fy, p);
    // Zoom interpolated in log space so push-ins feel linear to the eye.
    zoom = Math.exp(lerp(Math.log(prev.zoom), Math.log(cur.zoom), p));
  }
  // Slow push through every shot + a gentle floating drift: no frame is ever locked off.
  const next = shots[i + 1];
  const shotLen = (next ? next.t : S.scene.duration) - cur.t;
  zoom *= 1 + 0.03 * ease.inOutSine(clamp((lt - cur.t) / Math.max(shotLen, 0.1)));
  fx += Math.sin(lt * 0.55 + 1.3) * 5;
  fy += Math.sin(lt * 0.41) * 4;
  return { fx, fy, zoom };
}

export const worldToScreen = (cam, x, y) => [ANCHOR[0] + (x - cam.fx) * cam.zoom, ANCHOR[1] + (y - cam.fy) * cam.zoom];
export const screenToWorld = (cam, x, y) => [(x - ANCHOR[0]) / cam.zoom + cam.fx, (y - ANCHOR[1]) / cam.zoom + cam.fy];

// ---- sends: things travelling between actors --------------------------------------------------
function makeSends(S, b) {
  const out = [];
  const count = b.count || 1;
  const dur = b.dur || 0.9;
  const stagger = b.stagger ?? 0.22;
  for (let i = 0; i < count; i++) {
    const node = el("div", "send", S.fxLayer);
    const item = b.item || "packet";
    const col = tone(b.tone || "signal");
    let size = (b.size || (item === "packet" ? 0.36 : 0.9)) * U;
    if (item === "packet") {
      css(node, { width: `${size}px`, height: `${size}px`, "border-radius": "50%", background: rgb(col), "box-shadow": `0 0 ${size}px ${rgb(col, 0.8)}` });
    } else {
      const def = PROPS[item] || PROPS.box;
      node.innerHTML = `<svg viewBox="0 0 200 ${def.h}" width="100%" height="100%" style="overflow:visible">${def.svg()}</svg>`;
      css(node, { width: `${size}px`, height: `${(size * def.h) / 200}px` });
    }
    out.push({ node, b, t0: b.t + i * stagger, dur, size, spread: count > 1 ? (i - (count - 1) / 2) * 0.25 * U : 0 });
  }
  return out;
}

function endpoint(S, ref, t) {
  if (Array.isArray(ref)) return [ref[0] * U, ref[1] * U];
  const A = S.actors.get(ref);
  if (!A) return [6 * U, 7.6 * U];
  const st = actorState(A, t);
  return [st.x, st.y];
}

// ---- speech bubbles & fx ----------------------------------------------------------------------
function makeBubble(S, A, b) {
  const node = el("div", "bubble", S.fxLayer);
  el("div", "bubble-text", node, b.text);
  return { node, A, t: b.t, end: b.t + (b.hold ?? Math.max(1.6, b.text.length * 0.07)) };
}

const FX_GLYPH = {
  question: "?", exclaim: "!", zzz: "z", check: "✓", cross: "✕",
};
function makeFx(S, A, b) {
  const kind = b.kind || "sparkle";
  const n = { sparkle: 5, sweat: 3, zzz: 3, question: 1, exclaim: 1, check: 1, cross: 1, hearts: 3, steam: 3, dust: 6 }[kind] || 3;
  const out = [];
  for (let i = 0; i < n; i++) {
    const node = el("div", `fx fx-${kind}`, S.fxLayer);
    if (FX_GLYPH[kind]) node.textContent = FX_GLYPH[kind];
    out.push({ node, A, kind, t: b.t + i * (kind === "zzz" ? 0.35 : 0.06), i, n, tone: b.tone });
  }
  return out;
}

function morph(S, b) {
  const F = S.actors.get(b.from), T = S.actors.get(b.to);
  if (!F || !T) return;
  const dur = b.dur || 0.9;
  F.tr.dx.push({ t: b.t, dur, to: T.bx - F.bx, ease: ease.inOutBack });
  F.tr.dy.push({ t: b.t, dur, to: T.by - F.by, ease: ease.inOutBack });
  F.tr.s.push({ t: b.t, dur, to: T.w / F.w, ease: ease.inOutCubic });
  F.tr.o.push({ t: b.t + dur * 0.55, dur: dur * 0.35, to: 0 });
  T.tr.s.push({ t: b.t + dur * 0.5, dur: 0.7, from: 0.6, to: 1, ease: ease.spring });
  T.tr.o.push({ t: b.t + dur * 0.5, dur: 0.25, from: 0, to: 1 });
  T.spec._enterT = b.t + dur * 0.5;
  S.fx.push({ node: el("div", "fx fx-ring", S.fxLayer), A: T, kind: "ring", t: b.t + dur * 0.55, i: 0, n: 1, tone: b.tone || "signal" });
}

// ---- per-frame update of one scene at local time lt -------------------------------------------
export function updateScene(S, lt) {
  const cam = cameraAt(S, lt);
  css(S.world, { transform: `translate(${(ANCHOR[0] - cam.fx * cam.zoom).toFixed(2)}px, ${(ANCHOR[1] - cam.fy * cam.zoom).toFixed(2)}px) scale(${cam.zoom.toFixed(5)})` });
  // Background pattern moves at a third of the camera: cheap parallax depth.
  css(S.pattern, { "background-position": `${(-cam.fx * 0.3).toFixed(1)}px ${(-cam.fy * 0.3).toFixed(1)}px`, transform: `scale(${(1 + (cam.zoom - 1) * 0.3).toFixed(4)})` });

  for (const A of S.actors.values()) {
    const st = actorState(A, lt);
    A.cur = st;
    css(A.wrap, {
      transform: `translate(${(st.x - A.bx).toFixed(2)}px, ${(st.y - A.by).toFixed(2)}px) rotate(${st.r.toFixed(3)}deg) scale(${st.s.toFixed(4)})`,
      opacity: String(clamp(st.o).toFixed(3)),
      visibility: st.o < 0.002 ? "hidden" : "visible",
    });
    if (A.faceKeys) {
      const f = latest(A.faceKeys, lt);
      css(A.inner, { transform: f?.face === "left" || (!f && A.spec.face === "left") ? "scaleX(-1)" : "none" });
    }
    const h = latest(A.ev.hl, lt);
    const k = h ? envelope(lt, h.t, h.end) : 0;
    const c = h ? tone(h.tone) : TONES.signal;
    if (A.impl.highlight) A.impl.highlight(k, c);
    else css(A.inner, { filter: k > 0.01 ? `drop-shadow(0 0 ${(26 * k).toFixed(1)}px ${rgb(c, 0.85 * k)})` : "none" });
    if (A.badge) {
      const lab = latest(A.ev.labels, lt);
      if (lab && lt < lab.t + lab.hold) {
        if (A.badge.textContent !== lab.text) A.badge.textContent = lab.text;
        const bs = spring(lt, lab.t, { stiffness: 260, damping: 16 });
        css(A.badge, { opacity: String(clamp(bs * 2).toFixed(3)), transform: `translateX(-50%) scale(${(0.5 + 0.5 * bs).toFixed(4)})`, background: rgb(tone(lab.tone)) });
      } else css(A.badge, { opacity: "0" });
    }
    A.impl.update(lt);
  }

  for (const C of S.connectors) {
    const a = S.actors.get(C.spec.from), b = S.actors.get(C.spec.to);
    if (!a || !b) continue;
    const g = connectorGeom(a, b, C.spec);
    C.geom = g;
    const p = C.enterT < 0 ? 1 : prog(lt, C.enterT, 0.55, ease.inOutCubic);
    const fade = Math.min(a.cur.o, b.cur.o, 1 - prog(lt, C.exitT, 0.4));
    let heat = 0;
    for (const hz of C.heat) heat = Math.max(heat, envelope(lt, hz.t0, hz.t1, 0.1, 0.35));
    const base = C.spec.tone ? tone(C.spec.tone) : S.mood.wire;
    const col = rgb(heat > 0 ? base.map((v, i) => Math.round(lerp(v, TONES.signal[i], heat))) : base);
    C.path.setAttribute("d", g.d);
    const len = g.len;
    css(C.path, { stroke: col, opacity: String(fade.toFixed(3)), "stroke-dasharray": C.spec.style === "dashed" ? "4 16" : `${len}`, "stroke-dashoffset": C.spec.style === "dashed" ? `${(-lt * 30).toFixed(1)}` : `${(len * (1 - p)).toFixed(1)}` });
    if (C.head) {
      C.head.setAttribute("d", g.headD);
      css(C.head, { stroke: col, opacity: String((fade * prog(lt, C.enterT + 0.4, 0.2)).toFixed(3)) });
    }
    if (C.label) {
      C.label.setAttribute("x", g.mid[0]); C.label.setAttribute("y", g.mid[1] - 18);
      css(C.label, { opacity: String((fade * prog(lt, C.enterT + 0.45, 0.3)).toFixed(3)) });
    }
  }

  for (const sd of S.sends) {
    const { b } = sd;
    const p = clamp((lt - sd.t0) / sd.dur);
    const alive = lt >= sd.t0 && lt <= sd.t0 + sd.dur + 0.2;
    if (!alive) { css(sd.node, { opacity: "0" }); continue; }
    let x, y;
    const e = ease.inOutCubic(p);
    const via = b.via && S.connectors.find((c) => c.spec.id === b.via);
    if (via?.geom) {
      [x, y] = via.geom.at(b.reverse ? 1 - e : e);
    } else {
      const [x0, y0] = endpoint(S, b.from, sd.t0);
      const [x1, y1] = endpoint(S, b.to, sd.t0 + sd.dur);
      x = lerp(x0, x1, e) + sd.spread * Math.sin(Math.PI * p);
      y = lerp(y0, y1, e) - (b.arc === false ? 0 : (b.arc || 1.4) * U * Math.sin(Math.PI * p));
    }
    const o = prog(lt, sd.t0, 0.1) * (1 - prog(lt, sd.t0 + sd.dur, 0.18));
    css(sd.node, { opacity: String(o.toFixed(3)), transform: `translate(${(x - sd.size / 2).toFixed(1)}px, ${(y - sd.size / 2).toFixed(1)}px) rotate(${(b.spin ? p * 360 : 0).toFixed(1)}deg)` });
  }

  for (const B of S.bubbles) {
    const st = B.A.cur;
    const on = lt >= B.t && lt < B.end + 0.3;
    if (!on) { css(B.node, { opacity: "0", visibility: "hidden" }); continue; }
    const s = spring(lt, B.t, { stiffness: 240, damping: 17 });
    const out = prog(lt, B.end, 0.25, ease.inCubic);
    const top = st.y - (B.A.h * st.s) / 2 - 30;
    css(B.node, { visibility: "visible", opacity: String((clamp(s * 2) * (1 - out)).toFixed(3)), transform: `translate(${st.x.toFixed(1)}px, ${top.toFixed(1)}px) translate(-50%, -100%) scale(${(0.6 + 0.4 * s).toFixed(4)})` });
  }

  for (const F of S.fx) {
    const d = lt - F.t;
    const life = F.kind === "ring" ? 0.6 : 1.1;
    if (d < 0 || d > life) { css(F.node, { opacity: "0" }); continue; }
    const st = F.A.cur;
    const p = d / life;
    const top = st.y - (F.A.h * st.s) / 2;
    let x = st.x, y = top, sc = 1, o = Math.sin(Math.PI * p);
    const ang = (F.i / Math.max(F.n, 1)) * Math.PI * 2 + hash01(F.A.spec.id) * 3;
    if (F.kind === "sparkle" || F.kind === "dust") { x += Math.cos(ang) * (40 + 90 * p) * (F.kind === "dust" ? 1.4 : 1); y += Math.sin(ang) * (30 + 70 * p) + (F.kind === "dust" ? F.A.h * st.s * 0.5 : 0); sc = 1 - p * 0.5; }
    else if (F.kind === "zzz") { x += 40 + 30 * p + F.i * 20; y -= 40 + 90 * p; sc = 0.7 + F.i * 0.25; }
    else if (F.kind === "sweat") { x += (F.i - 1) * 50; y += 20 + 60 * p; }
    else if (F.kind === "ring") { x = st.x; y = st.y; sc = 0.6 + 1.2 * ease.outCubic(p); o = 1 - p; }
    else { y -= 30 + 50 * ease.outBack(clamp(p * 2)); sc = spring(lt, F.t, { stiffness: 300, damping: 14 }); o = 1 - prog(lt, F.t + 0.8, 0.3); }
    if (F.kind === "ring") css(F.node, { width: `${F.A.w * 1.1}px`, height: `${F.A.w * 1.1}px`, "border-color": rgb(tone(F.tone || "signal")) });
    css(F.node, { opacity: String(clamp(o).toFixed(3)), transform: `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(-50%, -50%) scale(${sc.toFixed(3)})` });
  }

  let flash = 0, fcol = TONES.signal;
  for (const f of S.flashes) { const d = lt - f.t; if (d > 0 && d < 0.5) { flash = Math.max(flash, 1 - d / 0.5); fcol = tone(f.tone); } }
  css(S.flashEl, { opacity: String((flash * 0.55).toFixed(3)), background: rgb(fcol) });
  return cam;
}

// Connector geometry: endpoints clipped to each actor's box so arrows touch edges, not centres.
function connectorGeom(a, b, spec) {
  const clip = (A, tx, ty) => {
    const st = A.cur, hw = (A.w * st.s) / 2 + 16, hh = (A.h * st.s) / 2 + 16;
    const dx = tx - st.x, dy = ty - st.y;
    const k = Math.min(Math.abs(dx) > 1e-6 ? hw / Math.abs(dx) : Infinity, Math.abs(dy) > 1e-6 ? hh / Math.abs(dy) : Infinity);
    return [st.x + dx * Math.min(k, 1), st.y + dy * Math.min(k, 1)];
  };
  const p0 = clip(a, b.cur.x, b.cur.y), p1 = clip(b, a.cur.x, a.cur.y);
  const curve = spec.curve || "straight";
  let cx = (p0[0] + p1[0]) / 2, cy = (p0[1] + p1[1]) / 2;
  if (curve === "arc") {
    const nx = -(p1[1] - p0[1]), ny = p1[0] - p0[0], n = Math.hypot(nx, ny) || 1;
    const bend = 0.22 * Math.hypot(p1[0] - p0[0], p1[1] - p0[1]) * (spec.bend ?? 1);
    cx += (nx / n) * bend; cy += (ny / n) * bend;
  }
  const at = (u) => [lerp(lerp(p0[0], cx, u), lerp(cx, p1[0], u), u), lerp(lerp(p0[1], cy, u), lerp(cy, p1[1], u), u)];
  const len = Math.hypot(cx - p0[0], cy - p0[1]) + Math.hypot(p1[0] - cx, p1[1] - cy);
  const [ex, ey] = p1, [qx, qy] = at(0.96);
  const ang = Math.atan2(ey - qy, ex - qx), L = 26;
  const headD = `M${ex - L * Math.cos(ang - 0.5)} ${ey - L * Math.sin(ang - 0.5)} L${ex} ${ey} L${ex - L * Math.cos(ang + 0.5)} ${ey - L * Math.sin(ang + 0.5)}`;
  return { d: `M${p0[0]} ${p0[1]} Q${cx} ${cy} ${p1[0]} ${p1[1]}`, len, at, mid: at(0.5), headD };
}

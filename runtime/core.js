// Deterministic animation primitives. Every visual property in this runtime is computed
// from a single number — the current time t in seconds — never from wall-clock timers,
// CSS transitions, or requestAnimationFrame deltas. That is what lets the renderer seek
// to any frame and screenshot it with zero drift (see pipeline/render.py).

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, p) => a + (b - a) * p;

export const ease = {
  linear: (x) => x,
  outCubic: (x) => 1 - (1 - x) ** 3,
  inCubic: (x) => x ** 3,
  inOutCubic: (x) => (x < 0.5 ? 4 * x ** 3 : 1 - (-2 * x + 2) ** 3 / 2),
  outExpo: (x) => (x >= 1 ? 1 : 1 - 2 ** (-10 * x)),
  inOutSine: (x) => -(Math.cos(Math.PI * x) - 1) / 2,
};

// Eased 0..1 progress of a tween that starts at `start` and lasts `dur`.
export function prog(t, start, dur, e = ease.outCubic) {
  if (dur <= 0) return t >= start ? 1 : 0;
  return e(clamp((t - start) / dur));
}

// Analytic damped spring (0 → 1 with a small overshoot). Closed form, so it is a pure
// function of t like everything else — no integration state to carry between frames.
export function spring(t, start, { stiffness = 180, damping = 16 } = {}) {
  const tau = t - start;
  if (tau <= 0) return 0;
  const w0 = Math.sqrt(stiffness);
  const zeta = damping / (2 * w0);
  if (zeta >= 1) return 1 - Math.exp(-w0 * tau) * (1 + w0 * tau);
  const wd = w0 * Math.sqrt(1 - zeta * zeta);
  return 1 - Math.exp(-zeta * w0 * tau) * (Math.cos(wd * tau) + ((zeta * w0) / wd) * Math.sin(wd * tau));
}

// Envelope for a "hold" state: rises over `rise`, holds until `end`, falls over `fall`.
export function envelope(t, start, end, rise = 0.25, fall = 0.4) {
  if (t < start) return 0;
  const up = prog(t, start, rise);
  const down = t > end ? 1 - prog(t, end, fall, ease.inOutCubic) : 1;
  return up * down;
}

// The most recent event (sorted by .t) at or before t, or null.
export function latest(events, t) {
  let hit = null;
  for (const ev of events) {
    if (ev.t <= t) hit = ev;
    else break;
  }
  return hit;
}

// ---- colour -------------------------------------------------------------------------
export const TONES = {
  ink: [232, 239, 240],
  ink2: [169, 189, 194],
  muted: [111, 135, 142],
  panel: [22, 38, 44],
  edge: [39, 64, 73],
  wire: [44, 69, 78],
  signal: [255, 178, 62],
  ok: [107, 221, 168],
  fail: [255, 111, 97],
  ground: [17, 34, 42],
};

export const tone = (name) => TONES[name] || TONES.signal;
export const mix = (a, b, p) => a.map((v, i) => Math.round(lerp(v, b[i], p)));
export const rgb = (c, a = 1) => (a >= 1 ? `rgb(${c[0]},${c[1]},${c[2]})` : `rgba(${c[0]},${c[1]},${c[2]},${a})`);

// ---- DOM ----------------------------------------------------------------------------
export function el(tag, cls, parent, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  if (parent) parent.appendChild(node);
  return node;
}

const SVG_NS = "http://www.w3.org/2000/svg";
export function svg(tag, attrs = {}, parent) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

// Style writes only when the value actually changed — keeps per-frame seeks cheap.
export function css(node, props) {
  const cache = (node.__css ||= {});
  for (const [k, v] of Object.entries(props)) {
    if (cache[k] !== v) {
      node.style.setProperty(k, v);
      cache[k] = v;
    }
  }
}

// Words entering one by one, used by headings and titles.
export function splitWords(node, text) {
  node.textContent = "";
  return text.split(/\s+/).filter(Boolean).map((w, i, all) => {
    const span = el("span", "word", node, w);
    if (i < all.length - 1) node.appendChild(document.createTextNode(" "));
    return span;
  });
}

export function wordsIn(words, t, start, stagger = 0.06, rise = 38) {
  words.forEach((w, i) => {
    const s = spring(t, start + i * stagger, { stiffness: 200, damping: 20 });
    css(w, {
      opacity: String(clamp(s * 1.4)),
      transform: `translateY(${((1 - s) * rise).toFixed(2)}px)`,
    });
  });
}

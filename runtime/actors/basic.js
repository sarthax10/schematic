// The non-character actors. Each factory returns { el, aspect?, update(t), highlight?(k, rgb) }.
// The engine owns position/scale/opacity/entrances; actors only animate their own insides
// (a counter counting, a jar's ticket count, a node's tone) from their `_states` events.
import { clamp, css, ease, el, latest, lerp, mix, prog, rgb, spring, tone, TONES } from "../core.js";
import { icon } from "../icons.js";
import { highlightLine } from "../highlight.js";
import { PROPS } from "../props.js";

const states = (spec) => [...(spec._states || [])].sort((a, b) => a.t - b.t);

// Merge every state event up to t into one object (later keys win).
function stateAt(events, t, base = {}) {
  const out = { ...base };
  for (const e of events) {
    if (e.t > t) break;
    Object.assign(out, e);
  }
  return out;
}

// ---- text -------------------------------------------------------------------------------
const TEXT_STYLES = {
  display: "font-size:168px;font-weight:800;letter-spacing:-0.04em;line-height:0.95",
  title: "font-size:88px;font-weight:740;letter-spacing:-0.026em;line-height:1.02",
  body: "font-size:56px;font-weight:560;letter-spacing:-0.01em;line-height:1.16",
  label: "font-size:44px;font-weight:650;letter-spacing:-0.01em;line-height:1.1",
  mono: "font-family:var(--mono);font-size:40px;font-weight:500;line-height:1.3",
  number: "font-size:220px;font-weight:800;letter-spacing:-0.05em;line-height:0.9;font-variant-numeric:tabular-nums",
};

function renderMarkup(node, text) {
  node.innerHTML = "";
  const words = [];
  const parts = String(text).split(/(\*\*[^*]+\*\*)/);
  for (const part of parts) {
    if (!part) continue;
    const isTerm = part.startsWith("**");
    const clean = isTerm ? part.slice(2, -2) : part;
    const host = isTerm ? el("span", "term", node) : node;
    clean.split(/(\s+)/).forEach((w) => {
      if (!w) return;
      if (/^\s+$/.test(w)) host.appendChild(document.createTextNode(" "));
      else words.push(el("span", "word", host, w));
    });
  }
  return { words, terms: [...node.querySelectorAll(".term")] };
}

export function text(spec) {
  const root = el("div", "a-text");
  root.style.cssText = TEXT_STYLES[spec.style || "title"] + `;text-align:${spec.align || "center"}`;
  if (spec.tone) root.style.color = rgb(tone(spec.tone));
  const versions = [{ t: -1, text: spec.text }, ...states(spec).filter((s) => s.text != null)];
  let shown = null, parts = null;
  const enterT = spec._enterT ?? -1;
  const style = spec._enterStyle || "words";
  return {
    el: root,
    update(t) {
      const v = latest(versions, t);
      const vi = versions.indexOf(v);
      // Swap: the old text sinks out, the new one rises in, crossing at the event time.
      const next = versions[vi + 1];
      const leaving = next && t > next.t - 0.2 ? prog(t, next.t - 0.2, 0.2, ease.inCubic) : 0;
      if (shown !== v) {
        parts = renderMarkup(root, v.text);
        shown = v;
      }
      const startT = vi === 0 ? enterT : v.t;
      parts.words.forEach((w, i) => {
        let p = 1;
        if (style === "type" && vi === 0) p = t >= startT + i * 0.07 ? 1 : 0;
        else p = spring(t, startT + i * 0.055, { stiffness: 210, damping: 20 });
        css(w, {
          opacity: String(clamp(p * 1.5 * (1 - leaving)).toFixed(3)),
          transform: `translateY(${((1 - p) * 0.4 + leaving * -0.3).toFixed(3)}em)`,
        });
      });
      const termT = startT + parts.words.length * 0.055 + 0.25;
      parts.terms.forEach((term) => css(term, { "background-size": `${(prog(t, termT, 0.45, ease.inOutCubic) * 100).toFixed(1)}% 38%` }));
    },
  };
}

// ---- prop -------------------------------------------------------------------------------
export function prop(spec) {
  const def = PROPS[spec.prop] || PROPS.box;
  const root = el("div", "a-prop");
  root.innerHTML = `<svg viewBox="0 0 200 ${def.h}" width="100%" height="100%" style="overflow:visible">${def.svg()}</svg>`;
  const svgEl = root.firstChild;
  const ev = states(spec);
  return {
    el: root,
    aspect: def.h / 200,
    update(t) {
      if (def.tick) def.tick(t, svgEl, stateAt(ev, t, spec.state || {}));
    },
  };
}

// ---- node (tech component card) ----------------------------------------------------------
export function node(spec) {
  const root = el("div", "a-node");
  root.innerHTML = icon(spec.icon || "server");
  const label = spec.label ? el("div", "label", root, spec.label) : null;
  const svgIcon = root.querySelector("svg");
  const ev = states(spec);
  let hl = 0, hlTone = TONES.signal;
  return {
    el: root,
    aspect: spec.label ? 0.8 : 0.64,
    highlight(k, c) { hl = k; hlTone = c; },
    update(t) {
      const st = stateAt(ev, t, { tone: spec.tone || null });
      const last = latest(ev.filter((e) => e.tone !== undefined), t);
      const k = st.tone ? (last ? prog(t, last.t, 0.35) : 1) : 0;
      const base = st.tone ? tone(st.tone) : null;
      const c = hl > k ? hlTone : base || hlTone;
      const amt = Math.max(hl, k);
      css(root, { "border-color": amt > 0.01 ? rgb(c, 0.25 + 0.75 * amt) : "var(--panel-edge)" });
      css(svgIcon, { color: amt > 0.01 ? rgb(c) : "var(--ink-2)" });
      css(root, { "box-shadow": `0 0 ${(50 * amt).toFixed(1)}px ${rgb(c, 0.3 * amt)}` });
      if (label && st.label && label.textContent !== st.label) label.textContent = st.label;
    },
  };
}

// ---- icon glyph --------------------------------------------------------------------------
export function glyph(spec) {
  const root = el("div", "a-glyph");
  root.innerHTML = icon(spec.icon || "info");
  root.style.color = rgb(tone(spec.tone || "ink2"));
  return { el: root, aspect: 1, update() {} };
}

// ---- shape -------------------------------------------------------------------------------
export function shape(spec) {
  const kind = spec.shape || "rect";
  const root = el("div", `a-shape s-${kind}`);
  const fill = spec.tone ? rgb(tone(spec.tone), kind === "zone" ? 0.08 : 1) : null;
  if (fill && kind !== "ring") root.style.background = fill;
  if (spec.tone && (kind === "ring" || kind === "zone")) root.style.borderColor = rgb(tone(spec.tone), 0.7);
  if (spec.label) el("div", "shape-label", root, spec.label);
  const aspect = { circle: 1, ring: 1, ground: 0.09, pill: 0.34, zone: spec.aspect || 0.8, rect: spec.aspect || 0.6 }[kind] ?? 0.6;
  return { el: root, aspect: spec.aspect || aspect, update() {} };
}

// ---- counter -----------------------------------------------------------------------------
export function counter(spec) {
  const root = el("div", "a-counter");
  root.style.cssText = TEXT_STYLES[spec.style || "number"];
  if (spec.tone) root.style.color = rgb(tone(spec.tone));
  const num = el("span", "", root);
  const unit = spec.unit ? el("span", "unit", root, spec.unit) : null;
  const counts = [{ t: -1, to: spec.value ?? 0, dur: 0 }, ...states(spec).filter((s) => s.to != null)];
  const fmt = (v) => (spec.decimals ? v.toFixed(spec.decimals) : Math.round(v).toLocaleString("en-US"));
  return {
    el: root,
    update(t) {
      const c = latest(counts, t);
      const i = counts.indexOf(c);
      const from = i > 0 ? counts[i - 1].to : c.to;
      const v = lerp(from, c.to, prog(t, c.t, c.dur ?? 1.2, ease.outExpo));
      const s = fmt(v);
      if (num.textContent !== s) num.textContent = s;
      if (unit) unit.style.opacity = "1";
    },
  };
}

// ---- meter (fill gauge) ------------------------------------------------------------------
export function meter(spec) {
  const root = el("div", "a-meter");
  const track = el("div", "track", root);
  const fill = el("div", "fill", track);
  const label = spec.label ? el("div", "m-label", root, spec.label) : null;
  const vals = [{ t: -1, value: spec.value ?? 0 }, ...states(spec).filter((s) => s.value != null)];
  return {
    el: root,
    aspect: 0.16 + (label ? 0.1 : 0),
    update(t) {
      const c = latest(vals, t);
      const i = vals.indexOf(c);
      const from = i > 0 ? vals[i - 1].value : c.value;
      const v = clamp(lerp(from, c.value, prog(t, c.t, 0.6, ease.inOutCubic)));
      const col = spec.tone ? tone(spec.tone) : v > 0.85 ? TONES.fail : v > 0.6 ? TONES.signal : TONES.ok;
      css(fill, { width: `${(v * 100).toFixed(2)}%`, background: rgb(col) });
    },
  };
}

// ---- bars (comparison chart) ---------------------------------------------------------------
export function bars(spec) {
  const root = el("div", "a-bars");
  const items = spec.items || [];
  const max = Math.max(...items.map((b) => b.value), 1e-9);
  const rows = items.map((b) => {
    const row = el("div", "bar", root);
    const head = el("div", "bar-head", row);
    el("span", "", head, b.label);
    el("span", "v", head, b.display ?? String(b.value));
    const f = el("div", "bar-fill", el("div", "bar-track", row));
    f.style.background = rgb(tone(b.tone || "ink2"));
    return { f, frac: b.value / max };
  });
  const t0 = spec._enterT ?? 0;
  return {
    el: root,
    update(t) {
      rows.forEach((r, i) => css(r.f, { width: `${(Math.max(r.frac, 0.015) * 100 * prog(t, t0 + 0.3 + i * 0.3, 0.9, ease.inOutCubic)).toFixed(2)}%` }));
    },
  };
}

// ---- list (key points) ---------------------------------------------------------------------
const LIST_ICON = { ok: "check", fail: "cross", signal: "alert", sky: "info", lavender: "info", ink2: "info" };
export function list(spec) {
  const root = el("div", "a-list");
  const reveals = new Map(states(spec).filter((s) => s.index != null).map((s) => [s.index, s.t]));
  const t0 = spec._enterT ?? 0;
  const rows = (spec.items || []).map((it, i) => {
    const row = el("div", "li", root);
    const ic = el("div", "li-icon", row);
    ic.innerHTML = icon(it.icon || LIST_ICON[it.tone || "ok"] || "check");
    ic.style.color = rgb(tone(it.tone || "ok"));
    el("div", "li-text", row, it.text);
    return { row, ic, at: reveals.get(i) ?? t0 + 0.2 + i * 0.5 };
  });
  return {
    el: root,
    update(t) {
      rows.forEach((r) => {
        const p = prog(t, r.at, 0.45);
        css(r.row, { opacity: String(p.toFixed(3)), transform: `translateX(${((1 - p) * -40).toFixed(1)}px)` });
        css(r.ic, { transform: `scale(${clamp(spring(t, r.at + 0.05, { stiffness: 260, damping: 15 }), 0, 1.2).toFixed(4)})` });
      });
    },
  };
}

// ---- code ------------------------------------------------------------------------------
export function code(spec) {
  const LINE_H = 60;
  const lines = Array.isArray(spec.code) ? spec.code : String(spec.code || "").split("\n");
  const root = el("div", "a-code");
  if (spec.file) el("div", "code-file", root, spec.file);
  const box = el("div", "code-lines", root);
  const hl = el("div", "code-hl", box);
  const CW = 34 * 0.6; // JetBrains Mono advance width is 0.6em
  const rows = lines.map((src, i) => {
    const row = el("div", "code-line", box);
    const s = el("span", "src", row);
    s.innerHTML = highlightLine(src) || " ";
    return { s, len: src.length };
  });
  const t0 = (spec._enterT ?? 0) + 0.2;
  const total = rows.reduce((a, r) => a + Math.max(r.len, 4), 0);
  const cps = total / Math.min(2.2, Math.max(0.8, total / 60));
  let acc = t0;
  rows.forEach((r) => { r.t0 = acc; r.t1 = acc + r.len / cps; acc = r.t1 + 0.04; });
  const marks = states(spec).filter((s) => Array.isArray(s.lines)).map((s) => ({ t: s.t, a: s.lines[0], b: s.lines[s.lines.length - 1] }));
  return {
    el: root,
    update(t) {
      rows.forEach((r) => {
        const n = r.len ? Math.floor(clamp((t - r.t0) / (r.t1 - r.t0)) * r.len) : 0;
        css(r.s, { "clip-path": `inset(-10px ${Math.max(0, (r.len - n) * CW).toFixed(1)}px -10px 0)` });
      });
      const cur = latest(marks, t);
      if (!cur) { css(hl, { opacity: "0" }); rows.forEach((r) => css(r.s, { opacity: "1" })); return; }
      const idx = marks.indexOf(cur);
      const prev = marks[idx - 1];
      const k = prev ? spring(t, cur.t, { stiffness: 220, damping: 24 }) : 1;
      const y = lerp(prev ? prev.a - 1 : cur.a - 1, cur.a - 1, k) * LINE_H;
      const h = lerp(prev ? prev.b - prev.a + 1 : cur.b - cur.a + 1, cur.b - cur.a + 1, k) * LINE_H;
      css(hl, { opacity: String((prev ? 1 : prog(t, cur.t, 0.25)).toFixed(3)), transform: `translateY(${y.toFixed(1)}px)`, height: `${h.toFixed(1)}px` });
      const dim = prog(t, cur.t, 0.3);
      rows.forEach((r, i) => css(r.s, { opacity: i + 1 >= cur.a && i + 1 <= cur.b ? "1" : String((1 - 0.6 * dim).toFixed(3)) }));
    },
  };
}

export { stateAt };

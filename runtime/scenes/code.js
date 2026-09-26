// Code scene: the snippet types itself in, then `highlight {lines:[a,b], tone?}` steps
// slide a marker bar between line ranges while the other lines dim back.
import { clamp, css, el, ease, latest, lerp, prog, spring } from "../core.js";
import { icon } from "../icons.js";
import { highlightLine } from "../highlight.js";

const LINE_H = 66;

export function build(stage, scene) {
  const { file = "", code = "" } = scene.data;
  const lines = (Array.isArray(code) ? code : code.split("\n"));
  const panel = el("div", "code-panel", stage);
  if (file) {
    const f = el("div", "code-file", panel);
    f.innerHTML = icon("function");
    el("span", "", f, file);
  }
  const box = el("div", "code-lines", panel);
  const hl = el("div", "code-hl", box);
  const cursor = el("div", "code-cursor", box);

  const probe = el("span", "", box, "M".repeat(20));
  probe.style.cssText = "font: 500 36px var(--mono); position:absolute; visibility:hidden; white-space:pre";
  const cw = probe.getBoundingClientRect().width / 20;
  probe.remove();

  const rows = lines.map((src, i) => {
    const row = el("div", "code-line", box);
    el("span", "ln", row, String(i + 1));
    const s = el("span", "src", row);
    s.innerHTML = highlightLine(src) || " ";
    return { row, s, len: src.length };
  });

  // Typing speed adapts so the whole snippet is in by ~40% of the scene (max 2.6s).
  const total = rows.reduce((a, r) => a + Math.max(r.len, 4), 0);
  const typeDur = Math.min(2.6, scene.duration * 0.4);
  const cps = total / typeDur;
  let acc = 0.4;
  for (const r of rows) {
    r.t0 = acc;
    r.t1 = acc + r.len / cps;
    acc = r.t1 + 0.05;
  }
  const typedEnd = acc;

  const marks = (scene.steps || [])
    .filter((s) => s.action === "highlight" && Array.isArray(s.lines))
    .map((s) => ({ t: s.t, a: s.lines[0], b: s.lines[s.lines.length - 1] }))
    .sort((x, y) => x.t - y.t);

  return function update(t) {
    let cursorAt = null;
    rows.forEach((r, i) => {
      const n = r.len ? Math.floor(clamp((t - r.t0) / (r.t1 - r.t0)) * r.len) : 0;
      css(r.s, { "clip-path": `inset(-10px ${Math.max(0, (r.len - n) * cw).toFixed(1)}px -10px 0)` });
      css(r.row, { opacity: t >= r.t0 - 0.02 ? "1" : "0" });
      if (t >= r.t0 && t < r.t1 + 0.05) cursorAt = { i, n };
    });
    const blinkOn = Math.floor(t * 2.4) % 2 === 0;
    if (!cursorAt && t >= typedEnd) cursorAt = { i: rows.length - 1, n: rows[rows.length - 1].len };
    css(cursor, {
      opacity: cursorAt && (t < typedEnd || blinkOn) && t < typedEnd + 1.2 ? "1" : "0",
      transform: cursorAt ? `translate(${(92 + cursorAt.n * cw + 4).toFixed(1)}px, ${cursorAt.i * LINE_H + 9}px)` : "none",
    });

    const idx = marks.findIndex((m) => m.t > t);
    const cur = latest(marks, t);
    if (!cur) {
      css(hl, { opacity: "0" });
      rows.forEach((r) => css(r.s, { opacity: "1" }));
      return;
    }
    const prev = marks[(idx === -1 ? marks.length : idx) - 2];
    const k = spring(t, cur.t, { stiffness: 220, damping: 24 });
    const y = lerp(prev ? prev.a - 1 : cur.a - 1, cur.a - 1, prev ? k : 1) * LINE_H;
    const h = lerp(prev ? prev.b - prev.a + 1 : cur.b - cur.a + 1, cur.b - cur.a + 1, prev ? k : 1) * LINE_H;
    css(hl, {
      opacity: String((prev ? 1 : prog(t, cur.t, 0.25)).toFixed(3)),
      transform: `translateY(${y.toFixed(1)}px)`,
      height: `${h.toFixed(1)}px`,
    });
    const dim = prog(t, cur.t, 0.3, ease.outCubic);
    rows.forEach((r, i) => {
      const on = i + 1 >= cur.a && i + 1 <= cur.b;
      css(r.s, { opacity: on ? "1" : String((1 - 0.6 * dim).toFixed(3)) });
    });
  };
}

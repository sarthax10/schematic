// Compare scene: two columns, `data.left/right: {name, icon, points:[...], tone?}`.
// `reveal {side: "left"|"right"}` cues bring each column in when it's first mentioned.
import { clamp, css, el, prog, rgb, spring, tone } from "../core.js";
import { icon } from "../icons.js";

export function build(stage, scene) {
  const cues = new Map((scene.steps || []).filter((s) => s.action === "reveal").map((s) => [s.side, s.t]));
  const grid = el("div", "cols", stage);
  const cols = ["left", "right"].map((side, ci) => {
    const d = scene.data[side] || { name: side, points: [] };
    const col = el("div", "col", grid);
    const head = el("div", "col-head", col);
    head.innerHTML = icon(d.icon || "server");
    head.querySelector("svg").style.color = rgb(tone(d.tone || "ink2"));
    el("div", "col-name", head, d.name);
    const pts = (d.points || []).map((p) => el("div", "col-pt", col, p));
    return { col, pts, t0: cues.get(side) ?? 0.3 + ci * 0.9 };
  });

  return function update(t) {
    for (const c of cols) {
      const s = spring(t, c.t0, { stiffness: 170, damping: 18 });
      css(c.col, { opacity: String(clamp(s * 1.5).toFixed(3)), transform: `translateY(${((1 - s) * 60).toFixed(1)}px)` });
      c.pts.forEach((p, i) => css(p, { opacity: String(prog(t, c.t0 + 0.3 + i * 0.18, 0.35).toFixed(3)) }));
    }
  };
}

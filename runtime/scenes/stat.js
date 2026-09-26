// Stat scene: one big number that counts up, a plain-language label, and optional
// comparison bars (`data.bars: [{label, value, tone?, display?}]`) grown to scale — the
// visual contrast between bar lengths is the point, so bars are linear, never log.
// A `bars` step (or the default at 1.0s) starts the bars growing.
import { clamp, css, el, ease, prog, rgb, spring, tone } from "../core.js";

export function build(stage, scene) {
  const { value = 0, unit = "", label = "", bars = [], decimals = 0 } = scene.data;
  const wrap = el("div", "stat-value", stage);
  const num = el("div", "stat-num", wrap, "0");
  if (unit) el("div", "stat-unit", wrap, unit);
  const lab = el("div", "stat-label", stage, label);

  const barsAt = (scene.steps || []).find((s) => s.action === "bars")?.t ?? 1.0;
  const max = Math.max(...bars.map((b) => b.value), 1e-9);
  const B = bars.map((b) => {
    const row = el("div", "bar", null);
    const head = el("div", "bar-head", row);
    el("span", "", head, b.label);
    el("span", "v", head, b.display ?? `${b.value}${unit ? " " + unit : ""}`);
    const fill = el("div", "bar-fill", el("div", "bar-track", row));
    fill.style.background = rgb(tone(b.tone || "ink2"));
    return { row, fill, frac: b.value / max };
  });
  if (B.length) {
    const box = el("div", "bars", stage);
    B.forEach((b) => box.appendChild(b.row));
  }

  return function update(t) {
    const p = prog(t, 0.2, 1.3, ease.outExpo);
    num.textContent = (value * p).toFixed(decimals);
    const s = spring(t, 0.15, { stiffness: 150, damping: 17 });
    css(wrap, { opacity: String(clamp(s * 1.5).toFixed(3)), transform: `translateY(${((1 - s) * 50).toFixed(1)}px)` });
    css(lab, { opacity: String(prog(t, 0.55, 0.4).toFixed(3)), transform: `translateY(${((1 - prog(t, 0.55, 0.5)) * 24).toFixed(1)}px)` });
    B.forEach((b, i) => {
      const t0 = barsAt + i * 0.35;
      css(b.row, { opacity: String(prog(t, t0 - 0.1, 0.3).toFixed(3)) });
      css(b.fill, { width: `${(Math.max(b.frac, 0.012) * 100 * prog(t, t0, 0.9, ease.inOutCubic)).toFixed(2)}%` });
    });
  };
}

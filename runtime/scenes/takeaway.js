// Takeaway / key-points scene: `data.items: [{text, tone?: ok|fail|signal|ink2}]`. Each
// item enters on its own `reveal {index}` cue (synced to when it's said), falling back to
// an even stagger. The tone picks the icon: ok → check, fail → cross, signal → alert.
import { clamp, css, el, prog, rgb, spring, tone } from "../core.js";
import { icon } from "../icons.js";

const ICON_FOR = { ok: "check", fail: "cross", signal: "alert", ink2: "info" };

export function build(stage, scene) {
  const items = scene.data.items || [];
  const cues = new Map((scene.steps || []).filter((s) => s.action === "reveal").map((s) => [s.index, s.t]));
  const box = el("div", "items", stage);
  const R = items.map((it, i) => {
    const row = el("div", "item", box);
    const ic = el("div", "item-icon", row);
    ic.innerHTML = icon(ICON_FOR[it.tone] || "check");
    ic.style.color = rgb(tone(it.tone || "ok"));
    el("div", "item-text", row, it.text);
    return { row, ic, t0: cues.get(i) ?? 0.35 + i * 0.55 };
  });

  return function update(t) {
    for (const r of R) {
      const p = prog(t, r.t0, 0.45);
      const s = spring(t, r.t0 + 0.05, { stiffness: 260, damping: 15 });
      css(r.row, { opacity: String(p.toFixed(3)), transform: `translateX(${((1 - p) * -36).toFixed(1)}px)` });
      css(r.ic, { transform: `scale(${clamp(s, 0, 1.2).toFixed(4)})` });
    }
  };
}

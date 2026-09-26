// Title / hook scene: a big headline that rises in word by word, over a small hero strip of
// the topic's own components (`data.icons`) with a packet looping between them — so even
// the opening frame shows the subject, not just words about it.
import { clamp, css, ease, el, prog, spring, splitWords, svg, wordsIn } from "../core.js";
import { icon } from "../icons.js";

export function build(stage, scene, root) {
  const { kicker = "", title = "", icons = [] } = scene.data;
  const k = kicker ? el("div", "title-kicker", root, kicker) : null;
  const words = splitWords(el("div", "title-main", root), title);

  const hero = el("div", "title-hero", root);
  const n = icons.length;
  const gap = n > 1 ? Math.min(330, 760 / (n - 1)) : 0;
  const x0 = 480 - (gap * (n - 1)) / 2;
  const line = svg("svg", { width: 960, height: 300, viewBox: "0 0 960 300", style: "position:absolute;inset:0;overflow:visible" }, hero);
  const wire = svg("path", { d: `M${x0} 150 H${x0 + gap * (n - 1)}`, stroke: "#2c454e", "stroke-width": 4, fill: "none", "stroke-linecap": "round" }, line);
  const wireLen = Math.max(1, gap * (n - 1));
  const dot = svg("circle", { r: 11, fill: "#ffb23e", cy: 150 }, line);
  const tiles = icons.map((name, i) => {
    const tile = el("div", "node", hero);
    tile.innerHTML = icon(name);
    css(tile, { left: `${x0 + gap * i}px`, top: "150px", width: "180px", height: "180px", margin: "-90px 0 0 -90px" });
    return tile;
  });
  stage.remove(); // the title composes directly on the scene, not the diagram stage

  return function update(t) {
    if (k) css(k, { opacity: String(prog(t, 0.1, 0.4).toFixed(3)) });
    wordsIn(words, t, 0.2, 0.075, 70);
    const heroT = 0.4 + words.length * 0.075;
    tiles.forEach((tile, i) => {
      const s = spring(t, heroT + i * 0.12, { stiffness: 200, damping: 16 });
      css(tile, { opacity: String(clamp(s * 1.6).toFixed(3)), transform: `scale(${(0.7 + 0.3 * s).toFixed(4)})` });
    });
    const wp = prog(t, heroT + 0.2, 0.6, ease.inOutCubic);
    css(wire, { "stroke-dasharray": `${wireLen}`, "stroke-dashoffset": `${(wireLen * (1 - wp)).toFixed(1)}` });
    // The packet shuttles left→right on a 1.6s loop once the wire is drawn.
    const loopT = t - (heroT + 0.9);
    const on = loopT > 0 && n > 1;
    const phase = on ? ease.inOutCubic((loopT % 1.6) / 1.6) : 0;
    dot.setAttribute("cx", String(x0 + wireLen * phase));
    css(dot, { opacity: on ? String(Math.sin(Math.PI * ((loopT % 1.6) / 1.6)).toFixed(3)) : "0" });
  };
}

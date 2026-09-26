// Architecture / request-flow scene. The plan names nodes and edges only — never pixel
// positions — and this scene lays them out itself as top-to-bottom layers (a vertical frame
// reads best as "request flows downward"). Steps drive everything that happens:
//   reveal    {target}                    node springs in (+ its edges draw on)
//   highlight {target, tone?, hold?}      border/icon glow in a tone
//   fail      {target}                    coral highlight + a short shake
//   packet    {path:[ids], tone?, hop?}   a glowing packet travels the path hop by hop
//   label     {target, text, tone?}       a pill badge on the node ("HIT", "40 ms")
import { clamp, css, ease, envelope, latest, mix, prog, rgb, spring, svg, tone, TONES, el } from "../core.js";
import { icon } from "../icons.js";

const W = 960, H = 940, NODE_W = 282, NODE_H = 226;

function layout(nodes, edges) {
  const layer = new Map(nodes.map((n) => [n.id, n.layer ?? null]));
  const incoming = new Map(nodes.map((n) => [n.id, []]));
  for (const e of edges) incoming.get(e.to)?.push(e.from);
  // Longest path from any source; explicit `layer` wins. Guarded against cycles.
  const depth = (id, seen = new Set()) => {
    if (layer.get(id) != null) return layer.get(id);
    if (seen.has(id)) return 0;
    seen.add(id);
    const parents = incoming.get(id) || [];
    const d = parents.length ? Math.max(...parents.map((p) => depth(p, seen) + 1)) : 0;
    return d;
  };
  const rows = [];
  for (const n of nodes) {
    const d = depth(n.id);
    (rows[d] ||= []).push(n);
  }
  const filled = rows.filter(Boolean);
  const gapY = filled.length > 1 ? Math.min(340, (H - NODE_H - 20) / (filled.length - 1)) : 0;
  const y0 = (H - gapY * (filled.length - 1)) / 2;
  const pos = new Map();
  filled.forEach((row, r) => {
    const gapX = row.length > 1 ? Math.min(340, (W - NODE_W) / (row.length - 1)) : 0;
    const x0 = W / 2 - (gapX * (row.length - 1)) / 2;
    row.forEach((n, i) => pos.set(n.id, { x: x0 + gapX * i, y: y0 + gapY * r, row: r }));
  });
  return pos;
}

function edgePath(a, b) {
  if (a.row === b.row) {
    const dir = b.x > a.x ? 1 : -1;
    const x1 = a.x + (dir * NODE_W) / 2, x2 = b.x - (dir * NODE_W) / 2;
    return `M${x1} ${a.y} L${x2} ${b.y}`;
  }
  const down = b.y > a.y ? 1 : -1;
  const y1 = a.y + (down * NODE_H) / 2, y2 = b.y - (down * NODE_H) / 2;
  const my = (y1 + y2) / 2;
  return `M${a.x} ${y1} C${a.x} ${my} ${b.x} ${my} ${b.x} ${y2}`;
}

export function build(stage, scene) {
  const { nodes = [], edges = [], carry = false } = scene.data;
  const steps = [...(scene.steps || [])].sort((a, b) => a.t - b.t);
  const pos = layout(nodes, edges);

  const wires = svg("svg", { class: "arch-wires", viewBox: `0 0 ${W} ${H}`, width: W, height: H }, stage);
  const defs = svg("defs", {}, wires);
  const blur = svg("filter", { id: `glow-${scene.index}`, x: "-2", y: "-2", width: "5", height: "5" }, defs);
  svg("feGaussianBlur", { stdDeviation: "9" }, blur);

  // ---- nodes -------------------------------------------------------------------------
  const revealAt = new Map();
  steps.filter((s) => s.action === "reveal").forEach((s) => {
    if (!revealAt.has(s.target)) revealAt.set(s.target, s.t);
  });
  let auto = 0;
  const N = new Map();
  for (const n of nodes) {
    const p = pos.get(n.id);
    const node = el("div", "node", stage);
    node.innerHTML = icon(n.kind);
    el("div", "label", node, n.label);
    const ring = el("div", "ring", node);
    const badge = el("div", "badge", node);
    css(node, { left: `${p.x}px`, top: `${p.y}px` });
    const t0 = revealAt.has(n.id) ? revealAt.get(n.id) : carry ? -10 : 0.3 + auto++ * 0.14;
    N.set(n.id, { n, p, node, ring, badge, svgIcon: node.querySelector("svg"), revealT: t0, hl: [], labels: [], arrivals: [], fails: [] });
  }

  // ---- edges -------------------------------------------------------------------------
  const E = [];
  const pathFor = new Map();
  for (const e of edges) {
    const a = N.get(e.from), b = N.get(e.to);
    if (!a || !b) continue;
    const path = svg("path", { d: edgePath(a.p, b.p), fill: "none", "stroke-width": "4", "stroke-linecap": "round" }, wires);
    const len = path.getTotalLength();
    const rec = { e, path, len, revealT: Math.max(a.revealT, b.revealT) + 0.12, heat: [] };
    if (e.label) {
      const mid = path.getPointAtLength(len / 2);
      rec.labelEl = svg("text", { class: "edge-label", x: mid.x + 16, y: mid.y + 9 }, wires);
      rec.labelEl.textContent = e.label;
    }
    E.push(rec);
    pathFor.set(`${e.from}>${e.to}`, { rec, reverse: false });
    pathFor.set(`${e.to}>${e.from}`, { rec, reverse: true });
  }

  // ---- steps → per-node / per-edge event lists ---------------------------------------
  const packets = [];
  for (const s of steps) {
    const target = N.get(s.target);
    if (s.action === "highlight" && target) target.hl.push({ t: s.t, tone: s.tone || "signal", hold: s.hold });
    if (s.action === "fail" && target) {
      target.hl.push({ t: s.t, tone: "fail", hold: s.hold });
      target.fails.push(s.t);
    }
    if (s.action === "label" && target) target.labels.push({ t: s.t, text: s.text, tone: s.tone || "signal" });
    if (s.action === "packet" && Array.isArray(s.path) && s.path.length > 1) {
      const hop = s.hop || 0.55;
      const hops = [];
      for (let i = 0; i < s.path.length - 1; i++) {
        const key = `${s.path[i]}>${s.path[i + 1]}`;
        let entry = pathFor.get(key);
        if (!entry) {
          // No declared edge: travel a straight ghost line between the two centres.
          const a = N.get(s.path[i])?.p, b = N.get(s.path[i + 1])?.p;
          if (!a || !b) continue;
          const ghost = svg("path", { d: `M${a.x} ${a.y} L${b.x} ${b.y}`, fill: "none", stroke: "none" }, wires);
          entry = { rec: { path: ghost, len: ghost.getTotalLength(), heat: [] }, reverse: false };
        }
        const t0 = s.t + i * hop;
        hops.push({ ...entry, t0, t1: t0 + hop });
        entry.rec.heat.push({ t0, t1: t0 + hop, tone: s.tone || "signal" });
        N.get(s.path[i + 1])?.arrivals.push({ t: t0 + hop, tone: s.tone || "signal" });
      }
      if (!hops.length) continue;
      const g = svg("g", { opacity: "0" }, wires);
      const col = rgb(tone(s.tone || "signal"));
      const halo = svg("circle", { r: "24", fill: col, opacity: "0.45", filter: `url(#glow-${scene.index})` }, g);
      const trail = [0.075, 0.05, 0.03].map((_, k) => svg("circle", { r: String(9 - k * 2.2), fill: col, opacity: String(0.5 - k * 0.14) }, g));
      const core = svg("circle", { r: "12", fill: col }, g);
      packets.push({ g, halo, core, trail, hops, start: s.t, end: hops[hops.length - 1].t1 });
    }
  }
  for (const v of N.values()) {
    v.hl.sort((a, b) => a.t - b.t);
    v.hl.forEach((h, i) => {
      const next = v.hl[i + 1];
      h.end = Math.min(h.t + (h.hold ?? 1.6), next ? next.t : Infinity);
    });
  }

  const pointAt = (hop, p) => {
    const d = hop.reverse ? hop.rec.len * (1 - p) : hop.rec.len * p;
    return hop.rec.path.getPointAtLength(clamp(d, 0, hop.rec.len));
  };

  return function update(t) {
    for (const v of N.values()) {
      const s = v.revealT < 0 ? 1 : spring(t, v.revealT, { stiffness: 190, damping: 17 });
      let shake = 0;
      for (const f of v.fails) {
        const d = t - f;
        if (d > 0 && d < 0.5) shake += Math.sin(d * 55) * 14 * (1 - d / 0.5);
      }
      css(v.node, {
        opacity: String(clamp(s * 1.6).toFixed(3)),
        transform: `translateX(${shake.toFixed(2)}px) scale(${(0.82 + 0.18 * s).toFixed(4)})`,
      });

      const h = latest(v.hl, t);
      const k = h ? envelope(t, h.t, h.end) : 0;
      const c = h ? tone(h.tone) : TONES.signal;
      css(v.node, {
        "border-color": rgb(mix(TONES.edge, c, k)),
        "box-shadow": `0 0 ${(60 * k).toFixed(1)}px ${rgb(c, 0.35 * k)}`,
        background: rgb(mix(TONES.panel, c, 0.08 * k)),
      });
      css(v.svgIcon, { color: rgb(mix(TONES.ink2, c, k)) });

      // Arrival ring: a quick outward ripple each time a packet lands here.
      const arr = latest(v.arrivals, t);
      const rp = arr ? (t - arr.t) / 0.55 : 2;
      css(v.ring, {
        opacity: rp < 1 ? String((0.8 * (1 - rp)).toFixed(3)) : "0",
        transform: `scale(${(1 + 0.16 * ease.outCubic(clamp(rp))).toFixed(4)})`,
        "border-color": arr ? rgb(tone(arr.tone)) : "transparent",
      });

      const lab = latest(v.labels, t);
      if (lab) {
        if (v.badge.textContent !== lab.text) v.badge.textContent = lab.text;
        const bs = spring(t, lab.t, { stiffness: 260, damping: 18 });
        css(v.badge, {
          opacity: String(clamp(bs * 2).toFixed(3)),
          transform: `scale(${(0.6 + 0.4 * bs).toFixed(4)})`,
          background: rgb(tone(lab.tone)),
        });
      } else css(v.badge, { opacity: "0" });
    }

    for (const e of E) {
      const p = prog(t, e.revealT, 0.45, ease.inOutCubic);
      let heat = 0, heatTone = "signal";
      for (const hz of e.heat) {
        const k = envelope(t, hz.t0, hz.t1, 0.12, 0.35);
        if (k > heat) { heat = k; heatTone = hz.tone; }
      }
      css(e.path, {
        "stroke-dasharray": `${e.len}`,
        "stroke-dashoffset": `${(e.len * (1 - p)).toFixed(2)}`,
        stroke: rgb(mix(TONES.wire, tone(heatTone), heat * 0.85)),
      });
      if (e.labelEl) css(e.labelEl, { opacity: String(prog(t, e.revealT + 0.3, 0.3).toFixed(3)) });
    }

    for (const pk of packets) {
      const alive = t >= pk.start && t <= pk.end + 0.25;
      css(pk.g, { opacity: alive ? String((prog(t, pk.start, 0.12) * (1 - prog(t, pk.end, 0.25))).toFixed(3)) : "0" });
      if (!alive) continue;
      const hop = pk.hops.find((h) => t < h.t1) || pk.hops[pk.hops.length - 1];
      const raw = clamp((t - hop.t0) / (hop.t1 - hop.t0));
      const p = ease.inOutCubic(raw);
      const at = pointAt(hop, p);
      pk.core.setAttribute("cx", at.x); pk.core.setAttribute("cy", at.y);
      pk.halo.setAttribute("cx", at.x); pk.halo.setAttribute("cy", at.y);
      pk.trail.forEach((c, k) => {
        const q = pointAt(hop, ease.inOutCubic(clamp(raw - (k + 1) * 0.06)));
        c.setAttribute("cx", q.x); c.setAttribute("cy", q.y);
      });
    }
  };
}

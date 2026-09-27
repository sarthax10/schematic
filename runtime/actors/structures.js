// Data-structure actors: ring buffer, array, stack/queue, binary search tree, hash map.
// Each is driven by `op` beats ({op: "write" | "read" | "push" | "insert" | "put" | ...}).
// Like everything in the runtime, state is a pure function of t: the op list is replayed
// into a sequence of snapshots at build time, and update(t) interpolates the transition
// into the latest snapshot. Colour follows the system: signal = the write / the thing
// moving, sky = reads, ok = found, fail = overwritten / missing.
import { clamp, css, ease, el, lerp, prog, rgb, spring, svg, tone, TONES } from "../core.js";

const OP_DUR = 0.8;
const opsOf = (spec) => [...(spec._states || [])].filter((s) => s.op).sort((a, b) => a.t - b.t);

function frame(w, h) {
  const root = el("div", "a-struct");
  const s = svg("svg", { viewBox: `0 0 ${w} ${h}`, width: "100%", height: "100%", style: "overflow:visible" }, root);
  return { root, s };
}
const TYPE_SCALE = 1.35; // structures are seen on a phone: every label is scaled up together
const txt = (parent, attrs, content, size = 34, mono = true) => {
  const t = svg("text", { "text-anchor": "middle", "dominant-baseline": "central", ...attrs }, parent);
  t.style.font = `${mono ? 600 : 700} ${Math.round(size * TYPE_SCALE)}px ${mono ? "var(--mono)" : "var(--display)"}`;
  t.style.fill = "var(--ink)";
  if (content != null) t.textContent = content;
  return t;
};
const box = (parent, attrs) => {
  const r = svg("rect", attrs, parent);
  r.style.fill = "var(--panel)";
  r.style.stroke = "var(--panel-edge)";
  r.style.strokeWidth = "5";
  return r;
};
// A pointer tag: pill + label + little triangle pointing at `dir` ("up" | "down" | "in").
function tag(parent, label, col) {
  const outer = svg("g", {}, parent);
  const g = svg("g", { transform: "scale(1.3)" }, outer);
  const w = Math.max(96, label.length * 22 + 36);
  const pill = svg("rect", { x: -w / 2, y: -24, width: w, height: 48, rx: 24 }, g);
  pill.style.fill = rgb(col);
  const tri = svg("path", { d: "M-12 -24 L0 -40 L12 -24 Z" }, g);
  tri.style.fill = rgb(col);
  const t = txt(g, { y: 1 }, label, 26, false);
  t.style.fill = "#10181b";
  return { g: outer, tri };
}
const place = (node, x, y, s = 1, rot = 0) =>
  node.setAttribute("transform", `translate(${x.toFixed(1)} ${y.toFixed(1)})${rot ? ` rotate(${rot.toFixed(1)})` : ""}${s !== 1 ? ` scale(${s.toFixed(3)})` : ""}`);
const glow = (rect, col, k) => {
  rect.style.stroke = k > 0.02 ? rgb(col, 0.35 + 0.65 * k) : "var(--panel-edge)";
  rect.style.filter = k > 0.02 ? `drop-shadow(0 0 ${(18 * k).toFixed(1)}px ${rgb(col, 0.6 * k)})` : "none";
};
// Index of the op in effect at t (-1 before the first) and its progress.
function current(ops, t) {
  let k = -1;
  for (let i = 0; i < ops.length; i++) if (ops[i].t <= t) k = i;
  return { k, p: k < 0 ? 1 : clamp((t - ops[k].t) / OP_DUR) };
}

// ---- ring buffer --------------------------------------------------------------------------
export function ring(spec) {
  const N = clamp(Math.round(spec.slots || 8), 3, 12);
  const W = 720, C = W / 2, R = 228, S = N > 8 ? 86 : 108;
  const { root, s } = frame(W, W);
  const track = svg("circle", { cx: C, cy: C, r: R, fill: "none", "stroke-width": 6, "stroke-dasharray": "2 20", "stroke-linecap": "round" }, s);
  track.style.stroke = "var(--wire)";
  const ang = (i) => ((-90 + (i * 360) / N) * Math.PI) / 180;
  const at = (i, r = R) => [C + r * Math.cos(ang(i)), C + r * Math.sin(ang(i))];
  const slots = Array.from({ length: N }, (_, i) => {
    const [x, y] = at(i);
    const g = svg("g", { transform: `translate(${x} ${y})` }, s);
    const r = box(g, { x: -S / 2, y: -S / 2, width: S, height: S, rx: 24 });
    const [ix, iy] = at(i, R - S / 2 - 30);
    const idx = txt(s, { x: ix, y: iy }, String(i), 22);
    idx.style.fill = "var(--muted)";
    return { g, r, val: txt(s, {}, "", N > 8 ? 28 : 32) };
  });
  const flying = txt(s, {}, "", 32);
  const count = txt(s, { x: C, y: C - 14 }, "", 64, false);
  const countLbl = txt(s, { x: C, y: C + 38 }, "stored", 26, false);
  countLbl.style.fill = "var(--muted)";
  const wTag = tag(s, spec.writeLabel || "write", TONES.signal);
  const rTag = tag(s, spec.readLabel || "read", TONES.sky);

  // Replay ops into snapshots.
  const init = (spec.values || []).slice(0, N).map(String);
  let st = { vals: Array.from({ length: N }, (_, i) => init[i] ?? null), head: init.length % N, tail: 0, count: init.length };
  const snaps = [st];
  const ops = opsOf(spec);
  const trans = ops.map((o) => {
    const v = st.vals.slice();
    let tr;
    if (o.op === "read") {
      if (st.count === 0) tr = { kind: "empty", slot: st.tail };
      else {
        tr = { kind: "read", slot: st.tail, old: v[st.tail] };
        v[st.tail] = null;
        st = { vals: v, head: st.head, tail: (st.tail + 1) % N, count: st.count - 1 };
      }
    } else {
      const full = st.count === N;
      tr = { kind: full ? "overwrite" : "write", slot: st.head, old: v[st.head], val: String(o.value ?? "") };
      v[st.head] = tr.val;
      st = { vals: v, head: (st.head + 1) % N, tail: full ? (st.tail + 1) % N : st.tail, count: full ? N : st.count + 1 };
    }
    if (tr.kind === "empty") st = { ...st };
    snaps.push(st);
    return tr;
  });

  // Pointers orbit forward only (a wrap from N-1 to 0 continues clockwise).
  const ptrAngle = (from, to, p) => {
    const t = to < from ? to + N : to;
    return lerp(from, t, p);
  };
  const placeTag = (tg, idxF, offset) => {
    const a = ((-90 + (idxF * 360) / N + offset) * Math.PI) / 180;
    const r = R + S / 2 + 62;
    place(tg.g, C + r * Math.cos(a), C + r * Math.sin(a));
    tg.tri.setAttribute("transform", `rotate(${((a * 180) / Math.PI + 90 + 180).toFixed(1)} 0 0) translate(0 ${-2})`);
  };

  return {
    el: root,
    aspect: 1,
    update(t) {
      const { k, p } = current(ops, t);
      const cur = snaps[k + 1], prev = snaps[Math.max(k, 0)], tr = k >= 0 ? trans[k] : null;
      slots.forEach((sl, i) => {
        const [x, y] = at(i);
        let v = cur.vals[i], sc = 1, col = null, k2 = 0, op = 1;
        if (tr && tr.slot === i) {
          if (tr.kind === "write") { sc = spring(t, ops[k].t + 0.15, { stiffness: 260, damping: 16 }); col = TONES.signal; k2 = 1 - prog(t, ops[k].t + 0.6, 0.6); }
          else if (tr.kind === "overwrite") {
            if (p < 0.4) { v = tr.old; sc = 1 - 0.4 * (p / 0.4); op = 1 - p / 0.4; col = TONES.fail; }
            else sc = spring(t, ops[k].t + 0.32, { stiffness: 260, damping: 16 });
            col = col || TONES.fail; k2 = 1 - prog(t, ops[k].t + 0.7, 0.6);
          } else if (tr.kind === "read") { v = null; col = TONES.sky; k2 = 1 - prog(t, ops[k].t + 0.5, 0.6); }
          else if (tr.kind === "empty") { col = TONES.fail; k2 = 1 - prog(t, ops[k].t + 0.5, 0.6); }
        }
        if (sl.val.textContent !== (v ?? "")) sl.val.textContent = v ?? "";
        place(sl.val, x, y, clamp(sc, 0, 1.3));
        sl.val.style.opacity = String(op.toFixed(3));
        if (col === TONES.fail && tr?.kind === "overwrite" && p < 0.4) sl.val.style.fill = rgb(TONES.fail);
        else sl.val.style.fill = "var(--ink)";
        glow(sl.r, col || TONES.signal, clamp(k2));
      });
      // A read value lifts out of its slot toward the centre and fades.
      if (tr?.kind === "read" && p < 1) {
        const [x, y] = at(tr.slot);
        const q = ease.inOutCubic(p);
        flying.textContent = tr.old;
        place(flying, lerp(x, C, q), lerp(y, C, q), 1 + 0.3 * q);
        flying.style.opacity = String((1 - q).toFixed(3));
        flying.style.fill = rgb(TONES.sky);
      } else flying.style.opacity = "0";
      const showCount = p > 0.5 ? cur.count : prev.count;
      const c = `${showCount} / ${N}`;
      if (count.textContent !== c) count.textContent = c;
      count.style.fill = showCount === N ? rgb(TONES.signal) : "var(--ink)";
      const mv = prog(t, (ops[k]?.t ?? 0) + 0.3, 0.45, ease.inOutCubic);
      const hF = ptrAngle(prev.head, cur.head, k >= 0 ? mv : 1);
      const tF = ptrAngle(prev.tail, cur.tail, k >= 0 ? mv : 1);
      const same = Math.abs(((hF - tF) % N + N) % N) < 0.5;
      placeTag(wTag, hF, same ? -9 : 0);
      placeTag(rTag, tF, same ? 9 : 0);
    },
  };
}

// ---- array ----------------------------------------------------------------------------------
const PTR_TONES = [TONES.signal, TONES.sky, TONES.lavender, TONES.ok];
export function array(spec) {
  const init = (spec.values || []).slice(0, 10).map(String);
  const N = Math.max(init.length, 1);
  const CW = 112, G = 14, PAD = 30;
  const W = N * (CW + G) - G + PAD * 2, H = 380;
  const { root, s } = frame(W, H);
  const cx = (i) => PAD + i * (CW + G) + CW / 2, CY = 110;
  const cells = init.map((_, i) => {
    const r = box(s, { x: cx(i) - CW / 2, y: CY - CW / 2, width: CW, height: CW, rx: 20 });
    const idx = txt(s, { x: cx(i), y: CY - CW / 2 - 26 }, String(i), 22);
    idx.style.fill = "var(--muted)";
    return { r, val: txt(s, {}, "", init[i].length > 3 ? 28 : 36) };
  });
  const ops = opsOf(spec);
  const names = [...new Set(ops.filter((o) => o.op === "pointer").map((o) => String(o.name || "i")))];
  const tags = new Map(names.map((n, k) => [n, tag(s, n, PTR_TONES[k % PTR_TONES.length])]));
  // Snapshots.
  let st = { vals: init.slice(), ptr: {}, hl: null, dim: new Set(), found: null };
  const snaps = [st];
  for (const o of ops) {
    const nx = { vals: st.vals.slice(), ptr: { ...st.ptr }, hl: st.hl, dim: new Set(st.dim), found: st.found };
    const I = (v) => clamp(Math.round(Number(v) || 0), 0, N - 1);
    if (o.op === "pointer") nx.ptr[String(o.name || "i")] = I(o.index);
    if (o.op === "set") nx.vals[I(o.index)] = String(o.value ?? "");
    if (o.op === "swap") { const a = I(o.i ?? o.from), b = I(o.j ?? o.to); [nx.vals[a], nx.vals[b]] = [nx.vals[b], nx.vals[a]]; }
    if (o.op === "highlight") nx.hl = { a: I(o.from ?? o.index), b: I(o.to ?? o.index), tone: o.tone || "signal" };
    if (o.op === "dim") for (let i = I(o.from ?? o.index); i <= I(o.to ?? o.index); i++) nx.dim.add(i);
    if (o.op === "found") nx.found = I(o.index);
    snaps.push(nx);
    st = nx;
  }
  return {
    el: root,
    aspect: H / W,
    update(t) {
      const { k, p } = current(ops, t);
      const cur = snaps[k + 1], prev = snaps[Math.max(k, 0)], o = ops[k];
      cells.forEach((c, i) => {
        let v = cur.vals[i], sy = 1, dy = 0;
        if (o?.op === "set" && Number(o.index) === i) { sy = Math.abs(Math.cos(Math.PI * p)); v = p < 0.5 ? prev.vals[i] : cur.vals[i]; }
        if (o?.op === "swap") {
          const a = Number(o.i ?? o.from), b = Number(o.j ?? o.to);
          if (i === a || i === b) {
            const q = ease.inOutCubic(p);
            const other = i === a ? b : a;
            v = prev.vals[i];
            place(c.val, lerp(cx(i), cx(other), q), CY + (i === a ? -1 : 1) * 70 * Math.sin(Math.PI * q));
            if (p >= 1) { v = cur.vals[i]; place(c.val, cx(i), CY); }
          } else place(c.val, cx(i), CY);
        } else place(c.val, cx(i), CY, 1);
        if (c.val.textContent !== v) c.val.textContent = v;
        c.val.setAttribute("transform", (c.val.getAttribute("transform") || "") + (sy !== 1 ? ` scale(1 ${sy.toFixed(3)})` : ""));
        const inHl = cur.hl && i >= cur.hl.a && i <= cur.hl.b;
        const kHl = inHl ? (o?.op === "highlight" ? prog(t, o.t, 0.35) : 1) : 0;
        const kFound = cur.found === i ? 1 : 0;
        const col = kFound ? TONES.ok : inHl ? tone(cur.hl.tone) : TONES.signal;
        glow(c.r, col, Math.max(kHl, kFound));
        c.r.style.fill = kHl > 0 || kFound ? rgb(col, 0.16 * Math.max(kHl, kFound)) : "var(--panel)";
        const dimmed = cur.dim.has(i) ? (o?.op === "dim" && prog(t, o.t, 0.4) < 1 && !prev.dim.has(i) ? prog(t, o.t, 0.4) : 1) : 0;
        const opac = String((1 - 0.7 * dimmed).toFixed(3));
        c.r.style.opacity = opac;
        c.val.style.opacity = opac;
      });
      // Pointers glide between cells; several on one cell stack downward.
      const stackAt = {};
      for (const [name, tg] of tags) {
        const to = cur.ptr[name], from = prev.ptr[name] ?? to;
        if (to == null) { css(tg.g, { opacity: "0" }); continue; }
        const moving = o?.op === "pointer" && String(o.name || "i") === name;
        const q = moving ? ease.inOutBack(prog(t, o.t, 0.55)) : 1;
        const fx = from == null ? to : from;
        const x = lerp(cx(fx), cx(to), q);
        const lvl = (stackAt[to] = (stackAt[to] ?? -1) + 1);
        place(tg.g, x, CY + CW / 2 + 70 + lvl * 74);
        css(tg.g, { opacity: String((moving && prev.ptr[name] == null ? prog(t, o.t, 0.25) : 1).toFixed(3)) });
      }
    },
  };
}

// ---- stack / queue -----------------------------------------------------------------------------
export function stack(spec) {
  const queue = spec.kind === "queue";
  const cap = clamp(Math.round(spec.capacity || 5), 3, 7);
  const ops = opsOf(spec);
  // Every item that will ever exist gets an id, so shifts animate instead of re-labelling.
  const init = (spec.values || []).slice(0, cap).map(String);
  let st = init.map((v, i) => ({ id: i, v }));
  let nextId = init.length;
  const all = [...st];
  const snaps = [st];
  const trans = ops.map((o) => {
    let tr;
    if (["push", "enqueue"].includes(o.op)) {
      const it = { id: nextId++, v: String(o.value ?? "") };
      all.push(it);
      st = [...st, it];
      tr = { kind: "in", id: it.id };
    } else if (st.length) {
      const out = queue ? st[0] : st[st.length - 1];
      st = queue ? st.slice(1) : st.slice(0, -1);
      tr = { kind: "out", id: out.id };
    } else tr = { kind: "empty" };
    snaps.push(st);
    return tr;
  });
  let W, H, slotPos;
  if (queue) {
    const B = 116, G = 16;
    W = cap * (B + G) + 220; H = 330;
    slotPos = (j) => [110 + j * (B + G) + B / 2, 150];
  } else {
    const B = 90, G = 12;
    W = 560; H = cap * (B + G) + 170;
    slotPos = (j) => [W / 2, H - 50 - B / 2 - j * (B + G)];
  }
  const { root, s } = frame(W, H);
  // The container: an open-topped pit for a stack, an open tube for a queue.
  const wall = svg("path", {
    d: queue ? `M80 76 H${W - 80} M80 224 H${W - 80}` : `M${W / 2 - 200} 60 V${H - 40} H${W / 2 + 200} V60`,
    fill: "none", "stroke-width": 8, "stroke-linecap": "round", "stroke-linejoin": "round",
  }, s);
  wall.style.stroke = "var(--wire)";
  const nodes = new Map(all.map((it) => {
    const g = svg("g", {}, s);
    const bw = queue ? 116 : 340, bh = queue ? 116 : 90;
    box(g, { x: -bw / 2, y: -bh / 2, width: bw, height: bh, rx: 20 });
    txt(g, {}, it.v, it.v.length > 4 ? 26 : 32);
    return [it.id, g];
  }));
  const tags = queue ? [tag(s, "front", TONES.sky), tag(s, "back", TONES.signal)] : [tag(s, "top", TONES.signal)];
  return {
    el: root,
    aspect: H / W,
    update(t) {
      const { k, p } = current(ops, t);
      const cur = snaps[k + 1], prev = snaps[Math.max(k, 0)], tr = k >= 0 ? trans[k] : null;
      for (const [id, g] of nodes) {
        const ci = cur.findIndex((x) => x.id === id), pi = prev.findIndex((x) => x.id === id);
        if (ci < 0 && !(tr?.kind === "out" && tr.id === id && p < 1)) { css(g, { opacity: "0" }); continue; }
        let [x, y] = slotPos(Math.max(ci, 0));
        let o = 1, sc = 1;
        if (tr?.kind === "in" && tr.id === id) {
          const q = spring(t, ops[k].t, { stiffness: 200, damping: 17 });
          if (queue) x = lerp(W + 120, x, clamp(q, 0, 1.1)); else y = lerp(-120, y, q);
          o = prog(t, ops[k].t, 0.15);
        } else if (tr?.kind === "out" && tr.id === id) {
          const [px, py] = slotPos(pi);
          const q = ease.inCubic(p);
          x = queue ? lerp(px, -140, q) : px;
          y = queue ? py : lerp(py, -160, q);
          o = 1 - prog(t, ops[k].t + 0.35, 0.4);
        } else if (queue && tr?.kind === "out" && pi >= 0 && ci >= 0 && pi !== ci) {
          const [px] = slotPos(pi);
          x = lerp(px, x, ease.inOutCubic(prog(t, ops[k].t + 0.2, 0.5)));
        }
        place(g, x, y, sc);
        css(g, { opacity: String(o.toFixed(3)) });
      }
      const n = (p > 0.5 ? cur : prev).length;
      if (queue) {
        const [fx, fy] = slotPos(0), [bx, by] = slotPos(Math.max(n - 1, 0));
        place(tags[0].g, fx, fy + 124); place(tags[1].g, bx, by + 124 + (n <= 1 ? 62 : 0));
        tags.forEach((tg) => css(tg.g, { opacity: n ? "1" : "0.3" }));
      } else {
        const [tx, ty] = slotPos(Math.max(n - 1, 0));
        place(tags[0].g, tx + 250, ty);
        tags[0].tri.setAttribute("transform", "rotate(-90) translate(0 -46)");
        css(tags[0].g, { opacity: n ? "1" : "0.3" });
      }
    },
  };
}

// ---- binary search tree ---------------------------------------------------------------------------
const cmp = (a, b) => {
  const na = Number(a), nb = Number(b);
  return !Number.isNaN(na) && !Number.isNaN(nb) ? na - nb : String(a).localeCompare(String(b));
};
export function tree(spec) {
  const init = (spec.values || []).map(String);
  const ops = opsOf(spec);
  // The final tree (every value ever inserted, in order) fixes the layout, so earlier
  // frames are exact subtrees of it and nothing jumps when a node is added.
  const order = [...init];
  for (const o of ops) if (o.op === "insert" && !order.includes(String(o.value))) order.push(String(o.value));
  const nodes = [];
  const byVal = new Map();
  for (const v of order.slice(0, 15)) {
    let parent = null, depth = 0, cur = nodes[0], side = null;
    while (cur) {
      parent = cur; depth++;
      side = cmp(v, cur.v) < 0 ? "l" : "r";
      cur = cur[side];
    }
    const n = { v, parent, depth, l: null, r: null };
    if (parent) parent[side] = n;
    nodes.push(n);
    byVal.set(v, n);
  }
  const sorted = [...nodes].sort((a, b) => cmp(a.v, b.v));
  const maxD = Math.max(...nodes.map((n) => n.depth), 0);
  const W = Math.max(640, nodes.length * 118), H = (maxD + 1) * 160 + 70;
  const { root, s } = frame(W, H);
  const pos = (n) => [40 + ((sorted.indexOf(n) + 0.5) * (W - 80)) / nodes.length, 90 + n.depth * 160];
  const edges = svg("g", {}, s);
  const R = 54;
  const vis = nodes.map((n) => {
    const [x, y] = pos(n);
    let line = null;
    if (n.parent) {
      const [px, py] = pos(n.parent);
      line = svg("line", { x1: px, y1: py, x2: x, y2: y, "stroke-width": 6, "stroke-linecap": "round" }, edges);
      line.style.stroke = "var(--wire)";
      line.len = Math.hypot(x - px, y - py);
    }
    const g = svg("g", { transform: `translate(${x} ${y})` }, s);
    const c = svg("circle", { r: R }, g);
    c.style.fill = "var(--panel)"; c.style.stroke = "var(--panel-edge)"; c.style.strokeWidth = "5";
    txt(g, {}, n.v, n.v.length > 3 ? 24 : 32);
    return { n, g, c, line, x, y };
  });
  const cursor = svg("circle", { r: R + 14, fill: "none", "stroke-width": 7 }, s);
  const probe = svg("g", {}, s);
  const probeBg = svg("rect", { x: -58, y: -32, width: 116, height: 64, rx: 32 }, probe);
  const probeTxt = txt(probe, {}, "", 28);
  probeTxt.style.fill = "#10181b";
  // When each node appears, and each op's path of visited nodes.
  const STEP = 0.4;
  const born = new Map(init.map((v) => [v, -1]));
  const plans = ops.map((o) => {
    const v = String(o.value);
    const path = [];
    let cur = nodes[0], found = null;
    while (cur) {
      const hereAlready = born.has(cur.v) && born.get(cur.v) <= o.t;
      if (!hereAlready) break;
      path.push(cur);
      const c = cmp(v, cur.v);
      if (c === 0) { found = cur; break; }
      cur = c < 0 ? cur.l : cur.r;
    }
    const end = o.t + Math.max(path.length, 1) * STEP;
    if (o.op === "insert" && !found && byVal.has(v)) born.set(v, end);
    return { o, v, path, found, end };
  });
  return {
    el: root,
    aspect: H / W,
    update(t) {
      for (const d of vis) {
        const b = born.has(d.n.v) ? born.get(d.n.v) : Infinity;
        const sc = b < 0 ? 1 : spring(t, b, { stiffness: 240, damping: 16 });
        d.g.setAttribute("transform", `translate(${d.x} ${d.y}) scale(${clamp(sc, 0, 1.2).toFixed(3)})`);
        css(d.g, { opacity: t >= b ? "1" : "0" });
        if (d.line) {
          const q = b < 0 ? 1 : prog(t, b - 0.15, 0.35);
          d.line.setAttribute("stroke-dasharray", `${d.line.len}`);
          d.line.setAttribute("stroke-dashoffset", `${(d.line.len * (1 - q)).toFixed(1)}`);
        }
        d.c.style.stroke = "var(--panel-edge)";
        d.c.style.filter = "none";
      }
      const pl = [...plans].reverse().find((x) => x.o.t <= t && t < x.end + 1.4);
      if (!pl) { css(cursor, { opacity: "0" }); css(probe, { opacity: "0" }); return; }
      const steps = Math.max(pl.path.length, 1);
      const f = clamp((t - pl.o.t) / STEP, 0, steps - 1e-3);
      const i = Math.floor(f), q = ease.inOutCubic(f - i);
      const a = pl.path[i] ? pos(pl.path[i]) : [W / 2, 80];
      const b = pl.path[i + 1] ? pos(pl.path[i + 1]) : a;
      const done = t >= pl.end;
      let [x, y] = done && pl.o.op === "insert" && !pl.found && byVal.get(pl.v) ? pos(byVal.get(pl.v)) : [lerp(a[0], b[0], q), lerp(a[1], b[1], q)];
      const missing = done && pl.o.op === "search" && !pl.found;
      const col = done ? (pl.found || pl.o.op === "insert" ? TONES.ok : TONES.fail) : TONES.signal;
      cursor.setAttribute("cx", x.toFixed(1)); cursor.setAttribute("cy", y.toFixed(1));
      cursor.style.stroke = rgb(col);
      css(cursor, { opacity: String((1 - prog(t, pl.end + 0.9, 0.5)).toFixed(3)) });
      place(probe, x - 112, y - 66);
      probeBg.style.fill = rgb(col);
      const label = missing ? `${pl.v} ✕` : pl.v;
      if (probeTxt.textContent !== label) probeTxt.textContent = label;
      css(probe, { opacity: String((prog(t, pl.o.t, 0.2) * (1 - prog(t, pl.end + 0.9, 0.5))).toFixed(3)) });
      if (done && pl.found) {
        const d = vis.find((v) => v.n === pl.found);
        glow(d.c, TONES.ok, 1 - prog(t, pl.end + 0.9, 0.5));
      }
    },
  };
}

// ---- hash map ---------------------------------------------------------------------------------
export function hashmap(spec) {
  const N = clamp(Math.round(spec.buckets || 5), 3, 8);
  const ops = opsOf(spec);
  const hash = (k) => [...String(k)].reduce((a, ch) => a + ch.charCodeAt(0), 0) % N;
  const bucketOf = (o) => (Number.isInteger(Number(o.bucket)) && o.bucket !== "" && o.bucket != null ? clamp(Number(o.bucket), 0, N - 1) : hash(o.key));
  const W = 960, ROW = 104, TOP = 190, H = TOP + N * ROW + 30;
  const { root, s } = frame(W, H);
  const hb = box(s, { x: 250, y: 24, width: 460, height: 104, rx: 26 });
  const ht = txt(s, { x: 480, y: 76 }, `hash(key) % ${N}`, 34);
  const rows = Array.from({ length: N }, (_, i) => {
    const y = TOP + i * ROW + ROW / 2;
    const r = box(s, { x: 40, y: y - 40, width: 96, height: 80, rx: 18 });
    const t = txt(s, { x: 88, y }, String(i), 32);
    t.style.fill = "var(--muted)";
    return { r, y };
  });
  // Chain membership replayed: every put key gets a chip that lands at its chain position.
  const chains = Array.from({ length: N }, () => []);
  const chips = new Map();
  const plans = ops.map((o) => {
    const b = bucketOf(o), key = String(o.key ?? "");
    if (o.op === "put") {
      const exists = chains[b].includes(key);
      const slot = exists ? chains[b].indexOf(key) : chains[b].length;
      const collision = !exists && chains[b].length > 0;
      if (!exists) chains[b].push(key);
      if (!chips.has(key + "@" + b)) {
        const g = svg("g", {}, s);
        const r = box(g, { x: -80, y: -34, width: 160, height: 68, rx: 20 });
        txt(g, {}, key, key.length > 6 ? 22 : 28);
        chips.set(key + "@" + b, { g, r, b, slot, t: o.t });
      }
      return { o, b, key, slot, collision };
    }
    return { o, b, key, slot: chains[b].indexOf(key), found: chains[b].includes(key) };
  });
  const chipX = (slot) => 250 + slot * 190;
  const links = Array.from({ length: N }, (_, i) => {
    const l = svg("path", { fill: "none", "stroke-width": 5 }, s);
    l.style.stroke = "var(--wire)";
    return l;
  });
  return {
    el: root,
    aspect: H / W,
    update(t) {
      let hashPulse = 0;
      const shown = Array(N).fill(0);
      for (const [, c] of chips) {
        const pl = plans.find((p) => p.o.op === "put" && p.b === c.b && p.slot === c.slot);
        const t0 = pl.o.t;
        if (t < t0) { css(c.g, { opacity: "0" }); continue; }
        const q1 = spring(t, t0, { stiffness: 260, damping: 18 });
        const q2 = ease.inOutCubic(prog(t, t0 + 0.35, 0.6));
        const [sx, sy] = [480, 76], [ex, ey] = [chipX(c.slot), rows[c.b].y];
        place(c.g, lerp(sx, ex, q2), lerp(sy, ey, q2) - 60 * Math.sin(Math.PI * q2), q2 > 0 ? 1 : clamp(q1, 0, 1.2));
        css(c.g, { opacity: "1" });
        if (t - t0 < 0.5) hashPulse = Math.max(hashPulse, Math.sin((Math.PI * (t - t0)) / 0.5));
        const k = 1 - prog(t, t0 + 1.0, 0.6);
        glow(c.r, pl.collision ? TONES.signal : TONES.ok, q2 >= 1 ? k : 0);
        if (q2 > 0.95) shown[c.b] = Math.max(shown[c.b], c.slot + 1);
      }
      links.forEach((l, i) => {
        l.setAttribute("d", shown[i] ? `M136 ${rows[i].y} H${chipX(0) - 80}` + Array.from({ length: shown[i] - 1 }, (_, j) => ` M${chipX(j) + 80} ${rows[i].y} H${chipX(j + 1) - 80}`).join("") : "");
      });
      hb.style.stroke = hashPulse > 0.02 ? rgb(TONES.signal, 0.4 + 0.6 * hashPulse) : "var(--panel-edge)";
      ht.style.fill = hashPulse > 0.3 ? rgb(TONES.signal) : "var(--ink)";
      // Bucket rows light up while a key is placed or looked up.
      rows.forEach((r, i) => {
        let k = 0, col = TONES.signal;
        for (const pl of plans) {
          if (pl.b !== i) continue;
          const e = prog(t, pl.o.t + 0.35, 0.3) * (1 - prog(t, pl.o.t + 1.5, 0.5));
          if (e > k) { k = e; col = pl.o.op === "get" ? (pl.found ? TONES.ok : TONES.fail) : pl.collision ? TONES.signal : TONES.sky; }
        }
        glow(r.r, col, k);
      });
      // A get scans its chain chip by chip.
      for (const pl of plans) {
        if (pl.o.op !== "get" || t < pl.o.t) continue;
        const chain = [...chips.values()].filter((c) => c.b === pl.b).sort((a, b) => a.slot - b.slot);
        chain.forEach((c, j) => {
          const hitT = pl.o.t + 0.5 + j * 0.3;
          if (pl.found && j > pl.slot) return;
          const k = t >= hitT ? 1 - prog(t, hitT + 0.35, 0.4) : 0;
          const isIt = pl.found && j === pl.slot;
          if (k > 0) glow(c.r, isIt ? TONES.ok : TONES.sky, isIt ? Math.max(k, 1 - prog(t, hitT + 1.2, 0.5)) : k);
        });
      }
    },
  };
}

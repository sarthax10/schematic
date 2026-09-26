// Runtime entry: loads a resolved timeline, builds every scene, and exposes window.seek(t),
// which puts the whole frame into its exact state at time t (renderer + preview both use it),
// and window.lint(t), which measures the real on-screen layout for automated design checks.
import { clamp, css, ease, lerp, prog } from "./core.js";
import { actorState, buildScene, cameraAt, FW, FH, screenToWorld, TRANS, updateScene, worldToScreen } from "./engine.js";

const params = new URLSearchParams(location.search);
const tlUrl = params.get("timeline") || "timeline.json";
const timeline = await (await fetch(tlUrl)).json();

await Promise.all([
  document.fonts.load('700 40px "Bricolage Grotesque"'),
  document.fonts.load('500 40px "JetBrains Mono"'),
]);
await document.fonts.ready;

const host = document.getElementById("scenes");
const capBox = document.getElementById("captions");
const capNode = capBox.querySelector(".cap");
const scenes = timeline.scenes.map((sc) => {
  const S = buildScene(sc, host);
  S.start = sc.start;
  S.end = sc.start + sc.duration;
  return S;
});

// ---- carries: an actor flies from its place in the outgoing scene to its place in the
// incoming one across the boundary, in screen space, with both copies following the same
// path (so the handover is invisible). -----------------------------------------------------
const span = TRANS.pre + TRANS.post;
scenes.forEach((S, i) => {
  if (i === 0) return;
  const O = scenes[i - 1];
  for (const A of S.actors.values()) {
    const src = A.spec.carry && O.actors.get(A.spec.carry);
    if (!src) continue;
    const oLocal = O.scene.duration - TRANS.pre;
    const oCam = cameraAt(O, oLocal);
    const oSt = actorState(src, oLocal);
    const s0 = worldToScreen(oCam, oSt.x, oSt.y);
    const w0 = src.w * oSt.s * oCam.zoom;
    const iCam = cameraAt(S, TRANS.post);
    const s1 = worldToScreen(iCam, A.bx, A.by);
    const w1 = A.w * iCam.zoom;
    const path = (lt) => {
      const p = ease.inOutCubic(clamp((lt + TRANS.pre) / span));
      return { sx: lerp(s0[0], s1[0], p), sy: lerp(s0[1], s1[1], p) - 120 * Math.sin(Math.PI * p), w: lerp(w0, w1, p) };
    };
    A.carryOverride = (lt) => {
      if (lt > TRANS.post) return null;
      const q = path(lt);
      const cam = cameraAt(S, lt);
      const [x, y] = screenToWorld(cam, q.sx, q.sy);
      return { x, y, s: q.w / (A.w * cam.zoom) };
    };
    src.carryOverride = (lt) => {
      const rel = lt - O.scene.duration;
      if (rel < -TRANS.pre) return null;
      const q = path(Math.min(rel, TRANS.post));
      const cam = cameraAt(O, lt);
      const [x, y] = screenToWorld(cam, q.sx, q.sy);
      return { x, y, s: q.w / (src.w * cam.zoom) };
    };
  }
});

// Screen position of an actor at a scene-local time (for zoom-through / iris origins).
function focalPoint(S, id, lt) {
  const A = id && S.actors.get(id);
  if (!A) return [FW / 2, 690];
  return worldToScreen(cameraAt(S, lt), actorState(A, lt).x, actorState(A, lt).y);
}

function transitionStyle(S, O, t) {
  // Style for incoming scene S and outgoing scene O at global time t around S.start.
  const tr = S.scene.transition || { type: "cut" };
  const p = clamp((t - (S.start - TRANS.pre)) / span);
  const e = ease.inOutCubic(p);
  const inc = { opacity: "1", transform: "none", filter: "none", "clip-path": "none", "transform-origin": "50% 50%" };
  const out = { opacity: "1", transform: "none", filter: "none", "clip-path": "none", "transform-origin": "50% 50%" };
  let outVisible = p < 1, incVisible = p > 0;
  switch (tr.type) {
    case "cut":
      incVisible = t >= S.start; outVisible = t < S.start;
      break;
    case "dissolve":
      inc.opacity = String(e.toFixed(3));
      break;
    case "pan": {
      const [dx, dy] = { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] }[tr.dir || "right"];
      const blur = (Math.sin(Math.PI * p) * 6).toFixed(2);
      inc.transform = `translate(${((1 - e) * dx * FW).toFixed(1)}px, ${((1 - e) * dy * FH).toFixed(1)}px)`;
      out.transform = `translate(${(-e * dx * FW).toFixed(1)}px, ${(-e * dy * FH).toFixed(1)}px)`;
      inc.filter = out.filter = `blur(${blur}px)`;
      break;
    }
    case "zoom-in": {
      const [fx, fy] = focalPoint(O, tr.actor, O.scene.duration - TRANS.pre);
      out["transform-origin"] = `${fx.toFixed(1)}px ${fy.toFixed(1)}px`;
      out.transform = `scale(${(1 + 7 * ease.inCubic(p)).toFixed(4)})`;
      out.opacity = String((1 - prog(p, 0.3, 0.35)).toFixed(3));
      inc.transform = `scale(${(0.55 + 0.45 * ease.outCubic(prog(p, 0.3, 0.7))).toFixed(4)})`;
      inc.opacity = String(prog(p, 0.35, 0.45).toFixed(3));
      break;
    }
    case "zoom-out": {
      out.transform = `scale(${(1 - 0.45 * e).toFixed(4)})`;
      out.opacity = String((1 - prog(p, 0.4, 0.5)).toFixed(3));
      inc.transform = `scale(${(1.6 - 0.6 * ease.outCubic(p)).toFixed(4)})`;
      inc.opacity = String(prog(p, 0.2, 0.5).toFixed(3));
      break;
    }
    case "iris": {
      const [fx, fy] = focalPoint(O, tr.actor, O.scene.duration - TRANS.pre);
      inc["clip-path"] = `circle(${(2300 * e).toFixed(1)}px at ${fx.toFixed(1)}px ${fy.toFixed(1)}px)`;
      break;
    }
  }
  return { inc, out, incVisible, outVisible };
}

function seek(t) {
  const styles = new Map();
  scenes.forEach((S, i) => {
    const O = scenes[i - 1];
    const N = scenes[i + 1];
    let visible = t >= S.start && t < S.end;
    let style = { opacity: "1", transform: "none", filter: "none", "clip-path": "none", "transform-origin": "50% 50%" };
    if (O && t >= S.start - TRANS.pre && t < S.start + TRANS.post) {
      const ts = transitionStyle(S, O, t);
      visible = ts.incVisible;
      style = ts.inc;
    }
    if (N && t >= N.start - TRANS.pre && t < N.start + TRANS.post) {
      const ts = transitionStyle(N, S, t);
      visible = ts.outVisible;
      style = ts.out;
    }
    if (i === 0 && t < 0.3) style.opacity = String(prog(t, 0, 0.3).toFixed(3));
    styles.set(S, { visible, style });
  });
  for (const S of scenes) {
    const { visible, style } = styles.get(S);
    css(S.el, { display: visible ? "block" : "none", ...style });
    if (visible) updateScene(S, t - S.start);
  }

  let cap = null;
  for (const c of timeline.captions) if (t >= c.start && t < c.end) cap = c;
  if (capNode.textContent !== (cap ? cap.text : "")) capNode.textContent = cap ? cap.text : "";
  css(capBox, { opacity: cap ? String(prog(t, cap.start, 0.08).toFixed(3)) : "0" });
}

// ---- layout lint --------------------------------------------------------------------------
const SAFE = { x0: 60, y0: 200, x1: 1020, y1: 1160 };
function lint(t) {
  seek(t);
  const S = scenes.find((s) => t >= s.start && t < s.end);
  if (!S) return [];
  const issues = [];
  const boxes = [];
  const cam = cameraAt(S, t - S.start);
  const shot = [...S.shots].reverse().find((sh) => sh.t <= t - S.start) || S.shots[0];
  const focusId = typeof shot.camera?.focus === "string" ? shot.camera.focus : null;
  for (const A of S.actors.values()) {
    if (!A.cur || A.cur.o < 0.5 || A.wrap.style.visibility === "hidden") continue;
    let r = A.wrap.getBoundingClientRect();
    if (A.badge && parseFloat(A.badge.style.opacity || "0") > 0.5) {
      // A visible badge is part of the actor's footprint.
      const b = A.badge.getBoundingClientRect();
      r = { left: Math.min(r.left, b.left), top: Math.min(r.top, b.top), right: Math.max(r.right, b.right), bottom: Math.max(r.bottom, b.bottom) };
    }
    if (r.right < 0 || r.left > FW || r.bottom < 0 || r.top > FH) continue; // fully off-frame: fine
    const bg = A.spec.type === "shape";
    const box = { id: A.spec.id, x0: r.left, y0: r.top, x1: r.right, y1: r.bottom, bg };
    // Text, screen-layer actors and the camera's subject must sit fully in the safe area.
    // Other world actors may be cropped by a close-up — that's framing, not a mistake.
    const strict = A.spec.type === "text" || A.spec.type === "counter" || A.spec.screen || A.spec.id === focusId || cam.zoom < 1.15;
    if (!bg && strict) {
      const off = Math.max(SAFE.x0 - r.left, r.right - SAFE.x1, SAFE.y0 - r.top, r.bottom - SAFE.y1);
      if (off > 24) issues.push({ scene: S.scene.id, t, kind: "outside_safe_area", actor: A.spec.id, px: Math.round(off) });
    }
    if (A.spec.type === "text") {
      const fs = parseFloat(getComputedStyle(A.impl.el).fontSize) * (A.spec.screen ? 1 : cam.zoom) * A.cur.s;
      if (fs < 34) issues.push({ scene: S.scene.id, t, kind: "text_too_small", actor: A.spec.id, px: Math.round(fs) });
    }
    boxes.push(box);
  }
  const fg = boxes.filter((b) => !b.bg);
  for (let i = 0; i < fg.length; i++) {
    for (let j = i + 1; j < fg.length; j++) {
      const a = fg[i], b = fg[j];
      const ix = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), iy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
      if (ix <= 0 || iy <= 0) continue;
      const small = Math.min((a.x1 - a.x0) * (a.y1 - a.y0), (b.x1 - b.x0) * (b.y1 - b.y0));
      const frac = (ix * iy) / small;
      const allowed = [a.id, b.id].some((id) => (S.actors.get(id).spec.allowOverlap || []).includes(a.id === id ? b.id : a.id));
      if (frac > 0.12 && !allowed) issues.push({ scene: S.scene.id, t, kind: "overlap", actors: [a.id, b.id], frac: +frac.toFixed(2) });
    }
  }
  if (fg.length === 0) issues.push({ scene: S.scene.id, t, kind: "empty_frame" });
  // A crowd of characters reads as one group, not N separate focal points.
  const chars = fg.filter((b) => S.actors.get(b.id).spec.type === "character").length;
  const focal = fg.length - (chars > 3 ? chars - 1 : 0);
  if (focal > 8) issues.push({ scene: S.scene.id, t, kind: "crowded", count: focal });
  return issues;
}

window.seek = seek;
window.lint = lint;
window.__timeline = { duration: timeline.duration, fps: timeline.fps };
seek(0);
window.__ready = true;

// ---- preview mode ------------------------------------------------------------------------
if (params.get("mode") === "preview") {
  document.body.classList.add("preview");
  const frame = document.getElementById("frame");
  const viewport = document.getElementById("viewport");
  const controls = document.getElementById("controls");
  controls.hidden = false;
  const fit = () => {
    const s = Math.min((innerHeight - 70) / FH, innerWidth / FW);
    frame.style.transform = `scale(${s})`;
    viewport.style.width = `${FW * s}px`;
    viewport.style.height = `${FH * s}px`;
  };
  addEventListener("resize", fit);
  fit();
  const audio = new Audio(new URL(timeline.audio || "narration.m4a", new URL(tlUrl, location.href)).href);
  const play = document.getElementById("play");
  const scrub = document.getElementById("scrub");
  const clock = document.getElementById("clock");
  const show = (t) => {
    seek(t);
    scrub.value = String(Math.round((t / timeline.duration) * 1000));
    clock.textContent = `${t.toFixed(1)}s`;
  };
  const loop = () => { show(audio.currentTime); if (!audio.paused) requestAnimationFrame(loop); };
  play.addEventListener("click", () => {
    if (audio.paused) { audio.play(); play.textContent = "Pause"; requestAnimationFrame(loop); }
    else { audio.pause(); play.textContent = "Play"; }
  });
  audio.addEventListener("ended", () => { play.textContent = "Play"; });
  scrub.addEventListener("input", () => { audio.currentTime = (Number(scrub.value) / 1000) * timeline.duration; show(audio.currentTime); });
  const t0 = Number(params.get("t"));
  if (t0) { show(t0); audio.addEventListener("loadedmetadata", () => { audio.currentTime = t0; show(t0); }, { once: true }); }
}

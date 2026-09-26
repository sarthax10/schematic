// A simple geometric person, built to act: jointed two-segment arms, swinging legs, a
// breathing torso, blinking eyes, and a mouth that changes with mood. Poses are target
// joint angles; `state {pose}` beats blend between them, so every gesture is an eased
// motion rather than a swap. Drawn in the same flat language as props.js.
import { clamp, ease, hash01, latest, lerp, prog, svg } from "../core.js";
import { C } from "../props.js";

const SKIN = ["#f3cfb1", "#dca47d", "#b07650", "#7a4f36"];
const HAIR = ["#2d2230", "#6b3f2a", "#c98a3c", "#1c1c22"];

// [upperL, foreL, upperR, foreR, legL, legR, headTilt]; angles in degrees, 0 = hanging down,
// negative = toward the direction the character faces.
const POSES = {
  idle: [8, -6, -8, -10, 0, 0, 0],
  wave: [8, -6, -150, -40, 0, 0, -4],
  point: [8, -6, -88, -4, 0, 0, 0],
  think: [8, -6, -40, -130, 0, 0, 8],
  carry: [-55, -40, -65, -35, 0, 0, 0],
  cheer: [150, 20, -150, -20, -6, 6, 0],
  shrug: [40, 100, -40, -100, 0, 0, 6],
  sad: [4, 0, -4, 0, 0, 0, 14],
  walk: [0, -10, 0, -10, 0, 0, 0],
  reach: [8, -6, -120, -10, 0, 0, -6],
};
const MOUTHS = { smile: "M86 84 q14 12 28 0", neutral: "M88 86 h24", open: "M92 82 a8 8 0 1 0 16 0 a8 8 0 1 0 -16 0", frown: "M86 90 q14 -10 28 0" };
export const POSE_NAMES = Object.keys(POSES);

export function create(spec, ctx) {
  const look = spec.look || {};
  const shirt = C[look.shirt] || C[look.shirt + ""] || C.sky;
  const shirtD = C[(look.shirt || "sky") + "D"] || C.skyD;
  const skin = SKIN[clamp(look.skin ?? Math.floor(hash01(spec.id) * 4), 0, 3)];
  const hairCol = HAIR[Math.floor(hash01(spec.id + "h") * HAIR.length)];
  const hair = look.hair || ["short", "long", "bun", "curly"][Math.floor(hash01(spec.id + "s") * 4)];

  const root = svg("svg", { viewBox: "0 0 200 320", width: "100%", height: "100%", style: "overflow:visible" });
  svg("ellipse", { cx: 100, cy: 314, rx: 52, ry: 7, fill: "rgba(0,0,0,0.18)" }, root);
  const body = svg("g", {}, root);

  const limb = (parent, x, y, len, w, fill) => {
    const g = svg("g", { transform: `translate(${x} ${y})` }, parent);
    const r = svg("g", {}, g);
    svg("rect", { x: -w / 2, y: -w / 2, width: w, height: len + w / 2, rx: w / 2, fill }, r);
    return { g: r, len };
  };
  const arm = (x, fill) => {
    const upper = limb(body, x, 130, 46, 22, fill);
    const fore = limb(upper.g, 0, 46, 42, 20, fill);
    svg("circle", { cx: 0, cy: 44, r: 12, fill: skin }, fore.g);
    return { upper, fore };
  };

  const back = arm(82, shirtD); // far arm, drawn behind the torso
  const legL = limb(body, 88, 206, 96, 26, C.slate);
  const legR = limb(body, 112, 206, 96, 26, C.slateD);
  svg("rect", { x: 72, y: 296, width: 32, height: 14, rx: 7, fill: C.ink }, legL.g).setAttribute("transform", "translate(-88 -206)");
  svg("rect", { x: 96, y: 296, width: 32, height: 14, rx: 7, fill: C.ink }, legR.g).setAttribute("transform", "translate(-112 -206)");
  const torso = svg("g", {}, body);
  svg("rect", { x: 64, y: 112, width: 72, height: 104, rx: 30, fill: shirt }, torso);
  svg("path", { d: "M84 114 q16 14 32 0", fill: "none", stroke: shirtD, "stroke-width": 6, "stroke-linecap": "round" }, torso);
  const front = arm(118, shirt);

  const head = svg("g", {}, body);
  if (hair === "long") svg("rect", { x: 60, y: 40, width: 80, height: 86, rx: 34, fill: hairCol }, head);
  svg("rect", { x: 92, y: 96, width: 16, height: 20, rx: 6, fill: skin }, head);
  svg("circle", { cx: 100, cy: 70, r: 36, fill: skin }, head);
  if (hair === "short") svg("path", { d: "M64 70 a36 36 0 0 1 72 -6 q-20 -14 -44 -6 q-16 4 -28 12z", fill: hairCol }, head);
  if (hair === "long") svg("path", { d: "M64 72 a36 36 0 0 1 72 0 q-10 -18 -36 -20 q-26 2 -36 20z", fill: hairCol }, head);
  if (hair === "bun") {
    svg("circle", { cx: 100, cy: 28, r: 16, fill: hairCol }, head);
    svg("path", { d: "M64 70 a36 36 0 0 1 72 0 q-36 -26 -72 0z", fill: hairCol }, head);
  }
  if (hair === "curly") [[72, 50], [88, 38], [106, 36], [124, 46], [134, 62], [66, 64]].forEach(([x, y]) => svg("circle", { cx: x, cy: y, r: 14, fill: hairCol }, head));
  const eyes = [svg("ellipse", { cx: 110, cy: 70, rx: 4.5, ry: 6, fill: C.ink }, head), svg("ellipse", { cx: 124, cy: 70, rx: 4.5, ry: 6, fill: C.ink }, head)];
  svg("circle", { cx: 131, cy: 82, r: 6, fill: "rgba(255,111,97,0.25)" }, head);
  const mouth = svg("path", { d: MOUTHS.smile, fill: "none", stroke: C.ink, "stroke-width": 4.5, "stroke-linecap": "round", transform: "translate(18 0)" }, head);

  // Pose / expression events come from `state` beats; walking is also implied by `move`
  // beats with walk:true (the engine adds a walk pose for the move's duration).
  const poseEvents = [{ t: -1, pose: spec.pose || "idle" }, ...(spec._poses || [])].sort((a, b) => a.t - b.t);
  const faceEvents = [{ t: -1, face: spec.expression || "smile" }, ...(spec._faces || [])].sort((a, b) => a.t - b.t);
  const phase = hash01(spec.id) * 10;

  const setRot = (g, deg, px = 0, py = 0) => g.setAttribute("transform", `rotate(${deg.toFixed(2)} ${px} ${py})`);

  return {
    el: root,
    aspect: 320 / 200,
    update(t) {
      const cur = latest(poseEvents, t);
      const idx = poseEvents.indexOf(cur);
      const prev = idx > 0 ? poseEvents[idx - 1] : cur;
      const k = prog(t, cur.t, 0.35, ease.inOutCubic);
      const a = POSES[prev.pose] || POSES.idle, b = POSES[cur.pose] || POSES.idle;
      const q = a.map((v, i) => lerp(v, b[i], k));
      let bob = Math.sin(t * 2.1 + phase) * 1.6; // breathing
      if (cur.pose === "walk" || (prev.pose === "walk" && k < 1)) {
        const w = cur.pose === "walk" ? k : 1 - k;
        const s = Math.sin(t * 9 + phase);
        q[4] += 24 * s * w; q[5] -= 24 * s * w;
        q[0] -= 20 * s * w; q[2] += 20 * s * w;
        bob += Math.abs(Math.cos(t * 9 + phase)) * -6 * w;
      }
      if (cur.pose === "wave" && k > 0.5) q[3] += 22 * Math.sin(t * 10);
      setRot(back.upper.g, q[0]); setRot(back.fore.g, q[1]);
      setRot(front.upper.g, q[2]); setRot(front.fore.g, q[3]);
      setRot(legL.g, q[4]); setRot(legR.g, q[5]);
      head.setAttribute("transform", `rotate(${q[6].toFixed(2)} 100 100)`);
      body.setAttribute("transform", `translate(0 ${bob.toFixed(2)})`);
      torso.setAttribute("transform", `translate(100 216) scale(1 ${(1 + 0.012 * Math.sin(t * 2.1 + phase)).toFixed(4)}) translate(-100 -216)`);
      const blink = (t + phase) % 3.4 < 0.12;
      eyes.forEach((e) => e.setAttribute("ry", blink ? "1" : "6"));
      const f = latest(faceEvents, t);
      mouth.setAttribute("d", MOUTHS[f.face] || MOUTHS.smile);
    },
  };
}

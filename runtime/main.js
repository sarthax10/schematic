// Runtime entry. Loads a resolved timeline (pipeline/timeline.py), builds every scene's DOM
// once, then exposes window.seek(t): the single function that puts the whole frame into
// its exact state at time t. The renderer calls seek() per frame; preview mode calls it
// from an audio-clocked playback loop.
import { clamp, css, ease, el, prog, splitWords, wordsIn } from "./core.js";

const ENTER = 0.5; // incoming scene rises in over this long
const EXIT_TAIL = 0.35; // outgoing scene fades over this long, overlapping the next one

const params = new URLSearchParams(location.search);
const timeline = await (await fetch(params.get("timeline") || "timeline.json")).json();

await Promise.all([
  document.fonts.load('700 40px "Bricolage Grotesque"'),
  document.fonts.load('500 40px "JetBrains Mono"'),
]);
await document.fonts.ready;

const scenesRoot = document.getElementById("scenes");
const progressRoot = document.getElementById("progress");
const capNode = document.querySelector("#captions .cap");
const gridNode = document.getElementById("grid");

const built = [];
for (const scene of timeline.scenes) {
  const root = el("div", "scene", scenesRoot);
  let headingWords = null;
  if (scene.heading) headingWords = splitWords(el("div", "heading", root), scene.heading);
  const stage = el("div", "stage", root);
  const mod = await import(`./scenes/${scene.type}.js`);
  const update = mod.build(stage, scene, root);
  const seg = el("div", "seg", progressRoot);
  built.push({ scene, root, stage, update, headingWords, fill: el("div", "fill", seg) });
}

let lastCap = null;

function seek(t) {
  // Background grid drifts very slowly — enough to feel alive, never enough to notice.
  css(gridNode, { transform: `translate(${(-(t * 6) % 44).toFixed(2)}px, ${(-(t * 10) % 44).toFixed(2)}px)` });

  for (const b of built) {
    const { start, duration } = b.scene;
    const end = start + duration;
    const lt = t - start;
    const visible = t >= start && t < end + EXIT_TAIL;
    css(b.root, { display: visible ? "block" : "none" });
    css(b.fill, { width: `${(clamp(lt / duration) * 100).toFixed(2)}%` });
    if (!visible) continue;

    const enter = start === 0 ? prog(lt, 0, 0.3) : prog(lt, 0, ENTER, ease.outCubic);
    const exit = t > end ? prog(t, end, EXIT_TAIL, ease.inCubic) : 0;
    // A slow camera push over the scene's life, so no frame is ever perfectly static.
    const push = 1 + 0.022 * ease.inOutSine(clamp(lt / duration));
    css(b.root, {
      opacity: String((enter * (1 - exit)).toFixed(4)),
      transform: `translateY(${((1 - enter) * 60 - exit * 30).toFixed(2)}px)`,
    });
    css(b.stage, { transform: `scale(${push.toFixed(4)})` });
    if (b.headingWords) wordsIn(b.headingWords, lt, 0.08, 0.05);
    b.update(lt);
  }

  let cap = null;
  for (const c of timeline.captions) {
    if (t >= c.start && t < c.end) cap = c;
  }
  if (cap !== lastCap) {
    capNode.textContent = cap ? cap.text : "";
    lastCap = cap;
  }
  css(capNode, { opacity: cap ? String(prog(t, cap.start, 0.1).toFixed(3)) : "0" });
}

window.seek = seek;
window.__timeline = { duration: timeline.duration, fps: timeline.fps };
seek(0);
window.__ready = true;

// ---- preview mode: scaled to fit, played against the narration audio's own clock ----
if (params.get("mode") === "preview") {
  document.body.classList.add("preview");
  const frame = document.getElementById("frame");
  const viewport = document.getElementById("viewport");
  const controls = document.getElementById("controls");
  controls.hidden = false;
  const fit = () => {
    const s = Math.min((innerHeight - 70) / 1920, innerWidth / 1080);
    frame.style.transform = `scale(${s})`;
    viewport.style.width = `${1080 * s}px`;
    viewport.style.height = `${1920 * s}px`;
  };
  addEventListener("resize", fit);
  fit();

  const audio = new Audio(new URL(timeline.audio || "narration.m4a", new URL(params.get("timeline") || "timeline.json", location.href)).href);
  const play = document.getElementById("play");
  const scrub = document.getElementById("scrub");
  const clock = document.getElementById("clock");
  const show = (t) => {
    seek(t);
    scrub.value = String(Math.round((t / timeline.duration) * 1000));
    clock.textContent = `${t.toFixed(1)}s`;
  };
  const loop = () => {
    show(audio.currentTime);
    if (!audio.paused) requestAnimationFrame(loop);
  };
  play.addEventListener("click", () => {
    if (audio.paused) { audio.play(); play.textContent = "Pause"; requestAnimationFrame(loop); }
    else { audio.pause(); play.textContent = "Play"; }
  });
  audio.addEventListener("ended", () => { play.textContent = "Play"; });
  scrub.addEventListener("input", () => {
    audio.currentTime = (Number(scrub.value) / 1000) * timeline.duration;
    show(audio.currentTime);
  });
  const t0 = Number(params.get("t"));
  if (t0) {
    show(t0);
    audio.addEventListener("loadedmetadata", () => { audio.currentTime = t0; show(t0); }, { once: true });
  }
}

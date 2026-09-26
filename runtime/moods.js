// Moods: each scene's environment. Variety between scenes comes mostly from here (light vs
// dark, warm vs cool), while the tones (signal/ok/fail/sky/lavender) keep one meaning across
// every mood so the video stays one coherent system.
export const MOODS = {
  // Tech/system scenes: petrol night, dot grid.
  night: {
    ground: "#11222a", ground2: "#0c1a20", pattern: "dots", patternColor: "#1f3640",
    ink: [232, 239, 240], ink2: [169, 189, 194], muted: [111, 135, 142],
    panel: [22, 38, 44], edge: [39, 64, 73], wire: [52, 80, 90], floor: "#16303a",
  },
  // Real-life analogy scenes, daylight: pale sage, fine paper grid, dark ink.
  day: {
    ground: "#e4ece8", ground2: "#d3e0da", pattern: "grid", patternColor: "#d2ded8",
    ink: [19, 38, 45], ink2: [58, 84, 92], muted: [110, 134, 138],
    panel: [248, 251, 250], edge: [196, 213, 207], wire: [150, 172, 168], floor: "#c9d8d1",
  },
  // Analogy scenes, evening: warm plum, soft bokeh circles.
  dusk: {
    ground: "#2b1d33", ground2: "#3b2439", pattern: "bokeh", patternColor: "rgba(255,190,120,0.10)",
    ink: [247, 236, 228], ink2: [214, 190, 196], muted: [160, 132, 146],
    panel: [55, 36, 60], edge: [92, 64, 94], wire: [110, 80, 108], floor: "#3f2a45",
  },
  // The key insight, used once: full amber field, dark ink.
  signal: {
    ground: "#ffb23e", ground2: "#f59e1f", pattern: "stripes", patternColor: "rgba(27,20,8,0.05)",
    ink: [27, 20, 8], ink2: [74, 52, 18], muted: [120, 88, 40],
    panel: [255, 214, 150], edge: [214, 140, 30], wire: [150, 100, 30], floor: "#e89a2a",
  },
};

export const mood = (name) => MOODS[name] || MOODS.night;

const PATTERNS = {
  dots: (c) => `radial-gradient(circle, ${c} 2.4px, transparent 2.9px) 0 0 / 44px 44px`,
  grid: (c) => `linear-gradient(${c} 2px, transparent 2px) 0 0 / 60px 60px, linear-gradient(90deg, ${c} 2px, transparent 2px) 0 0 / 60px 60px`,
  stripes: (c) => `repeating-linear-gradient(135deg, ${c} 0 18px, transparent 18px 44px)`,
  bokeh: (c) =>
    `radial-gradient(circle, ${c} 0 5px, transparent 6px) 0 0 / 140px 110px, radial-gradient(circle, ${c} 0 16px, transparent 17px) 70px 55px / 280px 220px`,
};

export function applyMood(sceneEl, bgEl, patternEl, name) {
  const m = mood(name);
  const c = (a) => `rgb(${a[0]},${a[1]},${a[2]})`;
  sceneEl.style.setProperty("--ink", c(m.ink));
  sceneEl.style.setProperty("--ink-2", c(m.ink2));
  sceneEl.style.setProperty("--muted", c(m.muted));
  sceneEl.style.setProperty("--panel", c(m.panel));
  sceneEl.style.setProperty("--panel-edge", c(m.edge));
  sceneEl.style.setProperty("--wire", c(m.wire));
  sceneEl.style.setProperty("--floor", m.floor);
  bgEl.style.background = `radial-gradient(ellipse 90% 60% at 50% 38%, ${m.ground} 0%, ${m.ground2} 100%)`;
  patternEl.style.background = PATTERNS[m.pattern](m.patternColor);
}

// Prop illustration library. One style for everything: flat fills, rounded geometry, one
// shade tone per colour for form (no gradients, no outlines), a soft contact shadow. Every
// prop is drawn on a 200-wide box so `size` (in grid units) means the same for all of them.
// Props with live parts expose `tick(t, root, state)`; state comes from `state` beats
// (e.g. jar {count: 3}, door {open: true}).
export const C = {
  amber: "#ffb23e", amberD: "#df8d1a", mint: "#6bdda8", mintD: "#3db07f", coral: "#ff6f61", coralD: "#d94a3e",
  sky: "#7cc4ff", skyD: "#4b98dc", lav: "#b9a2ff", lavD: "#8c72e0", sand: "#f2d6a2", sandD: "#d6b377",
  wood: "#b7794a", woodD: "#8a5731", slate: "#3b5560", slateD: "#28404a", steel: "#a8bcc3", steelD: "#71898f",
  white: "#f7faf9", whiteD: "#dbe5e2", ink: "#16262c", glass: "rgba(200,235,255,0.22)", glassEdge: "rgba(220,242,255,0.75)",
};

const shadow = (cx, cy, rx) => `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${rx * 0.12}" fill="rgba(0,0,0,0.18)"/>`;

const TICKET = (x, y, r = 0, s = 1) =>
  `<g transform="translate(${x} ${y}) rotate(${r}) scale(${s})"><path d="M-22 -12h44v7a5 5 0 0 0 0 10v7h-44v-7a5 5 0 0 0 0-10z" fill="${C.amber}"/><path d="M8 -12v24" stroke="${C.amberD}" stroke-width="2.5" stroke-dasharray="3 3"/><rect x="-16" y="-3" width="16" height="6" rx="2" fill="${C.amberD}"/></g>`;

export const PROPS = {
  jar: {
    h: 230,
    svg: () => `${shadow(100, 222, 70)}
      <rect x="40" y="40" width="120" height="180" rx="30" fill="${C.glass}" stroke="${C.glassEdge}" stroke-width="5"/>
      <g class="slots">${[
        [100, 196, -6], [74, 170, 8], [124, 172, -10], [98, 146, 4], [76, 120, -8], [122, 118, 10],
      ].map(([x, y, r], i) => `<g class="slot" data-i="${i}">${TICKET(x, y, r, 1)}</g>`).join("")}</g>
      <rect x="32" y="22" width="136" height="26" rx="10" fill="${C.wood}"/><rect x="32" y="40" width="136" height="8" rx="3" fill="${C.woodD}"/>
      <rect x="52" y="60" width="12" height="120" rx="6" fill="rgba(255,255,255,0.35)"/>`,
    tick(t, root, st) {
      const n = st.count ?? 6;
      root.querySelectorAll(".slot").forEach((g) => {
        g.style.opacity = Number(g.dataset.i) < n ? "1" : "0";
      });
    },
  },
  ticket: { h: 110, svg: () => `<g transform="translate(100 55) scale(3.6)">${TICKET(0, 0)}</g>` },
  token: {
    h: 200,
    svg: () => `${shadow(100, 192, 60)}<circle cx="100" cy="100" r="82" fill="${C.amberD}"/><circle cx="100" cy="92" r="82" fill="${C.amber}"/>
      <circle cx="100" cy="92" r="56" fill="none" stroke="${C.amberD}" stroke-width="8"/><path d="M100 62v60M80 80l20-18 20 18" stroke="${C.amberD}" stroke-width="10" stroke-linecap="round" fill="none"/>`,
  },
  bucket: {
    h: 210,
    svg: () => `${shadow(100, 204, 72)}<path d="M52 44 Q100 -14 148 44" fill="none" stroke="${C.steelD}" stroke-width="8"/>
      <path d="M30 50h140l-18 146a10 10 0 0 1-10 9H58a10 10 0 0 1-10-9z" fill="${C.sky}"/><path d="M30 50h140l-4 32H34z" fill="${C.skyD}"/>
      <rect x="22" y="42" width="156" height="18" rx="9" fill="${C.skyD}"/><rect x="60" y="92" width="12" height="90" rx="6" fill="rgba(255,255,255,0.3)"/>`,
  },
  cup: {
    h: 220,
    svg: () => `${shadow(100, 214, 58)}
      <g class="steam" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="7" stroke-linecap="round"><path d="M80 34c-10-12 10-18 0-30"/><path d="M104 38c-10-12 10-18 0-30"/><path d="M128 34c-10-12 10-18 0-30"/></g>
      <path d="M48 70h104l-14 136a10 10 0 0 1-10 9H72a10 10 0 0 1-10-9z" fill="${C.white}"/>
      <path d="M53 120h94l-5 50H58z" fill="${C.wood}"/><rect x="40" y="52" width="120" height="24" rx="10" fill="${C.whiteD}"/>`,
    tick(t, root) {
      root.querySelector(".steam").style.transform = `translateY(${(-4 * Math.sin(t * 2.2)).toFixed(2)}px)`;
      root.querySelector(".steam").style.opacity = String((0.6 + 0.4 * Math.sin(t * 1.7)).toFixed(3));
    },
  },
  "shop-counter": {
    h: 92,
    svg: () => `<rect x="4" y="18" width="192" height="74" rx="6" fill="${C.woodD}"/><rect x="0" y="6" width="200" height="18" rx="7" fill="${C.sand}"/><rect x="0" y="20" width="200" height="5" fill="${C.sandD}"/>
      ${[0, 1, 2, 3, 4, 5, 6, 7].map((i) => `<rect x="${14 + i * 22.5}" y="34" width="12" height="50" rx="6" fill="${C.wood}"/>`).join("")}`,
  },
  shop: {
    h: 220,
    svg: () => `${shadow(100, 216, 96)}<rect x="10" y="60" width="180" height="152" rx="6" fill="${C.white}"/>
      <path d="M0 30h200v34H0z" fill="${C.amber}"/>${[0, 1, 2, 3, 4].map((i) => `<path d="M${i * 40 + 20} 30h20v34h-20z" fill="${C.white}"/>`).join("")}
      ${[0, 1, 2, 3, 4].map((i) => `<path d="M${i * 40} 64a20 16 0 0 0 40 0z" fill="${i % 2 ? C.white : C.amber}"/>`).join("")}
      <rect x="24" y="100" width="84" height="64" rx="6" fill="${C.sky}"/><path d="M30 150l22-28 18 18 12-10 20 20z" fill="rgba(255,255,255,0.35)"/>
      <rect x="124" y="104" width="52" height="108" rx="6" fill="${C.slate}"/><circle cx="166" cy="160" r="4" fill="${C.amber}"/>`,
  },
  door: {
    h: 240,
    svg: () => `${shadow(100, 236, 80)}<rect x="30" y="10" width="140" height="226" rx="10" fill="${C.slateD}"/>
      <g class="leaf"><rect x="44" y="24" width="112" height="212" rx="6" fill="${C.coral}"/><rect x="60" y="44" width="80" height="70" rx="6" fill="${C.coralD}"/><rect x="60" y="130" width="80" height="80" rx="6" fill="${C.coralD}"/><circle cx="140" cy="126" r="7" fill="${C.amber}"/></g>`,
    tick(t, root, st) {
      const leaf = root.querySelector(".leaf");
      leaf.style.transformOrigin = "44px 130px";
      leaf.style.transform = `scaleX(${st.open ? 0.25 : 1})`;
    },
  },
  phone: {
    h: 300,
    svg: () => `${shadow(100, 294, 60)}<rect x="46" y="10" width="108" height="280" rx="22" fill="${C.slateD}"/><rect x="54" y="22" width="92" height="256" rx="14" fill="${C.sky}"/>
      <rect x="80" y="30" width="40" height="8" rx="4" fill="${C.slateD}"/><rect x="66" y="60" width="68" height="44" rx="8" fill="rgba(255,255,255,0.5)"/>
      <rect x="66" y="116" width="68" height="10" rx="5" fill="rgba(255,255,255,0.4)"/><rect x="66" y="134" width="48" height="10" rx="5" fill="rgba(255,255,255,0.4)"/>
      <rect x="66" y="230" width="68" height="26" rx="13" fill="${C.amber}"/>`,
  },
  laptop: {
    h: 160,
    svg: () => `${shadow(100, 156, 100)}<rect x="24" y="8" width="152" height="112" rx="10" fill="${C.slateD}"/><rect x="32" y="16" width="136" height="96" rx="5" fill="${C.ink}"/>
      <rect x="42" y="30" width="60" height="8" rx="4" fill="${C.mint}"/><rect x="42" y="46" width="96" height="8" rx="4" fill="${C.sky}"/><rect x="52" y="62" width="70" height="8" rx="4" fill="${C.lav}"/><rect x="52" y="78" width="50" height="8" rx="4" fill="${C.amber}"/>
      <path d="M4 124h192l-10 22H14z" fill="${C.steel}"/><rect x="80" y="124" width="40" height="6" rx="3" fill="${C.steelD}"/>`,
  },
  server: {
    h: 260,
    svg: () => `${shadow(100, 254, 80)}<rect x="30" y="10" width="140" height="240" rx="14" fill="${C.slateD}"/>
      ${[0, 1, 2, 3].map((i) => `<rect x="42" y="${24 + i * 56}" width="116" height="44" rx="8" fill="${C.slate}"/><rect x="56" y="${40 + i * 56}" width="50" height="10" rx="5" fill="${C.slateD}"/><circle class="led" data-i="${i}" cx="140" cy="${46 + i * 56}" r="7" fill="${C.mint}"/>`).join("")}`,
    tick(t, root) {
      root.querySelectorAll(".led").forEach((l) => {
        const i = Number(l.dataset.i);
        l.style.opacity = Math.sin(t * (5 + i * 1.7) + i * 2) > -0.2 ? "1" : "0.25";
      });
    },
  },
  database: {
    h: 230,
    svg: () => `${shadow(100, 224, 76)}${[2, 1, 0].map((i) => `<path d="M26 ${70 + i * 52}v44c0 14 33 24 74 24s74-10 74-24v-44" fill="${i % 2 ? C.skyD : C.sky}"/>`).join("")}
      <path d="M26 44v26c0 14 33 24 74 24s74-10 74-24V44" fill="${C.sky}"/><ellipse cx="100" cy="44" rx="74" ry="24" fill="${C.white}"/><ellipse cx="100" cy="44" rx="54" ry="14" fill="${C.whiteD}"/>`,
  },
  cloud: {
    h: 130,
    svg: () => `<path d="M48 120h112a36 36 0 0 0 4-72 50 50 0 0 0-94-8 40 40 0 0 0-22 80z" fill="${C.white}"/><path d="M48 120h112a36 36 0 0 0 30-18H22a40 40 0 0 0 26 18z" fill="${C.whiteD}"/>`,
  },
  globe: {
    h: 200,
    svg: () => `${shadow(100, 196, 60)}<circle cx="100" cy="96" r="84" fill="${C.sky}"/><path d="M50 50c20 10 30 30 16 44s6 30 26 34-4 34 8 46M140 30c-6 20 14 30 30 34M120 150c14-10 30-6 44-18" stroke="${C.mint}" stroke-width="18" stroke-linecap="round" fill="none"/>
      <ellipse cx="100" cy="96" rx="36" ry="84" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="4"/><path d="M16 96h168" stroke="rgba(255,255,255,0.4)" stroke-width="4"/>`,
  },
  clock: {
    h: 200,
    svg: () => `${shadow(100, 196, 60)}<circle cx="100" cy="98" r="86" fill="${C.slateD}"/><circle cx="100" cy="98" r="72" fill="${C.white}"/>
      ${Array.from({ length: 12 }, (_, i) => `<rect x="97" y="32" width="6" height="${i % 3 ? 8 : 16}" rx="3" fill="${C.slate}" transform="rotate(${i * 30} 100 98)"/>`).join("")}
      <rect class="hh" x="96" y="60" width="8" height="42" rx="4" fill="${C.ink}"/><rect class="mh" x="97.5" y="42" width="5" height="60" rx="2.5" fill="${C.coral}"/><circle cx="100" cy="98" r="8" fill="${C.ink}"/>`,
    tick(t, root, st) {
      const speed = st.fast ? 360 : 30;
      root.querySelector(".mh").setAttribute("transform", `rotate(${(t * speed) % 360} 100 98)`);
      root.querySelector(".hh").setAttribute("transform", `rotate(${(t * speed) / 12 % 360} 100 98)`);
    },
  },
  hourglass: {
    h: 230,
    svg: () => `${shadow(100, 226, 60)}<rect x="40" y="10" width="120" height="16" rx="8" fill="${C.wood}"/><rect x="40" y="204" width="120" height="16" rx="8" fill="${C.wood}"/>
      <path d="M56 26h88c0 50-36 60-36 89s36 39 36 89H56c0-50 36-60 36-89S56 76 56 26z" fill="${C.glass}" stroke="${C.glassEdge}" stroke-width="4"/>
      <path class="top" d="M68 44h64c-4 30-26 40-32 62-6-22-28-32-32-62z" fill="${C.amber}"/><path class="bottom" d="M66 196h68c-4-22-20-30-34-40-14 10-30 18-34 40z" fill="${C.amber}"/>`,
  },
  box: {
    h: 180,
    svg: () => `${shadow(100, 174, 86)}<path d="M20 60l80-34 80 34v96l-80 16-80-16z" fill="${C.sand}"/><path d="M100 94v78l80-16V60z" fill="${C.sandD}"/><path d="M20 60l80 34 80-34-80-34z" fill="#f8e3bc"/>
      <path d="M58 43l80 34v28l-18 -6v-24L42 50z" fill="${C.amber}"/>`,
  },
  envelope: {
    h: 140,
    svg: () => `${shadow(100, 136, 90)}<rect x="10" y="14" width="180" height="116" rx="10" fill="${C.white}"/><path d="M10 124l72-56h36l72 56z" fill="${C.whiteD}"/><path d="M14 20l86 64 86-64" fill="none" stroke="${C.steel}" stroke-width="6" stroke-linejoin="round"/><circle cx="160" cy="44" r="12" fill="${C.coral}"/>`,
  },
  truck: {
    h: 130,
    svg: () => `${shadow(100, 126, 96)}<rect x="4" y="10" width="124" height="88" rx="8" fill="${C.white}"/><rect x="20" y="28" width="56" height="10" rx="5" fill="${C.amber}"/>
      <path d="M128 36h38l26 30v32h-64z" fill="${C.coral}"/><path d="M140 46h22l16 20h-38z" fill="${C.sky}"/>
      ${[40, 156].map((x) => `<circle cx="${x}" cy="104" r="18" fill="${C.ink}"/><circle cx="${x}" cy="104" r="7" fill="${C.steel}"/>`).join("")}`,
  },
  house: {
    h: 200,
    svg: () => `${shadow(100, 196, 84)}<path d="M28 90h144v104H28z" fill="${C.sand}"/><path d="M10 96L100 22l90 74z" fill="${C.coral}"/><path d="M100 22l90 74h-22L100 40z" fill="${C.coralD}"/>
      <rect x="84" y="130" width="34" height="64" rx="4" fill="${C.slate}"/><rect x="44" y="116" width="28" height="28" rx="4" fill="${C.sky}"/><rect x="130" y="116" width="28" height="28" rx="4" fill="${C.sky}"/>`,
  },
  book: {
    h: 150,
    svg: () => `${shadow(100, 146, 76)}<rect x="30" y="10" width="140" height="130" rx="8" fill="${C.lavD}"/><rect x="40" y="10" width="130" height="122" rx="6" fill="${C.lav}"/><rect x="62" y="36" width="84" height="14" rx="7" fill="rgba(255,255,255,0.6)"/><rect x="62" y="60" width="56" height="10" rx="5" fill="rgba(255,255,255,0.4)"/><rect x="40" y="128" width="130" height="8" fill="${C.white}"/>`,
  },
  shelf: {
    h: 230,
    svg: () => `${shadow(100, 226, 96)}<rect x="8" y="8" width="184" height="216" rx="8" fill="${C.woodD}"/>
      ${[0, 1, 2].map((r) => `<rect x="18" y="${76 + r * 70}" width="164" height="8" fill="${C.wood}"/>` +
        [0, 1, 2, 3, 4, 5, 6].map((i) => `<rect x="${24 + i * 22}" y="${24 + r * 70 + (i % 3) * 6}" width="18" height="${52 - (i % 3) * 6}" rx="3" fill="${[C.coral, C.sky, C.amber, C.mint, C.lav, C.sand, C.coralD][(i + r * 2) % 7]}"/>`).join("")).join("")}`,
  },
  lightbulb: {
    h: 220,
    svg: () => `<circle class="glow" cx="100" cy="84" r="96" fill="rgba(255,178,62,0.18)"/><path d="M100 14a66 66 0 0 0-38 120c8 6 12 14 12 24h52c0-10 4-18 12-24a66 66 0 0 0-38-120z" fill="${C.amber}"/>
      <path d="M78 110l12 14 10-14 10 14 12-14" fill="none" stroke="${C.amberD}" stroke-width="6" stroke-linejoin="round"/><rect x="74" y="162" width="52" height="16" rx="6" fill="${C.steel}"/><rect x="80" y="182" width="40" height="16" rx="6" fill="${C.steelD}"/>`,
    tick(t, root) {
      root.querySelector(".glow").style.opacity = String((0.7 + 0.3 * Math.sin(t * 3)).toFixed(3));
    },
  },
  key: {
    h: 110,
    svg: () => `<circle cx="50" cy="55" r="38" fill="${C.amber}"/><circle cx="50" cy="55" r="14" fill="${C.amberD}"/><path d="M84 46h104v18h-16v20h-18V64h-14v14h-18V64H84z" fill="${C.amber}"/>`,
  },
  lock: {
    h: 220,
    svg: () => `${shadow(100, 216, 70)}<path class="shackle" d="M56 100V70a44 44 0 0 1 88 0v30" fill="none" stroke="${C.steel}" stroke-width="20"/><rect x="30" y="96" width="140" height="116" rx="20" fill="${C.amber}"/><rect x="30" y="180" width="140" height="32" rx="16" fill="${C.amberD}"/><circle cx="100" cy="140" r="14" fill="${C.ink}"/><rect x="94" y="140" width="12" height="30" rx="5" fill="${C.ink}"/>`,
    tick(t, root, st) {
      root.querySelector(".shackle").style.transform = st.open ? "translateY(-26px)" : "none";
    },
  },
  magnifier: {
    h: 200,
    svg: () => `<rect x="118" y="120" width="24" height="84" rx="12" fill="${C.wood}" transform="rotate(-45 130 162)"/><circle cx="84" cy="84" r="66" fill="${C.glass}" stroke="${C.slate}" stroke-width="16"/><path d="M50 70a36 36 0 0 1 30-28" stroke="rgba(255,255,255,0.6)" stroke-width="8" stroke-linecap="round" fill="none"/>`,
  },
  doc: {
    h: 250,
    svg: () => `${shadow(100, 246, 76)}<path d="M28 10h110l34 34v196H28z" fill="${C.white}"/><path d="M138 10v34h34z" fill="${C.whiteD}"/>
      ${[70, 96, 122, 148, 174].map((y, i) => `<rect x="48" y="${y}" width="${[104, 84, 110, 70, 96][i]}" height="10" rx="5" fill="${i === 0 ? C.sky : C.whiteD}"/>`).join("")}`,
  },
  gear: {
    h: 200,
    svg: () => `<g class="rot">${Array.from({ length: 8 }, (_, i) => `<rect x="86" y="8" width="28" height="40" rx="6" fill="${C.steelD}" transform="rotate(${i * 45} 100 100)"/>`).join("")}<circle cx="100" cy="100" r="66" fill="${C.steel}"/><circle cx="100" cy="100" r="24" fill="${C.slateD}"/></g>`,
    tick(t, root) {
      root.querySelector(".rot").setAttribute("transform", `rotate(${(t * 40) % 360} 100 100)`);
    },
  },
  bell: {
    h: 150,
    svg: () => `${shadow(100, 146, 86)}<rect x="10" y="118" width="180" height="24" rx="10" fill="${C.woodD}"/><path d="M28 118a72 72 0 0 1 144 0z" fill="${C.amber}"/><path d="M28 118a72 72 0 0 1 20-50c-4 16-4 34 0 50z" fill="${C.amberD}"/><rect x="92" y="28" width="16" height="20" rx="6" fill="${C.amberD}"/>`,
  },
  plant: {
    h: 230,
    svg: () => `${shadow(100, 226, 60)}<g class="leaves"><path d="M100 130C70 90 40 90 30 60c40 0 64 30 70 70z" fill="${C.mintD}"/><path d="M100 130c30-40 60-50 72-86-42 6-66 40-72 86z" fill="${C.mint}"/><path d="M100 136c-10-50 0-90 10-120 20 40 8 90-10 120z" fill="${C.mint}"/></g>
      <path d="M58 136h84l-12 88H70z" fill="${C.coral}"/><rect x="52" y="128" width="96" height="18" rx="6" fill="${C.coralD}"/>`,
    tick(t, root) {
      const l = root.querySelector(".leaves");
      l.style.transformOrigin = "100px 136px";
      l.style.transform = `rotate(${(1.5 * Math.sin(t * 1.3)).toFixed(3)}deg)`;
    },
  },
  "traffic-light": {
    h: 300,
    svg: () => `${shadow(100, 296, 40)}<rect x="92" y="200" width="16" height="96" fill="${C.slate}"/><rect x="56" y="10" width="88" height="200" rx="24" fill="${C.slateD}"/>
      <circle class="l0" cx="100" cy="52" r="24"/><circle class="l1" cx="100" cy="110" r="24"/><circle class="l2" cx="100" cy="168" r="24"/>`,
    tick(t, root, st) {
      const on = st.light ?? "green";
      root.querySelector(".l0").setAttribute("fill", on === "red" ? C.coral : "#4a2a2a");
      root.querySelector(".l1").setAttribute("fill", on === "amber" ? C.amber : "#4a3a1f");
      root.querySelector(".l2").setAttribute("fill", on === "green" ? C.mint : "#1f4a38");
    },
  },
  pin: {
    h: 240,
    svg: () => `${shadow(100, 236, 30)}<path d="M100 232C60 170 30 130 30 90a70 70 0 0 1 140 0c0 40-30 80-70 142z" fill="${C.coral}"/><circle cx="100" cy="88" r="28" fill="${C.white}"/>`,
  },
  printer: {
    h: 200,
    svg: () => `${shadow(100, 196, 86)}<rect x="50" y="10" width="100" height="62" rx="6" fill="${C.white}"/>
      <rect x="16" y="58" width="168" height="98" rx="18" fill="${C.slate}"/><rect x="16" y="58" width="168" height="30" rx="14" fill="${C.slateD}"/>
      <rect x="38" y="126" width="124" height="14" rx="7" fill="${C.ink}"/>
      <g class="page"><rect x="52" y="132" width="96" height="58" rx="4" fill="${C.white}"/><rect x="64" y="146" width="56" height="6" rx="3" fill="${C.whiteD}"/><rect x="64" y="160" width="72" height="6" rx="3" fill="${C.whiteD}"/></g>
      <circle class="led" cx="160" cy="104" r="7" fill="${C.mint}"/>`,
    tick(t, root) {
      root.querySelector(".led").style.opacity = Math.sin(t * 6) > -0.3 ? "1" : "0.3";
      root.querySelector(".page").style.transform = `translateY(${(4 * Math.sin(t * 2.4)).toFixed(2)}px)`;
    },
  },
  conveyor: {
    h: 120,
    svg: () => `${shadow(100, 116, 98)}<rect x="30" y="80" width="10" height="34" rx="4" fill="${C.steelD}"/><rect x="160" y="80" width="10" height="34" rx="4" fill="${C.steelD}"/>
      <rect x="2" y="38" width="196" height="46" rx="23" fill="${C.slateD}"/>
      <clipPath id="beltclip"><rect x="10" y="38" width="180" height="12" rx="4"/></clipPath>
      <g clip-path="url(#beltclip)"><g class="belt">${Array.from({ length: 10 }, (_, i) => `<rect x="${i * 24 - 12}" y="38" width="12" height="12" rx="2" fill="${C.steel}"/>`).join("")}</g></g>
      ${[26, 100, 174].map((x) => `<circle cx="${x}" cy="62" r="13" fill="${C.steel}"/><circle cx="${x}" cy="62" r="4" fill="${C.slateD}"/>`).join("")}`,
    tick(t, root) {
      root.querySelector(".belt").setAttribute("transform", `translate(${((t * 36) % 24).toFixed(2)} 0)`);
    },
  },
  crowd: {
    h: 150,
    svg: () => [0, 1, 2, 3, 4].map((i) => {
      const x = 20 + i * 40, col = [C.sky, C.coral, C.mint, C.lav, C.amber][i];
      return `<rect x="${x - 16}" y="${70 + (i % 2) * 8}" width="32" height="80" rx="14" fill="${col}"/><circle cx="${x}" cy="${52 + (i % 2) * 8}" r="16" fill="${["#f1c7a5", "#c98e6a", "#8a5a3c", "#f1c7a5", "#c98e6a"][i]}"/>`;
    }).join(""),
  },
};

export const PROP_NAMES = Object.keys(PROPS);

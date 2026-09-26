// House icon set: one 24×24 grid, 1.6 stroke, round caps/joins, no fills — every icon is
// drawn to the same rules so a diagram never mixes visual languages. `currentColor` lets
// a node recolour its icon when highlighted.
const P = {
  client: '<rect x="6.5" y="2.5" width="11" height="19" rx="2.6"/><path d="M10.5 18.5h3"/>',
  browser: '<rect x="2.5" y="4" width="19" height="16" rx="2.6"/><path d="M2.5 8.5h19"/><path d="M5.5 6.25h.01M7.8 6.25h.01"/>',
  user: '<circle cx="12" cy="8" r="3.6"/><path d="M4.8 20.2c1.3-3.7 4-5.6 7.2-5.6s5.9 1.9 7.2 5.6"/>',
  server: '<rect x="3.5" y="4" width="17" height="6.5" rx="1.6"/><rect x="3.5" y="13.5" width="17" height="6.5" rx="1.6"/><path d="M7 7.25h.01M7 16.75h.01M11 7.25h6M11 16.75h6"/>',
  api: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M9.2 9.2 6.4 12l2.8 2.8M14.8 9.2l2.8 2.8-2.8 2.8M12.9 8.6l-1.8 6.8"/>',
  database: '<ellipse cx="12" cy="5.6" rx="7.5" ry="2.8"/><path d="M4.5 5.6v12.8c0 1.55 3.36 2.8 7.5 2.8s7.5-1.25 7.5-2.8V5.6"/><path d="M4.5 12c0 1.55 3.36 2.8 7.5 2.8s7.5-1.25 7.5-2.8"/>',
  cache: '<rect x="3.5" y="3.5" width="17" height="17" rx="3.2"/><path d="M13.1 6.6 8.7 13h3.6l-1.3 4.4 4.4-6.4h-3.6z"/>',
  queue: '<rect x="2.8" y="7" width="4.6" height="10" rx="1.2"/><rect x="9.7" y="7" width="4.6" height="10" rx="1.2"/><rect x="16.6" y="7" width="4.6" height="10" rx="1.2"/>',
  load_balancer: '<circle cx="12" cy="4.8" r="2.3"/><path d="M12 7.1v4.4M12 11.5 5.5 16.6M12 11.5l6.5 5.1M12 11.5v5.1"/><circle cx="5.2" cy="18.8" r="2"/><circle cx="12" cy="18.8" r="2"/><circle cx="18.8" cy="18.8" r="2"/>',
  cdn: '<circle cx="12" cy="12" r="8.6"/><ellipse cx="12" cy="12" rx="3.7" ry="8.6"/><path d="M3.6 12h16.8M5 7.5h14M5 16.5h14"/>',
  gateway: '<path d="M4 20V9.5L12 4l8 5.5V20"/><path d="M9 20v-6h6v6"/><path d="M2.5 20h19"/>',
  worker: '<circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.6M12 18.6v2.6M2.8 12h2.6M18.6 12h2.6M5.5 5.5l1.85 1.85M16.65 16.65l1.85 1.85M5.5 18.5l1.85-1.85M16.65 7.35 18.5 5.5"/><circle cx="12" cy="12" r="6.3"/>',
  storage: '<path d="M4.3 6.6h15.4l-1.55 12.4a2 2 0 0 1-2 1.75H7.85a2 2 0 0 1-2-1.75z"/><path d="M3.5 6.6h17"/><path d="M9 3.4h6"/>',
  lock: '<rect x="5" y="10.5" width="14" height="10" rx="2.2"/><path d="M8.2 10.5V8a3.8 3.8 0 0 1 7.6 0v2.5M12 14.4v2.4"/>',
  function: '<path d="M6.5 20 12 10.6M8.3 4h1.9l7.3 16"/>',
  cloud: '<path d="M7.2 18.6h10a4.1 4.1 0 0 0 .55-8.16A5.6 5.6 0 0 0 7 9.7a4.46 4.46 0 0 0 .2 8.9z"/>',
  search: '<circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 5 5"/>',
  clock: '<circle cx="12" cy="12" r="8.6"/><path d="M12 7.4V12l3.1 2"/>',
  check: '<path d="m5 12.6 4.4 4.4L19 7.4"/>',
  alert: '<path d="M12 3.8 2.9 19.6h18.2z"/><path d="M12 10v4.4M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="8.6"/><path d="M12 11v5M12 8h.01"/>',
  cross: '<path d="m6.5 6.5 11 11M17.5 6.5l-11 11"/>',
};

export const ICON_NAMES = Object.keys(P);

export function icon(name) {
  const body = P[name] || P.server;
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

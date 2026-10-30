/* ---- Icons ---- */

const ICONS = {
  intent: '<circle cx="10" cy="10" r="6.5"/><circle cx="10" cy="10" r="2.5"/>',
  snap: '<path d="M5.5 17V3.5"/><path d="M5.5 4.5h9l-2 3 2 3h-9"/>',
  decision: '<path d="M10 2.8 17.2 10 10 17.2 2.8 10Z"/>',
  next: '<path d="M4 10h12M11 5l5 5-5 5"/>',
  blocker: '<path d="M10 3.2 17.6 16.5H2.4Z"/><path d="M10 8.3v3.6M10 14.1v.1"/>',
  clear: '<circle cx="10" cy="10" r="7"/><path d="m7 10.2 2 2 4-4.4"/>',
  boundary: '<rect x="3.5" y="3.5" width="13" height="13" rx="2.5" stroke-dasharray="2.4 2.2"/>',
  verified: '<path d="M10 2.8 16 5v4.6c0 3.6-2.5 6.2-6 7.6-3.5-1.4-6-4-6-7.6V5Z"/><path d="m7.4 10 1.8 1.8 3.5-3.6"/>',
  chevron: '<path d="m8 5 5 5-5 5"/>',
  chevronDown: '<path d="m5.5 8 4.5 4.5L14.5 8"/>',
  arrow: '<path d="M4 10h12M11 5l5 5-5 5"/>',
  copy: '<rect x="7" y="7" width="9.5" height="9.5" rx="2"/><path d="M13 7V5.5A1.5 1.5 0 0 0 11.5 4h-6A1.5 1.5 0 0 0 4 5.5v6A1.5 1.5 0 0 0 5.5 13H7"/>',
  key: '<circle cx="7" cy="13" r="3.5"/><path d="m9.5 10.5 7-7M14 6l2 2"/>',
  overview: '<rect x="3" y="3.5" width="14" height="13" rx="2"/><path d="M3 8h14M8.5 8v8.5"/>',
  timeline: '<path d="M6 3.5v13"/><circle cx="6" cy="6.5" r="1.7"/><circle cx="6" cy="13.5" r="1.7"/><path d="M10 6.5h7M10 13.5h7"/>',
  terminal: '<rect x="2.5" y="4" width="15" height="12" rx="2"/><path d="m6 8.5 2.5 2-2.5 2M10.5 13h3.5"/>',
  search: '<circle cx="9" cy="9" r="5.5"/><path d="m13.2 13.2 3.8 3.8"/>',
  flow: '<path d="M5.5 3v14"/><circle cx="14.5" cy="13" r="2.2"/><path d="M5.5 6.2c0 3.8 9 2.6 9 4.6"/>',
  focus: '<circle cx="10" cy="10" r="2.6"/><path d="M10 2.8v3M10 14.2v3M2.8 10h3M14.2 10h3"/>',
  hide: '<path d="M3 10s2.6-5 7-5 7 5 7 5-2.6 5-7 5-7-5-7-5Z"/><path d="m4 16 12-12"/>',
  history: '<path d="M3.6 10a6.4 6.4 0 1 0 1.9-4.6L3.5 7.3"/><path d="M3.5 3.7v3.6h3.6"/><path d="M10 6.6V10l2.4 1.5"/>',
  settings: '<path d="m8 2-.5 2-1.5.9-2-.6-2 3.4 1.5 1.4v1.8L2 12.3l2 3.4 2-.6 1.5.9.5 2h4l.5-2 1.5-.9 2 .6 2-3.4-1.5-1.4V9.1L18 7.7l-2-3.4-2 .6-1.5-.9-.5-2Z"/><circle cx="10" cy="10" r="2.5"/>',
  download: '<path d="M10 3.5v9M6 8.5l4 4 4-4"/><path d="M4 16h12"/>',
  external: '<path d="M8 4H4.5v11.5H16V12"/><path d="M11 4h5v5M16 4l-7 7"/>',
  sliders: '<path d="M3 6h6M13 6h4M3 14h3M10 14h7"/><circle cx="11" cy="6" r="2"/><circle cx="8" cy="14" r="2"/>',
  user: '<circle cx="10" cy="6.5" r="3"/><path d="M3.5 17v-1a6.5 6.5 0 0 1 13 0v1"/>',
  users: '<circle cx="7.5" cy="7" r="2.8"/><path d="M2.5 16.5v-.8a5 5 0 0 1 10 0v.8"/><path d="M13 4.6a2.8 2.8 0 0 1 0 4.8M14.8 11.6a5 5 0 0 1 2.7 4.1v.8"/>',
  userMinus: '<circle cx="8" cy="6.5" r="3"/><path d="M2.5 17v-1a5.5 5.5 0 0 1 11 0v1"/><path d="M13.5 8h5"/>',
  login: '<path d="M12 3.5h3.5v13H12"/><path d="M3 10h8.5M8 6.5l3.5 3.5L8 13.5"/>',
  logout: '<path d="M8 3.5H4.5v13H8"/><path d="M8.5 10H17M13.5 6.5 17 10l-3.5 3.5"/>',
  refresh: '<path d="M16 10a6 6 0 1 1-1.8-4.3L16 7.5"/><path d="M16 3.5v4h-4"/>',
  info: '<circle cx="10" cy="10" r="7"/><path d="M10 9v4.5M10 6.3v.1"/>',
  plus: '<path d="M10 4v12M4 10h12"/>',
  check: '<path d="m4.5 10.5 3.5 3.5 7.5-8"/>',
  gauge: '<path d="M3.5 14.5a7 7 0 1 1 13 0"/><path d="m10 12 3-4"/><circle cx="10" cy="12.5" r="1"/>',
  close: '<path d="m5 5 10 10M15 5 5 15"/>',
  trash: '<path d="M3.5 5.5h13M8 5.5v-2h4v2M5 5.5l.8 11h8.4l.8-11M8.5 8.5v5M11.5 8.5v5"/>',
  edit: '<path d="m4 16 .8-3.3L13 4.5a1.7 1.7 0 0 1 2.5 2.5l-8.2 8.2Z"/><path d="m11.5 6 2.5 2.5"/>',
  globe: '<circle cx="10" cy="10" r="7"/><path d="M3 10h14M10 3c2.2 2 3.2 4.4 3.2 7s-1 5-3.2 7c-2.2-2-3.2-4.4-3.2-7s1-5 3.2-7Z"/>',
  lock: '<rect x="4.5" y="9" width="11" height="8" rx="2"/><path d="M7 9V6.5a3 3 0 0 1 6 0V9"/>',
  transfer: '<path d="M3.5 7h12M12 3.5 15.5 7 12 10.5"/><path d="M16.5 13h-12M8 9.5 4.5 13 8 16.5"/>',
  link: '<path d="M8.5 11.5a3 3 0 0 0 4.3 0l2.2-2.2a3 3 0 0 0-4.3-4.3L9.5 6.2"/><path d="M11.5 8.5a3 3 0 0 0-4.3 0L5 10.7A3 3 0 0 0 9.3 15l1.2-1.2"/>',
  revoke: '<circle cx="10" cy="10" r="7"/><path d="m5 5 10 10"/>',
  sun: '<circle cx="10" cy="10" r="3.2"/><path d="M10 2.8v1.8M10 15.4v1.8M2.8 10h1.8M15.4 10h1.8M4.9 4.9l1.3 1.3M13.8 13.8l1.3 1.3M4.9 15.1l1.3-1.3M13.8 6.2l1.3-1.3"/>',
  moon: '<path d="M16.5 11.7a6.8 6.8 0 0 1-8.2-8.2 6.8 6.8 0 1 0 8.2 8.2Z"/>',
  monitor: '<rect x="3" y="4" width="14" height="10" rx="1.8"/><path d="M7 17h6M10 14v3"/>',
  contrast: '<circle cx="10" cy="10" r="7"/><path d="M10 3v14M10 6.5h6M10 10h7M10 13.5h6"/>',
  sparkle: '<path d="M10 3 11.7 8.3 17 10l-5.3 1.7L10 17l-1.7-5.3L3 10l5.3-1.7Z"/>',
  repository: '<path d="M4 15.8V5.2C4 4.2 4.8 3.5 5.8 3.5H16v10.8H5.7A1.7 1.7 0 0 0 4 16c0 .9.8 1.5 1.7 1.5H16v-3.2"/>',
  grid: '<rect x="3.5" y="3.5" width="5.5" height="5.5" rx="1.2"/><rect x="11" y="3.5" width="5.5" height="5.5" rx="1.2"/><rect x="3.5" y="11" width="5.5" height="5.5" rx="1.2"/><rect x="11" y="11" width="5.5" height="5.5" rx="1.2"/>',
  folder: '<path d="M3 15.5v-11h5l1.6 2H17v9Z"/>',
  arrowLeft: '<path d="M16 10H4M9 5l-5 5 5 5"/>',
};

function icon(name) {
  return `<svg viewBox="0 0 20 20" aria-hidden="true">${ICONS[name] || ""}</svg>`;
}

// Every action reads the same way: its icon, then its label. Only the label changes while it is busy.
function iconLabel(name, label) {
  return `${icon(name)}<span class="button-label">${esc(label)}</span>`;
}

function setButtonLabel(button, label) {
  (button.querySelector?.(":scope > .button-label") || button).textContent = label;
}

// The static markup names its icons, so the set stays in one place.
for (const node of document.querySelectorAll("[data-icon]")) node.insertAdjacentHTML("afterbegin", icon(node.dataset.icon));

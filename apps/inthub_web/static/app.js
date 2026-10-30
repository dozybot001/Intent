const { t } = window.IntHubI18n;
window.IntHubI18n.bindStatic(document.body);

/* ---- State ---- */

const TABS = ["overview", "intents", "flow", "snaps", "history", "decisions", "settings"];
const DETAIL_PATHS = { intent: "intents", decision: "decisions", snap: "snaps", revision: "revisions" };
const PAGE_SIZE = 30;
// One timeline page from /projects/{id}/snaps; the overview only carries the newest Snaps.
const SNAP_PAGE_SIZE = 50;
const REVISION_PAGE_SIZE = 30;
// Agents by name; any other label stays as the CLI recorded it.
const ORIGIN_NAMES = {
  "claude-code": "Claude Code", codex: "Codex", cursor: "Cursor", vscode: "VS Code",
  codespaces: "Codespaces", "github-actions": "GitHub Actions", gitpod: "Gitpod",
};
const INSTALL_COMMAND = "curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/scripts/install.sh | bash";
// Two agents by default: --all would create dozens of agent folders in the home directory.
const SKILL_COMMAND = "npx skills add dozybot001/Intent -g -a claude-code -a codex -y";
// The CLI's default endpoint: there `itt auth login` needs no URL and a push names the project after its directory.
const HOSTED_INTHUB = "https://inthub.tenon.asia";
// Account and Settings open in a dialog over the current page, and team pages have paths of their own;
// project views stay on / with query parameters.
const ACCOUNT_PATHS = { profile: "/account", danger: "/account/danger" };
const SETTINGS_PATHS = { tokens: "/settings", teams: "/settings/teams", usage: "/settings/usage" };
const DIALOG_PATHS = { account: ACCOUNT_PATHS, settings: SETTINGS_PATHS };
const TENON_ACCOUNT_URL = "https://account.tenon.asia/account/";
const SUPPORT_EMAIL = "support@tenonai.cn";
// Lifetimes the token form offers, in days.
const TOKEN_LIFETIMES = [30, 90, 365];
const DEFAULT_TOKEN_DAYS = 90;
// The hub's rule for project names (intent_cli.hub.versions.validate_project_name), checked while typing.
const PROJECT_NAME_MAX = 120;
const JSON_HEADERS = { "Content-Type": "application/json" };
// The hub's rule for team URLs (intent_cli.hub.versions.TEAM_SLUG), checked while typing.
const TEAM_SLUG = /^[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?$/;
const TEAM_ROLES = ["admin", "member", "viewer"];

const state = {
  config: null,
  projects: [],
  currentProjectId: null,
  activeTab: "overview",
  selectedDetail: null,
  searchQuery: "",
  overview: null,
  handoff: null,
  authenticated: false,
  account: null,
  // "project" shows the tabs; "home", "team", "invite" and "device" render beside the untouched project view.
  page: "project",
  // A visitor reads one public project on a hosted hub, without an account.
  visitor: false,
};

const el = {
  shell: document.getElementById("shell"),
  projectPicker: document.getElementById("project-picker"),
  projectPickerTrigger: document.getElementById("project-picker-trigger"),
  projectPickerLabel: document.getElementById("project-picker-label"),
  projectPickerEyebrow: document.getElementById("project-picker-eyebrow"),
  projectPickerDropdown: document.getElementById("project-picker-dropdown"),
  refreshBtn: document.getElementById("refresh-btn"),
  searchTrigger: document.getElementById("search-trigger"),
  searchDialog: document.getElementById("search-dialog"),
  searchForm: document.getElementById("search-form"),
  searchInput: document.getElementById("search-input"),
  searchResults: document.getElementById("search-results"),
  searchStatus: document.getElementById("search-status"),
  syncChip: document.getElementById("sync-chip"),
  syncIndicator: document.getElementById("sync-indicator"),
  tabBar: document.getElementById("tab-bar"),
  detailPane: document.getElementById("detail-pane"),
  detailContent: document.getElementById("detail-content"),
  siteContent: document.getElementById("site-content"),
  skipLink: document.querySelector(".skip-link"),
  statusLine: document.getElementById("status-line"),
  reportLink: document.getElementById("report-link"),
  authPitch: document.getElementById("auth-pitch"),
  authStart: document.getElementById("auth-start"),
  settingsDialog: document.getElementById("settings-dialog"),
  settingsDialogTitle: document.getElementById("settings-dialog-title"),
  settingsDialogBody: document.getElementById("settings-dialog-body"),
  settingsDialogClose: document.getElementById("settings-dialog-close"),
  intentCount: document.getElementById("intent-count"),
  decisionCount: document.getElementById("decision-count"),
  snapCount: document.getElementById("snap-count"),
  drawer: document.getElementById("drawer"),
  drawerOverlay: document.getElementById("drawer-overlay"),
  drawerClose: document.getElementById("drawer-close"),
  drawerBack: document.getElementById("drawer-back"),
  drawerTitle: document.getElementById("drawer-title"),
  drawerContent: document.getElementById("drawer-content"),
  logoutBtn: document.getElementById("logout-btn"),
  signInButton: document.getElementById("sign-in-button"),
  accountControl: document.getElementById("account-control"),
  accountLabel: document.getElementById("account-label"),
  accountMode: document.getElementById("account-mode"),
  accountMenuTrigger: document.getElementById("account-menu-trigger"),
  accountActions: document.getElementById("account-actions"),
  settingsLink: document.getElementById("settings-link"),
  authGate: document.getElementById("auth-gate"),
  authError: document.getElementById("auth-error"),
  authDismiss: document.getElementById("auth-dismiss"),
  tenonLogin: document.getElementById("tenon-login"),
  aboutDialog: document.getElementById("about-dialog"),
  aboutClose: document.getElementById("about-close"),
  aboutVersion: document.getElementById("about-version"),
  confirmDialog: document.getElementById("confirm-dialog"),
  confirmForm: document.getElementById("confirm-form"),
  confirmTitle: document.getElementById("confirm-title"),
  confirmBody: document.getElementById("confirm-body"),
  confirmField: document.getElementById("confirm-field"),
  confirmLabel: document.getElementById("confirm-label"),
  confirmInput: document.getElementById("confirm-input"),
  confirmError: document.getElementById("confirm-error"),
  confirmCancel: document.getElementById("confirm-cancel"),
  confirmOk: document.getElementById("confirm-ok"),
};

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

/* ---- Helpers ---- */

function productDeletionDestination(result) {
  let target;
  try {
    target = new URL(result?.url || "");
  } catch {
    throw new Error(t("Tenon returned an invalid deletion destination."));
  }
  if (target.origin !== "https://account.tenon.asia" || target.pathname !== "/account/delete/"
      || target.username || target.password || target.hash
      || [...target.searchParams].length !== 1 || !/^[A-Za-z0-9_-]{43}$/.test(target.searchParams.get("request") || "")
      || !Number.isFinite(result?.expiresAt) || result.expiresAt <= Date.now()) {
    throw new Error(t("Tenon returned an invalid deletion destination."));
  }
  return target.href;
}

function esc(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function fmtDate(v) {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  const pad = (part) => String(part).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function relativeDate(v) {
  if (!v) return t("Never synced");
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return String(v);
  // Clock skew can put fresh server times slightly in the future.
  const seconds = Math.min(0, Math.round((d.getTime() - Date.now()) / 1000));
  const abs = Math.abs(seconds);
  const formatter = new Intl.RelativeTimeFormat(window.IntHubI18n.language, { numeric: "auto" });
  if (abs < 60) return t("just now");
  if (abs < 3600) return formatter.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return formatter.format(Math.round(seconds / 3600), "hour");
  if (abs < 2592000) return formatter.format(Math.round(seconds / 86400), "day");
  return fmtDate(v);
}

function shortDay(v) {
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "—";
  const today = new Date();
  if (d.toDateString() === today.toDateString()) {
    return new Intl.DateTimeFormat(window.IntHubI18n.language, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(d);
  }
  // Earlier years use the compact numeric form so the date column never overflows.
  return new Intl.DateTimeFormat(window.IntHubI18n.language, d.getFullYear() === today.getFullYear()
    ? { month: "short", day: "numeric" }
    : { year: "2-digit", month: "numeric", day: "numeric" }).format(d);
}

function plural(count, one, other, values = {}) {
  return t(count === 1 ? one : other, { count, ...values });
}

function shortRevision(v) {
  return v ? v.slice(0, 8) : "—";
}

function truncate(v, n = 140) {
  if (!v || v.length <= n) return v || "";
  return v.slice(0, n).trimEnd() + "…";
}

function formatText(v) {
  if (!v) return "";
  return String(v)
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => `<p>${esc(line)}</p>`)
    .join("");
}

function highlight(text, query) {
  const source = String(text ?? "");
  const needle = String(query || "").trim().toLowerCase();
  const lower = source.toLowerCase();
  if (!needle || lower.length !== source.length) return esc(source);
  let out = "";
  let index = 0;
  for (let hit = lower.indexOf(needle); hit >= 0; hit = lower.indexOf(needle, index)) {
    out += `${esc(source.slice(index, hit))}<mark>${esc(source.slice(hit, hit + needle.length))}</mark>`;
    index = hit + needle.length;
  }
  return out + esc(source.slice(index));
}

function intentStatusLabel(status) {
  return {
    active: t("In progress"),
    suspend: t("On hold"),
    done: t("Completed"),
    cancelled: t("Cancelled"),
    deprecated: t("Deprecated"),
  }[status] || status || t("Unknown");
}

function decisionStatusLabel(status) {
  return { active: t("In effect"), deprecated: t("Deprecated") }[status] || status || t("Unknown");
}

function statusBadge(status, kind = "intent") {
  const label = kind === "decision" ? decisionStatusLabel(status) : intentStatusLabel(status);
  return `<span class="status-pill status-${esc(status || "unknown")}"><span class="status-dot" aria-hidden="true"></span>${esc(label)}</span>`;
}

function stateBadge(status) {
  return `<span class="status-pill state-${esc(status.key)}"><span class="status-dot" aria-hidden="true"></span>${esc(status.label)}</span>`;
}

function rowStatusIcon(status) {
  return `<span class="row-icon status-${esc(status || "unknown")}" aria-hidden="true"><span class="status-dot"></span></span>`;
}

function originName(origin) {
  return ORIGIN_NAMES[origin] || origin || "";
}

function authorName(object) {
  return object?.author?.name || object?.author?.email || "";
}

// "Ana Lee · Claude Code": who recorded it and with which agent. Without an author, only the agent.
function byline(object) {
  return [authorName(object), originName(object?.origin)].filter(Boolean).join(" · ");
}

function verifiedBadge(object) {
  if (!object?.verified) return "";
  return `<span class="status-pill status-verified" data-tip="${esc(t("Pushed by the account that owns this email."))}"><span class="status-dot" aria-hidden="true"></span>${esc(t("Verified"))}</span>`;
}

// One quiet line in a list row or timeline entry; nothing when the object names nobody.
function rowByline(object) {
  const line = byline(object);
  const badge = verifiedBadge(object);
  return line || badge ? `<span class="row-byline">${line ? `<span>${esc(line)}</span>` : ""}${badge}</span>` : "";
}

// Sheets name the author in full, and can explain "Verified".
function identityMeta(object) {
  const line = byline(object);
  const email = object?.author?.name ? object.author.email : "";
  return [
    line ? `<span class="chip">${esc(line)}</span>` : "",
    email ? `<span class="detail-email">${esc(email)}</span>` : "",
    object?.verified ? `<span class="detail-verified">${verifiedBadge(object)}${helpButton("verified")}</span>` : "",
  ].join("");
}

function idChip(id) {
  return `<span class="chip chip-id">${esc(id)}</span>`;
}

function remoteId(wksId, objId) {
  return `${wksId}__${objId}`;
}

function projectIdFromRemoteId(rId) {
  return String(rId || "").split("__", 1)[0] || "";
}

// Requests stay same-origin (CSP connect-src 'self'); apiBaseUrl is only for CLI snippets.
function apiUrl(path) {
  return path;
}

function configUrl() {
  return "/config.json";
}

// A newer action owns its view. Late responses may finish, but cannot replace it.
function beginViewRequest(view) {
  state._requestVersions ||= {};
  if (view === "detail" || view === "sheet") setViewBusy(view, false);
  return state._requestVersions[view] = (state._requestVersions[view] || 0) + 1;
}

function ownsViewRequest(view, request) {
  return state._requestVersions?.[view] === request;
}

function setViewBusy(view, busy) {
  const target = view === "sheet" ? el.drawerContent : el.detailPane;
  target.setAttribute("aria-busy", String(busy));
}

function viewLoadingHtml() {
  return `<div class="view-loading" role="status"><span class="view-loading-spinner" aria-hidden="true"></span><p data-view-loading-copy>${esc(t("Loading…"))}</p></div>`;
}

function pageSkeletonHtml() {
  return `<div class="page-skeleton" role="status" aria-label="${esc(t("Loading continuation brief"))}"><i></i><i></i><i></i></div>`;
}

function localizeViewLoadingCopy() {
  for (const node of document.querySelectorAll("[data-view-loading-copy]")) node.textContent = t("Loading…");
}

class ApiRequestError extends Error {
  constructor(message, status, code, detail = "") {
    super(message);
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

// gate: false lets a caller read a 401 as an answer instead of showing the sign-in gate.
async function fetchJson(url, { gate = true, ...options } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  let r;
  let p;
  try {
    r = await fetch(url, { credentials: "same-origin", ...options, signal: controller.signal });
    p = await r.json();
  } catch (error) {
    throw new ApiRequestError(t("Could not load data. Try again."), r?.status || 0, error.name === "AbortError" ? "REQUEST_TIMEOUT" : "INVALID_RESPONSE");
  } finally {
    clearTimeout(timeout);
  }
  if (!r.ok || p.ok === false) {
    const error = new ApiRequestError(
      t(r.status === 401 ? "Sign in again to continue." : r.status === 403 ? "Permission denied." : r.status === 404 ? "Object no longer exists." : "Could not load data. Try again."),
      r.status,
      p?.error?.code,
      p?.error?.message || "",
    );
    error.details = p?.error?.details;
    if (r.status === 401 && gate && state.config?.authRequired) showAuthGate();
    throw error;
  }
  return p.result;
}

async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
    setStatus(message);
    return true;
  } catch {
    setStatus(t("Copy failed. Select and copy the text manually."), true);
    return false;
  }
}

/* ---- Authentication ---- */

const LOGIN_LABELS = { github: "Continue with GitHub", apple: "Continue with Apple", email: "Continue with email" };
const LAST_LOGIN_METHOD = "inthub.last-method";

function setTenonLoginLoading(active = "") {
  for (const link of el.tenonLogin.querySelectorAll("[data-login-method]")) {
    const method = link.dataset.loginMethod, loading = method === active;
    link.classList.toggle("is-loading", loading);
    link.setAttribute("aria-busy", String(loading));
    if (active) link.setAttribute("aria-disabled", "true");
    else link.removeAttribute("aria-disabled");
    link.querySelector("[data-login-label]").textContent = t(loading ? "Opening sign-in…" : LOGIN_LABELS[method]);
  }
}

function showAuthGate(message = "", { keepPage = false } = {}) {
  closeHeaderMenus();
  closeDrawer({ history: "none" });
  if (el.searchDialog.open) el.searchDialog.close();
  if (el.confirmDialog.open) el.confirmDialog.close();
  closeSettingsDialog({ history: "none" });
  if (!keepPage) {
    if (state.page !== "project") setPage("project");
    for (const view of ["projects", "project", "detail", "sheet", "search"]) beginViewRequest(view);
    el.detailContent.innerHTML = "";
    el.searchResults.innerHTML = "";
    el.searchInput.value = "";
    el.accountLabel.textContent = "";
    state._searchResults = null;
    state._detailCache = new Map();
    state.visitor = false;
    el.signInButton.classList.add("is-hidden");
  }
  el.shell.inert = true;
  state._authMessage = window.IntHubI18n.keyFor(message);
  state.authenticated = false;
  el.shell.classList.add("is-locked");
  el.authGate.classList.remove("is-hidden");
  el.authDismiss.classList.toggle("is-hidden", !keepPage);
  // Someone reading a public project already knows what this is.
  el.authPitch.classList.toggle("is-hidden", keepPage);
  el.authStart.innerHTML = commandSnippet([INSTALL_COMMAND, "itt init"]);
  el.accountControl.classList.add("is-hidden");
  el.authError.textContent = message;
  el.authError.classList.toggle("is-hidden", !message);
  el.tenonLogin.classList.remove("is-hidden");
  const returnTo = `${window.location.pathname}${window.location.search}`;
  let lastMethod = null;
  try { lastMethod = window.localStorage.getItem(LAST_LOGIN_METHOD); } catch { /* The marker is only a convenience. */ }
  for (const link of el.tenonLogin.querySelectorAll("[data-login-method]")) {
    link.href = `/auth/redirect?method=${link.dataset.loginMethod}&return_to=${encodeURIComponent(returnTo)}`;
    link.querySelector(".last-used").classList.toggle("is-hidden", link.dataset.loginMethod !== lastMethod);
  }
  setTenonLoginLoading();
  window.setTimeout(() => el.tenonLogin.querySelector("[data-login-method]").focus(), 0);
}

function hideAuthGate() {
  el.shell.inert = false;
  state.authenticated = !state.visitor;
  el.shell.classList.remove("is-locked");
  el.authGate.classList.add("is-hidden");
  el.authDismiss.classList.add("is-hidden");
  el.accountControl.classList.toggle("is-hidden", !state.config?.authRequired || state.visitor);
  el.signInButton.classList.toggle("is-hidden", !state.visitor);
  el.logoutBtn.classList.remove("is-hidden");
  el.accountMenuTrigger.disabled = false;
  const account = state.account;
  // The name, then what tells two people with that name apart.
  el.accountLabel.textContent = account ? account.display_name || `@${account.login}` : "";
  el.accountMode.textContent = account ? account.email || (account.display_name && account.login ? `@${account.login}` : "") : "";
  el.authError.textContent = "";
  el.authError.classList.add("is-hidden");
}

// A visitor who opened the gate can go back to the project they were reading.
function dismissAuthGate() {
  hideAuthGate();
  el.signInButton.focus();
}

// Reading state.account === null afterwards means nobody is signed in: for a visitor that is not an error.
async function loadCurrentAccount() {
  if (!state.config?.authRequired) return;
  try {
    state.account = (await fetchJson(apiUrl("/api/v1/auth/me"), { gate: false })).account;
  } catch (error) {
    if (error.status !== 401) throw error;
    state.account = null;
  }
}

function callbackErrorMessage() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("auth_error");
  if (!code) return "";
  params.delete("auth_error");
  const query = params.toString();
  window.history.replaceState(
    {},
    "",
    `${window.location.pathname}${query ? `?${query}` : ""}`,
  );
  const messages = {
    tenon_denied: t("Tenon sign-in was cancelled."),
    invalid_state: t("That sign-in attempt expired. Please try again."),
    tenon_failed: t("Tenon sign-in could not be completed. Please try again."),
    suspended: t("This account is suspended. Contact support@tenonai.cn."),
  };
  return messages[code] || t("Sign-in could not be completed.");
}

/* ---- URL state ---- */

function readRoute() {
  const p = new URLSearchParams(window.location.search);
  const requestedTab = p.get("tab") || "overview";
  const q = p.get("q") || "";
  const path = window.location.pathname.replace(/\/+$/, "");
  const dialog = dialogRoute(path);
  const team = path.match(/^\/teams\/([^/]+)(?:\/(projects|settings))?$/);
  return {
    page: dialog?.page || (team ? "team" : path === "/invite" ? "invite" : path === "/device" ? "device" : "project"),
    pane: dialog?.pane || (team ? team[2] || "members" : ""),
    team: team ? team[1] : "",
    token: p.get("token") || "",
    project: p.get("project"),
    tab: TABS.includes(requestedTab) ? requestedTab : "overview",
    section: p.get("section") || "",
    intent: p.get("intent") || "",
    author: p.get("author") || "",
    detail: p.get("detail"),
    detailType: p.get("detailType"),
    q,
    search: requestedTab === "search" || Boolean(q),
  };
}

// Which dialog pane a path opens, if any.
function dialogRoute(path) {
  for (const [page, panes] of Object.entries(DIALOG_PATHS)) {
    const pane = Object.keys(panes).find((name) => panes[name] === path);
    if (pane) return { page, pane };
  }
  return null;
}

function teamPath(slug, pane = "members") {
  return `/teams/${encodeURIComponent(slug)}${pane === "members" ? "" : `/${pane}`}`;
}

function projectPath(projectId, query = {}) {
  return `/?${new URLSearchParams({ project: projectId, ...query })}`;
}

function routeUrl() {
  if (state._dialog) return DIALOG_PATHS[state._dialog][state._pane];
  if (state.page === "team") return teamPath(state._team.slug, state._team.pane);
  if (state.page === "invite") return `/invite${window.location.search}`;
  if (state.page === "device") return "/device";
  if (state.page === "home") return "/";
  const p = new URLSearchParams();
  if (state.currentProjectId) p.set("project", state.currentProjectId);
  if (state.activeTab !== "overview") p.set("tab", state.activeTab);
  if (state.activeTab === "settings" && state._settingsSection && state._settingsSection !== "general") p.set("section", state._settingsSection);
  const timeline = state.activeTab === "snaps" && state._timeline?.projectId === state.currentProjectId ? state._timeline : null;
  if (timeline?.intentId) p.set("intent", timeline.intentId);
  if (timeline?.author) p.set("author", timeline.author);
  if (state.selectedDetail) {
    p.set("detail", state.selectedDetail.remoteId);
    p.set("detailType", state.selectedDetail.type);
  }
  const q = p.toString();
  return q ? `/?${q}` : "/";
}

// "push" creates a browser history entry, "replace" updates the current one,
// "none" is used while applying an entry that the browser already restored.
function writeRoute(mode = "replace", entry = "page") {
  if (mode === "none") return "none";
  const url = routeUrl();
  if (mode === "push" && window.history.pushState && url !== `${window.location.pathname}${window.location.search}`) {
    window.history.pushState({ inthub: entry, sheetPushed: entry === "sheet" }, "", url);
    return "pushed";
  }
  const previous = window.history.state || {};
  const sheetPushed = entry === "sheet" && previous.inthub === "sheet" && Boolean(previous.sheetPushed);
  window.history.replaceState({ ...previous, inthub: entry, sheetPushed }, "", url);
  return "replaced";
}

/* ---- Status ---- */

// A modal dialog leaves the page inert and under its backdrop, so the message moves into the top one.
function placeStatusLine() {
  const parent = [...document.querySelectorAll("dialog[open]")].at(-1) || el.statusHome;
  if (parent && el.statusLine.parentElement !== parent) parent.append(el.statusLine);
}

function setStatus(msg, isError = false) {
  state._statusMessage = window.IntHubI18n.keyFor(msg);
  placeStatusLine();
  el.statusLine.textContent = msg;
  el.statusLine.classList.toggle("muted", !isError);
  el.statusLine.classList.toggle("is-error", isError);
  el.statusLine.classList.add("is-visible");
  window.clearTimeout(setStatus._timer);
  setStatus._timer = window.setTimeout(() => {
    el.statusLine.classList.remove("is-visible");
  }, isError ? 6000 : 2600);
}

/* ---- Tabs ---- */

// Who may manage this project; the server enforces the same rule.
function canManageProject() {
  return state.overview?.project?.permission === "admin";
}

function syncSettingsTab() {
  el.tabBar.querySelector?.('[data-tab="settings"]')?.classList.toggle("is-hidden", !canManageProject());
  // Anyone who reads a public project can report it; its managers have no need to.
  const project = state.overview?.project;
  const reportable = project?.visibility === "public" && !canManageProject();
  el.reportLink.classList.toggle("is-hidden", !reportable);
  if (reportable) el.reportLink.href = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(`Report IntHub project ${project.id}`)}`;
}

function setActiveTabUI() {
  el.shell.dataset.activeTab = state.activeTab;
  for (const btn of el.tabBar.querySelectorAll(".tab")) {
    btn.classList.toggle("is-active", btn.dataset.tab === state.activeTab);
    if (btn.dataset.tab === state.activeTab) btn.setAttribute("aria-current", "page");
    else btn.removeAttribute("aria-current");
  }
  revealActiveTab();
}

// Scroll only the tab strip (never the page) so narrow screens show the active tab.
function revealActiveTab() {
  const bar = el.tabBar;
  const tab = bar.querySelector?.(".tab.is-active");
  if (!tab || bar.scrollWidth <= bar.clientWidth) return;
  bar.scrollLeft = Math.max(0, tab.offsetLeft - bar.offsetLeft - (bar.clientWidth - tab.offsetWidth) / 2);
}

function switchTab(tab, { history = "push", section = "" } = {}) {
  if (!TABS.includes(tab)) return;
  if (tab === "settings" && !canManageProject()) tab = "overview";
  if (state.activeTab === tab && state.page === "project") {
    window.scrollTo?.({ top: 0, behavior: "smooth" });
    return;
  }
  closeDrawer({ history: "none" });
  leaveSitePage();
  state.activeTab = tab;
  state._settingsSection = section;
  setActiveTabUI();
  renderProjectBody();
  writeRoute(history);
  window.scrollTo?.({ top: 0 });
}

/* ---- Data helpers ---- */

function hasHistory() {
  return Boolean(historySources(state.overview).length);
}

function renderProjectBody() {
  if (hasHistory()) renderView();
  else if (state.overview) renderEmptyProject();
}

function historySources(overview) {
  if (overview?.history) return overview.history.revision ? [{
    project_id: overview.history.project_id,
    last_synced_at: overview.history.last_synced_at,
    revision: overview.history.revision,
  }] : [];
  return [];
}

function overviewIntents() {
  return [
    ...(state.overview?.active_intents || []),
    ...(state.overview?.other_intents || []),
  ];
}

const snapIndexes = new WeakMap();

function snapIndex() {
  const overview = state.overview;
  if (!overview) return new Map();
  if (!snapIndexes.has(overview)) {
    snapIndexes.set(overview, new Map((overview.recent_snaps || []).map((snap) => [snap.remote_id || remoteId(snap.project_id, snap.id), snap])));
  }
  return snapIndexes.get(overview);
}

function rememberSnap(snap) {
  if (!snap?.id) return;
  const key = snap.remote_id || remoteId(snap.project_id, snap.id);
  (state._snapCache ||= new Map()).set(key, { ...snap, remote_id: key });
}

// The overview carries only the newest Snaps; older ones come from timeline pages or detail fetches.
function knownSnap(rId) {
  return snapIndex().get(rId) || state._snapCache?.get(rId) || null;
}

function latestSnapFor(intent) {
  return intent.latest_snap_id ? knownSnap(remoteId(intent.project_id, intent.latest_snap_id)) : null;
}

function latestSnapCopy(intent) {
  const snap = latestSnapFor(intent);
  if (snap) return t("Updated {time}", {time: relativeDate(snap.created_at)});
  return intent.latest_snap_id ? t("Checkpoint {id}", {id: intent.latest_snap_id}) : t("Checkpoint missing");
}

// Fetch Snaps that are referenced but not loaded, a few at a time, then refresh only their labels.
async function fetchMissingSnaps(remoteIds) {
  const projectId = state.currentProjectId;
  state._snapPending ||= new Set();
  state._snapFailed ||= new Set();
  const queue = [...new Set(remoteIds)].filter((rId) => rId && projectIdFromRemoteId(rId) === projectId
    && !knownSnap(rId) && !state._snapPending.has(rId) && !state._snapFailed.has(rId));
  if (!queue.length) return;
  for (const rId of queue) state._snapPending.add(rId);
  const worker = async () => {
    while (queue.length) {
      const rId = queue.shift();
      try {
        const payload = await fetchJson(apiUrl(`/api/v1/snaps/${encodeURIComponent(rId)}`));
        if (state.currentProjectId !== projectId || !payload?.snap) continue;
        rememberSnap({ ...payload.snap, project_id: payload.project_id || projectId, remote_id: rId });
        state._detailCache?.set(`snap:${rId}`, payload);
      } catch {
        state._snapFailed.add(rId);
      } finally {
        state._snapPending.delete(rId);
      }
    }
  };
  try {
    await Promise.all(Array.from({ length: Math.min(4, queue.length) }, worker));
  } catch { /* labels keep their checkpoint id */ }
  if (state.currentProjectId !== projectId) return;
  for (const node of el.detailContent.querySelectorAll("[data-latest-snap]")) {
    const snap = knownSnap(node.dataset.latestSnap);
    if (snap) node.textContent = t("Updated {time}", {time: relativeDate(snap.created_at)});
  }
}

function intentForSnap(snap) {
  const intents = overviewIntents();
  return intents.find((intent) =>
    intent.id === snap.intent_id && intent.project_id === snap.project_id,
  ) || (!snap.project_id ? intents.find((intent) => intent.id === snap.intent_id) : null) || null;
}

function decisionScope(decision) {
  const ids = decision.intent_ids || [];
  const linked = overviewIntents().filter((intent) =>
    intent.project_id === decision.project_id && ids.includes(intent.id),
  );
  return {
    count: ids.length,
    titles: linked.map((intent) => intent.what),
  };
}

/* ---- Relations between Intents ----
   Mirrors src/intent_cli/relations.py. Relations live on the Intent that declares
   them (the subject B) and point at a target A. Their states are never stored:
   they follow from the statuses of the two Intents. */

const RELATION_TYPES = ["part_of", "derived_from", "succeeds", "depends_on", "conflicts_with"];
const PARENT_RELATIONS = new Set(["part_of", "derived_from"]);
const ENDED_STATUSES = new Set(["done", "cancelled"]);
const ATTENTION_STATES = new Set(["orphaned", "pending", "blocked", "broken", "unresolved"]);

function activeRelationEntries(intent) {
  const entries = Array.isArray(intent?.relations) ? intent.relations : [];
  return entries.filter((entry) => entry && typeof entry === "object" && !("removed_at" in entry)
    && RELATION_TYPES.includes(entry.type) && typeof entry.intent === "string");
}

function relationState(kind, subject, target) {
  const subjectStatus = subject?.status;
  const targetStatus = target?.status;
  if (kind === "part_of") {
    if (subjectStatus === "done") return "done";
    if (subjectStatus === "cancelled") return "dropped";
    return ENDED_STATUSES.has(targetStatus) ? "orphaned" : "in_progress";
  }
  if (kind === "succeeds") return ENDED_STATUSES.has(targetStatus) ? "handed_over" : "pending";
  if (kind === "depends_on") return targetStatus === "done" ? "satisfied" : targetStatus === "cancelled" ? "broken" : "blocked";
  if (kind === "conflicts_with") return ENDED_STATUSES.has(subjectStatus) || ENDED_STATUSES.has(targetStatus) ? "resolved" : "unresolved";
  return null;
}

function intentMap(intents) {
  if (intents instanceof Map) return intents;
  const map = new Map();
  for (const intent of intents || []) if (intent?.id && !map.has(intent.id)) map.set(intent.id, intent);
  return map;
}

// Every active relation whose two Intents exist, with its derived state.
function relationLinks(intents) {
  const byId = intentMap(intents);
  const links = [];
  for (const [id, subject] of byId) {
    for (const entry of activeRelationEntries(subject)) {
      const target = byId.get(entry.intent);
      if (!target || entry.intent === id) continue;
      links.push({ type: entry.type, subject: id, target: entry.intent, state: relationState(entry.type, subject, target) });
    }
  }
  return links;
}

// Relations touching one Intent, both directions: outgoing first (where it comes from), then by type.
function relationView(intents, intentId) {
  const byId = intentMap(intents);
  const rows = [];
  for (const link of relationLinks(byId)) {
    if (link.subject !== intentId && link.target !== intentId) continue;
    const outgoing = link.subject === intentId;
    rows.push({ type: link.type, direction: outgoing ? "out" : "in", intent: byId.get(outgoing ? link.target : link.subject), state: link.state });
  }
  return rows.sort((left, right) => (left.direction !== "out") - (right.direction !== "out")
    || RELATION_TYPES.indexOf(left.type) - RELATION_TYPES.indexOf(right.type)
    || String(left.intent.id).localeCompare(String(right.intent.id)));
}

function relationLabel(type, direction) {
  const labels = {
    part_of: [t("Part of"), t("Parts")],
    derived_from: [t("Derived from"), t("Spawned")],
    succeeds: [t("Succeeds"), t("Succeeded by")],
    depends_on: [t("Depends on"), t("Needed by")],
    conflicts_with: [t("Conflicts with"), t("Conflicts with")],
  }[type];
  return labels ? labels[direction === "out" ? 0 : 1] : String(type || "");
}

// Read from one side: the prerequisite of an unmet dependency is "blocking", the dependent "blocked".
function relationStateLabel(key, row = null) {
  if (key === "blocked" && row?.type === "depends_on" && row.direction === "in") return t("Blocking");
  return {
    in_progress: t("In progress"), done: t("Completed"), dropped: t("Dropped"), orphaned: t("Parent ended"),
    pending: t("Handover pending"), handed_over: t("Handed over"),
    blocked: t("Blocked"), satisfied: t("Satisfied"), broken: t("Broken dependency"),
    unresolved: t("Unresolved conflict"), resolved: t("Resolved"),
  }[key] || "";
}

function relationTone(key) {
  if (key === "broken") return "danger";
  if (ATTENTION_STATES.has(key)) return "attention";
  if (["satisfied", "handed_over", "resolved", "done"].includes(key)) return "settled";
  return "neutral";
}

// A relation state is never shown by colour alone: the pill always carries its label.
function relationBadge(key, row = null) {
  if (!key) return "";
  return `<span class="status-pill rel-state rel-${relationTone(key)}"><span class="status-dot" aria-hidden="true"></span>${esc(relationStateLabel(key, row))}</span>`;
}

const intentMaps = new WeakMap();

function overviewIntentMap() {
  const overview = state.overview;
  if (!overview) return new Map();
  if (!intentMaps.has(overview)) intentMaps.set(overview, intentMap(overviewIntents()));
  return intentMaps.get(overview);
}

// Relations of one Intent against the whole project; a fresher copy of the Intent (handoff, detail) wins.
function intentRelations(intent) {
  if (!intent?.id) return [];
  const byId = new Map(overviewIntentMap());
  byId.set(intent.id, { ...(byId.get(intent.id) || {}), ...intent });
  return relationView(byId, intent.id);
}

function relationContext(intent) {
  const rows = intentRelations(intent);
  const parent = rows.find((row) => row.direction === "out" && PARENT_RELATIONS.has(row.type)) || null;
  return { rows, parent, attention: rows.filter((row) => row !== parent && ATTENTION_STATES.has(row.state)) };
}

// An open Intent cannot proceed while a dependency is unmet or was cancelled.
function dependencyBlocked(intent) {
  return intentRelations(intent).some((row) => row.type === "depends_on" && row.direction === "out" && ["blocked", "broken"].includes(row.state));
}

/* ---- Checkpoint contract ---- */

function checkpointKey(label) {
  const normalized = String(label || "").trim().toLowerCase();
  if (/verified|已验证|验证结果|当前状态/.test(normalized)) return "verified";
  if (/boundary|边界/.test(normalized)) return "boundary";
  if (/^next|下一步/.test(normalized)) return "next";
  if (/blocker|阻塞/.test(normalized)) return "blocker";
  if (/constraint|约束|必须遵守/.test(normalized)) return "constraints";
  return null;
}

function extractCheckpointParts(value) {
  const source = String(value || "")
    .trim()
    .replace(/^(?:checkpoint|检查点)\s*[:：]\s*/i, "");
  const fields = {};
  const marker = /(?:^|[\n\r.。；;])\s*(Verified(?: state)?|Boundary|Current(?: work)? boundary|Next(?: step)?|Blockers?|Constraints?|已验证(?:到)?(?:的?状态)?|验证结果|当前状态|当前(?:真正的)?工作边界|当前边界|工作边界|边界|下一步|阻塞(?:项)?|必须遵守(?:的约束)?|约束)\s*[:：]\s*/giu;
  const matches = [];
  let match;
  while ((match = marker.exec(source)) !== null) {
    matches.push({
      key: checkpointKey(match[1]),
      markerStart: match.index,
      valueStart: marker.lastIndex,
    });
  }

  for (let index = 0; index < matches.length; index += 1) {
    const current = matches[index];
    const end = matches[index + 1]?.markerStart ?? source.length;
    const value = source
      .slice(current.valueStart, end)
      .replace(/^[\s.。；;]+|[\s.。；;]+$/g, "")
      .trim();
    if (current.key && value && !fields[current.key]) fields[current.key] = value;
  }

  const context = matches.length
    ? source.slice(0, matches[0].markerStart).replace(/[\s.。；;]+$/g, "").trim()
    : source;
  return { fields, context, structured: matches.length > 0 };
}

const CHECKPOINT_KEYS = ["verified", "boundary", "next", "blocker", "constraints"];

function recordedCheckpointFields(checkpoint) {
  if (!checkpoint || typeof checkpoint !== "object" || Array.isArray(checkpoint)) return null;
  const fields = {};
  for (const key of CHECKPOINT_KEYS) {
    const value = typeof checkpoint[key] === "string" ? checkpoint[key].trim() : "";
    if (value) fields[key] = value;
  }
  return Object.keys(fields).length ? fields : null;
}

// A recorded snap.checkpoint is the explicit contract: absent cells stay missing
// instead of being guessed from prose. Legacy Snaps fall back to text labels.
function snapCheckpointParts(snap) {
  const recorded = recordedCheckpointFields(snap?.checkpoint);
  if (recorded) return { fields: recorded, context: String(snap?.why || "").trim(), recorded: true };
  const what = extractCheckpointParts(snap?.what);
  const why = extractCheckpointParts(snap?.why);
  const context = [what.structured ? what.context : "", why.context]
    .filter(Boolean)
    .filter((value, index, values) => values.indexOf(value) === index)
    .join(" · ");
  return { fields: { ...why.fields, ...what.fields }, context, recorded: false };
}

function parseCheckpoint(snap) {
  const { fields, context } = snapCheckpointParts(snap);
  return {
    verified: fields.verified || snap?.what || "",
    boundary: fields.boundary || "",
    next: fields.next || "",
    blocker: fields.blocker || "",
    constraints: fields.constraints || "",
    context,
  };
}

function conciseSnapTitle(snap, maxLength = 86) {
  const { fields, recorded } = snapCheckpointParts(snap);
  // With a recorded checkpoint WHAT stays a clean milestone; legacy WHAT may hold the whole checkpoint.
  const source = String((recorded ? snap?.what || fields.verified : fields.verified || snap?.what) || "")
    .replace(/\s+/g, " ")
    .replace(/^(?:verified(?: state)?|已验证(?:到)?(?:的?状态)?|验证结果|当前状态)\s*[:：]\s*/i, "")
    .trim();
  if (!source) return t("{id} checkpoint", {id: snap?.id || "Snap"});

  const stop = source.search(/[。！？!?；;\n]/);
  const clause = stop >= 16 && stop <= maxLength + 18
    ? source.slice(0, stop + 1)
    : source;
  return truncate(clause, maxLength);
}

function isClearBlocker(value) {
  return /^(none|n\/a|not blocked|no blocker|无|没有|无阻塞|暂无)[.!。！]?$/.test(
    String(value || "").trim().toLowerCase(),
  );
}

function timelineState(checkpoint) {
  if (checkpoint.blocker && !isClearBlocker(checkpoint.blocker)) {
    return { key: "blocked", className: " is-blocked", label: t("Blocked") };
  }
  if (!checkpoint.next) {
    return { key: "incomplete", className: " is-incomplete", label: t("Next missing") };
  }
  if (checkpoint.blocker && isClearBlocker(checkpoint.blocker)) {
    return { key: "ready", className: " is-ready", label: t("Unblocked") };
  }
  return { key: "checkpoint", className: "", label: t("Checkpoint") };
}

function continuationHealth(intents) {
  if (!intents.length) return { ready: false, label: t("No active objective") };
  const checkpoints = intents.map(intent => snapCheckpointParts(intent.latest_snap).fields);
  const incomplete = checkpoints.filter(checkpoint => !checkpoint.verified || !checkpoint.boundary || !checkpoint.next || !checkpoint.blocker).length;
  if (incomplete) return { ready: false, label: plural(incomplete, "{count} incomplete checkpoint", "{count} incomplete checkpoints") };
  const blocked = checkpoints.filter((checkpoint, index) => !isClearBlocker(checkpoint.blocker) || dependencyBlocked(intents[index])).length;
  if (blocked) return { ready: false, label: plural(blocked, "{count} blocked objective", "{count} blocked objectives") };
  return { ready: true, label: t("Ready to continue") };
}

function checkpointCell(key, label, value) {
  const missing = !value;
  const clearBlocker = key === "blocker" && isClearBlocker(value);
  const blocked = key === "blocker" && !missing && !clearBlocker;
  const iconName = key === "blocker" ? (clearBlocker ? "clear" : "blocker") : key;
  return `
    <section class="checkpoint checkpoint-${esc(key)}${missing ? " is-missing" : ""}${clearBlocker ? " is-clear" : ""}${blocked ? " is-blocked" : ""}">
      <h4 class="checkpoint-label">${icon(iconName)}${esc(label)}</h4>
      <p class="checkpoint-value">${esc(missing ? t("Not explicitly recorded in the latest Snap.") : value)}</p>
    </section>`;
}

function checkpointGrid(checkpoint, order = ["next", "blocker", "boundary", "verified"], className = "") {
  const labels = { verified: t("Verified"), boundary: t("Boundary"), next: t("Next"), blocker: t("Blocker") };
  return `<div class="checkpoint-grid${className}">${order.map((key) => checkpointCell(key, labels[key], checkpoint[key])).join("")}</div>`;
}

/* ---- Shared render pieces ---- */

function pageHeader({ eyebrow = "", title, help = "", meta = [], actions = "" }) {
  const heading = `<h1 class="page-title">${esc(title)}</h1>`;
  return `
    <header class="page-header">
      <div class="page-heading">
        ${eyebrow ? `<span class="eyebrow">${esc(eyebrow)}</span>` : ""}
        ${help ? `<div class="heading-with-help">${heading}${helpButton(help)}</div>` : heading}
        ${meta.length ? `<p class="page-meta">${meta.map((item) => `<span>${item}</span>`).join("")}</p>` : ""}
      </div>
      ${actions ? `<div class="page-actions">${actions}</div>` : ""}
    </header>`;
}

function sectionHeader(title, count, extra = "") {
  return `<header class="section-header"><h2 class="section-title">${esc(title)}${count === undefined ? "" : `<span class="count">${count}</span>`}</h2>${extra}</header>`;
}

function helpButton(topic) {
  return `<button class="help-trigger" data-help="${esc(topic)}" type="button" aria-label="${esc(t("Explanation"))}" aria-expanded="false"><span aria-hidden="true">i</span></button>`;
}

function emptyState({ iconName = "intent", title = "", body = "", extra = "" }) {
  return `
    <div class="empty-state">
      <span class="empty-icon">${icon(iconName)}</span>
      ${title ? `<h3>${esc(title)}</h3>` : ""}
      ${body ? `<p>${esc(body)}</p>` : ""}
      ${extra}
    </div>`;
}

// Each hyphenated word (--depends-on, -g, claude-code) is one inline block, so a narrow screen never breaks a
// line after its hyphen; a word wider than the line still wraps inside its block. Copy uses the plain text.
function shellArg(value) {
  return `'${String(value).replaceAll("'", "'\\''")}'`;
}

function commandSnippet(lines) {
  const text = lines.join("\n");
  const shown = esc(text).replace(/\S*-\S*/g, (word) => `<span class="command-word">${word}</span>`);
  return `<div class="snippet"><pre class="command-snippet">${shown}</pre><button class="icon-button copy-button" type="button" data-copy="${esc(text)}" aria-label="${esc(t("Copy command"))}">${icon("copy")}</button></div>`;
}

function detailSection(title, body, count) {
  return `<section class="detail-section"><h3 class="detail-section-title">${esc(title)}${count === undefined ? "" : `<span class="count">${count}</span>`}</h3>${body}</section>`;
}

function relationItem(type, rId, id, title, meta, status, badge = "") {
  const cls = status === "deprecated"
    ? " rel-deprecated"
    : status === "cancelled"
      ? " rel-cancelled"
      : status === "done"
        ? " rel-muted"
        : "";
  return `<button type="button" class="relation-item${cls}" data-detail-type="${esc(type)}" data-remote-id="${esc(rId)}">
    <span class="row-icon">${icon(type)}</span>
    <span class="relation-title">${esc(title)}</span>
    ${meta || badge ? `<span class="relation-meta">${badge}${esc(meta)}</span>` : ""}
    <span class="relation-side"><span class="row-id">${esc(id)}</span>${status ? statusBadge(status, type) : ""}</span>
  </button>`;
}

function collapsibleRelation(allItems, visibleCount) {
  if (!allItems.length) return "";
  const visible = allItems.slice(0, visibleCount);
  const rest = allItems.slice(visibleCount);
  let html = `<div class="relation-list">${visible.join("")}</div>`;
  if (rest.length) {
    html += `<details class="collapse-toggle"><summary>${icon("chevron")}<span>${esc(t("Show {count} more", {count: rest.length}))}</span></summary><div class="relation-list">${rest.join("")}</div></details>`;
  }
  return html;
}

function rawToggle(data) {
  return `<details class="raw-toggle"><summary>${icon("chevron")}${esc(t("Raw JSON"))}</summary><pre class="raw-pre">${esc(JSON.stringify(data, null, 2))}</pre></details>`;
}

/* ---- Views ---- */

function renderView() {
  if (!state.overview) return;
  el.shell.classList.remove("is-empty");
  switch (state.activeTab) {
    case "intents":
      renderIntentsTab();
      break;
    case "flow":
      renderFlowTab();
      break;
    case "snaps":
      renderSnapsTab();
      break;
    case "history":
      renderHistoryTab();
      break;
    case "decisions":
      renderDecisionsTab();
      break;
    case "settings":
      renderProjectSettings();
      break;
    default:
      renderProjectSummary();
  }
  syncSelected();
}

function syncSelected() {
  const root = state._sheetStack?.[0];
  for (const node of el.detailContent.querySelectorAll("[data-detail-type][data-remote-id]")) {
    const selected = Boolean(root) && node.dataset.detailType === root.type && node.dataset.remoteId === root.remoteId;
    node.classList.toggle("is-selected", selected);
    if (selected) node.setAttribute("aria-current", "true");
    else node.removeAttribute("aria-current");
  }
}

/* Overview: the continuation brief */

function relatedIntentId(intent, row) {
  return row.intent.remote_id || remoteId(intent.project_id || state.currentProjectId, row.intent.id);
}

// Where the goal sits, and only the relations someone has to act on, each named in words.
function briefRelations(intent) {
  const { parent, attention } = relationContext(intent);
  if (!parent && !attention.length) return "";
  const item = (row, badge) => `
    <li class="brief-relation">
      ${badge}
      <span class="brief-relation-label">${esc(relationLabel(row.type, row.direction))}</span>
      <button class="brief-relation-target" type="button" data-detail-type="intent" data-remote-id="${esc(relatedIntentId(intent, row))}">${esc(row.intent.what || row.intent.id)}</button>
      <span class="brief-relation-id">${esc(row.intent.id)}</span>
    </li>`;
  return `<ul class="brief-relations" aria-label="${esc(t("Relations"))}">
    ${parent ? item(parent, ATTENTION_STATES.has(parent.state) ? relationBadge(parent.state, parent) : "") : ""}
    ${attention.map((row) => item(row, relationBadge(row.state, row))).join("")}
  </ul>`;
}

function continuationCard(intent) {
  const snap = intent.latest_snap;
  const checkpoint = parseCheckpoint(snap);
  const snapRemoteId = snap ? remoteId(intent.project_id, snap.id) : "";
  return `
    <article class="brief-card">
      <header class="brief-card-head">
        <div>
          <div class="brief-meta">
            ${statusBadge(intent.status)}
            ${idChip(intent.id)}
            ${snap ? `<span>${esc(t("Updated {time}", {time: relativeDate(snap.created_at)}))}</span>` : `<span>${esc(t("Checkpoint missing"))}</span>`}
          </div>
          <h3 class="brief-title">${esc(intent.what)}</h3>
          ${intent.why ? `<p class="brief-why">${esc(intent.why)}</p>` : ""}
          ${briefRelations(intent)}
        </div>
        <button class="brief-open" type="button" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">${esc(t("Open Intent"))}${icon("arrow")}</button>
      </header>
      ${checkpointGrid(checkpoint)}
      ${checkpoint.constraints ? `<p class="checkpoint-note brief-constraints"><strong>${esc(t("Constraints:"))}</strong> ${esc(checkpoint.constraints)}</p>` : ""}
      <footer class="brief-foot">
        <span class="brief-foot-meta">
          ${snap
            ? `<span>${esc(t("Latest checkpoint"))} <span class="mono">${esc(snap.id)}</span></span><span>${esc(fmtDate(snap.created_at))}</span>${byline(snap) ? `<span>${esc(byline(snap))}</span>` : ""}${verifiedBadge(snap)}`
            : `<span>${esc(t("No continuation checkpoint recorded."))}</span>`}
        </span>
        ${snap ? `<button class="link-button" type="button" data-detail-type="snap" data-remote-id="${esc(snapRemoteId)}">${esc(t("View checkpoint"))}${icon("arrow")}</button>` : ""}
      </footer>
    </article>`;
}

function pausedRow(intent) {
  const snap = intent.latest_snap;
  const checkpoint = parseCheckpoint(snap);
  const summary = checkpoint.next
    ? `<b>${esc(t("Next"))}</b> ${esc(truncate(checkpoint.next, 200))}`
    : esc(truncate(intent.why || t("No continuation checkpoint recorded."), 200));
  const { attention } = relationContext(intent);
  return `
    <button class="list-row queue-item" type="button" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
      ${rowStatusIcon(intent.status)}
      <span class="row-main">
        <span class="row-title">${esc(intent.what)}</span>
        <span class="row-summary">${summary}</span>
        ${rowByline(intent)}
        ${attention.length ? `<span class="row-relations">${attention.map((row) => `<span class="row-relation">${relationBadge(row.state, row)}<span>${esc(relationLabel(row.type, row.direction))} ${esc(row.intent.id)}</span></span>`).join("")}</span>` : ""}
      </span>
      <span class="row-meta">
        <span class="row-id">${esc(intent.id)}</span>
        ${snap ? `<span>${esc(t("Updated {time}", {time: relativeDate(snap.created_at)}))}</span>` : ""}
      </span>
    </button>`;
}

function decisionRows(decisions, limit = 5) {
  if (!decisions.length) {
    return `<div class="inline-empty">${esc(t("N/A — no active Decision constrains future work."))}</div>`;
  }
  return `<div class="list-card">${decisions
    .slice(0, limit)
    .map((decision, index) => `
      <button class="list-row decision-row" type="button" data-detail-type="decision" data-remote-id="${esc(decision.remote_id)}">
        <span class="decision-index">${String(index + 1).padStart(2, "0")}</span>
        <span class="row-main">
          <span class="row-title">${esc(decision.what)}</span>
          ${decision.why ? `<span class="row-summary">${esc(truncate(decision.why, 160))}</span>` : ""}
          ${rowByline(decision)}
        </span>
      </button>`)
    .join("")}</div>`;
}

function activityRows(snaps) {
  if (!snaps.length) return `<div class="inline-empty">${esc(t("No snaps synced yet."))}</div>`;
  return `<div class="list-card">${snaps
    .map((snap) => {
      const intent = intentForSnap(snap);
      return `
        <button class="list-row activity-row" type="button" data-detail-type="snap" data-remote-id="${esc(snap.remote_id)}">
          <span class="activity-time">${esc(shortDay(snap.created_at))}</span>
          <span class="row-main">
            <span class="row-title">${esc(conciseSnapTitle(snap))}</span>
            <span class="row-summary">${esc(intent ? intent.what : snap.intent_id || t("Unlinked Intent"))}</span>
          </span>
        </button>`;
    })
    .join("")}</div>`;
}

// Who owns the project and who can read it. Only hosted hubs have owners; a local hub has neither.
function projectOwnerMeta(project) {
  if (!state.config?.authRequired) return [];
  const owner = project.owner;
  const member = project.permission !== "public";
  return [
    ...(owner?.name ? [owner.type === "team" && member ? `<a class="meta-link" href="${esc(teamPath(owner.slug))}" data-route>${esc(owner.name)}</a>` : esc(owner.name)] : []),
    visibilityBadge(project.visibility),
  ];
}

function renderProjectSummary() {
  const project = state.overview.project;
  const history = state.overview.history || {};
  const intents = state.handoff?.intents || [];
  const suspended = state.handoff?.suspended_intents || [];
  const decisions = state.handoff?.active_decisions || [];
  const health = continuationHealth(intents);
  const healthTone = health.ready ? "" : intents.length ? " is-warning" : " is-neutral";
  const healthIcon = health.ready ? "clear" : intents.length ? "blocker" : "intent";

  const brief = intents.length
    ? `<div class="brief-stack">${intents.map(continuationCard).join("")}</div>`
    : emptyState({
        iconName: "intent",
        title: t("No active Intent defines the next move."),
        body: t("History is available, but IntHub cannot name the current goal until an active Intent and a self-contained checkpoint are synced."),
      });

  el.detailContent.innerHTML = `
    <div class="continuation-page">
      ${pageHeader({
        eyebrow: t("Continuation brief"),
        title: project.name,
        meta: [
          ...projectOwnerMeta(project),
          esc(t("Shared history")),
          `<span class="mono">${esc(shortRevision(history.revision))}</span>`,
          esc(history.last_synced_at ? t("Synced {time}", {time: relativeDate(history.last_synced_at)}) : t("Waiting for first sync")),
        ],
        actions: `
          <span class="health-pill${healthTone}">${icon(healthIcon)}${esc(health.label)}</span>
          <button class="button button-secondary" type="button" data-copy-brief>${iconLabel("copy", t("Copy brief"))}</button>`,
      })}

      <section class="section">
        ${sectionHeader(t("Active work"), intents.length)}
        ${brief}
      </section>

      ${suspended.length ? `
        <section class="section">
          ${sectionHeader(t("Suspended"), suspended.length)}
          <div class="list-card">${suspended.map(pausedRow).join("")}</div>
        </section>` : ""}

      <div class="overview-columns">
        <section class="section">
          ${sectionHeader(t("Active decisions"), decisions.length, decisions.length > 5 ? `<button class="link-button" type="button" data-tab-jump="decisions">${esc(t("View all"))}${icon("arrow")}</button>` : "")}
          ${decisionRows([...decisions].reverse())}
        </section>
        <section class="section">
          ${sectionHeader(t("Recent activity"), undefined, state.overview.recent_snaps?.length ? `<button class="link-button" type="button" data-tab-jump="snaps">${esc(t("View timeline"))}${icon("arrow")}</button>` : "")}
          ${activityRows((state.overview.recent_snaps || []).slice(0, 6))}
        </section>
      </div>
    </div>`;
}

function briefMarkdown() {
  const project = state.overview.project;
  const history = state.overview.history || {};
  const intents = state.handoff?.intents || [];
  const suspended = state.handoff?.suspended_intents || [];
  const decisions = state.handoff?.active_decisions || [];
  const lines = [
    `# ${project.name} · ${t("Continuation brief")}`,
    "",
    `${t("Shared history")} ${shortRevision(history.revision)} · ${t("Synced {time}", {time: fmtDate(history.last_synced_at)})}`,
    "",
  ];
  // The same relations the cards show: the parent, then blockers, conflicts and pending handovers.
  const relationLine = (row) => `${row.intent.what || row.intent.id} (${row.intent.id})${ATTENTION_STATES.has(row.state) ? ` · ${relationStateLabel(row.state, row)}` : ""}`;
  if (!intents.length) lines.push(t("No active Intent defines the next move."), "");
  for (const intent of intents) {
    const checkpoint = parseCheckpoint(intent.latest_snap);
    const { parent, attention } = relationContext(intent);
    lines.push(`## ${intent.what} (${intent.id})`, "");
    if (intent.why) lines.push(`${t("Why")}: ${intent.why}`, "");
    for (const row of [parent, ...attention].filter(Boolean)) lines.push(`- **${relationLabel(row.type, row.direction)}:** ${relationLine(row)}`);
    for (const [label, value] of [[t("Next"), checkpoint.next], [t("Blocker"), checkpoint.blocker], [t("Boundary"), checkpoint.boundary], [t("Verified"), checkpoint.verified]]) {
      lines.push(`- **${label}:** ${value || t("Not explicitly recorded in the latest Snap.")}`);
    }
    if (checkpoint.constraints) lines.push(`- **${t("Constraints:")}** ${checkpoint.constraints}`);
    lines.push("");
  }
  if (suspended.length) {
    lines.push(`## ${t("Suspended")}`, "", ...suspended.map((intent) => {
      const { attention } = relationContext(intent);
      return `- ${intent.what} (${intent.id})${attention.map((row) => `; ${relationLabel(row.type, row.direction)} ${relationLine(row)}`).join("")}`;
    }), "");
  }
  lines.push(`## ${t("Active decisions")}`, "");
  lines.push(...(decisions.length ? decisions.map((decision) => `- ${decision.what} (${decision.id})`) : [t("N/A — no active Decision constrains future work.")]));
  return `${lines.join("\n").trim()}\n`;
}

/* Intents */

function latestSnapRemoteId(intent) {
  return intent.latest_snap_id ? remoteId(intent.project_id, intent.latest_snap_id) : "";
}

function intentEntry(intent) {
  const snaps = (intent.snap_ids || []).length;
  const decisions = (intent.decision_ids || []).length;
  const latest = latestSnapRemoteId(intent);
  return `
    <button type="button" class="list-row intent-entry intent-entry-${esc(intent.status)}" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
      ${rowStatusIcon(intent.status)}
      <span class="row-main">
        <strong class="row-title intent-entry-title">${esc(intent.what)}</strong>
        ${intent.why ? `<span class="row-summary">${esc(truncate(intent.why, 220))}</span>` : ""}
        ${rowByline(intent)}
      </span>
      <span class="row-meta">
        <span class="row-id">${esc(intent.id)}</span>
        <span class="row-meta-line"><span>${esc(plural(snaps, "{count} snap", "{count} snaps"))}</span><span>${esc(plural(decisions, "{count} decision", "{count} decisions"))}</span></span>
        <span${latest ? ` data-latest-snap="${esc(latest)}"` : ""}>${esc(latestSnapCopy(intent))}</span>
      </span>
    </button>`;
}

function intentGroup(label, intents, tone, emptyMessage = "") {
  const body = intents.length
    ? `<div class="list-card object-group-list">${intents.map(intentEntry).join("")}</div>`
    : `<div class="object-group-empty">${esc(emptyMessage)}</div>`;
  return `
    <section class="object-group intent-group intent-group-${esc(tone)}">
      <header class="object-group-header">
        <h2 class="object-group-title">${esc(label)}</h2>
        <span class="object-group-count">${intents.length}</span>
      </header>
      ${body}
    </section>`;
}

function intentSubgroup(label, intents, tone) {
  if (!intents.length) return "";
  return `
    <section class="object-subgroup object-subgroup-${esc(tone)}">
      <header><span>${esc(label)}</span> · <span>${intents.length}</span></header>
      <div class="list-card object-group-list">${intents.map(intentEntry).join("")}</div>
    </section>`;
}

function renderIntentsTab() {
  const active = state.overview.active_intents || [];
  const other = [...(state.overview.other_intents || [])].reverse();
  const suspended = other.filter((intent) => intent.status === "suspend");
  const completed = other.filter((intent) => intent.status === "done");
  const cancelled = other.filter((intent) => intent.status === "cancelled");
  const otherHistory = other.filter((intent) =>
    !["suspend", "done", "cancelled"].includes(intent.status),
  );
  const total = active.length + other.length;
  const header = pageHeader({
    title: t("Intents"),
    meta: total ? [esc(plural(total, "{count} intent", "{count} intents")), esc(t("{count} active", {count: active.length}))] : [],
  });

  if (!total) {
    el.detailContent.innerHTML = header + emptyState({
      iconName: "intent",
      title: t("No intents."),
      body: t("An Intent is one goal with its own outcome. Agents record them while they work."),
      extra: commandSnippet(['itt intent create "Goal" --why "Reason"']),
    });
    return;
  }

  state._pageState ||= {};
  const archiveShown = state._pageState.intentArchive || PAGE_SIZE;
  const archived = [...completed, ...cancelled, ...otherHistory];
  const visibleArchive = archived.slice(0, archiveShown);
  const visibleIds = new Set(visibleArchive.map((intent) => intent.remote_id));
  const visibleCompleted = completed.filter((intent) => visibleIds.has(intent.remote_id));
  const visibleCancelled = cancelled.filter((intent) => visibleIds.has(intent.remote_id));
  const visibleOther = otherHistory.filter((intent) => visibleIds.has(intent.remote_id));
  const archiveRemaining = archived.length - visibleArchive.length;
  const archiveOpen = state._pageState.intentArchiveOpen ?? (!active.length && !suspended.length);

  const archive = archived.length
    ? `<details class="object-archive intent-archive" data-archive="intents"${archiveOpen ? " open" : ""}>
        <summary>${icon("chevron")}<span>${esc(t("Resolved history"))}</span><span class="object-archive-count">${archived.length}</span></summary>
        <div class="object-archive-body">
          ${intentSubgroup(t("Completed"), visibleCompleted, "done")}
          ${intentSubgroup(t("Cancelled"), visibleCancelled, "cancelled")}
          ${intentSubgroup(t("Other"), visibleOther, "history")}
          ${archiveRemaining > 0
            ? `<button type="button" class="load-more-btn" id="load-more-intent-archive">${iconLabel("chevronDown", t("Load more ({count})", {count: archiveRemaining}))}</button>`
            : ""}
        </div>
      </details>`
    : "";

  el.detailContent.innerHTML = `
    ${header}
    ${intentGroup(
      t("Active objectives"),
      active,
      "active",
      t("No active objective. Resume a suspended Intent or record a new one."),
    )}
    ${suspended.length
      ? intentGroup(t("Suspended"), suspended, "suspend")
      : ""}
    ${archive}`;
  // Only rows a reader can see ask for their latest Snap; the archive asks when it opens.
  fetchMissingSnaps([...active, ...suspended, ...(archiveOpen ? visibleArchive : [])].map(latestSnapRemoteId));
}

/* Flow: Intents as cards, relations as curves */

// Card size, gaps and padding of the Flow canvas. A row grows where a card carries Decision pins.
const FLOW_GEOMETRY = {
  nodeW: 200, nodeH: 100, gapX: 72, gapY: 32, padX: 28, padTop: 12, padBottom: 28,
  axisH: 26, bandLabel: 24, bandRow: 28, pinTop: 18, pinRow: 18, pinBottom: 8,
};
const FLOW_PINS = 2;
const FLOW_BAND_ROWS = 3;
// Where vertical runs may sit inside a gap, as a share of its width; parts fan out nearest first.
const FLOW_TRACKS = [0.5, 0.3, 0.7, 0.15, 0.85];
const FLOW_FAN = [0.7, 0.5, 0.3, 0.15, 0.85];
// Heights (from a card's middle) where lines may meet its side, in each kind's order of preference.
const FLOW_PORTS = {
  flow: [0, -12, 12, -24, 24, -36, 36],
  branch: [12, 24, 36, 0, -12, -24, -36],
  depends: [12, 24, 36, 0, -12, -24, -36],
  conflict: [-12, -24, -36, 0, 12, 24, 36],
};
// How far a bend may reach along a horizontal leg (across a gap) and a vertical one, and how full it is.
const FLOW_BEND = { across: 36, along: 84, fullness: 0.62 };
// Regular-weight labels run narrower than the semibold titles the width estimate is tuned for.
const FLOW_REGULAR = 0.9;
const FLOW_LINE_ORDER = ["rejoin", "branch", "flow", "depends", "conflict"];

function flowTime(object) {
  const time = Date.parse(object?.created_at || "");
  return Number.isFinite(time) ? time : 0;
}

function byCreation(left, right) {
  return flowTime(left) - flowTime(right) || String(left.id).localeCompare(String(right.id));
}

function flowDay(time) {
  const date = new Date(time);
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
}

// Lay out the Flow graph: logical columns and lanes, pixel boxes and routed lines. Pure, no DOM.
// - Columns follow creation time and never go back; a parent or predecessor also pushes the
//   later Intent at least one column right.
// - Lanes are rows. A successor continues its predecessor's lane; parts and derived Intents open
//   lanes below their parent. A row is as tall as its tallest card with Decision pins.
// - Routes run only through the gaps between columns and rows, so they never cross a card;
//   flowCurve() then turns each route into curves that stay in the same free space.
function flowLayout(intents, decisions = [], { hideEnded = false, focus = "", geometry = {} } = {}) {
  const g = { ...FLOW_GEOMETRY, ...geometry };
  const byId = intentMap(intents);
  const links = relationLinks(byId);
  const focusId = focus && byId.has(focus) ? focus : "";
  let visible = new Set(byId.keys());
  if (focusId) {
    visible = new Set([focusId]);
    for (const link of links) {
      if (link.subject === focusId) visible.add(link.target);
      if (link.target === focusId) visible.add(link.subject);
    }
  }
  if (hideEnded) for (const id of [...visible]) if (id !== focusId && ENDED_STATUSES.has(byId.get(id).status)) visible.delete(id);
  const relations = links.filter((link) => visible.has(link.subject) && visible.has(link.target));
  // Standalone means no relation at all; an Intent whose partners are hidden still belongs to the flow.
  const related = new Set(links.flatMap((link) => [link.subject, link.target]));
  const shown = [...visible].map((id) => byId.get(id)).sort(byCreation);
  const placed = focusId ? shown : shown.filter((intent) => related.has(intent.id));
  const standalone = focusId ? [] : shown.filter((intent) => !related.has(intent.id));
  const rank = new Map(placed.map((intent, index) => [intent.id, index]));

  const parentOf = new Map();
  const predecessors = new Map();
  for (const link of relations) {
    if (PARENT_RELATIONS.has(link.type) && !parentOf.has(link.subject)) parentOf.set(link.subject, link.target);
    if (link.type === "succeeds") predecessors.set(link.subject, [...(predecessors.get(link.subject) || []), link.target]);
  }
  for (const list of predecessors.values()) list.sort((left, right) => rank.get(left) - rank.get(right));
  const before = (id) => [parentOf.get(id), ...(predecessors.get(id) || [])].filter((other) => rank.has(other));

  // Creation order, except that a parent or predecessor always comes first. A cycle across
  // relation families (allowed by the rules) falls back to creation order.
  const order = [];
  const done = new Set();
  while (order.length < placed.length) {
    const next = placed.find((intent) => !done.has(intent.id) && before(intent.id).every((id) => done.has(id)))
      || placed.find((intent) => !done.has(intent.id));
    done.add(next.id);
    order.push(next);
  }

  const lanes = [];
  const laneOf = new Map();
  const placement = new Map();
  for (const intent of order) {
    const id = intent.id;
    const parent = laneOf.has(parentOf.get(id)) ? parentOf.get(id) : null;
    const preds = (predecessors.get(id) || []).filter((pred) => laneOf.has(pred));
    const free = preds.filter((pred) => lanes[laneOf.get(pred)].nodes.at(-1) === pred);
    // Carry on a predecessor's lane unless that would pull a part away from its own parent.
    const carry = free.find((pred) => !parent || parentOf.get(pred) === parent || lanes[laneOf.get(pred)].anchor === parent);
    if (carry) {
      const lane = lanes[laneOf.get(carry)];
      lane.nodes.push(id);
      laneOf.set(id, lane.index);
      placement.set(id, { kind: "continue", anchor: carry });
      continue;
    }
    const kind = parent ? "child" : preds.length ? "branch" : "root";
    const anchor = parent || preds[0] || null;
    lanes.push({ index: lanes.length, nodes: [id], kind, anchor });
    laneOf.set(id, lanes.length - 1);
    placement.set(id, { kind, anchor });
  }

  const colOf = new Map();
  let ratchet = 0;
  for (const intent of order) {
    const lane = lanes[laneOf.get(intent.id)];
    const index = lane.nodes.indexOf(intent.id);
    let col = ratchet;
    if (index > 0) col = Math.max(col, colOf.get(lane.nodes[index - 1]) + 1);
    for (const other of before(intent.id)) if (colOf.has(other)) col = Math.max(col, colOf.get(other) + 1);
    colOf.set(intent.id, col);
    ratchet = col;
  }

  const childLanes = new Map(lanes.map((lane) => [lane.index, []]));
  for (const lane of lanes) if (lane.kind !== "root") childLanes.get(laneOf.get(lane.anchor)).push(lane);
  const headOf = (lane) => lane.nodes[0];
  const rows = [];
  const visit = (lane) => {
    lane.row = rows.length;
    rows.push(lane);
    childLanes.get(lane.index)
      .sort((left, right) => colOf.get(right.anchor) - colOf.get(left.anchor)
        || colOf.get(headOf(left)) - colOf.get(headOf(right)) || rank.get(headOf(left)) - rank.get(headOf(right)))
      .forEach(visit);
  };
  lanes.filter((lane) => lane.kind === "root").sort((left, right) => rank.get(headOf(left)) - rank.get(headOf(right))).forEach(visit);

  // Decisions with a placed source hang as pins under its card; the others sit in the Project band.
  const knownDecisions = (decisions || []).filter((decision) => decision?.id).sort(byCreation);
  const hasSource = (decision) => Boolean(decision.source_intent_id) && byId.has(decision.source_intent_id);
  const pinned = new Map();
  for (const decision of knownDecisions) {
    if (hasSource(decision) && rank.has(decision.source_intent_id)) {
      pinned.set(decision.source_intent_id, [...(pinned.get(decision.source_intent_id) || []), decision]);
    }
  }
  const pinRows = (id) => {
    const count = (pinned.get(id) || []).length;
    return Math.min(count, FLOW_PINS) + (count > FLOW_PINS ? 1 : 0);
  };
  const pinSpace = (id) => (pinRows(id) ? g.pinTop + (pinRows(id) - 1) * g.pinRow + g.pinBottom : 0);

  const columnAt = (time) => order.reduce((col, intent) => (flowTime(intent) <= time ? Math.max(col, colOf.get(intent.id)) : col), 0);
  const bandColumns = new Map();
  for (const decision of focusId || !placed.length ? [] : knownDecisions.filter((entry) => !hasSource(entry))) {
    const col = columnAt(flowTime(decision));
    bandColumns.set(col, [...(bandColumns.get(col) || []), decision]);
  }
  const chips = [];
  for (const [col, list] of bandColumns) {
    const listed = list.length > FLOW_BAND_ROWS ? list.slice(0, FLOW_BAND_ROWS - 1) : list;
    listed.forEach((decision, row) => chips.push({ decision, col, row }));
    if (list.length > listed.length) chips.push({ decision: null, col, row: listed.length, more: list.length - listed.length });
  }
  const bandRows = chips.reduce((most, chip) => Math.max(most, chip.row + 1), 0);

  // From the top: the time axis, the Project band, then the lanes.
  const colX = (col) => g.padX + col * (g.nodeW + g.gapX);
  const axisY = g.padTop;
  const bandY = axisY + g.axisH;
  const bandHeight = bandRows ? g.bandLabel + bandRows * g.bandRow : 0;
  const top = bandY + bandHeight + (bandRows ? g.gapY : g.gapY / 2);
  const extra = rows.map((lane) => Math.max(0, ...lane.nodes.map(pinSpace)));
  const rowTop = [];
  let next = top;
  rows.forEach((lane, row) => {
    rowTop[row] = next;
    next += g.nodeH + extra[row] + g.gapY;
  });
  const rowBottom = (row) => rowTop[row] + g.nodeH + extra[row];

  // A quiet time axis: the creation date of the first Intent to reach each column. An Intent moved right
  // by its predecessor counts from that predecessor's date, so the axis never runs back; one label a day.
  const reached = new Map();
  let clock = 0;
  for (const intent of order) {
    clock = Math.max(clock, flowTime(intent));
    if (!reached.has(colOf.get(intent.id))) reached.set(colOf.get(intent.id), clock);
  }
  const axis = [];
  for (const col of [...reached.keys()].sort((left, right) => left - right)) {
    const time = reached.get(col);
    if (time && axis.at(-1)?.day !== flowDay(time)) axis.push({ col, x: colX(col), y: axisY, time, day: flowDay(time) });
  }

  const nodes = order.map((intent) => {
    const row = lanes[laneOf.get(intent.id)].row;
    const x = colX(colOf.get(intent.id));
    const y = rowTop[row];
    const { kind, anchor } = placement.get(intent.id);
    return {
      id: intent.id, intent, col: colOf.get(intent.id), lane: row, x, y, cx: x + g.nodeW / 2, cy: y + g.nodeH / 2,
      placement: kind, anchor, decisions: pinned.get(intent.id) || [],
      box: { x1: x, y1: y, x2: x + g.nodeW, y2: y + g.nodeH + pinSpace(intent.id) },
    };
  });
  const nodeOf = new Map(nodes.map((node) => [node.id, node]));
  const rowNodes = new Map();
  for (const node of nodes) rowNodes.set(node.lane, [...(rowNodes.get(node.lane) || []), node]);
  const laneClear = (row, from, to) => !(rowNodes.get(row) || []).some((node) => node.col > Math.min(from, to) && node.col < Math.max(from, to));
  const maxCol = nodes.reduce((most, node) => Math.max(most, node.col), 0);

  // Vertical runs share the gaps between columns (gap k lies just left of column k);
  // each run takes its own track so two lines never lie on top of each other.
  const usedTracks = new Map();
  const track = (gap, y1, y2, prefer, allowed = FLOW_TRACKS) => {
    const lo = Math.min(y1, y2) - 10;
    const hi = Math.max(y1, y2) + 10;
    const used = usedTracks.get(gap) || [];
    const share = [...allowed].sort((a, b) => Math.abs(a - prefer) - Math.abs(b - prefer))
      .find((candidate) => !used.some((entry) => entry.share === candidate && entry.lo < hi && entry.hi > lo)) ?? prefer;
    used.push({ share, lo, hi });
    usedTracks.set(gap, used);
    return Math.max(4, colX(gap) - g.gapX + g.gapX * share);
  };
  // Lines meeting the same side of a card do so at their own height.
  const usedPorts = new Map();
  const portsOf = (node, side) => {
    const key = `${node.id}:${side}`;
    if (!usedPorts.has(key)) usedPorts.set(key, new Set());
    return usedPorts.get(key);
  };
  const reserve = (node, side) => portsOf(node, side).add(0);
  const port = (node, side, kind) => {
    const used = portsOf(node, side);
    const slot = FLOW_PORTS[kind].find((offset) => !used.has(offset)) ?? FLOW_PORTS[kind][0];
    used.add(slot);
    return node.cy + slot;
  };
  // Along whichever lane is clear, through the gap beside the other end; around on a gap row otherwise.
  const connect = (from, to, kind, prefer) => {
    if (to.col === from.col) {
      const y1 = port(from, "right", kind);
      const y2 = port(to, "right", kind);
      const gx = track(from.col + 1, y1, y2, prefer);
      return [[from.x + g.nodeW, y1], [gx, y1], [gx, y2], [to.x + g.nodeW, y2]];
    }
    const forward = to.col > from.col;
    const exitX = forward ? from.x + g.nodeW : from.x;
    const enterX = forward ? to.x : to.x + g.nodeW;
    const y1 = port(from, forward ? "right" : "left", kind);
    const y2 = port(to, forward ? "left" : "right", kind);
    const besideTarget = forward ? to.col : to.col + 1;
    const besideSource = forward ? from.col + 1 : from.col;
    if (laneClear(from.lane, from.col, to.col)) {
      if (from.lane === to.lane && y1 === y2) return [[exitX, y1], [enterX, y2]];
      const gx = track(besideTarget, y1, y2, prefer);
      return [[exitX, y1], [gx, y1], [gx, y2], [enterX, y2]];
    }
    if (laneClear(to.lane, from.col, to.col)) {
      const gx = track(besideSource, y1, y2, prefer);
      return [[exitX, y1], [gx, y1], [gx, y2], [enterX, y2]];
    }
    const rowLine = from.cy <= to.cy ? rowTop[to.lane] - g.gapY / 2 : rowBottom(to.lane) + g.gapY / 2;
    const sx = track(besideSource, y1, rowLine, prefer);
    const tx = track(besideTarget, rowLine, y2, prefer);
    return [[exitX, y1], [sx, y1], [sx, rowLine], [tx, rowLine], [tx, y2], [enterX, y2]];
  };

  const lines = [];
  const laneEnd = new Map(lanes.map((lane) => [lane.row, nodeOf.get(lane.nodes.at(-1)).x + g.nodeW]));
  const ends = (link) => [nodeOf.get(link.target), nodeOf.get(link.subject)];
  const about = (link) => ({ type: link.type, subject: link.subject, target: link.target, state: link.state });
  const carried = (from, to) => to.lane === from.lane && lanes[laneOf.get(to.id)].nodes[lanes[laneOf.get(to.id)].nodes.indexOf(to.id) - 1] === from.id;
  const forked = (from, to) => to.placement === "branch" && to.anchor === from.id;
  const tree = (from, to) => to.placement === "child" && to.anchor === from.id;

  // A lane's own successions keep the middle of both sides.
  for (const link of relations) {
    const [from, to] = ends(link);
    if (link.type !== "succeeds" || !carried(from, to)) continue;
    reserve(from, "right");
    reserve(to, "left");
    lines.push({ ...about(link), kind: "flow", arrow: true, points: [[from.x + g.nodeW, from.cy], [to.x, to.cy]] });
  }
  // Each part or derived Intent gets its own strand from its parent's side, nearest child highest and
  // furthest from the parent, so the strands nest instead of crossing.
  const children = new Map();
  for (const link of relations) {
    const [from, to] = ends(link);
    if (PARENT_RELATIONS.has(link.type) && tree(from, to)) children.set(from.id, [...(children.get(from.id) || []), { link, to }]);
  }
  for (const [parentId, list] of children) {
    const from = nodeOf.get(parentId);
    list.sort((left, right) => left.to.lane - right.to.lane).forEach(({ link, to }, index) => {
      reserve(to, "left");
      const y1 = port(from, "right", "branch");
      const gx = track(from.col + 1, y1, to.cy, FLOW_FAN[index] ?? 0.5);
      lines.push({ ...about(link), kind: "branch", points: [[from.x + g.nodeW, y1], [gx, y1], [gx, to.cy], [to.x, to.cy]] });
    });
  }
  for (const link of relations) {
    const [from, to] = ends(link);
    // A part that has ended (done or dropped) rejoins its parent's lane.
    if (link.type === "part_of" && ENDED_STATUSES.has(to.intent.status) && to.lane !== from.lane) {
      reserve(to, "right");
      // It turns back along the parent's lane, so it keeps clear of the column edge.
      const gx = track(to.col + 1, to.cy, from.cy, 0.3, FLOW_TRACKS.filter((share) => share >= 0.3));
      const endX = Math.max(to.x + g.nodeW + 2, gx - 30);
      lines.push({ ...about(link), kind: "rejoin", points: [[to.x + g.nodeW, to.cy], [gx, to.cy], [gx, from.cy], [endX, from.cy]] });
      laneEnd.set(from.lane, Math.max(laneEnd.get(from.lane), gx));
    }
    if (link.type === "succeeds" && forked(from, to)) {
      reserve(from, "right");
      reserve(to, "left");
      const gx = track(from.col + 1, from.cy, to.cy, 0.5);
      lines.push({ ...about(link), kind: "flow", arrow: true, points: [[from.x + g.nodeW, from.cy], [gx, from.cy], [gx, to.cy], [to.x, to.cy]] });
    }
  }
  for (const type of [...PARENT_RELATIONS, "succeeds", "depends_on", "conflicts_with"]) {
    for (const link of relations.filter((entry) => entry.type === type)) {
      const [from, to] = ends(link);
      if (PARENT_RELATIONS.has(type) && !tree(from, to)) {
        lines.push({ ...about(link), kind: "branch", points: connect(from, to, "branch", 0.5) });
      } else if (type === "succeeds" && !carried(from, to) && !forked(from, to)) {
        lines.push({ ...about(link), kind: "flow", arrow: true, points: connect(from, to, "flow", 0.5) });
      } else if (type === "depends_on") {
        lines.push({ ...about(link), kind: "depends", arrow: true, points: connect(from, to, "depends", 0.3) });
      } else if (type === "conflicts_with") {
        lines.push({ ...about(link), kind: "conflict", points: connect(from, to, "conflict", 0.7) });
      }
    }
  }
  lines.sort((left, right) => FLOW_LINE_ORDER.indexOf(left.kind) - FLOW_LINE_ORDER.indexOf(right.kind));
  const obstacles = nodes.map((node) => node.box);
  for (const line of lines) line.curve = flowCurve(line.points, obstacles);
  // A parent's lane only runs on as far as its ended parts come back to join it.
  const laneLines = lanes.map((lane) => {
    const last = nodeOf.get(lane.nodes.at(-1));
    const x2 = laneEnd.get(lane.row);
    return x2 > last.x + g.nodeW + 1 ? { row: lane.row, x1: last.x + g.nodeW, x2, y: last.cy } : null;
  }).filter(Boolean);

  const reach = Math.max(colX(maxCol) + g.nodeW + g.padX, ...lines.flatMap((line) => line.points.map((point) => point[0] + 16)), ...laneLines.map((line) => line.x2 + 16));
  return {
    geometry: g, hasRelations: links.length > 0, focus: focusId, relations, standalone,
    nodes: [...nodes].sort((left, right) => left.lane - right.lane || left.col - right.col),
    lines, laneLines, axis,
    band: bandRows ? {
      y: bandY, height: bandHeight,
      // A chip may run on over the next column when no chip of its row starts there.
      chips: chips.map((chip) => {
        const next = chips.filter((other) => other.row === chip.row && other.col > chip.col).reduce((nearest, other) => Math.min(nearest, other.col), chip.col + 2);
        const span = Math.min(next, chip.col + 2) - chip.col;
        const width = Math.min(span * g.nodeW + (span - 1) * g.gapX, colX(maxCol) + g.nodeW - colX(chip.col));
        return { ...chip, x: colX(chip.col), y: bandY + g.bandLabel + chip.row * g.bandRow, width };
      }),
    } : null,
    width: nodes.length ? Math.ceil(reach) : 0,
    height: nodes.length ? Math.ceil(rowBottom(rows.length - 1) + g.padBottom) : 0,
    columns: nodes.length ? maxCol + 1 : 0, lanes: rows.length,
  };
}

// The card to bring into view first: the focused Intent, else the most recent open one.
function flowTarget(layout) {
  if (!layout.nodes.length) return null;
  if (layout.focus) return layout.nodes.find((node) => node.id === layout.focus) || null;
  const open = layout.nodes.filter((node) => !ENDED_STATUSES.has(node.intent.status));
  return [...(open.length ? open : layout.nodes)].sort((left, right) => byCreation(right.intent, left.intent))[0];
}

// Drop repeated points and merge straight runs, so every remaining point is a real bend.
function flowSimplify(points) {
  const list = [];
  for (const point of points) {
    const last = list.at(-1);
    if (last && last[0] === point[0] && last[1] === point[1]) continue;
    const before = list.at(-2);
    if (before && ((before[0] === last[0] && last[0] === point[0] && Math.sign(last[1] - before[1]) === Math.sign(point[1] - last[1]))
        || (before[1] === last[1] && last[1] === point[1] && Math.sign(last[0] - before[0]) === Math.sign(point[0] - last[0])))) {
      list.pop();
    }
    list.push(point);
  }
  return list;
}

// Turn an orthogonal route into tangent-continuous curves. A single step across a gap
// (horizontal, vertical, horizontal) becomes one S with horizontal tangents and control points
// half way across, when its box is clear. Otherwise each bend becomes a cubic reaching up to
// FLOW_BEND.across along a horizontal leg and FLOW_BEND.along along a vertical one, never more than
// half a shared leg; it shrinks until its control box, which holds the whole curve, clears every card.
function flowCurve(points, obstacles = []) {
  const list = flowSimplify(points);
  const start = list[0] || [0, 0];
  if (list.length < 2) return { start, segments: [] };
  const clear = (x1, y1, x2, y2) => !obstacles.some((box) => Math.min(x1, x2) < box.x2 - 0.5 && Math.max(x1, x2) > box.x1 + 0.5
    && Math.min(y1, y2) < box.y2 - 0.5 && Math.max(y1, y2) > box.y1 + 0.5);
  const [p0, p1, p2, p3] = list;
  if (list.length === 4 && p0[1] === p1[1] && p1[0] === p2[0] && p2[1] === p3[1]
      && Math.sign(p1[0] - p0[0]) === Math.sign(p3[0] - p2[0]) && clear(p0[0], p0[1], p3[0], p3[1])) {
    const half = (p3[0] - p0[0]) / 2;
    return { start, segments: [{ c1: [p0[0] + half, p0[1]], c2: [p3[0] - half, p3[1]], to: p3 }] };
  }
  const segments = [];
  let at = start;
  for (let index = 1; index < list.length - 1; index++) {
    const [px, py] = list[index - 1];
    const [x, y] = list[index];
    const [nx, ny] = list[index + 1];
    const inLength = Math.hypot(x - px, y - py);
    const outLength = Math.hypot(nx - x, ny - y);
    const uIn = [(x - px) / inLength, (y - py) / inLength];
    const uOut = [(nx - x) / outLength, (ny - y) / outLength];
    // The legs at either end keep a short straight piece where they meet a card.
    const reach = (length, unit, shared) => Math.max(0, Math.min(unit[1] ? FLOW_BEND.along : FLOW_BEND.across, shared ? length / 2 : length - 8));
    let rIn = reach(inLength, uIn, index > 1);
    let rOut = reach(outLength, uOut, index < list.length - 2);
    const box = () => {
      const ax = x - uIn[0] * rIn;
      const ay = y - uIn[1] * rIn;
      const bx = x + uOut[0] * rOut;
      const by = y + uOut[1] * rOut;
      return [Math.min(ax, bx, x), Math.min(ay, by, y), Math.max(ax, bx, x), Math.max(ay, by, y)];
    };
    for (let attempt = 0; attempt < 12 && !clear(...box()); attempt++) {
      rIn *= 0.7;
      rOut *= 0.7;
    }
    if (rIn < 1 || rOut < 1 || !clear(...box())) {
      segments.push({ to: [x, y] });
      at = [x, y];
      continue;
    }
    const a = [x - uIn[0] * rIn, y - uIn[1] * rIn];
    const b = [x + uOut[0] * rOut, y + uOut[1] * rOut];
    if (Math.hypot(a[0] - at[0], a[1] - at[1]) > 0.01) segments.push({ to: a });
    const k = FLOW_BEND.fullness;
    segments.push({ c1: [a[0] + uIn[0] * rIn * k, a[1] + uIn[1] * rIn * k], c2: [b[0] - uOut[0] * rOut * k, b[1] - uOut[1] * rOut * k], to: b });
    at = b;
  }
  const last = list.at(-1);
  if (Math.hypot(last[0] - at[0], last[1] - at[1]) > 0.01) segments.push({ to: last });
  return { start, segments };
}

function flowCubicPoint(from, c1, c2, to, t) {
  const s = 1 - t;
  return [0, 1].map((axis) => s * s * s * from[axis] + 3 * s * s * t * c1[axis] + 3 * s * t * t * c2[axis] + t * t * t * to[axis]);
}

// Points along a rendered curve: each cubic sampled `steps` times, each straight piece at its ends.
function flowSamples(curve, steps = 12) {
  const points = [curve.start];
  let from = curve.start;
  for (const segment of curve.segments) {
    if (segment.c1) for (let index = 1; index <= steps; index++) points.push(flowCubicPoint(from, segment.c1, segment.c2, segment.to, index / steps));
    else points.push(segment.to);
    from = segment.to;
  }
  return points;
}

function flowCurveEnd(curve) {
  const last = curve.segments.at(-1);
  const [x, y] = last.to;
  const from = last.c2 || curve.segments.at(-2)?.to || curve.start;
  const length = Math.hypot(x - from[0], y - from[1]);
  return { x, y, ux: length ? (x - from[0]) / length : 1, uy: length ? (y - from[1]) / length : 0, length };
}

// Stop the stroke short of an arrow tip so it never pokes through; a final cubic keeps its tangent.
function flowTrimCurve(curve, by) {
  const end = flowCurveEnd(curve);
  const last = curve.segments.at(-1);
  if (!last.c2 && end.length <= by) return curve;
  const trimmed = { ...last, to: [end.x - end.ux * by, end.y - end.uy * by] };
  if (last.c2) trimmed.c2 = [last.c2[0] - end.ux * by, last.c2[1] - end.uy * by];
  return { start: curve.start, segments: [...curve.segments.slice(0, -1), trimmed] };
}

function flowCurvePath(curve) {
  const n = flowNumber;
  return [`M${n(curve.start[0])} ${n(curve.start[1])}`, ...curve.segments.map((segment) => (segment.c1
    ? `C${n(segment.c1[0])} ${n(segment.c1[1])} ${n(segment.c2[0])} ${n(segment.c2[1])} ${n(segment.to[0])} ${n(segment.to[1])}`
    : `L${n(segment.to[0])} ${n(segment.to[1])}`))].join(" ");
}

// A small arrowhead along the end tangent.
function flowArrowHead(end, size) {
  const n = flowNumber;
  const bx = end.x - end.ux * size;
  const by = end.y - end.uy * size;
  const half = size * 0.5;
  return `M${n(end.x)} ${n(end.y)} L${n(bx - end.uy * half)} ${n(by + end.ux * half)} L${n(bx + end.uy * half)} ${n(by - end.ux * half)} Z`;
}

const FLOW_WIDE = /[\u1100-\u115f\u2e80-\ua4cf\uac00-\ud7a3\uf900-\ufaff\ufe30-\ufe4f\uff00-\uff60\uffe0-\uffe6]/;

// SVG text does not wrap, so titles are fitted by an estimate that errs on the narrow side
// (semibold by default; `scale` below 1 for regular text).
function flowTextWidth(text, size, scale = 1) {
  let units = 0;
  for (const char of String(text)) {
    units += FLOW_WIDE.test(char) ? 1 : char === " " ? 0.3 : /[ijlrtf.,:;'|!()[\]]/.test(char) ? 0.36 : /[A-Z0-9mwMW@#%&]/.test(char) ? 0.72 : 0.6;
  }
  return units * size * scale;
}

function flowTokens(text) {
  const tokens = [];
  let word = "";
  for (const char of String(text || "").replace(/\s+/g, " ").trim()) {
    if (char === " " || FLOW_WIDE.test(char)) {
      if (word) tokens.push(word);
      word = "";
      tokens.push(char);
    } else {
      word += char;
    }
  }
  if (word) tokens.push(word);
  return tokens;
}

function flowLines(text, maxWidth, size = 13, maxLines = 2, scale = 1) {
  const fits = (value) => flowTextWidth(value, size, scale) <= maxWidth;
  const tokens = flowTokens(text);
  const lines = [];
  let line = "";
  let overflow = false;
  const close = () => {
    lines.push(line.trimEnd());
    line = "";
    return lines.length >= maxLines;
  };
  for (let index = 0; index < tokens.length && !overflow; index++) {
    const token = tokens[index];
    if (fits(line + token)) {
      line += token;
    } else if (token === " ") {
      if (close()) overflow = index < tokens.length - 1;
    } else {
      if (line.trim() && close()) {
        overflow = true;
        break;
      }
      line = "";
      // A word wider than the whole line breaks between characters.
      for (const char of token) {
        if (line && !fits(line + char) && close()) {
          overflow = true;
          break;
        }
        line += char;
      }
    }
  }
  if (!overflow && line.trim()) {
    if (lines.length < maxLines) lines.push(line.trimEnd());
    else overflow = true;
  }
  if (overflow && lines.length) {
    let last = lines.at(-1);
    while (last && !fits(`${last}…`)) last = [...last].slice(0, -1).join("");
    lines[lines.length - 1] = `${last.trimEnd()}…`;
  }
  return lines;
}

function flowNumber(value) {
  return Math.round(value * 10) / 10;
}

function flowMidpoint(points) {
  const lengths = points.slice(1).map((point, index) => Math.hypot(point[0] - points[index][0], point[1] - points[index][1]));
  let remaining = lengths.reduce((sum, length) => sum + length, 0) / 2;
  for (let index = 0; index < lengths.length; index++) {
    if (remaining <= lengths[index] && lengths[index]) {
      const ratio = remaining / lengths[index];
      return [points[index][0] + (points[index + 1][0] - points[index][0]) * ratio, points[index][1] + (points[index + 1][1] - points[index][1]) * ratio];
    }
    remaining -= lengths[index];
  }
  return points.at(-1);
}

// Line colour carries relation state; only dependencies turn green once satisfied.
function flowLineTone(line) {
  if (line.type === "depends_on") return relationTone(line.state);
  return ATTENTION_STATES.has(line.state) ? "attention" : "neutral";
}

function flowLineSvg(line) {
  const size = line.kind === "flow" ? 8 : 6;
  const end = flowCurveEnd(line.curve);
  const d = flowCurvePath(line.arrow ? flowTrimCurve(line.curve, size * 0.75) : line.curve);
  const state = relationStateLabel(line.state);
  const title = `${line.subject} · ${relationLabel(line.type, "out")} · ${line.target}${state ? ` · ${state}` : ""}`;
  const settled = line.state === "resolved" ? " is-settled" : "";
  let mark = "";
  if (line.kind === "conflict") {
    const [mx, my] = flowMidpoint(flowSamples(line.curve));
    mark = `<g class="flow-vs"><rect x="${flowNumber(mx - 12)}" y="${flowNumber(my - 8)}" width="24" height="16" rx="8"/><text x="${flowNumber(mx)}" y="${flowNumber(my + 3.5)}" text-anchor="middle">vs</text></g>`;
  } else if (line.kind === "branch") {
    // Where a branch meets the child: a filled dot for a part, a hollow one for a derived Intent.
    mark = `<circle class="flow-terminal" cx="${flowNumber(end.x - end.ux * 4)}" cy="${flowNumber(end.y - end.uy * 4)}" r="2.75"/>`;
  }
  return `<g class="flow-line flow-${line.kind} flow-type-${line.type} tone-${flowLineTone(line)}${settled}"><title>${esc(title)}</title><path class="flow-hit-line" d="${d}"/><path class="flow-stroke" d="${d}"/>${line.arrow ? `<path class="flow-arrow" d="${flowArrowHead(end, size)}"/>` : ""}${mark}</g>`;
}

function flowNodeLabel(node, layout) {
  const intent = node.intent;
  const parts = [`${intent.id}: ${intent.what || ""}`, intentStatusLabel(intent.status), plural((intent.snap_ids || []).length, "{count} snap", "{count} snaps")];
  if (node.decisions.length) parts.push(plural(node.decisions.length, "{count} decision", "{count} decisions"));
  // Spoken in the order of the detail sheet: where it comes from first, then by relation type.
  const rows = layout.relations
    .filter((link) => link.subject === node.id || link.target === node.id)
    .map((link) => ({ link, outgoing: link.subject === node.id }))
    .sort((left, right) => right.outgoing - left.outgoing || RELATION_TYPES.indexOf(left.link.type) - RELATION_TYPES.indexOf(right.link.type)
      || String(left.outgoing ? left.link.target : left.link.subject).localeCompare(String(right.outgoing ? right.link.target : right.link.subject)));
  for (const { link, outgoing } of rows) {
    const state = relationStateLabel(link.state, { type: link.type, direction: outgoing ? "out" : "in" });
    parts.push(`${relationLabel(link.type, outgoing ? "out" : "in")} ${outgoing ? link.target : link.subject}${state ? ` (${state})` : ""}`);
  }
  return parts.join(". ");
}

// A card: status pill and id, a title of up to two lines, then its Snaps and Decisions.
function flowNodeSvg(node, layout) {
  const g = layout.geometry;
  const intent = node.intent;
  const status = ["active", "suspend", "done", "cancelled"].includes(intent.status) ? intent.status : "unknown";
  const label = intentStatusLabel(intent.status);
  const title = flowLines(intent.what || intent.id, g.nodeW - 28, 13, 2);
  const meta = [plural((intent.snap_ids || []).length, "{count} snap", "{count} snaps")];
  if (node.decisions.length) meta.push(plural(node.decisions.length, "{count} decision", "{count} decisions"));
  return `<g class="flow-node status-${status}${layout.focus === node.id ? " is-focus" : ""}" role="button" tabindex="0" data-detail-type="intent" data-remote-id="${esc(intent.remote_id || remoteId(intent.project_id, intent.id))}" aria-label="${esc(flowNodeLabel(node, layout))}" transform="translate(${flowNumber(node.x)} ${flowNumber(node.y)})">
    <title>${esc(intent.what || intent.id)}</title>
    <g class="flow-node-body">
      <rect class="flow-node-ring" x="-4" y="-4" width="${g.nodeW + 8}" height="${g.nodeH + 8}" rx="15"/>
      <rect class="flow-node-box" width="${g.nodeW}" height="${g.nodeH}" rx="12"/>
      <g class="flow-pill" data-fit="25"><rect class="flow-pill-box" x="12" y="12" width="${flowNumber(25 + flowTextWidth(label, 11, FLOW_REGULAR))}" height="20" rx="10" data-fit-box/><circle class="flow-node-dot" cx="21" cy="22" r="3"/><text class="flow-node-status" x="29" y="25.5" data-fit-text>${esc(label)}</text></g>
      <text class="flow-node-id" x="${g.nodeW - 12}" y="25.5" text-anchor="end">${esc(intent.id)}</text>
      ${title.map((line, index) => `<text class="flow-node-title" x="14" y="${50 + index * 17}">${esc(line)}</text>`).join("")}
      <text class="flow-node-meta" x="14" y="${g.nodeH - 12}">${esc(meta.join(" · "))}</text>
    </g>
  </g>`;
}

function flowDecisionLabel(decision, projectLevel) {
  return `${t("Decision")} ${decision.id}: ${decision.what || ""} (${decisionStatusLabel(decision.status)}${projectLevel ? ` · ${t("Project-level")}` : ""})`;
}

function flowDiamond(x, y, size) {
  const n = flowNumber;
  return `M${n(x)} ${n(y - size)} L${n(x + size)} ${n(y)} L${n(x)} ${n(y + size)} L${n(x - size)} ${n(y)} Z`;
}

// Decisions taken from an Intent hang under its card: a dotted stem, then a diamond and a line of text each.
function flowPinsSvg(node, layout) {
  if (!node.decisions.length) return "";
  const g = layout.geometry;
  const x = node.x + 18;
  const top = node.y + g.nodeH;
  const listed = node.decisions.length > FLOW_PINS ? node.decisions.slice(0, FLOW_PINS) : node.decisions;
  const more = node.decisions.length - listed.length;
  const rowY = (index) => top + g.pinTop + index * g.pinRow;
  const pins = listed.map((decision, index) => {
    const y = rowY(index);
    const text = flowLines(decision.what || decision.id, g.nodeW - 40, 11.5, 1, FLOW_REGULAR)[0] || "";
    return `<g class="flow-decision flow-pin${decision.status === "deprecated" ? " is-deprecated" : ""}" role="button" tabindex="0" data-detail-type="decision" data-remote-id="${esc(decision.remote_id || remoteId(decision.project_id, decision.id))}" aria-label="${esc(flowDecisionLabel(decision, false))}" data-fit="0" data-fit-max="${g.nodeW - 40}">
      <title>${esc(`${decision.id} · ${decision.what || ""}`)}</title>
      <rect class="flow-hit" x="${flowNumber(x - 9)}" y="${flowNumber(y - 9)}" width="${flowNumber(g.nodeW - 18)}" height="18" rx="6"/>
      <path class="flow-decision-shape" d="${flowDiamond(x, y, 4.5)}"/>
      <text class="flow-pin-text" x="${flowNumber(x + 11)}" y="${flowNumber(y + 4)}" data-fit-text data-full="${esc(decision.what || decision.id)}">${esc(text)}</text>
    </g>`;
  }).join("");
  return `<path class="flow-pin-stem" aria-hidden="true" d="M${flowNumber(x)} ${flowNumber(top + 3)} V${flowNumber(rowY(listed.length - 1) - 6)}"/>${pins}`
    + (more ? `<text class="flow-pin-more" x="${flowNumber(x + 11)}" y="${flowNumber(rowY(listed.length) + 4)}">${esc(t("+{count} more", {count: more}))}</text>` : "");
}

// A Project-level Decision: a chip at the column of its time.
function flowChipSvg(chip) {
  const { x, y } = chip;
  if (!chip.decision) {
    return `<g class="flow-chip is-more" aria-hidden="true"><rect class="flow-chip-box" x="${x}" y="${y}" width="44" height="22" rx="11"/><text class="flow-chip-text" x="${x + 22}" y="${y + 15}" text-anchor="middle">+${chip.more}</text></g>`;
  }
  const decision = chip.decision;
  const text = flowLines(decision.what || decision.id, chip.width - 38, 12, 1, FLOW_REGULAR)[0] || "";
  return `<g class="flow-decision flow-chip${decision.status === "deprecated" ? " is-deprecated" : ""}" role="button" tabindex="0" data-detail-type="decision" data-remote-id="${esc(decision.remote_id || remoteId(decision.project_id, decision.id))}" aria-label="${esc(flowDecisionLabel(decision, true))}" data-fit="36" data-fit-max="${chip.width}">
    <title>${esc(`${decision.id} · ${decision.what || ""}`)}</title>
    <rect class="flow-chip-box" x="${x}" y="${y}" width="${flowNumber(Math.min(chip.width, 36 + flowTextWidth(text, 12, FLOW_REGULAR)))}" height="22" rx="11" data-fit-box/>
    <path class="flow-decision-shape" d="${flowDiamond(x + 13, y + 11, 4.5)}"/>
    <text class="flow-chip-text" x="${x + 24}" y="${y + 15}" data-fit-text data-full="${esc(decision.what || decision.id)}">${esc(text)}</text>
  </g>`;
}

function flowAxisLabel(time) {
  const date = new Date(time);
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return new Intl.DateTimeFormat(window.IntHubI18n.language, sameYear ? { month: "short", day: "numeric" } : { year: "numeric", month: "short", day: "numeric" }).format(date);
}

function renderFlowSvg(layout) {
  if (!layout.nodes.length) return "";
  const g = layout.geometry;
  const n = flowNumber;
  const defs = `<defs>
    <filter id="flow-card-shadow" x="-10%" y="-15%" width="120%" height="150%"><feDropShadow class="flow-shadow" dx="0" dy="1" stdDeviation="1.4"/></filter>
    <filter id="flow-card-lift" x="-15%" y="-20%" width="130%" height="170%"><feDropShadow class="flow-shadow-lift" dx="0" dy="5" stdDeviation="6"/></filter>
  </defs>`;
  const axis = layout.axis.length
    ? `<g class="flow-axis" aria-hidden="true"><path class="flow-axis-rule" d="M${g.padX} ${n(g.padTop + g.axisH - 6)} H${n(layout.width - g.padX)}"/>${layout.axis.map((tick) => `<path class="flow-axis-tick" d="M${n(tick.x)} ${n(tick.y + g.axisH - 10)} V${n(tick.y + g.axisH - 2)}"/><text class="flow-axis-label" x="${n(tick.x)}" y="${n(tick.y + 11)}">${esc(flowAxisLabel(tick.time))}</text>`).join("")}</g>`
    : "";
  const band = layout.band
    ? `<g class="flow-band" aria-hidden="true"><rect class="flow-band-box" x="10" y="${n(layout.band.y)}" width="${layout.width - 20}" height="${n(layout.band.height + 6)}" rx="12"/><text class="flow-band-label" x="${g.padX}" y="${n(layout.band.y + 16)}">${esc(t("Project"))}</text></g>${layout.band.chips.map(flowChipSvg).join("")}`
    : "";
  const laneLines = layout.laneLines.map((line) => `<path class="flow-lane-line" d="M${n(line.x1)} ${n(line.y)} H${n(line.x2)}"/>`).join("");
  // Reading order: the project band, then each card followed by its own Decisions.
  const nodes = layout.nodes.map((node) => flowNodeSvg(node, layout) + flowPinsSvg(node, layout)).join("");
  return `<svg class="flow-svg" width="${layout.width}" height="${layout.height}" viewBox="0 0 ${layout.width} ${layout.height}" role="group" aria-label="${esc(t("Flow between Intents"))}">
    ${defs}
    ${axis}
    ${band}
    <g class="flow-lines" aria-hidden="true">${laneLines}${layout.lines.map(flowLineSvg).join("")}</g>
    ${nodes}
  </svg>`;
}

// Cut a label to the longest start that fits, measured on the drawn text.
function fitFlowLabel(text, maxWidth) {
  const full = text.getAttribute("data-full");
  if (full === null) return;
  text.textContent = full;
  if (text.getComputedTextLength() <= maxWidth) return;
  let low = 0;
  let high = full.length;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    text.textContent = `${full.slice(0, middle).trimEnd()}…`;
    if (text.getComputedTextLength() <= maxWidth) low = middle;
    else high = middle - 1;
  }
  text.textContent = `${full.slice(0, low).trimEnd()}…`;
}

// SVG text cannot size its own box. Once drawn, labels are cut to fit exactly and pills and chips
// take the width of their text; the estimate drawn first stays wherever nothing can be measured.
function fitFlowText() {
  for (const group of el.detailContent.querySelectorAll?.(".flow-svg [data-fit]") || []) {
    const text = group.querySelector("[data-fit-text]");
    if (typeof text?.getComputedTextLength !== "function" || !text.getComputedTextLength()) continue;
    const pad = Number(group.dataset.fit) || 0;
    const max = Number(group.dataset.fitMax) || Infinity;
    fitFlowLabel(text, max - pad);
    group.querySelector("[data-fit-box]")?.setAttribute("width", String(flowNumber(Math.min(text.getComputedTextLength() + pad, max))));
  }
}

// Where a frame smaller than the graph should start: the target card fully in view, and among those
// positions the one showing the most card area, so the frame does not open on empty canvas.
function flowViewport(layout, width, height) {
  const target = flowTarget(layout);
  if (!target) return { left: 0, top: 0 };
  const margin = 16;
  const range = (start, size, extent, frame) => {
    const most = Math.max(0, extent - frame);
    const low = Math.min(most, Math.max(0, start + size + margin - frame));
    const high = Math.max(low, Math.min(most, start - margin));
    return Array.from({ length: 9 }, (_, index) => low + (high - low) * index / 8);
  };
  const box = target.box;
  let best = { left: 0, top: 0, score: -Infinity };
  for (const left of range(box.x1, box.x2 - box.x1, layout.width, width)) {
    for (const top of range(box.y1, box.y2 - box.y1, layout.height, height)) {
      let score = 0;
      for (const node of layout.nodes) {
        const across = Math.min(node.box.x2, left + width) - Math.max(node.box.x1, left);
        const down = Math.min(node.box.y2, top + height) - Math.max(node.box.y1, top);
        if (across > 0 && down > 0) score += across * down;
      }
      // Ties go to the position that centres the target best.
      score -= Math.abs(left + width / 2 - (box.x1 + box.x2) / 2) + Math.abs(top + height / 2 - (box.y1 + box.y2) / 2);
      if (score > best.score) best = { left, top, score };
    }
  }
  return { left: Math.round(best.left), top: Math.round(best.top) };
}

// The rows a window over [left, left + width] should keep: the target and its direct relations,
// and every card at least half inside the window.
function flowVisibleSpan(layout, left, width) {
  const target = flowTarget(layout);
  const near = new Set([target?.id]);
  for (const link of layout.relations) {
    if (link.subject === target?.id) near.add(link.target);
    if (link.target === target?.id) near.add(link.subject);
  }
  const shown = layout.nodes.filter((node) => near.has(node.id)
    || Math.min(node.box.x2, left + width) - Math.max(node.box.x1, left) >= (node.box.x2 - node.box.x1) / 2);
  if (!shown.length) return null;
  return { top: Math.min(...shown.map((node) => node.box.y1)), bottom: Math.max(...shown.map((node) => node.box.y2)) };
}

// When the graph is larger than its frame (a phone, a long history), open it at the card that matters.
// A frame that scrolls both ways (phones) also shrinks to the rows it opens on instead of empty canvas.
function revealFlowTarget(layout) {
  const canvas = el.detailContent.querySelector?.(".flow-canvas");
  if (!canvas?.clientWidth) return;
  canvas.style.removeProperty("height");
  if (canvas.scrollWidth <= canvas.clientWidth && canvas.scrollHeight <= canvas.clientHeight) return;
  let { left, top } = flowViewport(layout, canvas.clientWidth, canvas.clientHeight);
  const span = getComputedStyle(canvas).overflowY !== "hidden" ? flowVisibleSpan(layout, left, canvas.clientWidth) : null;
  if (span && span.bottom - span.top + 48 < canvas.clientHeight) {
    canvas.style.height = `${Math.max(280, Math.ceil(span.bottom - span.top + 48))}px`;
    top = Math.max(0, Math.round(span.top - 24));
  }
  canvas.scrollLeft = left;
  canvas.scrollTop = top;
}

function flowLegend() {
  const sample = (className, d, extra = "") => `<svg class="flow-legend-sample" viewBox="0 0 34 16" aria-hidden="true"><g class="flow-line ${className}"><path class="flow-stroke" d="${d}"/>${extra}</g></svg>`;
  const curve = "M2 3C17 3 17 13 31 13";
  const items = [
    [sample("flow-branch flow-type-part_of tone-neutral", curve, '<circle class="flow-terminal" cx="30" cy="13" r="2.75"/>'), t("Part of")],
    [sample("flow-branch flow-type-derived_from tone-neutral", curve, '<circle class="flow-terminal" cx="30" cy="13" r="2.75"/>'), t("Derived from")],
    [sample("flow-rejoin flow-type-part_of tone-neutral", "M2 13C17 13 17 3 32 3"), t("Rejoin")],
    [sample("flow-flow flow-type-succeeds tone-neutral", "M2 8H25", `<path class="flow-arrow" d="${flowArrowHead({ x: 32, y: 8, ux: 1, uy: 0 }, 8)}"/>`), t("Succeeds")],
    [sample("flow-depends flow-type-depends_on tone-neutral", "M2 3C15 3 15 13 27 13", `<path class="flow-arrow" d="${flowArrowHead({ x: 32, y: 13, ux: 1, uy: 0 }, 6)}"/>`), t("Depends on")],
    [sample("flow-conflict flow-type-conflicts_with tone-neutral", "M2 8H32"), t("Conflicts with")],
    [sample("flow-depends tone-attention", "M2 8H32"), t("Needs attention")],
    [sample("flow-depends tone-settled", "M2 8H32"), t("Satisfied")],
    [sample("flow-depends tone-danger", "M2 8H32"), t("Broken")],
    [`<svg class="flow-legend-sample is-mark" viewBox="0 0 16 16" aria-hidden="true"><g class="flow-decision"><path class="flow-decision-shape" d="${flowDiamond(8, 8, 5)}"/></g></svg>`, t("Decision")],
    [`<svg class="flow-legend-sample is-mark" viewBox="0 0 16 16" aria-hidden="true"><g class="flow-decision is-deprecated"><path class="flow-decision-shape" d="${flowDiamond(8, 8, 5)}"/></g></svg>`, t("Deprecated")],
  ];
  return `<ul class="flow-legend" aria-label="${esc(t("Legend"))}">${items.map(([visual, label]) => `<li>${visual}<span>${esc(label)}</span></li>`).join("")}</ul>`;
}

function flowFocusOptions(intents) {
  const related = new Set(relationLinks(intents).flatMap((link) => [link.subject, link.target]));
  return [...intentMap(intents).values()].filter((intent) => related.has(intent.id)).sort((left, right) => byCreation(right, left));
}

function flowControls(flow, options, focused) {
  const option = (key, label, meta = "") => `<button type="button" class="timeline-filter-option${flow.focus === key ? " is-selected" : ""}" data-flow-focus="${esc(key)}" aria-pressed="${flow.focus === key}"><span>${esc(label)}</span>${meta ? `<small>${esc(meta)}</small>` : ""}</button>`;
  return `
    <div class="flow-controls">
      <button type="button" class="flow-toggle" data-flow-hide-ended aria-pressed="${Boolean(flow.hideEnded)}">${icon("hide")}<span>${esc(t("Hide ended"))}</span></button>
      <details class="timeline-filter flow-focus">
        <summary class="timeline-filter-trigger" data-tip="${esc(t("Focus on one Intent and its direct relations"))}">${icon("focus")}<span>${esc(focused ? truncate(focused.what || focused.id, 36) : t("Focus on…"))}</span>${icon("chevronDown")}</summary>
        <div class="timeline-filter-menu">${option("", t("All Intents"))}${options.map((intent) => option(intent.id, intent.what || intent.id, intent.id)).join("")}</div>
      </details>
    </div>`;
}

// Intents without relations, drawn as the same cards as the graph.
function flowCard(intent, decisions) {
  const status = ["active", "suspend", "done", "cancelled"].includes(intent.status) ? intent.status : "unknown";
  const snaps = (intent.snap_ids || []).length;
  return `
    <button type="button" class="flow-card status-${status}" data-detail-type="intent" data-remote-id="${esc(intent.remote_id || remoteId(intent.project_id, intent.id))}">
      <span class="flow-card-top">${statusBadge(intent.status)}<span class="flow-card-id">${esc(intent.id)}</span></span>
      <strong class="flow-card-title">${esc(intent.what || intent.id)}</strong>
      <span class="flow-card-meta"><span>${esc(plural(snaps, "{count} snap", "{count} snaps"))}</span>${decisions ? `<span>${esc(plural(decisions, "{count} decision", "{count} decisions"))}</span>` : ""}</span>
    </button>`;
}

function renderFlowTab() {
  state._flow ||= { hideEnded: false, focus: "", standalone: PAGE_SIZE };
  const flow = state._flow;
  const intents = overviewIntents();
  const decisions = [...(state.overview.active_decisions || []), ...(state.overview.deprecated_decisions || [])];
  const byId = overviewIntentMap();
  if (flow.focus && !byId.has(flow.focus)) flow.focus = "";
  const layout = flowLayout(intents, decisions, { hideEnded: flow.hideEnded, focus: flow.focus });
  if (!layout.hasRelations) {
    el.detailContent.innerHTML = pageHeader({ title: t("Flow"), help: "flow" }) + `<div class="flow-empty">${emptyState({
      iconName: "flow",
      title: t("No relations between Intents yet."),
      body: t("Relations record where a goal comes from and what constrains it. Add them from the CLI; the flow appears here after the next push."),
      extra: commandSnippet([
        'itt intent create "Goal" --why "Reason" --part-of ID',
        "itt intent relate ID --depends-on OTHER",
        'itt intent cancel ID --into OTHER --reason "Duplicate"',
        'itt decision create "Rule" --why "Reason" --from ID',
      ]),
    })}</div>`;
    return;
  }
  const focused = flow.focus ? byId.get(flow.focus) : null;
  const attention = layout.relations.filter((link) => ATTENTION_STATES.has(link.state)).length;
  const header = pageHeader({
    title: t("Flow"),
    help: "flow",
    meta: [
      esc(plural(layout.relations.length, "{count} relation", "{count} relations")),
      ...(attention ? [esc(plural(attention, "{count} needs attention", "{count} need attention"))] : []),
      ...(focused ? [esc(t("Focused on {id}", {id: focused.id}))] : []),
    ],
    actions: flowControls(flow, flowFocusOptions(intents), focused),
  });
  const canvas = layout.nodes.length
    ? `<div class="flow-canvas">${renderFlowSvg(layout)}</div>`
    : `<div class="inline-empty">${esc(t("No related Intent is open. Show ended Intents to see the rest of the flow."))}</div>`;
  const sourced = new Map();
  for (const decision of decisions) if (decision.source_intent_id) sourced.set(decision.source_intent_id, (sourced.get(decision.source_intent_id) || 0) + 1);
  const cards = layout.standalone.slice(0, flow.standalone || PAGE_SIZE);
  const standalone = layout.standalone.length ? `
    <section class="section flow-standalone">
      ${sectionHeader(t("Not related to other Intents"), layout.standalone.length)}
      <div class="flow-standalone-grid">${cards.map((intent) => flowCard(intent, sourced.get(intent.id) || 0)).join("")}</div>
      ${layout.standalone.length > cards.length ? `<button type="button" class="load-more-btn" id="load-more-flow-standalone">${iconLabel("chevronDown", t("Load more ({count})", {count: layout.standalone.length - cards.length}))}</button>` : ""}
    </section>` : "";
  el.detailContent.innerHTML = `<div class="flow-page">${header}${flowLegend()}${canvas}${standalone}</div>`;
  fitFlowText();
  revealFlowTarget(layout);
  // Text measured before the web font arrived is measured again once it has.
  document.fonts?.ready?.then(() => { if (state.activeTab === "flow") fitFlowText(); });
}

// Focus the Flow on one Intent (or clear it with ""). From the sheet, the view moves to that node.
function showFlowFocus(intentId, { fromSheet = false } = {}) {
  state._flow ||= { hideEnded: false, focus: "", standalone: PAGE_SIZE };
  state._flow.focus = intentId || "";
  if (state.activeTab !== "flow") switchTab("flow");
  else {
    if (sheetIsOpen()) closeDrawer();
    renderView();
  }
  const target = fromSheet && intentId
    ? el.detailContent.querySelector(".flow-node.is-focus")
    : el.detailContent.querySelector(".flow-focus .timeline-filter-trigger");
  target?.focus();
}

/* Timeline */

function snapNumber(id) {
  return Number(String(id || "").match(/(\d+)$/)?.[1] || 0);
}

// Filter choices come from the Intents, not from loaded pages, so every Intent with Snaps is reachable.
// Most recently active first: Snap IDs grow with time inside a project.
function timelineIntentOptions(intents) {
  return (intents || [])
    .filter((intent) => (intent.snap_ids || []).length)
    .map((intent) => ({ key: intent.id, count: intent.snap_ids.length, label: intent.what || intent.id, latest: snapNumber(intent.latest_snap_id || intent.snap_ids.at(-1)) }))
    .sort((left, right) => right.latest - left.latest || left.label.localeCompare(right.label));
}

function snapPageUrl(projectId, { offset = 0, limit = SNAP_PAGE_SIZE, intentId = "", author = "" } = {}) {
  const query = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (intentId) query.set("intent_id", intentId);
  if (author) query.set("author", author);
  return apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/snaps?${query}`);
}

function resetTimeline(intentId = "", author = "") {
  state._timeline = { projectId: state.currentProjectId, intentId, author, snaps: [], total: null, hasMore: false, loaded: false, loading: false, error: "" };
  return state._timeline;
}

// A link can carry the timeline's filters; they apply when that project's timeline first opens.
function routedTimelineFilters(projectId) {
  const route = readRoute();
  return route.tab === "snaps" && (!route.project || route.project === projectId)
    ? { intentId: route.intent, author: route.author }
    : { intentId: "", author: "" };
}

function setTimelineFilter(change, trigger) {
  const current = state._timeline;
  resetTimeline(change.intentId ?? current?.intentId ?? "", change.author ?? current?.author ?? "");
  renderView();
  writeRoute("push");
  el.detailContent.querySelector(trigger)?.focus();
}

// Pages are newest first; the server filters by Intent. A newer timeline (filter, project) owns the view.
async function loadTimelinePage() {
  const timeline = state._timeline;
  if (!timeline || timeline.loading || (timeline.loaded && !timeline.hasMore)) return;
  timeline.loading = true;
  timeline.error = "";
  try {
    const page = await fetchJson(snapPageUrl(timeline.projectId, { offset: timeline.snaps.length, intentId: timeline.intentId, author: timeline.author }));
    if (state._timeline !== timeline) return;
    const seen = new Set(timeline.snaps.map((snap) => snap.remote_id));
    for (const snap of page?.snaps || []) {
      const entry = { ...snap, remote_id: snap.remote_id || remoteId(snap.project_id || timeline.projectId, snap.id) };
      if (seen.has(entry.remote_id)) continue;
      seen.add(entry.remote_id);
      timeline.snaps.push(entry);
      rememberSnap(entry);
    }
    timeline.total = Number.isFinite(page?.total) ? page.total : timeline.snaps.length;
    timeline.hasMore = Boolean(page?.has_more) && Boolean((page?.snaps || []).length);
    timeline.loaded = true;
  } catch (error) {
    if (state._timeline !== timeline) return;
    timeline.error = error.message || t("Could not load data. Try again.");
  } finally {
    timeline.loading = false;
  }
  if (state._timeline !== timeline || state.activeTab !== "snaps" || !state.overview || state.currentProjectId !== timeline.projectId) return;
  const refocus = document.activeElement?.closest?.(".timeline-filter-trigger");
  const author = Boolean(refocus?.closest?.(".author-filter"));
  renderView();
  if (refocus) el.detailContent.querySelector(author ? ".author-filter .timeline-filter-trigger" : ".timeline-filter-trigger")?.focus();
}

function timelineDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { key: "undated", label: t("Undated"), time: "—", datetime: "" };
  }
  const dayKey = (entry) => [
    entry.getFullYear(),
    String(entry.getMonth() + 1).padStart(2, "0"),
    String(entry.getDate()).padStart(2, "0"),
  ].join("-");
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const key = dayKey(date);
  const label = key === dayKey(today)
    ? t("Today")
    : key === dayKey(yesterday)
      ? t("Yesterday")
      : new Intl.DateTimeFormat(window.IntHubI18n.language, {
          month: "short",
          day: "numeric",
          weekday: "short",
          year: date.getFullYear() === today.getFullYear() ? undefined : "numeric",
        }).format(date);
  return {
    key,
    label,
    time: new Intl.DateTimeFormat(window.IntHubI18n.language, {
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(date),
    datetime: date.toISOString(),
  };
}

function snapTimelineEntry(snap) {
  const checkpoint = parseCheckpoint(snap);
  const recordedAt = timelineDate(snap.created_at);
  const status = timelineState(checkpoint);
  const intent = intentForSnap(snap);
  const supportingValue = checkpoint.next || checkpoint.boundary || snap.why || "";
  const supportingLabel = checkpoint.next
    ? t("Next")
    : checkpoint.boundary
      ? t("Boundary")
      : t("Context");
  return `
    <button type="button" class="timeline-entry${status.className}" data-detail-type="snap" data-remote-id="${esc(snap.remote_id)}">
      <time datetime="${esc(recordedAt.datetime)}">${esc(recordedAt.time)}</time>
      <span class="timeline-node" aria-hidden="true"></span>
      <span class="timeline-entry-body">
        <span class="timeline-entry-topline">
          ${idChip(snap.id)}
          ${status.key === "blocked" ? stateBadge(status) : ""}
          <span class="timeline-entry-time-inline">${esc(recordedAt.time)}</span>
          <span class="timeline-entry-intent">${esc(intent ? intent.what : snap.intent_id || t("Unlinked Intent"))}</span>
        </span>
        <strong class="timeline-entry-title">${esc(conciseSnapTitle(snap, 120))}</strong>
        ${supportingValue ? `<span class="timeline-entry-summary"><i>${esc(supportingLabel)}</i>${esc(truncate(supportingValue, 240))}</span>` : ""}
        ${rowByline(snap)}
      </span>
    </button>`;
}

// Consecutive items of one local day, for the Timeline and History lists.
function groupByDay(items) {
  const groups = [];
  for (const item of items) {
    const date = timelineDate(item.created_at);
    const current = groups.at(-1);
    if (current?.key === date.key) current.items.push(item);
    else groups.push({ key: date.key, label: date.label, items: [item] });
  }
  return groups;
}

function renderTimeline(timeline) {
  const groups = groupByDay(timeline.snaps);
  const remaining = Math.max(0, (timeline.total ?? timeline.snaps.length) - timeline.snaps.length);
  const more = timeline.hasMore
    ? `<button type="button" class="load-more-btn" id="load-more-snaps"${timeline.loading ? ' disabled aria-busy="true"' : ""}>${iconLabel("chevronDown", timeline.loading ? t("Loading…") : t("Load more ({count})", {count: remaining}))}</button>`
    : "";
  return groups
    .map((group) => `
      <section class="timeline-group">
        <h2 class="timeline-day"><span>${esc(group.label)}</span><span>${group.items.length}</span></h2>
        <div class="timeline-events">${group.items.map(snapTimelineEntry).join("")}</div>
      </section>`)
    .join("")
    + (timeline.error ? `<p class="timeline-error" role="alert">${esc(timeline.error)}</p>` : "")
    + more;
}

function renderSnapsTab() {
  const total = state.overview.total_snaps ?? (state.overview.recent_snaps || []).length;
  if (!total) {
    el.detailContent.innerHTML = pageHeader({ title: t("Timeline") }) + emptyState({
      iconName: "timeline",
      title: t("No snaps synced yet."),
      body: t("Snaps are verified checkpoints. They appear here after the next push."),
    });
    return;
  }
  let timeline = state._timeline;
  if (!timeline || timeline.projectId !== state.currentProjectId) timeline = resetTimeline("");
  const options = timelineIntentOptions(overviewIntents());
  // The author menu only appears once a project has two authors; a filter nothing can clear is dropped.
  const authors = (state.overview.authors || []).length >= 2 ? state.overview.authors : [];
  const staleIntent = timeline.intentId && !options.some((option) => option.key === timeline.intentId);
  const staleAuthor = timeline.author && !authors.some((entry) => entry.key === timeline.author);
  if (staleIntent || staleAuthor) {
    timeline = resetTimeline(staleIntent ? "" : timeline.intentId, staleAuthor ? "" : timeline.author);
    writeRoute("replace");
  }
  const selected = options.find((option) => option.key === timeline.intentId);
  const author = authors.find((entry) => entry.key === timeline.author);
  const optionHtml = (attribute, value, chosen, label, count) => `<button type="button" class="timeline-filter-option${chosen === value ? " is-selected" : ""}" ${attribute}="${esc(value)}" aria-pressed="${chosen === value}"><span>${esc(label)}</span><small>${count}</small></button>`;
  const filter = `
    <div class="timeline-toolbar">
      <details class="timeline-filter">
        <summary class="timeline-filter-trigger" data-tip="${esc(t("Filter timeline by Intent"))}">${icon("intent")}<span>${esc(selected ? truncate(selected.label, 44) : t("All Intents"))}</span>${icon("chevronDown")}</summary>
        <div class="timeline-filter-menu">${optionHtml("data-timeline-intent", "", timeline.intentId, t("All Intents"), total)}${options.map((option) => optionHtml("data-timeline-intent", option.key, timeline.intentId, option.label, option.count)).join("")}</div>
      </details>
      ${authors.length ? `<details class="timeline-filter author-filter">
        <summary class="timeline-filter-trigger" data-tip="${esc(t("Filter timeline by author"))}">${icon("user")}<span>${esc(author ? truncate(author.name, 28) : t("All authors"))}</span>${icon("chevronDown")}</summary>
        <div class="timeline-filter-menu">${optionHtml("data-timeline-author", "", timeline.author, t("All authors"), total)}${authors.map((entry) => optionHtml("data-timeline-author", entry.key, timeline.author, entry.name, entry.snaps)).join("")}</div>
      </details>` : ""}
    </div>`;
  const count = timeline.total ?? (selected ? selected.count : author ? author.snaps : total);
  const body = !timeline.loaded
    ? timeline.error
      ? `<div class="empty-state"><p>${esc(timeline.error)}</p><button type="button" class="secondary-btn" data-retry-timeline>${iconLabel("refresh", t("Retry"))}</button></div>`
      : viewLoadingHtml()
    : timeline.snaps.length
      ? renderTimeline(timeline)
      : `<div class="inline-empty">${esc(selected || author ? t("No checkpoints match these filters.") : t("No snaps synced yet."))}</div>`;
  el.detailContent.innerHTML = pageHeader({
    title: t("Timeline"),
    meta: [
      esc(plural(count, "{count} checkpoint", "{count} checkpoints")),
      esc(selected ? truncate(selected.label, 60) : t("All Intents")),
      ...(author ? [esc(truncate(author.name, 40))] : []),
    ],
    actions: filter,
  }) + `<div class="timeline" aria-busy="${timeline.loading || !timeline.loaded && !timeline.error}">${body}</div>`;
  if (!timeline.loaded && !timeline.loading && !timeline.error) loadTimelinePage();
}

/* History */

// Who pushed: the signed-in account when there is one, else what the CLI declared.
function pushedBy(revision) {
  return revision?.pushed_by?.name || revision?.pushed_by?.login || revision?.pusher?.name || revision?.pusher?.email || "";
}

function joinList(items) {
  if (items.length < 2) return items[0] || "";
  return t("{items} and {last}", { items: items.slice(0, -1).join(t(", ")), last: items.at(-1) });
}

// One sentence for a revision: "Added 2 Intents and 5 Snaps; changed 1 Decision".
function revisionSummary(summary = {}) {
  const counts = (kind) => joinList([
    ["intents", "{count} Intent", "{count} Intents"],
    ["snaps", "{count} Snap", "{count} Snaps"],
    ["decisions", "{count} Decision", "{count} Decisions"],
  ].filter(([collection]) => summary[`${collection}_${kind}`]).map(([collection, one, other]) => plural(summary[`${collection}_${kind}`], one, other)));
  const added = counts("added");
  const changed = counts("changed");
  if (added && changed) return t("Added {added}; changed {changed}", { added, changed });
  if (added) return t("Added {items}", { items: added });
  return changed ? t("Changed {items}", { items: changed }) : t("No semantic changes");
}

function revisionPageUrl(projectId, offset = 0, limit = REVISION_PAGE_SIZE) {
  return apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/revisions?${new URLSearchParams({ offset: String(offset), limit: String(limit) })}`);
}

function resetHistory() {
  state._history = { projectId: state.currentProjectId, revisions: [], total: null, hasMore: false, loaded: false, loading: false, error: "" };
  return state._history;
}

async function loadHistoryPage() {
  const history = state._history;
  if (!history || history.loading || (history.loaded && !history.hasMore)) return;
  history.loading = true;
  history.error = "";
  try {
    const page = await fetchJson(revisionPageUrl(history.projectId, history.revisions.length));
    if (state._history !== history) return;
    const seen = new Set(history.revisions.map((entry) => entry.revision));
    history.revisions.push(...(page?.revisions || []).filter((entry) => !seen.has(entry.revision)));
    history.total = Number.isFinite(page?.total) ? page.total : history.revisions.length;
    history.hasMore = Boolean(page?.has_more) && Boolean((page?.revisions || []).length);
    history.loaded = true;
  } catch (error) {
    if (state._history !== history) return;
    history.error = error.message || t("Could not load data. Try again.");
  } finally {
    history.loading = false;
  }
  if (state._history === history && state.activeTab === "history" && state.overview && state.currentProjectId === history.projectId) renderView();
}

function revisionRow(revision, projectId) {
  const who = pushedBy(revision);
  return `
    <button type="button" class="list-row history-row" data-detail-type="revision" data-remote-id="${esc(remoteId(projectId, revision.revision))}">
      <span class="row-main">
        <strong class="row-title">${esc(revisionSummary(revision.summary))}</strong>
        <span class="row-byline">
          ${who ? `<span>${esc(who)}</span>` : ""}
          <span data-tip="${esc(fmtDate(revision.created_at))}">${esc(relativeDate(revision.created_at))}</span>
          ${revision.parent ? "" : `<span class="chip">${esc(t("First push"))}</span>`}
        </span>
      </span>
      <span class="row-id">${esc(shortRevision(revision.revision))}</span>
    </button>`;
}

function renderHistoryTab() {
  let history = state._history;
  if (!history || history.projectId !== state.currentProjectId) history = resetHistory();
  const header = pageHeader({
    title: t("History"),
    help: "history",
    meta: history.total ? [esc(plural(history.total, "{count} push", "{count} pushes"))] : [],
  });
  if (history.loaded && !history.revisions.length) {
    el.detailContent.innerHTML = header + emptyState({
      iconName: "history",
      title: t("No pushes yet."),
      body: t("Each push is one revision: what changed, who pushed it and when."),
      extra: commandSnippet(["itt push"]),
    });
    return;
  }
  const remaining = Math.max(0, (history.total ?? history.revisions.length) - history.revisions.length);
  const list = groupByDay(history.revisions).map((group) => `
    <section class="history-group">
      <h2 class="history-day"><span>${esc(group.label)}</span><span>${group.items.length}</span></h2>
      <div class="list-card">${group.items.map((revision) => revisionRow(revision, history.projectId)).join("")}</div>
    </section>`).join("");
  const body = !history.loaded
    ? history.error
      ? `<div class="empty-state"><p>${esc(history.error)}</p><button type="button" class="secondary-btn" data-retry-history>${iconLabel("refresh", t("Retry"))}</button></div>`
      : viewLoadingHtml()
    : list
      + (history.error ? `<p class="timeline-error" role="alert">${esc(history.error)}</p>` : "")
      + (history.hasMore ? `<button type="button" class="load-more-btn" id="load-more-history"${history.loading ? ' disabled aria-busy="true"' : ""}>${iconLabel("chevronDown", history.loading ? t("Loading…") : t("Load more ({count})", {count: remaining}))}</button>` : "");
  el.detailContent.innerHTML = `${header}<div class="history" aria-busy="${history.loading || !history.loaded && !history.error}">${body}</div>`;
  if (!history.loaded && !history.loading && !history.error) loadHistoryPage();
}

function revisionObjectRow(type, object, projectId) {
  const title = type === "snap" ? conciseSnapTitle(object) : object.what || object.id;
  return relationItem(type, remoteId(projectId, object.id), object.id, title, byline(object), type === "snap" ? "" : object.status);
}

function revisionChange(change, type, projectId) {
  if (change.field === "status") {
    const label = (status) => (type === "decision" ? decisionStatusLabel(status) : intentStatusLabel(status));
    return `<li><span>${esc(label(change.from))} → ${esc(label(change.to))}</span>${change.reason ? `<span class="revision-reason">${esc(change.reason)}</span>` : ""}</li>`;
  }
  const target = `<button type="button" class="revision-target" data-detail-type="intent" data-remote-id="${esc(remoteId(projectId, change.intent))}">${esc(change.intent)}</button>`;
  return `<li><span>${tHtml(change.action === "removed" ? "Removed: {relation} {intent}" : "Added: {relation} {intent}", { relation: esc(relationLabel(change.type, "out")), intent: target })}</span></li>`;
}

function revisionChangedRow(type, item, projectId) {
  return `<div class="revision-changed">
    ${revisionObjectRow(type, item.object, projectId)}
    <ul class="revision-changes">${item.changes.map((change) => revisionChange(change, type, projectId)).join("")}</ul>
  </div>`;
}

// Each list stops at 200 entries while the summary stays exact, so a long push says what it left out.
function revisionList(rows, total) {
  const hidden = total - rows.length;
  return collapsibleRelation(rows, 8) + (hidden > 0 ? `<p class="revision-more">${esc(t("{count} more not shown", {count: hidden}))}</p>` : "");
}

function buildRevisionDetailHtml(payload) {
  const summary = payload.summary || {};
  const changes = payload.changes || {};
  const projectId = payload.project_id;
  const who = pushedBy(payload);
  const collections = [
    ["intents", "intent", t("Added Intents")],
    ["snaps", "snap", t("Added Snaps")],
    ["decisions", "decision", t("Added Decisions")],
  ];
  const sections = collections.map(([collection, type, title]) => {
    const total = summary[`${collection}_added`] || 0;
    const rows = (changes[collection]?.added || []).map((object) => revisionObjectRow(type, object, projectId));
    return total ? detailSection(title, revisionList(rows, total), total) : "";
  });
  const changed = collections.flatMap(([collection, type]) => (changes[collection]?.changed || []).map((item) => revisionChangedRow(type, item, projectId)));
  const changedTotal = collections.reduce((sum, [collection]) => sum + (summary[`${collection}_changed`] || 0), 0);
  if (changedTotal) sections.push(detailSection(t("Changed"), revisionList(changed, changedTotal), changedTotal));
  return `
    <div class="detail-header">
      ${detailMeta([
        payload.parent ? "" : `<span class="chip">${esc(t("First push"))}</span>`,
        idChip(shortRevision(payload.revision)),
        who ? `<span>${esc(t("Pushed by {name}", {name: who}))}</span>` : "",
        `<span>${esc(fmtDate(payload.created_at))}</span>`,
      ])}
      <h2 class="detail-title" tabindex="-1">${esc(revisionSummary(summary))}</h2>
    </div>
    ${sections.join("") || `<div class="inline-empty">${esc(t("This push added and changed nothing."))}</div>`}
    ${rawToggle(payload)}`;
}

/* Decisions */

function decisionConstraint(decision, index, deprecated = false) {
  const scope = decisionScope(decision);
  const scopeLabel = scope.count
    ? plural(scope.count, "{count} linked Intent", "{count} linked Intents")
    : t("No Intent scope recorded");
  const scopePreview = scope.titles.length
    ? truncate(scope.titles.join(" · "), 120)
    : scope.count
      ? truncate((decision.intent_ids || []).join(" · "), 120)
      : t("Open the Decision to inspect its recorded rationale.");
  return `
    <button type="button" class="list-row decision-row decision-constraint${deprecated ? " is-deprecated" : ""}" data-detail-type="decision" data-remote-id="${esc(decision.remote_id)}">
      <span class="decision-index" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
      <span class="row-main">
        <strong class="row-title decision-constraint-title">${esc(decision.what)}</strong>
        ${decision.why ? `<span class="row-summary">${esc(truncate(decision.why, 220))}</span>` : ""}
        ${deprecated && decision.reason ? `<span class="row-summary"><b>${esc(t("Reason"))}</b> ${esc(truncate(decision.reason, 200))}</span>` : ""}
        <span class="decision-scope">
          <strong>${esc(scopeLabel)}</strong>
          <span>${esc(scopePreview)}</span>
        </span>
        ${rowByline(decision)}
      </span>
    </button>`;
}

function renderDecisionsTab() {
  const active = [...(state.overview.active_decisions || [])].reverse();
  const deprecated = [...(state.overview.deprecated_decisions || [])].reverse();
  const header = pageHeader({
    title: t("Decisions"),
    help: "decisions",
    meta: active.length || deprecated.length
      ? [esc(t("{count} in effect", {count: active.length})), esc(t("{count} deprecated", {count: deprecated.length}))]
      : [],
  });

  if (!active.length && !deprecated.length) {
    el.detailContent.innerHTML = header + emptyState({
      iconName: "decision",
      title: t("No decisions."),
      body: t("Decisions are durable rules that bind future Intents, such as an architecture choice or a product constraint."),
      extra: commandSnippet(['itt decision create "Rule" --why "Reason"']),
    });
    return;
  }

  const activeHtml = active.length
    ? `<div class="list-card decision-constraint-list">${active.map((decision, index) => decisionConstraint(decision, index)).join("")}</div>`
    : `<div class="object-group-empty">${esc(t("No active cross-Intent constraints."))}</div>`;
  const archiveOpen = state._pageState?.decisionArchiveOpen ?? false;
  const deprecatedHtml = deprecated.length
    ? `<details class="object-archive decision-archive" data-archive="decisions"${archiveOpen ? " open" : ""}>
        <summary>${icon("chevron")}<span>${esc(t("Deprecated history"))}</span><span class="object-archive-count">${deprecated.length}</span></summary>
        <div class="list-card decision-archive-body">
          ${deprecated.map((decision, index) => decisionConstraint(decision, index, true)).join("")}
        </div>
      </details>`
    : "";

  el.detailContent.innerHTML = `
    ${header}
    <section class="object-group decision-group">
      <header class="object-group-header">
        <h2 class="object-group-title">${esc(t("Active constraints"))}</h2>
        <span class="object-group-count">${active.length}</span>
      </header>
      ${activeHtml}
    </section>
    ${deprecatedHtml}`;
}

/* ---- Detail sheet ---- */

function detailErrorHtml(error, type, rId) {
  return `<div class="empty-state"><p>${esc(error.message)}</p><button type="button" class="secondary-btn" data-retry-detail="sheet" data-detail-type="${esc(type)}" data-remote-id="${esc(rId)}">${iconLabel("refresh", t("Retry"))}</button></div>`;
}

function sheetIsOpen() {
  return el.drawer.classList.contains("open");
}

function renderSheetHeader(payload = null) {
  const entry = state._sheetStack?.at(-1);
  const labels = { intent: t("Intent"), snap: t("Snap"), decision: t("Decision"), revision: t("Revision") };
  const raw = payload?.id || (entry ? entry.remoteId.split("__").slice(1).join("__") : "");
  const id = entry?.type === "revision" ? shortRevision(raw) : raw;
  el.drawerTitle.innerHTML = entry ? `${esc(labels[entry.type] || "")} · <b class="mono">${esc(id)}</b>` : esc(t("Details"));
  el.drawerBack.classList.toggle("is-hidden", (state._sheetStack?.length || 0) < 2);
}

function openDrawer() {
  closeHeaderMenus();
  toggleProjectPicker(false);
  if (!sheetIsOpen()) state._drawerTrigger = document.activeElement;
  el.drawer.inert = false;
  el.drawer.classList.add("open");
  el.drawerOverlay.classList.add("open");
  el.drawer.setAttribute("aria-hidden", "false");
  el.drawer.setAttribute("aria-modal", "true");
  for (const node of document.querySelectorAll(".app-header, .page")) node.inert = true;
  el.drawerClose.focus();
}

function closeDrawer({ history = "auto" } = {}) {
  const wasOpen = sheetIsOpen();
  beginViewRequest("sheet");
  state._drawerPayload = null;
  state._sheetStack = [];
  state.selectedDetail = null;
  el.drawer.classList.remove("open");
  el.drawerOverlay.classList.remove("open");
  el.drawer.setAttribute("aria-hidden", "true");
  el.drawer.inert = true;
  el.drawer.removeAttribute("aria-modal");
  for (const node of document.querySelectorAll(".app-header, .page")) node.inert = false;
  el.drawerContent.innerHTML = "";
  syncSelected();
  if (wasOpen) {
    if (state._drawerTrigger?.isConnected && !state._drawerTrigger.disabled) state._drawerTrigger.focus();
    else el.detailContent.focus();
    if (history === "auto") {
      // Closing a sheet that added its own history entry steps back over it;
      // a sheet restored from a deep link only drops its URL parameters.
      if (state._sheetPushed && window.history.state?.inthub === "sheet" && window.history.back) window.history.back();
      else writeRoute("replace");
    }
  }
  state._sheetPushed = false;
  state._drawerTrigger = null;
}

function buildDetailHtml(type, payload) {
  if (type === "revision") return buildRevisionDetailHtml(payload);
  return type === "intent"
    ? buildIntentDetailHtml(payload)
    : type === "decision"
      ? buildDecisionDetailHtml(payload)
      : buildSnapDetailHtml(payload);
}

function detailUrl(type, rId) {
  if (type !== "revision") return apiUrl(`/api/v1/${DETAIL_PATHS[type]}/${encodeURIComponent(rId)}`);
  const revision = rId.split("__").slice(1).join("__");
  return apiUrl(`/api/v1/projects/${encodeURIComponent(projectIdFromRemoteId(rId))}/revisions/${encodeURIComponent(revision)}`);
}

// mode: "reset" opens a fresh stack, "push" adds a related object, "replace" retries the top.
async function openDetail(type, rId, { mode = "reset", history = "auto" } = {}) {
  if (!DETAIL_PATHS[type]) return;
  const targetProjectId = projectIdFromRemoteId(rId);
  if (targetProjectId && state.currentProjectId && targetProjectId !== state.currentProjectId
      && state.projects.some((project) => project.id === targetProjectId)) {
    closeDrawer({ history: "none" });
    await loadProject(targetProjectId, { detail: { type, remoteId: rId }, history: "push" });
    return;
  }
  const request = beginViewRequest("sheet");
  const wasOpen = sheetIsOpen();
  const entry = { type, remoteId: rId };
  state._sheetStack ||= [];
  if (mode === "push" && wasOpen) state._sheetStack.push(entry);
  else if (mode === "replace" && wasOpen && state._sheetStack.length) state._sheetStack[state._sheetStack.length - 1] = entry;
  else state._sheetStack = [entry];
  state.selectedDetail = entry;
  state._drawerPayload = null;
  renderSheetHeader();
  if (!wasOpen) openDrawer();
  syncSelected();
  const routed = writeRoute(history === "auto" ? (wasOpen ? "replace" : "push") : history, "sheet");
  if (!wasOpen) state._sheetPushed = routed === "pushed" || (routed === "none" && Boolean(window.history.state?.sheetPushed));

  const cacheKey = `${type}:${rId}`;
  const cached = state._detailCache?.get(cacheKey);
  if (cached) {
    showDetailPayload(type, cached, wasOpen);
    return;
  }
  el.drawerContent.innerHTML = viewLoadingHtml();
  el.drawerContent.scrollTop = 0;
  setViewBusy("sheet", true);
  try {
    const payload = await fetchJson(detailUrl(type, rId));
    if (!ownsViewRequest("sheet", request) || !sheetIsOpen()) return;
    state._detailCache?.set(cacheKey, payload);
    showDetailPayload(type, payload, wasOpen);
  } catch (error) {
    if (!ownsViewRequest("sheet", request)) return;
    el.drawerContent.innerHTML = detailErrorHtml(error, type, rId);
    throw error;
  } finally {
    if (ownsViewRequest("sheet", request)) setViewBusy("sheet", false);
  }
}

function showDetailPayload(type, payload, moveFocus) {
  state._drawerPayload = { type, payload };
  el.drawerContent.innerHTML = buildDetailHtml(type, payload);
  el.drawerContent.scrollTop = 0;
  renderSheetHeader(payload);
  if (moveFocus) el.drawerContent.querySelector(".detail-title")?.focus();
}

async function sheetBack() {
  if ((state._sheetStack?.length || 0) < 2) {
    closeDrawer();
    return;
  }
  state._sheetStack.pop();
  const previous = state._sheetStack.pop();
  await openDetail(previous.type, previous.remoteId, { mode: "push", history: "replace" });
}

function allDecisionsMap() {
  const map = {};
  for (const d of state.overview?.active_decisions || []) map[d.id] = d;
  for (const d of state.overview?.deprecated_decisions || []) map[d.id] = d;
  return map;
}

function activeDecisionIds() {
  const ids = new Set();
  for (const d of state.overview?.active_decisions || []) {
    ids.add(d.id);
  }
  return ids;
}

function detailMeta(parts) {
  return `<div class="detail-meta">${parts.filter(Boolean).join("")}</div>`;
}

function buildIntentDetailHtml(payload) {
  const intent = payload.intent;
  const activeIds = activeDecisionIds();

  const dMap = allDecisionsMap();
  for (const decision of payload.decisions || []) {
    dMap[decision.id] = decision;
    if (decision.status === "active") activeIds.add(decision.id);
  }
  const allIds = intent.decision_ids || [];
  const decisionLinks = [
    ...allIds.filter((dId) => activeIds.has(dId)).map((dId) => [dId, "active"]),
    ...allIds.filter((dId) => !activeIds.has(dId)).map((dId) => [dId, "deprecated"]),
  ].map(([dId, status]) => relationItem(
    "decision",
    remoteId(payload.project_id, dId),
    dId,
    dMap[dId]?.what || dId,
    truncate(dMap[dId]?.why || "", 120),
    status,
  ));
  const decisionsBody = decisionLinks.length
    ? collapsibleRelation(decisionLinks, 5)
    : `<div class="inline-empty">${esc(t("No decisions linked."))}</div>`;

  const allSnaps = [...payload.snaps].reverse();
  const latest = allSnaps[0];
  const snapLinks = allSnaps.map((s) =>
    relationItem(
      "snap",
      remoteId(payload.project_id, s.id),
      s.id,
      conciseSnapTitle(s),
      fmtDate(s.created_at),
    ),
  );
  const snapTimelineBody = snapLinks.length
    ? collapsibleRelation(snapLinks, 5)
    : `<div class="inline-empty">${esc(t("No snaps recorded."))}</div>`;
  const sourced = Object.values(dMap).filter((decision) => decision.source_intent_id === intent.id);
  const sourcedLinks = sourced.map((decision) => relationItem(
    "decision",
    decision.remote_id || remoteId(payload.project_id, decision.id),
    decision.id,
    decision.what || decision.id,
    truncate(decision.why || "", 120),
    decision.status,
  ));

  return `
    <div class="detail-header">
      ${detailMeta([statusBadge(intent.status), idChip(intent.id), identityMeta(intent), `<span>${esc(t("Created {time}", {time: fmtDate(intent.created_at)}))}</span>`])}
      <h2 class="detail-title" tabindex="-1">${esc(intent.what)}</h2>
    </div>
    ${intent.why ? detailSection(t("Why"), formatText(intent.why)) : ""}
    ${intent.reason ? detailSection(t("Reason"), formatText(intent.reason)) : ""}
    ${latest && ["active", "suspend"].includes(intent.status) ? detailSection(t("Latest checkpoint"), checkpointGrid(parseCheckpoint(latest), ["next", "blocker", "boundary", "verified"], " detail-checkpoint-grid")) : ""}
    ${intentRelationsSection(payload)}
    ${detailSection(t("Snaps"), snapTimelineBody, allSnaps.length)}
    ${detailSection(t("Linked decisions"), decisionsBody, allIds.length)}
    ${sourcedLinks.length ? detailSection(t("Decisions from this Intent"), collapsibleRelation(sourcedLinks, 5), sourcedLinks.length) : ""}
    ${rawToggle({ intent, snaps: payload.snaps, decisions: payload.decisions || [] })}`;
}

// Both directions, grouped by how they read from this Intent ("Part of", "Parts", …), each with its state.
function intentRelationsSection(payload) {
  const rows = intentRelations({ ...payload.intent, project_id: payload.project_id });
  if (!rows.length) return detailSection(t("Relations"), `<div class="inline-empty">${esc(t("No relations to other Intents."))}</div>`);
  const groups = [];
  for (const row of rows) {
    const label = relationLabel(row.type, row.direction);
    const group = groups.find((entry) => entry.label === label);
    if (group) group.rows.push(row);
    else groups.push({ label, rows: [row] });
  }
  // A part's state only repeats the part's own status, so it is shown only when its parent has ended.
  const badge = (row) => (row.type === "part_of" && !ATTENTION_STATES.has(row.state) ? "" : relationBadge(row.state, row));
  const body = groups.map((group) => `
    <div class="relation-group">
      <h4 class="relation-group-label">${esc(group.label)}</h4>
      <div class="relation-list">${group.rows.map((row) => relationItem(
        "intent",
        row.intent.remote_id || remoteId(payload.project_id, row.intent.id),
        row.intent.id,
        row.intent.what || row.intent.id,
        "",
        row.intent.status,
        badge(row),
      )).join("")}</div>
    </div>`).join("");
  const flowLink = `<button type="button" class="link-button relation-flow-link" data-flow-focus="${esc(payload.intent.id)}">${icon("flow")}${esc(t("Show in Flow"))}</button>`;
  return detailSection(t("Relations"), body + flowLink, rows.length);
}

function decisionSourceSection(payload) {
  const sourceId = payload.decision.source_intent_id;
  if (!sourceId) {
    return detailSection(t("Source"), `<div class="decision-source-none"><span class="chip">${esc(t("Project-level"))}</span><span>${esc(t("Not traced to one Intent; it applies across the project."))}</span></div>`);
  }
  const source = overviewIntentMap().get(sourceId) || (payload.intents || []).find((intent) => intent.id === sourceId) || { id: sourceId };
  return detailSection(t("Source"), `<div class="relation-list">${relationItem(
    "intent",
    source.remote_id || remoteId(payload.project_id, sourceId),
    sourceId,
    source.what || sourceId,
    truncate(source.why || "", 120),
    source.status,
  )}</div>`);
}

function buildDecisionDetailHtml(payload) {
  const decision = payload.decision;
  const linkedCount = payload.intents.length;
  const scopeSummary = linkedCount
    ? plural(linkedCount, "Applies to {count} linked Intent.", "Applies to {count} linked Intents.")
    : t("No Intent scope is recorded.");
  const intentLinks = payload.intents.map((i) =>
    relationItem(
      "intent",
      remoteId(payload.project_id, i.id),
      i.id,
      i.what || i.title || i.id,
      truncate(i.why || "", 120),
      i.status,
    ),
  );

  const intentsBody = intentLinks.length
    ? collapsibleRelation(intentLinks, 5)
    : `<div class="inline-empty">${esc(t("No linked intents."))}</div>`;

  return `
    <div class="detail-header">
      ${detailMeta([statusBadge(decision.status, "decision"), idChip(decision.id), identityMeta(decision), `<span>${esc(t("Created {time}", {time: fmtDate(decision.created_at)}))}</span>`])}
      <h2 class="detail-title" tabindex="-1">${esc(decision.what)}</h2>
      <p class="detail-context decision-detail-scope">${esc(decision.status === "active" ? t("Current cross-Intent constraint") : t("Deprecated constraint history"))} · ${esc(scopeSummary)}</p>
    </div>
    ${detailSection(t("Why"), formatText(decision.why) || `<p>${esc(t("No why provided."))}</p>`)}
    ${decision.reason ? detailSection(t("Reason"), formatText(decision.reason)) : ""}
    ${decisionSourceSection(payload)}
    ${detailSection(t("Affected Intents"), intentsBody, payload.intents.length)}
    ${rawToggle({ decision, intents: payload.intents })}`;
}

// {repo}/commit/{sha}, or the /-/ form on GitLab; only https on the hosts the CLI recognises becomes a link.
function commitUrl(repository, sha) {
  let url;
  try { url = new URL(repository); } catch { return ""; }
  if (url.protocol !== "https:" || !["github.com", "gitlab.com", "gitee.com"].includes(url.hostname) || !/^[0-9a-f]{40,64}$/.test(sha)) return "";
  return `${url.origin}${url.pathname.replace(/\/+$/, "")}${url.hostname === "gitlab.com" ? "/-" : ""}/commit/${sha}`;
}

function commitLine(snap) {
  const sha = snap.git?.commit;
  if (!sha) return "";
  const label = tHtml("Commit {sha}", { sha: `<span class="mono">${esc(sha.slice(0, 7))}</span>` });
  const url = commitUrl(state.overview?.project?.repository_url, sha);
  const commit = url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label}</a>` : label;
  return `<p class="detail-context snap-commit">${commit}${snap.git.dirty ? ` · ${esc(t("with uncommitted changes"))}` : ""}</p>`;
}

function buildSnapDetailHtml(payload) {
  const snap = payload.snap;
  const checkpoint = parseCheckpoint(snap);
  const status = timelineState(checkpoint);
  const parent = payload.intent
    ? `<button type="button" data-detail-type="intent" data-remote-id="${esc(remoteId(payload.project_id, payload.intent.id))}">${esc(payload.intent.what || payload.intent.id)}</button>`
    : esc(t("an unlinked Intent"));
  const parentLink = payload.intent
    ? `<div class="relation-list">${relationItem(
        "intent",
        remoteId(payload.project_id, payload.intent.id),
        payload.intent.id,
        payload.intent.what || payload.intent.id,
        truncate(payload.intent.why || "", 120),
        payload.intent.status,
      )}</div>`
    : `<div class="inline-empty">${esc(t("No linked intent."))}</div>`;

  return `
    <div class="detail-header detail-header-snap">
      ${detailMeta([stateBadge(status), idChip(snap.id), identityMeta(snap), `<span>${esc(fmtDate(snap.created_at))}</span>`])}
      <h2 class="detail-title detail-title-snap" tabindex="-1">${esc(conciseSnapTitle(snap, 110))}</h2>
      <p class="detail-context snap-detail-context">${esc(t("Semantic checkpoint for"))} ${parent}</p>
      ${commitLine(snap)}
    </div>
    ${detailSection(
      t("Continuation checkpoint"),
      `${checkpointGrid(checkpoint, ["verified", "boundary", "next", "blocker"], " detail-checkpoint-grid")}
      ${checkpoint.constraints ? `<p class="checkpoint-note"><strong>${esc(t("Constraints:"))}</strong> ${esc(checkpoint.constraints)}</p>` : ""}`,
    )}
    ${checkpoint.context ? detailSection(t("Context"), formatText(checkpoint.context)) : ""}
    ${detailSection(t("Parent Intent"), parentLink)}
    ${rawToggle({ snap, intent: payload.intent })}`;
}

/* ---- Setup guide ---- */

// A project with no history. Readers cannot push, so a guide to pushing would mislead them.
// Its Settings tab works all the same: a project can be renamed, made public or deleted before its first push.
function renderEmptyProject() {
  if (state.activeTab === "settings" && canManageProject()) {
    renderView();
    return;
  }
  const project = state.overview?.project;
  if (state.visitor || ["read", "public"].includes(project?.permission)) {
    el.shell.classList.add("is-empty");
    el.detailContent.innerHTML = emptyState({
      iconName: "intent",
      title: currentProject()?.full_name || "",
      body: t("Nothing has been published yet."),
    });
    return;
  }
  renderSetupGuide(state.projects.length ? "unsynced" : "unlinked");
}

function renderSetupGuide(mode) {
  el.shell.classList.add("is-empty");
  const projectName = currentProject()?.full_name;
  const linkCmd = `itt remote add origin ${shellArg(state.config.apiBaseUrl)} --project ${projectName ? shellArg(projectName) : "PROJECT"}`;
  const hosted = String(state.config.apiBaseUrl || "").replace(/\/+$/, "") === HOSTED_INTHUB;
  const steps = [];
  if (mode === "unlinked") {
    steps.push(
      { title: t("Install the Intent CLI"), desc: t("Requires Python 3.9+. Re-run any time to upgrade."), cmd: [INSTALL_COMMAND] },
      // Without the Skill an agent never records anything.
      { title: t("Add the agent skill"), desc: t("Needs Node.js. Installs for Claude Code and Codex; add -a cursor and so on for other agents."), cmd: [SKILL_COMMAND] },
      { title: t("Initialize your project"), desc: t("Detects the agent you use, or asks; --host codex / claude-code overrides that. Git is optional."), cmd: ["itt init"] },
    );
  }
  if (state.config.authRequired) {
    steps.push({
      title: t("Sign in from the CLI"),
      desc: t("It shows a code; approve it in the browser."),
      cmd: [hosted ? "itt auth login" : `itt auth login --api-base-url ${shellArg(state.config.apiBaseUrl)}`],
    });
  }
  if (hosted && mode === "unlinked") {
    // The hosted site is the CLI default: a push alone creates the project, named after the directory.
    steps.push({
      title: t("Push"),
      desc: t("Creates the project under this directory's name and pushes its semantic history."),
      cmd: ["itt push"],
      optional: { desc: t("Optional: to use a different project name, link it first."), cmd: [linkCmd] },
    });
  } else {
    // Any other endpoint (IntHub Local, a self-hosted hub) and an existing project need the remote first.
    steps.push({
      title: t("Link and push"),
      desc: mode === "unlinked"
        ? t("Choose a shared project name, then push its semantic history.")
        : t("Ensure CLI points here, then push the next snapshot."),
      cmd: [linkCmd, "itt push"],
    });
  }

  el.detailContent.innerHTML = `
    <div class="setup-page setup-guide">
      ${pageHeader({
        eyebrow: mode === "unlinked" ? t("Welcome") : projectName || t("Project"),
        title: mode === "unlinked" ? t("Get started with IntHub") : t("Complete the first sync"),
        help: "setup",
        meta: [esc(t("Sync semantic history from the Intent CLI, then continue from the brief here."))],
        // The tabs stay hidden until there is something to show, and Settings is the one that works before that.
        actions: mode === "unsynced" && canManageProject()
          ? `<a class="button button-secondary" href="${esc(projectPath(state.currentProjectId, { tab: "settings" }))}" data-route>${iconLabel("settings", t("Project settings"))}</a>`
          : "",
      })}
      <ol class="setup-steps">
        ${steps.map((step) => `
          <li class="setup-step">
            <h3>${esc(step.title)}</h3>
            <p>${esc(step.desc)}</p>
            <div>
              ${commandSnippet(step.cmd)}
              ${step.optional ? `<p class="setup-step-note">${esc(step.optional.desc)}</p>${commandSnippet(step.optional.cmd)}` : ""}
            </div>
          </li>`).join("")}
      </ol>
      <p class="setup-resume">${esc(t("Once the project hooks are trusted, tell the agent “Resume this project through Intent.” to continue later."))}</p>
    </div>`;
}

/* ---- Site pages ---- */

function currentProject() {
  return state.projects.find((project) => project.id === state.currentProjectId) || null;
}

function updateDocumentTitle() {
  const project = currentProject();
  const lead = state._dialog ? dialogTitle() : {
    project: project?.full_name,
    home: t("Projects"),
    team: state._team?.data?.team?.name || state._team?.slug,
    invite: t("Team invite"),
    device: t("Connect a device"),
  }[state.page];
  document.title = lead ? `${lead} · IntHub` : "IntHub";
}

// A translated sentence whose placeholders are markup; the sentence itself is escaped.
function tHtml(key, markup) {
  const text = t(key, Object.fromEntries(Object.keys(markup).map((name) => [name, `\u0001${name}\u0001`])));
  return esc(text).replace(/\u0001(\w+)\u0001/g, (_, name) => markup[name]);
}

function calendarDate(v) {
  const d = new Date(v);
  if (!v || Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat(window.IntHubI18n.language, { year: "numeric", month: "short", day: "numeric" }).format(d);
}

function roleLabel(role) {
  return { admin: t("Admin"), member: t("Member"), viewer: t("Viewer") }[role] || role;
}

function visibilityBadge(visibility) {
  return `<span class="status-pill visibility-pill">${esc(visibility === "public" ? t("Public") : t("Private"))}</span>`;
}

// A monogram: the page only loads its own images, and Tenon accounts carry no avatar URL.
function monogram(name) {
  return `<span class="monogram" aria-hidden="true">${esc([...String(name || "").trim()][0]?.toUpperCase() || "?")}</span>`;
}

// One layout for the Account and Settings dialog, a team and the project's Settings tab: a nav of links and one pane at a time.
function settingsLayout({ title = "", label, items, pane }) {
  return `
    <div class="settings-layout">
      ${title ? `<h1 class="page-title settings-title">${esc(title)}</h1>` : ""}
      <nav class="settings-nav" aria-label="${esc(label)}">
        ${items.map((item) => `<a class="settings-nav-item" href="${esc(item.href)}" data-route${item.current ? ' aria-current="page"' : ""}>${icon(item.icon)}<span>${esc(item.label)}</span></a>`).join("")}
      </nav>
      <div class="settings-pane">${pane}</div>
    </div>`;
}

// Title, hairline, then rows: every block starts and ends on the pane's edges.
function settingsBlock(id, title, body, lead = "") {
  return `
    <section class="settings-block" aria-labelledby="settings-${id}">
      <h2 class="settings-block-title" id="settings-${id}">${esc(title)}</h2>
      ${lead ? `<p class="settings-lead">${lead}</p>` : ""}
      ${body}
    </section>`;
}

// Title and description on the left, the control on the right. Title and meta arrive escaped.
function settingsRow({ title, meta = "", control = "", before = "" }) {
  return `
    <div class="settings-row">
      ${before}
      <div class="settings-row-copy"><strong>${title}</strong>${meta ? `<p class="settings-meta">${meta}</p>` : ""}</div>
      ${control ? `<div class="settings-row-control">${control}</div>` : ""}
    </div>`;
}

function settingsList(rows) {
  return `<div class="settings-list">${rows}</div>`;
}

function metaParts(parts) {
  return parts.filter(Boolean).map((part) => `<span>${esc(part)}</span>`).join("");
}

/* Select: the browser's popup ignores the page's look, so this is a listbox of our own. The value lives in a
   hidden input, which forms and change listeners read like any field. */
function selectField({ id, name = "", value, options, label = "", className = "", attrs = "" }) {
  const selected = options.find((option) => String(option.value) === String(value)) || options[0];
  return `
    <div class="select${className ? ` ${className}` : ""}" data-select>
      <input type="hidden"${name ? ` name="${esc(name)}"` : ""} value="${esc(selected.value)}"${attrs}>
      <button class="text-field select-trigger" id="${esc(id)}" type="button" role="combobox" aria-haspopup="listbox" aria-expanded="false" aria-controls="${esc(id)}-options"${label ? ` aria-label="${esc(label)}"` : ""}>
        <span class="select-value">${esc(selected.label)}</span>${icon("chevronDown")}
      </button>
      <div class="select-menu" id="${esc(id)}-options" role="listbox" popover="manual"${label ? ` aria-label="${esc(label)}"` : ""}>
        ${options.map((option) => `<button class="select-option" type="button" role="option" tabindex="-1" data-value="${esc(option.value)}" aria-selected="${option === selected}">${icon("check")}<span>${esc(option.label)}</span></button>`).join("")}
      </div>
    </div>`;
}

function selectParts(root) {
  return { input: root.querySelector("input"), trigger: root.querySelector(".select-trigger"), menu: root.querySelector(".select-menu") };
}

function closeSelect({ focus = false } = {}) {
  const root = state._openSelect;
  if (!root) return;
  state._openSelect = null;
  const { trigger, menu } = selectParts(root);
  trigger.setAttribute("aria-expanded", "false");
  if (menu.matches(":popover-open")) menu.hidePopover();
  if (focus) trigger.focus();
}

// The menu sits in the top layer, so nothing clips it; it opens below the field unless the window ends first.
function openSelect(root) {
  closeSelect();
  const { trigger, menu } = selectParts(root);
  if (trigger.disabled) return;
  state._openSelect = root;
  trigger.setAttribute("aria-expanded", "true");
  menu.style.minWidth = `${trigger.offsetWidth}px`;
  menu.showPopover();
  const rect = trigger.getBoundingClientRect();
  const fits = rect.bottom + menu.offsetHeight + 12 <= window.innerHeight;
  menu.style.top = `${fits ? rect.bottom + 4 : Math.max(8, rect.top - menu.offsetHeight - 4)}px`;
  menu.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - menu.offsetWidth - 8))}px`;
  menu.querySelector('[aria-selected="true"]').focus({ preventScroll: true });
}

function setSelectValue(input, value) {
  const { trigger, menu } = selectParts(input.closest("[data-select]"));
  input.value = value;
  for (const option of menu.querySelectorAll("[role=option]")) {
    const selected = option.dataset.value === String(value);
    option.setAttribute("aria-selected", String(selected));
    if (selected) trigger.querySelector(".select-value").textContent = option.textContent;
  }
}

function chooseOption(option) {
  const root = option.closest("[data-select]");
  const { input } = selectParts(root);
  const changed = input.value !== option.dataset.value;
  setSelectValue(input, option.dataset.value);
  closeSelect({ focus: true });
  if (!changed) return;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function selectKeydown(event) {
  const root = event.target.closest?.("[data-select]");
  if (!root) return;
  if (event.key === "Escape") {
    if (root !== state._openSelect) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    closeSelect({ focus: true });
    return;
  }
  if (root !== state._openSelect) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    openSelect(root);
    return;
  }
  const options = [...root.querySelectorAll("[role=option]")];
  const current = options.indexOf(document.activeElement);
  const typed = event.key.length === 1 && !event.metaKey && !event.ctrlKey && !event.altKey && event.key !== " "
    ? [...options.slice(current + 1), ...options.slice(0, current + 1)].find((option) => option.textContent.trim().toLowerCase().startsWith(event.key.toLowerCase()))
    : null;
  const target = typed || { ArrowDown: options[(current + 1) % options.length], ArrowUp: options.at(current - 1), Home: options[0], End: options.at(-1) }[event.key];
  if (!target) return;
  event.preventDefault();
  target.focus();
}

// A secret the server returns once: a new access token, an invite link.
function secretBox(value, copyAttribute, note) {
  return `
    <div class="secret-box">
      <code class="secret-value">${esc(value)}</code>
      <button class="button button-secondary button-small" type="button" ${copyAttribute}>${iconLabel("copy", t("Copy"))}</button>
      <p class="secret-note">${esc(note)}</p>
    </div>`;
}

function setFieldError(form, message, field = form?.querySelector?.(".text-field")) {
  const error = form?.querySelector?.(".field-error");
  if (!error) return;
  error.textContent = message;
  error.hidden = !message;
  for (const input of form.querySelectorAll?.(".text-field") || []) input.removeAttribute("aria-invalid");
  if (message) field?.setAttribute("aria-invalid", "true");
}

function serverMessage(error) {
  return t(error.detail || error.message);
}

function sitePageError(message) {
  return `<div class="empty-state"><p>${esc(message)}</p><button type="button" class="secondary-btn" data-retry-site>${iconLabel("refresh", t("Retry"))}</button></div>`;
}

// Secrets stay for one visit to their pane; moving away drops them.
function forgetShownSecrets() {
  state._newToken = null;
  state._newInvite = null;
}

function setPage(page) {
  if (state.page !== page) forgetShownSecrets();
  const site = page !== "project";
  state.page = page;
  el.shell.classList.toggle("is-site", site);
  el.detailContent.classList.toggle("is-hidden", site);
  el.siteContent.classList.toggle("is-hidden", !site);
  el.skipLink?.setAttribute("href", site ? "#site-content" : "#detail-content");
  if (!site) {
    // Focus inside the page about to be emptied moves to the project view.
    if (el.siteContent.contains?.(document.activeElement)) el.detailContent.focus?.({ preventScroll: true });
    beginViewRequest("site");
    state._team = null;
    state._invite = null;
    state._device = null;
    // Teams change on these pages: the project's Settings tab asks again.
    state._teams = null;
    state._teamsError = "";
    state._projectTeam = null;
    el.siteContent.innerHTML = "";
  }
  renderProjectSelector();
}

function leaveSitePage() {
  if (state.page === "project") return;
  setPage("project");
  if (state.activeTab === "settings") renderProjectBody();
}

function closeOverlays() {
  closeHeaderMenus();
  toggleProjectPicker(false);
  closeDrawer({ history: "none" });
  closeSettingsDialog({ history: "none" });
}

// On a phone the nav is one scrolling row: bring the current item into it.
function revealNavItem(root) {
  const nav = root.querySelector?.(".settings-nav");
  const item = nav?.querySelector?.('[aria-current="page"]');
  if (item && nav.scrollWidth > nav.clientWidth) nav.scrollLeft = Math.max(0, item.offsetLeft - nav.offsetLeft - (nav.clientWidth - item.offsetWidth) / 2);
  return item;
}

// Keep the reader's place: focus a page on arrival, and the nav item when moving between panes.
function settlePage(root, arriving) {
  const item = revealNavItem(root);
  window.scrollTo?.({ top: 0 });
  // The first paint leaves focus where the browser put it.
  if (state._ready) (!arriving && item ? item : root).focus?.({ preventScroll: true });
}

function renderSitePage() {
  if (state._dialog) renderSettingsDialog();
  if (state.page === "home") renderHomePage();
  else if (state.page === "team") renderTeamPage();
  else if (state.page === "invite") renderInvitePage();
  else if (state.page === "device") renderDevicePage();
  updateDocumentTitle();
}

async function reloadSitePage() {
  if (state._dialog) await loadPane();
  else if (state.page === "home") await loadHome();
  else if (state.page === "team") await loadTeam();
  else if (state.page === "invite") await loadInvite();
}

/* Home: every project the viewer works on. */

function listedProjects() {
  return state.projects.filter((project) => !project.transient);
}

// Without a default project, two or more projects need a page of their own at /.
function hasHomePage() {
  return !state.visitor && !defaultProjectId() && listedProjects().length >= 2;
}

async function showHome({ history = "replace" } = {}) {
  closeOverlays();
  const arriving = state.page !== "home";
  setPage("home");
  writeRoute(history);
  renderHomePage();
  settlePage(el.siteContent, arriving);
  await loadHome();
}

async function loadHome() {
  const request = beginViewRequest("site");
  state._homeError = "";
  try {
    const result = await fetchJson(apiUrl("/api/v1/home"));
    if (!ownsViewRequest("site", request)) return;
    state._home = result.projects || [];
  } catch (error) {
    if (!ownsViewRequest("site", request)) return;
    state._homeError = error.message;
  }
  if (state.page === "home") renderHomePage();
}

function homeRow(project) {
  const synced = project.last_synced_at ? t("Synced {time}", { time: relativeDate(project.last_synced_at) }) : t("Not synced");
  return `
    <a class="list-row home-row" href="${esc(projectPath(project.id))}" data-route>
      <span class="row-main">
        <strong class="row-title">${esc(project.full_name)}</strong>
        <span class="row-byline">
          <span>${esc(t("{count} active", { count: project.active_intents || 0 }))}</span>
          ${project.blocked_intents ? stateBadge({ key: "blocked", label: t("{count} blocked", { count: project.blocked_intents }) }) : ""}
        </span>
      </span>
      <span class="row-meta">
        ${state.config?.authRequired ? visibilityBadge(project.visibility) : ""}
        <span>${esc(synced)}</span>
      </span>
    </a>`;
}

function renderHomePage() {
  const body = state._homeError
    ? sitePageError(state._homeError)
    : state._home
      ? `<div class="list-card">${state._home.map(homeRow).join("")}</div>`
      : viewLoadingHtml();
  el.siteContent.innerHTML = `<div class="home-page">${pageHeader({ title: t("Projects") })}${body}</div>`;
}

/* Account and Settings: who you are, and how you use IntHub. Each pane has its own URL. */

function accountNav(pane) {
  return [
    { label: t("Profile"), icon: "user", href: ACCOUNT_PATHS.profile, current: pane === "profile" },
    { label: t("Danger zone"), icon: "blocker", href: ACCOUNT_PATHS.danger, current: pane === "danger" },
  ];
}

function settingsNav(pane) {
  return [
    { label: t("Access tokens"), icon: "key", href: SETTINGS_PATHS.tokens, current: pane === "tokens" },
    { label: t("Teams"), icon: "users", href: SETTINGS_PATHS.teams, current: pane === "teams" },
    { label: t("Usage"), icon: "gauge", href: SETTINGS_PATHS.usage, current: pane === "usage" },
  ];
}

function dialogTitle() {
  return t(state._dialog === "account" ? "Account" : "Settings");
}

// The dialog keeps its size whichever pane shows, opens over the current page, and adds one history entry however
// many panes it passes through, so Back closes it. A dialog restored by a link or Back leaves its entry in place.
function openSettingsDialog(page, pane, { history = "auto" } = {}) {
  closeHeaderMenus();
  toggleProjectPicker(false);
  closeDrawer({ history: "none" });
  const wasOpen = Boolean(state._dialog);
  if (state._dialog !== page || state._pane !== pane) {
    forgetShownSecrets();
    state._dialog = page;
    state._pane = pane;
    state._tokenDraft = { name: "itt", days: DEFAULT_TOKEN_DAYS };
    state._teamDraft = { name: "", slug: "", edited: false };
    renderSettingsDialog();
    loadPane();
  }
  if (!el.settingsDialog.open) el.settingsDialog.showModal();
  revealNavItem(el.settingsDialogBody)?.focus?.({ preventScroll: true });
  updateDocumentTitle();
  const routed = writeRoute(history === "auto" ? (wasOpen ? "replace" : "push") : history, "dialog");
  if (!wasOpen) state._dialogPushed = routed === "pushed";
}

function closeSettingsDialog({ history = "auto" } = {}) {
  if (!state._dialog) return;
  closeSelect();
  const trigger = state._dialog === "settings" ? el.settingsLink : el.accountMenuTrigger;
  beginViewRequest("dialog");
  forgetShownSecrets();
  state._dialog = null;
  state._pane = "";
  state._tokens = null;
  state._tokensError = "";
  state._teams = null;
  state._teamsError = "";
  state._usage = null;
  if (el.settingsDialog.open) el.settingsDialog.close();
  el.settingsDialogBody.innerHTML = "";
  updateDocumentTitle();
  trigger.focus?.();
  if (history === "auto") {
    if (state._dialogPushed && window.history.state?.inthub === "dialog" && window.history.back) window.history.back();
    else writeRoute("replace");
  }
  state._dialogPushed = false;
}

async function loadPane() {
  if (state._pane === "tokens") await loadAccountTokens();
  else if (state._pane === "teams") await loadTeams();
  else if (state._pane === "usage") await loadUsage();
}

function renderSettingsDialog() {
  const pane = state._pane;
  const account = state._dialog === "account";
  if (!state._dialog) return;
  const title = dialogTitle();
  el.settingsDialogTitle.textContent = title;
  el.settingsDialogBody.innerHTML = settingsLayout({
    label: title,
    items: account ? accountNav(pane) : settingsNav(pane),
    pane: { profile: profilePane, danger: accountDangerPane, tokens: tokensPane, teams: teamsPane, usage: usagePane }[pane](),
  });
}

function profilePane() {
  const account = state.account || {};
  const name = account.display_name || account.login || "";
  return `
    ${settingsBlock("profile", t("Profile"), settingsList(settingsRow({
      before: monogram(name),
      title: esc(name),
      meta: metaParts([account.email || (account.login && account.login !== name ? `@${account.login}` : "")]),
      control: `<a class="settings-link" href="${TENON_ACCOUNT_URL}">${esc(t("Edit in Tenon"))}${icon("external")}</a>`,
    })))}
    ${settingsBlock("identity", t("Link your Snaps"), profileIdentityHtml(account))}`;
}

function accountDangerPane() {
  return settingsBlock("account-danger", t("Danger zone"), settingsList(settingsRow({
    title: esc(t("Delete account")),
    meta: esc(t("Removes the account with its personal projects and access tokens. Teams you administer pass to the next member; a team with nobody else is deleted with its projects. You confirm it in Tenon's account center.")),
    control: `<button id="delete-account-btn" class="button button-danger" type="button" data-delete-account>${iconLabel("trash", t("Delete account"))}</button>`,
  })));
}

// The link between Git and this account is the author email, as on GitHub.
function profileIdentityHtml(account) {
  if (!account.email) return `<p class="settings-lead">${esc(t("Sign in again to link Snaps to this account."))}</p>`;
  const email = /^[\w.+@-]+$/.test(account.email) ? account.email : shellArg(account.email);
  return `
    <p class="settings-lead">${tHtml("Snaps link to this account when their author email is {email}. Set Git to the same address:", { email: `<span class="profile-email">${esc(account.email)}</span>` })}</p>
    ${commandSnippet([`git config --global user.email ${email}`])}`;
}

function tokensPane() {
  return settingsBlock("tokens", t("Access tokens"), `${tokenFormHtml()}<div class="settings-slot" id="token-list" tabindex="-1">${tokenListHtml()}</div>`,
    esc(t("The Intent CLI signs in with an access token to push this account's projects. Revoke a token when a machine no longer needs it.")));
}

function tokenFormHtml() {
  const draft = state._tokenDraft || { name: "itt", days: DEFAULT_TOKEN_DAYS };
  const days = TOKEN_LIFETIMES.includes(Number(draft.days)) ? Number(draft.days) : DEFAULT_TOKEN_DAYS;
  return `
    <form class="settings-form token-form" data-token-form novalidate>
      <div class="settings-field token-name-field">
        <label class="field-label" for="token-name">${esc(t("Name"))}</label>
        <input class="text-field" id="token-name" name="token-name" type="text" value="${esc(draft.name ?? "itt")}" maxlength="100" autocomplete="off" autocapitalize="off" spellcheck="false" aria-describedby="token-form-error">
      </div>
      <div class="settings-field">
        <label class="field-label" for="token-days">${esc(t("Expires in"))}</label>
        ${selectField({ id: "token-days", name: "token-days", value: days, options: TOKEN_LIFETIMES.map((value) => ({ value, label: plural(value, "{count} day", "{count} days") })) })}
      </div>
      <button class="button button-primary" type="submit">${iconLabel("key", t("Generate token"))}</button>
      <p class="field-error" id="token-form-error" role="alert" hidden></p>
    </form>`;
}

// Active tokens only: revoked and expired ones no longer let the CLI in.
function activeTokens() {
  const now = Date.now();
  return (state._tokens || []).filter((token) => !token.revoked_at && !(token.expires_at && new Date(token.expires_at).getTime() <= now));
}

function tokenRowHtml(token) {
  const fresh = state._newToken?.id === token.id ? state._newToken : null;
  return settingsRow({
    title: esc(token.name || "CLI"),
    meta: metaParts([
      t("Created {date}", { date: calendarDate(token.created_at) }),
      token.last_used_at ? t("Last used {time}", { time: relativeDate(token.last_used_at) }) : t("Never used"),
      token.expires_at ? t("Expires {date}", { date: calendarDate(token.expires_at) }) : "",
    ]),
    control: `<button class="button button-danger button-small" type="button" data-revoke-token="${esc(token.id)}">${iconLabel("revoke", t("Revoke"))}</button>`,
  }) + (fresh ? secretBox(fresh.token, "data-copy-new-token", t("Copy it now; it won't be shown again.")) : "");
}

function tokenListHtml() {
  if (state._tokensError) {
    return `<div class="inline-empty settings-retry"><p>${esc(state._tokensError)}</p><button type="button" class="secondary-btn" data-retry-tokens>${iconLabel("refresh", t("Retry"))}</button></div>`;
  }
  if (!state._tokens) return viewLoadingHtml();
  const tokens = activeTokens();
  if (!tokens.length) return `<p class="inline-empty">${esc(t("No active tokens. Generate one for each machine or Agent that runs the Intent CLI."))}</p>`;
  return settingsList(tokens.map(tokenRowHtml).join(""));
}

function renderTokenList() {
  const list = el.settingsDialogBody.querySelector?.("#token-list");
  if (list) list.innerHTML = tokenListHtml();
  else renderSettingsDialog();
}

async function loadAccountTokens() {
  const request = beginViewRequest("dialog");
  state._tokensError = "";
  try {
    const result = await fetchJson(apiUrl("/api/v1/auth/tokens"));
    if (!ownsViewRequest("dialog", request) || state._dialog !== "settings") return;
    state._tokens = result.tokens || [];
  } catch (error) {
    if (!ownsViewRequest("dialog", request) || state._dialog !== "settings") return;
    state._tokensError = error.message;
  }
  renderTokenList();
}

async function generateAccessToken({ name, days }) {
  const label = String(name ?? "").trim();
  if (!label) throw new ApiRequestError(t("Enter a token name."), 0, "INVALID_INPUT");
  const lifetime = TOKEN_LIFETIMES.includes(Number(days)) ? Number(days) : DEFAULT_TOKEN_DAYS;
  const issued = await fetchJson(apiUrl("/api/v1/auth/tokens"), {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ name: label, ttl_seconds: lifetime * 86400 }),
  });
  if (state._dialog !== "settings") return issued;
  // The secret lives only here, for this visit to the pane; the list shows it once, under its row.
  state._newToken = { id: issued.id, token: issued.token };
  state._tokens = [
    { id: issued.id, name: issued.name, created_at: issued.created_at, expires_at: issued.expires_at, last_used_at: null, revoked_at: null },
    ...(state._tokens || []).filter((token) => token.id !== issued.id),
  ];
  renderTokenList();
  return issued;
}

async function submitTokenForm(form) {
  const button = form.querySelector("[type=submit]");
  if (!button || button.disabled) return;
  setFieldError(form, "");
  setButtonBusy(button, true, "Generating…", "Generate token");
  try {
    await generateAccessToken({ name: form.elements["token-name"].value, days: form.elements["token-days"].value });
    // The next token starts from the default name again; the lifetime choice stays.
    form.elements["token-name"].value = "itt";
    state._tokenDraft = { ...(state._tokenDraft || {}), name: "itt" };
    setStatus(t("Token created. Copy it now; it won't be shown again."));
    el.settingsDialogBody.querySelector("[data-copy-new-token]")?.focus();
  } catch (error) {
    setFieldError(form, error.code === "INVALID_INPUT" && error.detail ? error.detail : error.message);
  } finally {
    setButtonBusy(button, false, "Generating…", "Generate token");
  }
}

function confirmRevokeToken(id, trigger = null) {
  const token = (state._tokens || []).find((entry) => entry.id === id);
  if (!token) return;
  openConfirm({
    title: () => t("Revoke {name}?", { name: token.name || "CLI" }),
    body: () => t("Every CLI that uses this token stops being able to push at once. This cannot be undone."),
    action: "Revoke token",
    icon: "revoke",
    busy: "Revoking…",
    run: () => revokeAccessToken(id),
    returnFocus: trigger,
  });
}

async function revokeAccessToken(id) {
  try {
    await fetchJson(apiUrl(`/api/v1/auth/tokens/${encodeURIComponent(id)}/revoke`), { method: "POST", headers: JSON_HEADERS, body: "{}" });
  } catch (error) {
    // Already revoked (404) is the state we asked for.
    if (error.status !== 404) throw error;
  }
  state._tokens = (state._tokens || []).filter((token) => token.id !== id);
  if (state._newToken?.id === id) state._newToken = null;
  renderTokenList();
  setStatus(t("Token revoked."));
}

async function startAccountDeletion(button) {
  if (button.disabled) return;
  setButtonBusy(button, true, "Opening account management…", "Delete account");
  try {
    const result = await fetchJson(apiUrl("/api/auth/tenon/delete/start"), { method: "POST", headers: JSON_HEADERS, body: "{}" });
    window.location.assign(productDeletionDestination(result));
  } catch (error) {
    setStatus(error.message, true);
    setButtonBusy(button, false, "Opening account management…", "Delete account");
  }
}

function formatBytes(bytes) {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${unit && value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}

function usageRow(owner) {
  return settingsRow({
    title: esc(owner.name || t("Personal")),
    meta: metaParts([
      t("{used} of {limit} projects", { used: owner.projects, limit: owner.projects_limit }),
      t("{used} of {limit} history storage", { used: formatBytes(owner.storage_bytes), limit: formatBytes(owner.storage_limit) }),
    ]),
  });
}

function usageListHtml() {
  if (state._usageError) return `<div class="inline-empty settings-retry"><p>${esc(state._usageError)}</p><button type="button" class="secondary-btn" data-retry-site>${iconLabel("refresh", t("Retry"))}</button></div>`;
  return state._usage ? settingsList(state._usage.map(usageRow).join("")) : viewLoadingHtml();
}

function usagePane() {
  return settingsBlock("usage", t("Usage"), `<div class="settings-slot" id="usage-list">${usageListHtml()}</div>`,
    esc(t("Your account and each team have their own allowance. Deleting a project frees its storage.")));
}

async function loadUsage() {
  const request = beginViewRequest("dialog");
  state._usageError = "";
  try {
    const result = await fetchJson(apiUrl("/api/v1/usage"));
    if (!ownsViewRequest("dialog", request)) return;
    state._usage = result.owners;
  } catch (error) {
    if (!ownsViewRequest("dialog", request)) return;
    state._usageError = error.message;
  }
  const list = el.settingsDialogBody.querySelector?.("#usage-list");
  if (list) list.innerHTML = usageListHtml();
}

/* Teams: the list in Settings, and each team's own page. */

async function loadTeams() {
  const request = beginViewRequest("teams");
  state._teamsError = "";
  try {
    const result = await fetchJson(apiUrl("/api/v1/teams"));
    if (!ownsViewRequest("teams", request)) return;
    state._teams = result.teams || [];
  } catch (error) {
    if (!ownsViewRequest("teams", request)) return;
    state._teamsError = error.message;
  }
  if (state._dialog === "settings" && state._pane === "teams") renderTeamList();
  else if (state.page === "project" && state.activeTab === "settings") renderTransferControl();
}

// Latin names give a URL to start from; others leave it for the person to type.
function slugFromName(name) {
  const latin = String(name || "").normalize("NFKD").replace(/[̀-ͯ]/g, "");
  if (/[^\x00-\x7f]/.test(latin)) return "";
  return latin.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 39).replace(/^-+|-+$/g, "");
}

function teamSlugProblem(slug) {
  if (!slug) return t("Enter a team URL.");
  return TEAM_SLUG.test(slug) ? "" : t("Use lowercase letters, digits and hyphens, up to 39 characters, with no hyphen at either end.");
}

function teamNameProblem(name) {
  if (!name) return t("Enter a team name.");
  return [...name].length > 80 ? t("Use {count} characters or fewer.", { count: 80 }) : "";
}

function teamRow(team) {
  return `
    <a class="settings-row settings-row-link" href="${esc(teamPath(team.slug))}" data-route>
      <div class="settings-row-copy">
        <strong>${esc(team.name)}</strong>
        <p class="settings-meta">${metaParts([
          team.slug,
          roleLabel(team.role),
          plural(team.members, "{count} member", "{count} members"),
          plural(team.projects, "{count} project", "{count} projects"),
        ])}</p>
      </div>
      <div class="settings-row-control">${icon("chevron")}</div>
    </a>`;
}

function teamFields(idPrefix, name, slug) {
  return `
    <div class="settings-field">
      <label class="field-label" for="${idPrefix}-name">${esc(t("Team name"))}</label>
      <input class="text-field" id="${idPrefix}-name" name="team-name" type="text" value="${esc(name)}" maxlength="80" autocomplete="off" aria-describedby="${idPrefix}-error">
    </div>
    <div class="settings-field">
      <label class="field-label" for="${idPrefix}-slug">${esc(t("Team URL"))}</label>
      <input class="text-field" id="${idPrefix}-slug" name="team-slug" type="text" value="${esc(slug)}" maxlength="39" autocomplete="off" autocapitalize="off" spellcheck="false" aria-describedby="${idPrefix}-error">
    </div>`;
}

function teamListHtml() {
  const teams = state._teams;
  if (state._teamsError) return `<div class="inline-empty settings-retry"><p>${esc(state._teamsError)}</p><button type="button" class="secondary-btn" data-retry-site>${iconLabel("refresh", t("Retry"))}</button></div>`;
  if (!teams) return viewLoadingHtml();
  return teams.length ? settingsList(teams.map(teamRow).join("")) : `<p class="inline-empty">${esc(t("You are not in a team yet."))}</p>`;
}

function renderTeamList() {
  const list = el.settingsDialogBody.querySelector?.("#team-list");
  if (list) list.innerHTML = teamListHtml();
  else renderSettingsDialog();
}

function teamsPane() {
  const draft = state._teamDraft || { name: "", slug: "" };
  return `
    ${settingsBlock("teams", t("Teams"), `<div class="settings-slot" id="team-list">${teamListHtml()}</div>`)}
    ${settingsBlock("new-team", t("New team"), `
      <form class="settings-form team-form" data-team-form novalidate>
        ${teamFields("new-team", draft.name, draft.slug)}
        <button class="button button-primary" type="submit">${iconLabel("plus", t("Create team"))}</button>
        <p class="field-error" id="new-team-error" role="alert" hidden></p>
        <p class="field-note">${esc(t("Lowercase letters, digits and hyphens. Team projects use it in the CLI as team/project."))}</p>
      </form>`)}`;
}

function updateTeamDraft(field) {
  const draft = state._teamDraft ||= { name: "", slug: "", edited: false };
  if (field.name === "team-name") {
    draft.name = field.value;
    if (!draft.edited) {
      draft.slug = slugFromName(field.value);
      const slug = field.form?.elements?.["team-slug"];
      if (slug) slug.value = draft.slug;
    }
  } else {
    draft.slug = field.value;
    draft.edited = Boolean(field.value);
  }
  setFieldError(field.form, "");
}

// The team form's values, or null after marking the field at fault.
function checkTeamForm(form) {
  const name = form.elements["team-name"].value.trim();
  const slug = form.elements["team-slug"].value.trim();
  const nameProblem = teamNameProblem(name);
  const problem = nameProblem || teamSlugProblem(slug);
  setFieldError(form, problem, form.elements[nameProblem ? "team-name" : "team-slug"]);
  return problem ? null : { name, slug };
}

function teamErrorMessage(error, slug) {
  if (error.code === "NAME_TAKEN") return t("The team URL {slug} is taken.", { slug });
  if (error.code === "TEAM_LIMIT") return t("You have reached the limit on teams.");
  return serverMessage(error);
}

async function createTeam(form) {
  const button = form.querySelector("[type=submit]");
  const values = checkTeamForm(form);
  if (!button || button.disabled || !values) return;
  setButtonBusy(button, true, "Creating team…", "Create team");
  try {
    const created = await fetchJson(apiUrl("/api/v1/teams"), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(values) });
    state._teams = null;
    setStatus(t("Created {name}.", { name: created.team.name }));
    window.history.pushState({ inthub: "page" }, "", teamPath(created.team.slug));
    await showTeam(created.team.slug, "members", { history: "none" });
  } catch (error) {
    setFieldError(form, teamErrorMessage(error, values.slug), form.elements["team-slug"]);
    setButtonBusy(button, false, "Creating team…", "Create team");
  }
}

async function showTeam(slug, pane = "members", { history = "none" } = {}) {
  closeOverlays();
  const arriving = state.page !== "team" || state._team?.slug !== slug;
  if (arriving || state._team?.pane !== pane) forgetShownSecrets();
  if (arriving) {
    state._team = { slug, pane, data: null, error: "" };
    setPage("team");
  }
  state._team.pane = pane;
  writeRoute(history);
  renderTeamPage();
  settlePage(el.siteContent, arriving);
  if (arriving) await loadTeam();
}

async function loadTeam() {
  const team = state._team;
  if (!team) return;
  const request = beginViewRequest("site");
  team.error = "";
  try {
    const data = await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(team.slug)}`));
    if (!ownsViewRequest("site", request) || state._team !== team) return;
    team.data = data;
    team.edit = null;
  } catch (error) {
    if (!ownsViewRequest("site", request) || state._team !== team) return;
    team.error = error.status === 404 ? t("This team does not exist, or you are not in it.") : error.message;
  }
  // Settings is for admins; anyone else who lands there reads the members instead.
  if (team.pane === "settings" && team.data && team.data.role !== "admin") {
    team.pane = "members";
    writeRoute("replace");
  }
  renderTeamPage();
  updateDocumentTitle();
}

function teamNav(team) {
  const admin = team.data?.role === "admin";
  return [
    { label: t("Members"), icon: "users", href: teamPath(team.slug), current: team.pane === "members" },
    { label: t("Projects"), icon: "folder", href: teamPath(team.slug, "projects"), current: team.pane === "projects" },
    ...(admin ? [{ label: t("Settings"), icon: "settings", href: teamPath(team.slug, "settings"), current: team.pane === "settings" }] : []),
  ];
}

function renderTeamPage() {
  const team = state._team;
  if (state.page !== "team" || !team) return;
  if (team.error) {
    el.siteContent.innerHTML = `<div class="home-page">${pageHeader({ title: team.slug })}${sitePageError(team.error)}</div>`;
    return;
  }
  el.siteContent.innerHTML = settingsLayout({
    title: team.data?.team.name || team.slug,
    label: t("Team"),
    items: teamNav(team),
    pane: team.data ? { members: teamMembersPane, projects: teamProjectsPane, settings: teamSettingsPane }[team.pane](team.data) : viewLoadingHtml(),
  });
}

function roleOptions() {
  return TEAM_ROLES.map((role) => ({ value: role, label: roleLabel(role) }));
}

function memberRow(member, admin) {
  const name = `${esc(member.name)}${member.you ? ` <span class="chip">${esc(t("You"))}</span>` : ""}`;
  return settingsRow({
    before: monogram(member.name),
    title: name,
    meta: metaParts([member.email, t("Joined {date}", { date: calendarDate(member.joined_at) })]),
    control: admin
      ? `${selectField({ id: `member-role-${member.id}`, value: member.role, options: roleOptions(), label: t("Role of {name}", { name: member.name }), className: "role-select", attrs: ` data-member-role="${esc(member.id)}"` })}
         <button class="button button-danger button-small" type="button" data-remove-member="${esc(member.id)}">${iconLabel("userMinus", t("Remove"))}</button>`
      : `<span class="settings-role">${esc(roleLabel(member.role))}</span>`,
  });
}

function inviteRow(invite) {
  return settingsRow({
    title: esc(t("{role} invite", { role: roleLabel(invite.role) })),
    meta: metaParts([invite.invited_by ? t("Created by {name}", { name: invite.invited_by }) : "", t("Expires {date}", { date: calendarDate(invite.expires_at) })]),
    control: `<button class="button button-danger button-small" type="button" data-revoke-invite="${esc(invite.id)}">${iconLabel("revoke", t("Revoke"))}</button>`,
  });
}

function teamMembersPane(data) {
  const admin = data.role === "admin";
  const fresh = state._newInvite;
  return `
    ${settingsBlock("members", t("Members"), settingsList(data.members.map((member) => memberRow(member, admin)).join("")))}
    ${admin ? settingsBlock("invite", t("Invite people"), `
      <form class="settings-form invite-form" data-invite-form novalidate>
        <div class="settings-field">
          <label class="field-label" for="invite-role">${esc(t("Role"))}</label>
          ${selectField({ id: "invite-role", name: "invite-role", value: state._inviteRole || "member", options: roleOptions() })}
        </div>
        <button class="button button-primary" type="submit">${iconLabel("link", t("Create invite link"))}</button>
        <p class="field-error" role="alert" hidden></p>
      </form>
      ${fresh ? secretBox(fresh.url, "data-copy-invite", t("Copy it now; it won't be shown again.")) : ""}`,
      esc(t("A link works once and expires after 7 days. Anyone who opens it and signs in joins with the role you choose."))) : ""}
    ${admin && data.invites.length ? settingsBlock("pending-invites", t("Pending invites"), settingsList(data.invites.map(inviteRow).join(""))) : ""}
    <div class="settings-block">${settingsList(settingsRow({
      title: esc(t("Leave team")),
      meta: esc(t("You lose access to the team's projects until someone invites you again.")),
      control: `<button class="button button-danger" type="button" data-leave-team>${iconLabel("logout", t("Leave team"))}</button>`,
    }))}</div>`;
}

function teamProjectRow(project) {
  return `
    <a class="settings-row settings-row-link" href="${esc(projectPath(project.id))}" data-route>
      <div class="settings-row-copy">
        <strong>${esc(project.name)}</strong>
        <p class="settings-meta">${metaParts([project.last_synced_at ? t("Synced {time}", { time: relativeDate(project.last_synced_at) }) : t("Not synced")])}</p>
      </div>
      <div class="settings-row-control">${visibilityBadge(project.visibility)}${icon("chevron")}</div>
    </a>`;
}

function teamProjectsPane(data) {
  return settingsBlock("projects", t("Projects"), data.projects.length
    ? settingsList(data.projects.map(teamProjectRow).join(""))
    : `<p class="inline-empty">${esc(t("This team has no projects yet."))}</p>`);
}

function teamSettingsPane(data) {
  const edit = state._team.edit || { name: data.team.name, slug: data.team.slug };
  const count = data.projects.length;
  return `
    ${settingsBlock("team", t("General"), `
      <form class="settings-form team-form" data-team-settings-form novalidate>
        ${teamFields("edit-team", edit.name, edit.slug)}
        <button class="button button-secondary" type="submit">${iconLabel("check", t("Save"))}</button>
        <p class="field-error" id="edit-team-error" role="alert" hidden></p>
        <p class="field-note">${esc(t("Clones follow a new team URL on their next push or pull."))}</p>
      </form>`)}
    ${settingsBlock("team-danger", t("Danger zone"), settingsList(settingsRow({
      title: esc(t("Delete this team")),
      meta: esc(count ? plural(count, "Removes the team and its {count} project.", "Removes the team and its {count} projects.") : t("Removes the team. It has no projects.")),
      control: `<button class="button button-danger" type="button" data-delete-team>${iconLabel("trash", t("Delete team"))}</button>`,
    })))}`;
}

async function saveTeam(form) {
  const team = state._team;
  const button = form.querySelector("[type=submit]");
  const values = checkTeamForm(form);
  if (!team?.data || !button || button.disabled || !values) return;
  setButtonBusy(button, true, "Saving…", "Save");
  try {
    const result = await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(team.data.team.id)}`), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(values) });
    team.data = { ...team.data, team: result.team };
    team.slug = result.team.slug;
    team.edit = null;
    state._teams = null;
    writeRoute("replace");
    renderTeamPage();
    updateDocumentTitle();
    el.siteContent.querySelector?.("#edit-team-name")?.focus();
    setStatus(t("Team saved."));
    await refreshProjectList();
  } catch (error) {
    setFieldError(form, teamErrorMessage(error, values.slug), form.elements["team-slug"]);
    setButtonBusy(button, false, "Saving…", "Save");
  }
}

function confirmDeleteTeam(trigger = null) {
  const data = state._team?.data;
  if (!data) return;
  const count = data.projects.length;
  openConfirm({
    title: () => t("Delete {name}?", { name: data.team.name }),
    body: () => count
      ? plural(count, "This removes the team and its {count} project from this hub, with their history. Local .intent data is not touched. This cannot be undone.", "This removes the team and its {count} projects from this hub, with their history. Local .intent data is not touched. This cannot be undone.")
      : t("This removes the team from this hub. This cannot be undone."),
    label: () => tHtml("Type {name} to confirm.", { name: `<strong class="confirm-name">${esc(data.team.slug)}</strong>` }),
    expect: data.team.slug,
    action: "Delete team",
    icon: "trash",
    busy: "Deleting…",
    run: (typed) => deleteTeam(data.team, typed),
    returnFocus: trigger,
  });
}

async function leaveTeamPage(message) {
  state._teams = null;
  setStatus(message);
  await refreshProjectList();
  await openDefault();
}

async function deleteTeam(team, confirm) {
  await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(team.id)}/delete`), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ confirm }) });
  await leaveTeamPage(t("Deleted {name}.", { name: team.name }));
}

function confirmLeaveTeam(trigger = null) {
  const data = state._team?.data;
  const me = data?.members.find((member) => member.you);
  if (!me) return;
  openConfirm({
    title: () => t("Leave {name}?", { name: data.team.name }),
    body: () => t("You lose access to the team's projects until someone invites you again."),
    action: "Leave team",
    icon: "logout",
    busy: "Leaving…",
    run: async () => {
      await removeMember(data.team, me.id);
      await leaveTeamPage(t("You left {name}.", { name: data.team.name }));
    },
    message: serverMessage,
    returnFocus: trigger,
  });
}

function removeMember(team, memberId) {
  return fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(team.id)}/members/${encodeURIComponent(memberId)}/remove`), { method: "POST", headers: JSON_HEADERS, body: "{}" });
}

function confirmRemoveMember(memberId, trigger = null) {
  const data = state._team?.data;
  const member = data?.members.find((entry) => entry.id === memberId);
  if (!member) return;
  if (member.you) {
    confirmLeaveTeam(trigger);
    return;
  }
  openConfirm({
    title: () => t("Remove {name}?", { name: member.name }),
    body: () => t("{name} loses access to the team's projects.", { name: member.name }),
    action: "Remove member",
    icon: "userMinus",
    busy: "Removing…",
    run: async () => {
      await removeMember(data.team, member.id);
      await loadTeam();
      setStatus(t("Removed {name}.", { name: member.name }));
    },
    message: serverMessage,
    returnFocus: trigger,
  });
}

async function changeMemberRole(select) {
  const data = state._team?.data;
  const member = data?.members.find((entry) => entry.id === select.dataset.memberRole);
  if (!member || select.value === member.role) return;
  const role = select.value;
  const { trigger } = selectParts(select.closest("[data-select]"));
  trigger.disabled = true;
  try {
    await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(data.team.id)}/members/${encodeURIComponent(member.id)}/role`), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ role }) });
    member.role = role;
    setStatus(t("{name} is now {role}.", { name: member.name, role: roleLabel(role) }));
    // Losing the admin role takes the management controls away.
    if (member.you && role !== "admin") {
      await loadTeam();
      el.siteContent.focus?.({ preventScroll: true });
    }
  } catch (error) {
    setSelectValue(select, member.role);
    setStatus(serverMessage(error), true);
  } finally {
    trigger.disabled = false;
  }
}

async function createInvite(form) {
  const data = state._team?.data;
  const button = form.querySelector("[type=submit]");
  if (!data || !button || button.disabled) return;
  const role = form.elements["invite-role"].value;
  setFieldError(form, "");
  setButtonBusy(button, true, "Creating link…", "Create invite link");
  try {
    const result = await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(data.team.id)}/invites`), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ role }) });
    state._inviteRole = role;
    // The link exists only in this response; the hub keeps its hash.
    state._newInvite = { id: result.invite.id, url: `${window.location.origin}${result.path}` };
    data.invites = [{ ...result.invite, invited_by: state.account?.display_name || "" }, ...data.invites];
    renderTeamPage();
    setStatus(t("Invite link created. Copy it now; it won't be shown again."));
    el.siteContent.querySelector("[data-copy-invite]")?.focus();
  } catch (error) {
    setFieldError(form, serverMessage(error));
    setButtonBusy(button, false, "Creating link…", "Create invite link");
  }
}

async function revokeInvite(inviteId, button) {
  const data = state._team?.data;
  if (!data || button.disabled) return;
  button.disabled = true;
  try {
    await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(data.team.id)}/invites/${encodeURIComponent(inviteId)}/revoke`), { method: "POST", headers: JSON_HEADERS, body: "{}" });
    data.invites = data.invites.filter((invite) => invite.id !== inviteId);
    if (state._newInvite?.id === inviteId) state._newInvite = null;
    renderTeamPage();
    el.siteContent.focus?.({ preventScroll: true });
    setStatus(t("Invite revoked."));
  } catch (error) {
    button.disabled = false;
    setStatus(serverMessage(error), true);
  }
}

/* Invite: /invite?token=… */

async function showInvite(token, { history = "none" } = {}) {
  closeOverlays();
  setPage("invite");
  state._invite = { token, preview: null, error: "" };
  writeRoute(history);
  renderInvitePage();
  settlePage(el.siteContent, true);
  await loadInvite();
}

async function loadInvite() {
  const invite = state._invite;
  if (!invite) return;
  const request = beginViewRequest("site");
  invite.error = "";
  try {
    if (!invite.token) throw new ApiRequestError("", 410, "INVITE_INVALID");
    const preview = await fetchJson(apiUrl(`/api/v1/invites/preview?${new URLSearchParams({ token: invite.token })}`));
    if (!ownsViewRequest("site", request) || state._invite !== invite) return;
    invite.preview = preview;
  } catch (error) {
    if (!ownsViewRequest("site", request) || state._invite !== invite) return;
    invite.error = error.code === "INVITE_INVALID" ? t("This invite link is no longer valid.") : error.message;
    invite.invalid = error.code === "INVITE_INVALID";
  }
  renderInvitePage();
}

function renderInvitePage() {
  const invite = state._invite;
  if (state.page !== "invite" || !invite) return;
  const preview = invite.preview;
  const home = `<a class="button button-secondary" href="/" data-route>${iconLabel("close", t("Not now"))}</a>`;
  const card = invite.error
    ? `<h1>${esc(t("Team invite"))}</h1><p>${esc(invite.error)}</p>
       <div class="invite-actions">${invite.invalid ? `<a class="button button-secondary" href="/" data-route>${iconLabel("arrow", t("Go to IntHub"))}</a>` : `<button type="button" class="button button-secondary" data-retry-site>${iconLabel("refresh", t("Retry"))}</button>`}</div>`
    : !preview
      ? viewLoadingHtml()
      : preview.already_member
        ? `<h1>${esc(preview.team.name)}</h1><p>${esc(t("You are already in this team."))}</p>
           <div class="invite-actions"><a class="button button-primary" href="${esc(teamPath(preview.team.slug))}" data-route>${iconLabel("arrow", t("Open team"))}</a></div>`
        : `<h1>${esc(preview.team.name)}</h1>
           <p>${esc(preview.invited_by
             ? t("{name} invited you to join {team} as {role}.", { name: preview.invited_by, team: preview.team.name, role: roleLabel(preview.role) })
             : t("You are invited to join {team} as {role}.", { team: preview.team.name, role: roleLabel(preview.role) }))}</p>
           <div class="invite-actions">${home}<button class="button button-primary" type="button" data-accept-invite>${iconLabel("check", t("Accept"))}</button></div>
           <p class="field-error" role="alert" hidden></p>`;
  el.siteContent.innerHTML = `<div class="invite-page"><section class="invite-card">${card}</section></div>`;
}

async function acceptInvite(button) {
  const invite = state._invite;
  if (!invite || button.disabled) return;
  setButtonBusy(button, true, "Joining…", "Accept");
  try {
    const result = await fetchJson(apiUrl("/api/v1/invites/accept"), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ token: invite.token }) });
    // The token has done its job; it does not stay in the address bar or the history.
    window.history.replaceState({ inthub: "page" }, "", teamPath(result.team.slug));
    state._teams = null;
    await showTeam(result.team.slug, "members", { history: "none" });
    if (result.joined) setStatus(t("You joined {name}.", { name: result.team.name }));
    await refreshProjectList();
  } catch (error) {
    if (error.code === "INVITE_INVALID") {
      invite.preview = null;
      invite.invalid = true;
      invite.error = t("This invite link is no longer valid.");
      renderInvitePage();
      return;
    }
    setButtonBusy(button, false, "Joining…", "Accept");
    const message = el.siteContent.querySelector(".invite-card .field-error");
    if (message) { message.textContent = serverMessage(error); message.hidden = false; }
  }
}

/* Project settings: the Settings tab. */

function projectNameProblem(name) {
  if (!name) return t("Enter a project name.");
  if ([...name].length > PROJECT_NAME_MAX) return t("Use {count} characters or fewer.", { count: PROJECT_NAME_MAX });
  if (/[\\/\u0000-\u001f\u007f]/.test(name)) return t("Project names cannot contain slashes or control characters.");
  if (name === "." || name === "..") return t("Choose a name other than . or ..");
  return "";
}

// What the rename field shows: the owner's draft (kept across re-renders) and its problem, if any.
function renameState(project) {
  const draft = state._renameDraft?.projectId === project.id ? state._renameDraft : null;
  const value = draft ? draft.value : project.name;
  const name = value.trim();
  const problem = draft?.error || (name === project.name ? "" : projectNameProblem(name));
  return { value, problem, ready: !problem && name !== project.name };
}

function projectOwner() {
  return state.overview?.project?.owner || null;
}

function isTeamProject() {
  return projectOwner()?.type === "team";
}

function projectSettingsSection() {
  const section = state._settingsSection;
  return section === "danger" || (section === "members" && isTeamProject()) ? section : "general";
}

function renderProjectSettings() {
  const project = currentProject();
  if (!project) return;
  const section = projectSettingsSection();
  const link = (name) => projectPath(project.id, { tab: "settings", ...(name === "general" ? {} : { section: name }) });
  el.detailContent.innerHTML = settingsLayout({
    label: t("Project settings"),
    items: [
      { label: t("General"), icon: "sliders", href: link("general"), current: section === "general" },
      ...(isTeamProject() ? [{ label: t("Members"), icon: "users", href: link("members"), current: section === "members" }] : []),
      { label: t("Danger zone"), icon: "blocker", href: link("danger"), current: section === "danger" },
    ],
    pane: { general: projectGeneralPane, members: projectMembersPane, danger: projectDangerPane }[section](project),
  });
  if (section === "members" && state._projectTeam?.id !== projectOwner().id) loadProjectTeam();
  if (section === "danger" && state.config?.authRequired && !state._teams && !state._teamsError) loadTeams();
}

function projectGeneralPane(project) {
  const rename = renameState(project);
  const visibility = state.overview?.project?.visibility;
  return `
    ${settingsBlock("general", t("General"), `
      <form class="settings-form" data-rename-form novalidate>
        <label class="field-label" for="project-name">${esc(t("Project name"))}</label>
        <div class="field-row">
          <input class="text-field" id="project-name" name="project-name" type="text" value="${esc(rename.value)}" autocomplete="off" autocapitalize="off" spellcheck="false" aria-describedby="project-name-error project-name-note"${rename.problem ? ' aria-invalid="true"' : ""}>
          <button class="button button-secondary" type="submit" data-rename-submit${rename.ready ? "" : " disabled"}>${iconLabel("edit", t("Rename"))}</button>
        </div>
        <p class="field-error" id="project-name-error" role="alert"${rename.problem ? "" : " hidden"}>${esc(rename.problem)}</p>
        <p class="field-note" id="project-name-note">${tHtml("Clones on itt 7.3 or later follow the new name on their next push or pull. Older versions report {code} until they upgrade.", { code: "<code>REMOTE_CHANGED</code>" })}</p>
      </form>`)}
    ${state.config?.authRequired ? settingsBlock("visibility", t("Visibility"), settingsList(settingsRow({
      title: esc(visibility === "public" ? t("Public") : t("Private")),
      meta: esc(visibility === "public"
        ? t("Anyone on the internet can read this project. Only members can push.")
        : t("Only people with access to this project can read it.")),
      control: `<button class="button button-secondary" type="button" data-change-visibility="${visibility === "public" ? "private" : "public"}">${visibility === "public" ? iconLabel("lock", t("Make private")) : iconLabel("globe", t("Make public"))}</button>`,
    }))) : ""}
    ${settingsBlock("export", t("Export"), settingsList(settingsRow({
      title: esc(t("Download project data")),
      meta: esc(t("The current semantic snapshot and the revision list as JSON: everything itt pull can restore.")),
      control: `<button class="button button-secondary" type="button" data-export-project>${iconLabel("download", t("Download export"))}</button>`,
    })))}`;
}

async function loadProjectTeam() {
  const owner = projectOwner();
  if (!owner?.id) return;
  state._projectTeam = { id: owner.id, data: null, error: "" };
  const team = state._projectTeam;
  try {
    team.data = await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(owner.id)}`));
  } catch (error) {
    team.error = error.message;
  }
  if (state._projectTeam !== team || state.page !== "project" || state.activeTab !== "settings") return;
  const list = el.detailContent.querySelector?.("#project-team");
  if (list) list.innerHTML = projectTeamHtml();
  else renderView();
}

function projectTeamHtml() {
  const team = state._projectTeam?.id === projectOwner().id ? state._projectTeam : null;
  if (team?.error) return `<p class="inline-empty">${esc(team.error)}</p>`;
  return team?.data ? settingsList(team.data.members.map((member) => memberRow(member, false)).join("")) : viewLoadingHtml();
}

function projectMembersPane() {
  const owner = projectOwner();
  return settingsBlock("project-members", t("Members"), `<div class="settings-slot" id="project-team">${projectTeamHtml()}</div>`,
    tHtml("Everyone in {team} works on this project. Manage them on the team page.", { team: `<a href="${esc(teamPath(owner.slug))}" data-route>${esc(owner.name)}</a>` }));
}

function transferTargets() {
  const owner = projectOwner();
  const teams = (state._teams || []).filter((team) => team.role === "admin" && team.id !== owner?.id);
  return [
    ...teams.map((team) => ({ value: team.id, label: team.name })),
    ...(owner?.type === "team" ? [{ value: "account", label: t("My account") }] : []),
  ];
}

function transferControlHtml() {
  const targets = transferTargets();
  if (!state._teams && !state._teamsError) return `<span class="settings-role">${esc(t("Loading…"))}</span>`;
  if (!targets.length) return `<a class="settings-link" href="${SETTINGS_PATHS.teams}" data-route>${icon("plus")}${esc(t("Create a team"))}</a>`;
  return `${selectField({ id: "transfer-target", value: targets[0].value, options: targets, label: t("New owner"), className: "transfer-select" })}
    <button class="button button-danger" type="button" data-transfer-project>${iconLabel("transfer", t("Transfer"))}</button>`;
}

function renderTransferControl() {
  const control = el.detailContent.querySelector?.("#transfer-control");
  if (control) control.innerHTML = transferControlHtml();
  else renderView();
}

function projectDangerPane() {
  return settingsBlock("danger", t("Danger zone"), settingsList(`
    ${state.config?.authRequired ? settingsRow({
      title: esc(t("Transfer this project")),
      meta: esc(t("Moves it to a team you administer, or back to your account. Clones follow on their next push or pull.")),
      control: `<div class="transfer-control" id="transfer-control">${transferControlHtml()}</div>`,
    }) : ""}
    ${settingsRow({
      title: esc(t("Delete this project")),
      meta: esc(t("Removes the project and its semantic history from this hub. Local .intent data is not touched.")),
      control: `<button class="button button-danger" type="button" data-delete-project>${iconLabel("trash", t("Delete project"))}</button>`,
    })}`));
}

function updateRenameForm(form) {
  const project = currentProject();
  const input = form?.elements?.["project-name"];
  if (!project || !input) return;
  state._renameDraft = { projectId: project.id, value: input.value, error: "" };
  const rename = renameState(project);
  setFieldError(form, rename.problem);
  form.querySelector("[data-rename-submit]").disabled = !rename.ready;
}

function renameErrorMessage(error, name) {
  if (error.code === "NAME_TAKEN") return t("A project named {name} already exists.", { name });
  if (error.code === "INVALID_INPUT" && error.detail) return error.detail;
  return error.message;
}

async function renameProject(projectId, name) {
  const result = await fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/rename`), {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ name }),
  });
  const { id, name: newName, full_name: fullName } = result.project;
  // The URL carries the ID, so it stays; the picker, the title and the brief take the new name.
  state.projects = state.projects.map((project) => project.id === id ? { ...project, name: newName, full_name: fullName } : project);
  if (state.overview?.project && state._loadedProjectId === id) state.overview.project = { ...state.overview.project, name: newName, full_name: fullName };
  renderProjectSelector();
  return result.project;
}

async function renameCurrentProject(form) {
  const project = currentProject();
  const input = form.elements["project-name"];
  const button = form.querySelector("[data-rename-submit]");
  if (!project || !input || !button || button.disabled) return;
  const name = input.value.trim();
  if (projectNameProblem(name) || name === project.name) {
    updateRenameForm(form);
    return;
  }
  setButtonBusy(button, true, "Renaming…", "Rename");
  try {
    const renamed = await renameProject(project.id, name);
    state._renameDraft = null;
    if (state.activeTab === "settings" && state.page === "project") renderView();
    el.detailContent.querySelector?.("#project-name")?.focus();
    setStatus(t("Renamed to {name}.", { name: renamed.name }));
  } catch (error) {
    state._renameDraft = { projectId: project.id, value: input.value, error: renameErrorMessage(error, name) };
    setButtonBusy(button, false, "Renaming…", "Rename");
    setFieldError(form, state._renameDraft.error);
    button.disabled = true;
    input.focus();
  }
}

function confirmVisibility(visibility, trigger = null) {
  const project = currentProject();
  if (!project) return;
  const going = visibility === "public";
  // The server stops on a likely credential once; confirming after that warning is the decision to publish anyway.
  let acknowledged = false;
  openConfirm({
    title: () => (going ? t("Make {name} public?", { name: project.name }) : t("Make {name} private?", { name: project.name })),
    body: () => (going
      ? t("Anyone on the internet will be able to read all its Intents, Snaps, Decisions and history. Author emails stay hidden from visitors. People who already read it may keep it.")
      : t("Only people with access to this project will be able to read it. Visitors lose access at once.")),
    ...(going ? {
      label: () => tHtml("Type {name} to confirm.", { name: `<strong class="confirm-name">${esc(project.name)}</strong>` }),
      expect: project.name,
    } : { tone: "neutral" }),
    action: going ? "Make public" : "Make private",
    icon: going ? "globe" : "lock",
    busy: "Saving…",
    run: (typed) => changeVisibility(project.id, visibility, typed, acknowledged),
    message: (error) => {
      if (error.code !== "POSSIBLE_SECRETS") return serverMessage(error);
      acknowledged = true;
      const objects = (error.details?.objects || []).map((object) => `${object.id} (${object.kinds.map((kind) => t(kind)).join(", ")})`);
      return t("These may contain credentials: {list}. Check them first. Confirming again publishes anyway.", { list: objects.join(", ") });
    },
    returnFocus: trigger,
  });
}

async function changeVisibility(projectId, visibility, confirm, acknowledgeSecrets = false) {
  await fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/visibility`), {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ visibility, confirm, ...(acknowledgeSecrets ? { acknowledge_secrets: true } : {}) }),
  });
  state.projects = state.projects.map((project) => project.id === projectId ? { ...project, visibility } : project);
  if (state.overview?.project) state.overview.project = { ...state.overview.project, visibility };
  if (state.activeTab === "settings") renderView();
  setStatus(visibility === "public" ? t("This project is now public.") : t("This project is now private."));
}

function transferErrorMessage(error) {
  if (error.code === "NAME_TAKEN") return t("A project with this name already exists there.");
  if (error.code === "TEAM_NOT_FOUND") return t("Choose a team you administer.");
  return serverMessage(error);
}

function confirmTransfer(trigger = null) {
  const project = currentProject();
  const select = el.detailContent.querySelector?.(".transfer-select input");
  const target = transferTargets().find((entry) => entry.value === select?.value);
  if (!project || !target) return;
  openConfirm({
    title: () => t("Transfer {name} to {target}?", { name: project.name, target: target.label }),
    body: () => t("Who can read, push and manage it changes with the owner. Its ID stays, so clones follow on their next push or pull."),
    label: () => tHtml("Type {name} to confirm.", { name: `<strong class="confirm-name">${esc(project.name)}</strong>` }),
    expect: project.name,
    action: "Transfer project",
    icon: "transfer",
    busy: "Transferring…",
    run: (typed) => transferProject(project.id, target, typed),
    message: transferErrorMessage,
    returnFocus: trigger,
  });
}

async function transferProject(projectId, target, confirm) {
  await fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/transfer`), {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ team_id: target.value === "account" ? null : target.value, confirm }),
  });
  setStatus(t("Transferred to {target}.", { target: target.label }));
  state._teams = null;
  state._projectTeam = null;
  await refreshProjectList();
  // Not awaited: the dialog closes as soon as the project has moved, while it reloads under its new owner.
  loadProject(projectId, { history: "replace" }).catch((error) => setStatus(error.message, true));
}

function exportFileName(name) {
  // Keep the name readable (spaces, CJK); drop only what file systems refuse.
  const safe = String(name || "").replace(/[\\/:*?"<>|\u0000-\u001f\u007f]/g, "-").replace(/^\.+/, "").trim();
  return `${safe || "project"}.inthub-export.json`;
}

function downloadFile(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function exportCurrentProject(button) {
  const project = currentProject();
  if (!project || button.disabled) return;
  setButtonBusy(button, true, "Preparing export…", "Download export");
  try {
    const data = await fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(project.id)}/export`));
    downloadFile(exportFileName(data.project?.name || project.name), `${JSON.stringify(data, null, 2)}\n`, "application/json");
    setStatus(t("Export downloaded."));
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setButtonBusy(button, false, "Preparing export…", "Download export");
    button.innerHTML = `${icon("download")}<span>${esc(t("Download export"))}</span>`;
  }
}

function confirmDeleteProject(trigger = null) {
  const project = currentProject();
  if (!project) return;
  openConfirm({
    title: () => t("Delete {name}?", { name: project.name }),
    body: () => t("This removes the project and its semantic history from this hub. Local .intent data is not touched. This cannot be undone."),
    label: () => tHtml("Type {name} to confirm.", { name: `<strong class="confirm-name">${esc(project.name)}</strong>` }),
    expect: project.name,
    action: "Delete project",
    icon: "trash",
    busy: "Deleting…",
    run: (typed) => deleteProject(project.id, typed),
    returnFocus: trigger,
  });
}

async function deleteProject(projectId, confirm) {
  await fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/delete`), {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ confirm }),
  });
  const name = state.projects.find((project) => project.id === projectId)?.name || "";
  state.projects = state.projects.filter((project) => project.id !== projectId);
  state._renameDraft = null;
  setStatus(t("Deleted {name}.", { name }));
  // Go on to another project, to the list of them, or to the empty state when none is left.
  closeDrawer({ history: "none" });
  forgetProject();
  state.activeTab = "overview";
  setActiveTabUI();
  // Not awaited: the dialog closes as soon as the project is gone, while the next one loads.
  openDefault().catch((error) => setStatus(error.message, true));
}

/* One dialog for confirmations. */

function openConfirm(spec) {
  state._confirm = spec;
  state._confirmBusy = false;
  el.confirmInput.value = "";
  el.confirmField.hidden = spec.expect === undefined;
  el.confirmError.textContent = "";
  el.confirmError.hidden = true;
  el.confirmOk.disabled = spec.expect !== undefined;
  el.confirmOk.classList.toggle("button-danger", spec.tone !== "neutral");
  el.confirmOk.classList.toggle("button-primary", spec.tone === "neutral");
  el.confirmCancel.disabled = false;
  localizeConfirm();
  el.confirmDialog.showModal();
  (spec.expect === undefined ? el.confirmCancel : el.confirmInput).focus();
}

function localizeConfirm() {
  const spec = state._confirm;
  if (!spec) return;
  el.confirmTitle.textContent = spec.title();
  el.confirmBody.textContent = spec.body();
  el.confirmLabel.innerHTML = spec.label ? spec.label() : "";
  el.confirmOk.innerHTML = iconLabel(spec.icon, t(state._confirmBusy ? spec.busy : spec.action));
}

async function runConfirm() {
  const spec = state._confirm;
  if (!spec || state._confirmBusy || el.confirmOk.disabled) return;
  const typed = el.confirmInput.value;
  if (spec.expect !== undefined && typed !== spec.expect) return;
  state._confirmBusy = true;
  setButtonBusy(el.confirmOk, true, spec.busy, spec.action);
  el.confirmCancel.disabled = true;
  el.confirmError.hidden = true;
  try {
    await spec.run(typed);
    state._confirmBusy = false;
    if (el.confirmDialog.open) el.confirmDialog.close();
  } catch (error) {
    state._confirmBusy = false;
    el.confirmError.textContent = error.code === "CONFIRMATION_MISMATCH" ? t("Type the name exactly as shown.") : (spec.message || ((reason) => reason.message))(error);
    el.confirmError.hidden = false;
  } finally {
    state._confirmBusy = false;
    setButtonBusy(el.confirmOk, false, spec.busy, spec.action);
    el.confirmCancel.disabled = false;
    if (spec.expect !== undefined) el.confirmOk.disabled = el.confirmInput.value !== spec.expect;
  }
}

/* Device: approving `itt auth login`. The code is typed, never carried in a link, so nobody can send one to approve. */

function showDevice() {
  closeOverlays();
  setPage("device");
  state._device = { step: "code", code: "", name: "", days: 0 };
  writeRoute("none");
  renderDevicePage();
  settlePage(el.siteContent, true);
  el.siteContent.querySelector?.("#device-code")?.focus();
}

function renderDevicePage() {
  const device = state._device;
  if (state.page !== "device" || !device) return;
  const home = `<a class="button button-secondary" href="/" data-route>${iconLabel("arrow", t("Go to IntHub"))}</a>`;
  const card = {
    code: () => `
      <h1>${esc(t("Connect a device"))}</h1>
      <p>${esc(t("Enter the code shown in your terminal."))}</p>
      <form class="device-form" data-device-form novalidate>
        <input class="text-field device-code" id="device-code" name="device-code" type="text" value="${esc(device.code)}" maxlength="9" placeholder="XXXX-XXXX" autocomplete="off" autocapitalize="characters" spellcheck="false" aria-label="${esc(t("Device code"))}" aria-describedby="device-error">
        <p class="field-error" id="device-error" role="alert" hidden></p>
        <button class="button button-primary" type="submit">${iconLabel("arrow", t("Continue"))}</button>
      </form>`,
    confirm: () => `
      <h1>${esc(t("Authorize {name}?", { name: device.name }))}</h1>
      <p>${esc(t("It will be able to read and push your projects for {count} days. Only continue if you ran itt auth login yourself.", { count: device.days }))}</p>
      <div class="invite-actions">
        <button class="button button-secondary" type="button" data-device-deny>${iconLabel("close", t("Cancel"))}</button>
        <button class="button button-primary" type="button" data-device-approve>${iconLabel("check", t("Authorize"))}</button>
      </div>
      <p class="field-error" role="alert" hidden></p>`,
    approved: () => `
      <h1>${esc(t("Device connected"))}</h1>
      <p>${esc(t("Return to the terminal. Its token is listed under Settings, where you can revoke it."))}</p>
      <div class="invite-actions">${home}</div>`,
    denied: () => `
      <h1>${esc(t("Not authorized"))}</h1>
      <p>${esc(t("No access was granted."))}</p>
      <div class="invite-actions">${home}</div>`,
  }[device.step]();
  el.siteContent.innerHTML = `<div class="invite-page"><section class="invite-card">${card}</section></div>`;
}

function formatDeviceCode(value) {
  const letters = value.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 8);
  return letters.length > 4 ? `${letters.slice(0, 4)}-${letters.slice(4)}` : letters;
}

function deviceErrorMessage(error) {
  return error.code === "DEVICE_CODE_INVALID" ? t("This code is not valid or has expired. Run itt auth login again.") : serverMessage(error);
}

async function lookupDevice(form) {
  const device = state._device;
  const button = form.querySelector("[type=submit]");
  const code = form.elements["device-code"].value;
  if (!device || !button || button.disabled) return;
  if (code.length !== 9) {
    setFieldError(form, t("Enter the 8-letter code."));
    return;
  }
  setButtonBusy(button, true, "Checking…", "Continue");
  try {
    const result = await fetchJson(apiUrl("/api/v1/auth/device/lookup"), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ code }) });
    if (state._device !== device) return;
    Object.assign(device, { step: "confirm", code, name: result.name, days: result.token_days });
    renderDevicePage();
  } catch (error) {
    setFieldError(form, deviceErrorMessage(error));
    setButtonBusy(button, false, "Checking…", "Continue");
  }
}

async function decideDevice(button, approve) {
  const device = state._device;
  if (!device || button.disabled) return;
  const message = el.siteContent.querySelector(".invite-card .field-error");
  setButtonBusy(button, true, approve ? "Authorizing…" : "Cancelling…", approve ? "Authorize" : "Cancel");
  try {
    await fetchJson(apiUrl("/api/v1/auth/device/decide"), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ code: device.code, approve }) });
    if (state._device !== device) return;
    device.step = approve ? "approved" : "denied";
    renderDevicePage();
  } catch (error) {
    setButtonBusy(button, false, approve ? "Authorizing…" : "Cancelling…", approve ? "Authorize" : "Cancel");
    if (message) { message.textContent = deviceErrorMessage(error); message.hidden = false; }
  }
}

/* ---- Project selector ---- */

function renderProjectSelector() {
  updateDocumentTitle();
  el.projectPicker.classList.toggle("is-static", state.visitor);
  if (!state.projects.length) {
    el.projectPickerTrigger.disabled = true;
    el.projectPickerLabel.textContent = t("No projects yet");
    el.projectPickerDropdown.innerHTML = "";
    return;
  }
  // A visitor reads the one project the link named; there is nothing to pick from.
  el.projectPickerTrigger.disabled = Boolean(state._projectBusy) || state.visitor;
  const onHome = state.page === "home";
  const selected = onHome ? null : state.currentProjectId;
  const home = hasHomePage();
  el.projectPickerLabel.textContent = onHome || (home && !currentProject())
    ? t("All projects")
    : (currentProject() || state.projects[0]).full_name;
  const allProjects = home
    ? `<a role="option" aria-selected="${onHome}" class="project-picker-option project-picker-home${onHome ? " is-selected" : ""}" href="/" data-route>
        ${icon("grid")}<span class="project-picker-option-name">${esc(t("All projects"))}</span>
      </a>`
    : "";
  el.projectPickerDropdown.innerHTML = allProjects + state.projects
    .map(
      (p) =>
        `<button type="button" role="option" aria-selected="${p.id === selected ? "true" : "false"}" class="project-picker-option${p.id === selected ? " is-selected" : ""}" data-id="${esc(p.id)}">
          <span class="project-picker-option-name">${esc(p.full_name)}</span>
          <span class="project-picker-option-repo">${esc(p.last_synced_at ? t("Synced {time}", {time: relativeDate(p.last_synced_at)}) : t("Shared history"))}</span>
        </button>`,
    )
    .join("");
}

function toggleProjectPicker(open) {
  const isOpen = open ?? !el.projectPickerDropdown.classList.contains("is-open");
  if (isOpen) closeHeaderMenus();
  el.projectPickerDropdown.classList.toggle("is-open", isOpen);
  el.projectPickerTrigger.classList.toggle("is-open", isOpen);
  el.projectPickerTrigger.setAttribute("aria-expanded", String(isOpen));
}

function updateSyncChip() {
  const ws = [...historySources(state.overview)]
    .sort((left, right) => String(right.last_synced_at || "").localeCompare(String(left.last_synced_at || "")))[0];
  el.syncChip.textContent = ws
    ? t("Synced {time}", {time: relativeDate(ws.last_synced_at)})
    : state.currentProjectId ? t("Not synced") : t("Waiting for first project");
  if (ws) el.syncChip.dataset.tip = fmtDate(ws.last_synced_at);
  else delete el.syncChip.dataset.tip;
  el.syncIndicator.classList.toggle("is-unsynced", !ws);
}

/* ---- Project loading ---- */

async function loadProject(projectId, { detail = null, history = "replace" } = {}) {
  const request = beginViewRequest("project");
  state._projectPending = request;
  const previous = {
    projectId: state._loadedProjectId || state.currentProjectId,
    overview: state.overview, handoff: state.handoff,
    pageState: state._pageState, timeline: state._timeline, history: state._history, flow: state._flow,
    searchResults: state._searchResults, detailCache: state._detailCache, snapCache: state._snapCache,
  };
  const switching = Boolean(state._loadedProjectId && state._loadedProjectId !== projectId);
  beginViewRequest("search");
  state._searchBusy = false;
  if (switching) {
    closeDrawer({ history: "none" });
    state.overview = null;
    state.handoff = null;
    state._searchResults = null;
    state._timeline = null;
    state._history = null;
    state._flow = null;
    state._pageState = {};
    state._detailCache = new Map();
    state._snapCache = new Map();
  }
  state.currentProjectId = projectId;
  renderProjectSelector();
  setViewBusy("detail", true);
  if (!state.overview) el.detailContent.innerHTML = pageSkeletonHtml();

  let overview;
  let handoff;
  try {
    [overview, handoff] = await Promise.all([
      fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/overview`)),
      fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/handoff`)),
    ]);
  } catch (error) {
    if (!ownsViewRequest("project", request)) return;
    state._projectPending = null;
    if (previous.overview) {
      state.currentProjectId = previous.projectId;
      state.overview = previous.overview;
      state.handoff = previous.handoff;
      state._pageState = previous.pageState;
      state._timeline = previous.timeline;
      state._history = previous.history;
      state._flow = previous.flow;
      state._searchResults = previous.searchResults;
      state._detailCache = previous.detailCache;
      state._snapCache = previous.snapCache;
      renderProjectSelector();
      renderView();
    } else {
      el.detailContent.innerHTML = emptyState({
        iconName: "blocker",
        title: t("Could not load this project."),
        body: error.message,
        extra: `<button type="button" class="secondary-btn" data-retry-project="${esc(projectId)}">${iconLabel("refresh", t("Retry"))}</button>`,
      });
    }
    setViewBusy("detail", false);
    throw error;
  }
  if (!ownsViewRequest("project", request)) return;
  state._projectPending = null;
  state._loadedProjectId = projectId;
  state.overview = overview;
  state.handoff = handoff;
  state._detailCache = new Map();
  state._snapFailed = new Set();
  // The timeline pages again from the new revision, keeping the reader's Intent filter.
  const filters = state._timeline?.projectId === projectId ? state._timeline : routedTimelineFilters(projectId);
  resetTimeline(filters.intentId, filters.author);
  state._history = null;
  keepProjectListed(overview);
  syncSettingsTab();
  // The URL can name the tab; only the people who manage this project get it.
  if (state.activeTab === "settings" && !canManageProject()) {
    state.activeTab = "overview";
    setActiveTabUI();
  }
  renderProjectSelector();

  el.intentCount.textContent = (overview.active_intents?.length || 0) + (overview.other_intents?.length || 0) || "";
  el.decisionCount.textContent = (overview.active_decisions?.length || 0) + (overview.deprecated_decisions?.length || 0) || "";
  el.snapCount.textContent = (overview.total_snaps ?? overview.recent_snaps?.length ?? 0) || "";
  updateSyncChip();
  revealActiveTab();

  if (!hasHistory()) {
    renderEmptyProject();
    writeRoute(history);
    setViewBusy("detail", false);
    return;
  }

  renderView();
  writeRoute(history);
  setViewBusy("detail", false);
  if (detail) {
    try {
      await openDetail(detail.type, detail.remoteId, { history: "replace" });
    } catch (error) { setStatus(error.message, true); }
  }
}

// A project reached by link that the list does not carry: public, or not readable at all.
function linkedProject(overview) {
  return { ...overview.project, last_synced_at: overview.history?.last_synced_at || null, transient: true };
}

// A project the viewer does not belong to stays in the picker for as long as it is open.
function keepProjectListed(overview) {
  state.projects = state.projects.filter((project) => !project.transient || project.id === overview.project.id);
  if (!state.projects.some((project) => project.id === overview.project.id)) state.projects.push(linkedProject(overview));
}

// gate: false because a private project answers a visitor with 401, which is an answer here.
async function fetchLinkedProject(projectId) {
  try {
    return linkedProject(await fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/overview`), { gate: false }));
  } catch (error) {
    if (error.status === 401 || error.status === 404) return null;
    throw error;
  }
}

function routedDetail(route, projectId) {
  return route.detail && DETAIL_PATHS[route.detailType] && projectIdFromRemoteId(route.detail) === projectId
    ? { type: route.detailType, remoteId: route.detail }
    : null;
}

// Account, team and invite views exist only where there are accounts.
function isDialogRoute(route) {
  return Boolean(DIALOG_PATHS[route.page] && state.config?.authRequired);
}

function isSiteRoute(route) {
  return ["team", "invite", "device"].includes(route.page) && Boolean(state.config?.authRequired);
}

// The project `/` opens: the hub's default, else the only one there is.
function defaultProjectId() {
  const listed = listedProjects();
  if (listed.some((project) => project.id === state.config?.defaultProjectId)) return state.config.defaultProjectId;
  return listed.length === 1 ? listed[0].id : null;
}

function forgetProject() {
  beginViewRequest("project");
  state.currentProjectId = null;
  state._loadedProjectId = null;
  state.overview = null;
  state.handoff = null;
  el.intentCount.textContent = "";
  el.decisionCount.textContent = "";
  el.snapCount.textContent = "";
  syncSettingsTab();
  updateSyncChip();
}

// Show `/` for someone with no project named: the project it opens, the list of them, or the setup guide.
async function openDefault({ history = "replace" } = {}) {
  if (hasHomePage()) {
    await showHome({ history });
    return;
  }
  leaveSitePage();
  const projectId = defaultProjectId();
  if (projectId) {
    await loadProject(projectId, { history });
    return;
  }
  forgetProject();
  renderProjectSelector();
  renderSetupGuide("unlinked");
  writeRoute(history);
}

async function loadProjects(route = readRoute()) {
  const request = beginViewRequest("projects");
  const result = await fetchJson(apiUrl("/api/v1/projects"));
  if (!ownsViewRequest("projects", request)) return;
  state.projects = result.projects;
  if (state.currentProjectId && !currentProject()) forgetProject();
  if (isSiteRoute(route)) {
    renderProjectSelector();
    return;
  }
  let projectId = state.projects.some((project) => project.id === route.project) ? route.project : null;
  if (route.project && !projectId) {
    const linked = await fetchLinkedProject(route.project);
    if (!ownsViewRequest("projects", request)) return;
    if (linked) {
      state.projects.push(linked);
      projectId = linked.id;
    } else setStatus(t("This project does not exist, or you cannot see it."), true);
  }
  projectId ||= defaultProjectId();
  if (!projectId) {
    await openDefault();
    return;
  }
  state.currentProjectId = projectId;
  renderProjectSelector();
  await loadProject(projectId, { detail: routedDetail(route, projectId) });
}

// Without a session a public project still opens, read-only. False when the link is not one.
async function openAsVisitor(route) {
  const project = await fetchLinkedProject(route.project);
  if (!project) return false;
  state.visitor = true;
  state.projects = [project];
  state.currentProjectId = project.id;
  hideAuthGate();
  await loadProject(project.id, { detail: routedDetail(route, project.id) });
  return true;
}

// Names, owners and access changed on another page: the picker follows, and an open project reloads on return.
async function refreshProjectList() {
  const result = await fetchJson(apiUrl("/api/v1/projects"));
  const listed = new Set(result.projects.map((project) => project.id));
  state.projects = [...result.projects, ...state.projects.filter((project) => project.transient && !listed.has(project.id))];
  state._home = null;
  if (state.currentProjectId && !currentProject()) forgetProject();
  else if (state.page !== "project") state._loadedProjectId = null;
  renderProjectSelector();
}

/* ---- Search palette ---- */

function openSearch(query = null) {
  if (el.shell.inert && !sheetIsOpen()) return;
  if (sheetIsOpen()) closeDrawer();
  closeHeaderMenus();
  toggleProjectPicker(false);
  if (!el.searchDialog.open) {
    state._searchReturnFocus = document.activeElement;
    el.searchDialog.showModal();
  }
  if (query !== null) el.searchInput.value = query;
  el.searchInput.focus();
  el.searchInput.select?.();
  if (el.searchInput.value.trim()) runSearch(el.searchInput.value.trim());
  else renderSearchSuggestions();
}

function closeSearch() {
  if (el.searchDialog.open) el.searchDialog.close();
}

function searchOptions() {
  return [...el.searchResults.querySelectorAll("[role=option]")];
}

function setSearchStatus(message = "", { visible = true, html = "", note = false } = {}) {
  el.searchStatus.innerHTML = html || esc(message);
  el.searchStatus.classList.toggle("visually-hidden", !visible);
  el.searchStatus.classList.toggle("is-note", note);
}

// The server returns at most 50 matches; say so instead of implying that is everything.
function searchSummary(result) {
  const shown = (result?.matches || []).length;
  const total = Number(result?.total) || shown;
  if (result?.truncated && total > shown) {
    return { text: t("Showing {shown} of {total} — refine the search", {shown, total}), visible: true };
  }
  return { text: plural(shown, "{count} result", "{count} results"), visible: false };
}

function searchGroup(key, label, optionsHtml) {
  return `<div role="group" aria-labelledby="search-group-${key}"><div class="search-group-label" id="search-group-${key}" role="presentation">${esc(label)}</div>${optionsHtml}</div>`;
}

function setActiveSearchOption(index) {
  const options = searchOptions();
  el.searchInput.setAttribute("aria-expanded", String(options.length > 0));
  if (!options.length) {
    el.searchInput.removeAttribute("aria-activedescendant");
    return;
  }
  const next = (index + options.length) % options.length;
  options.forEach((option, position) => {
    option.classList.toggle("is-active", position === next);
    option.setAttribute("aria-selected", String(position === next));
  });
  el.searchInput.setAttribute("aria-activedescendant", options[next].id);
  options[next].scrollIntoView?.({ block: "nearest" });
  state._searchActive = next;
}

async function activateSearchOption(option) {
  if (!option) return;
  closeSearch();
  if (option.dataset.tabJump) {
    switchTab(option.dataset.tabJump);
    return;
  }
  try {
    await openDetail(option.dataset.detailType, option.dataset.remoteId);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function renderSearchSuggestions() {
  const tabs = [
    ["overview", t("Overview"), "overview"],
    ["intents", t("Intents"), "intent"],
    ["flow", t("Flow"), "flow"],
    ["snaps", t("Timeline"), "timeline"],
    ["history", t("History"), "history"],
    ["decisions", t("Decisions"), "decision"],
    ...(canManageProject() ? [["settings", t("Settings"), "settings"]] : []),
  ];
  const active = state.handoff?.intents || [];
  let index = 0;
  const option = (attributes, iconName, title, meta = "", side = "") => `
    <div class="search-result" role="option" id="search-option-${index++}" aria-selected="false" ${attributes}>
      ${icon(iconName)}
      <span class="search-result-title">${title}</span>
      ${meta ? `<span class="search-result-meta">${esc(meta)}</span>` : ""}
      ${side ? `<span class="search-result-side">${esc(side)}</span>` : ""}
    </div>`;
  const synced = Boolean(state.overview) && hasHistory();
  el.searchResults.innerHTML = `
    ${active.length ? searchGroup("active", t("Active work"), active.map((intent) => option(`data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}"`, "intent", esc(intent.what), parseCheckpoint(intent.latest_snap).next ? `${t("Next")} · ${truncate(parseCheckpoint(intent.latest_snap).next, 90)}` : "", intent.id)).join("")) : ""}
    ${synced ? searchGroup("goto", t("Go to"), tabs.map(([tab, label, iconName]) => option(`data-tab-jump="${tab}"`, iconName, esc(label))).join("")) : ""}`;
  setSearchStatus(synced ? "" : t("Link a project to search its history."), { visible: !synced });
  setActiveSearchOption(0);
}

function renderSearchResults(result) {
  state._searchResults = result;
  if (!el.searchDialog.open && !state._localizing) return;
  const matches = result.matches || [];
  const query = result.query || state.searchQuery;
  if (!matches.length) {
    el.searchResults.innerHTML = "";
    setSearchStatus(t("No matches found."));
    setActiveSearchOption(0);
    return;
  }
  const groups = [
    ["intent", t("Intents")],
    ["snap", t("Checkpoints")],
    ["decision", t("Decisions")],
  ];
  let index = 0;
  el.searchResults.innerHTML = groups
    .map(([type, label]) => {
      const items = matches.filter((m) => m.object_type === type);
      if (!items.length) return "";
      return searchGroup(type, label, items.map((m) => {
        const title = type === "snap" ? conciseSnapTitle(m) : m.what || m.title || m.id;
        const meta = type === "snap"
          ? intentForSnap(m)?.what || m.intent_id || ""
          : `${type === "decision" ? decisionStatusLabel(m.status) : intentStatusLabel(m.status)}${m.why ? ` · ${truncate(m.why, 90)}` : ""}`;
        return `
          <div class="search-result" role="option" id="search-option-${index++}" aria-selected="false" data-detail-type="${esc(m.object_type)}" data-remote-id="${esc(m.remote_id)}">
            ${icon(type)}
            <span class="search-result-title">${highlight(title, query)}</span>
            <span class="search-result-meta">${esc(meta)}</span>
            <span class="search-result-side">${esc(m.id)}</span>
          </div>`;
      }).join(""));
    })
    .join("");
  const summary = searchSummary(result);
  setSearchStatus(summary.text, { visible: summary.visible, note: summary.visible });
  setActiveSearchOption(0);
}

async function submitSearch() {
  const query = el.searchInput.value.trim();
  window.clearTimeout(state._searchTimer);
  const fresh = !query || (state._searchResults && state._searchResultQuery === query
    && state._searchResultProject === state.currentProjectId && !state._searchBusy);
  if (!fresh) {
    await runSearch(query);
    if (el.searchInput.value.trim() !== query) return;
  }
  activateSearchOption(el.searchResults.querySelector("[role=option].is-active"));
}

function scheduleSearch(delay = 180) {
  window.clearTimeout(state._searchTimer);
  state._searchTimer = window.setTimeout(() => runSearch(el.searchInput.value.trim()), delay);
}

async function runSearch(query, button = null) {
  state.searchQuery = query;
  const container = el.searchResults;
  const projectId = state.currentProjectId;
  const request = beginViewRequest("search");
  if (!query || !projectId) {
    state._searchBusy = false;
    state._searchResults = null;
    renderSearchSuggestions();
    return;
  }
  state._searchBusy = true;
  if (button) setButtonBusy(button, true, "Searching…", "Retry");
  container.setAttribute("aria-busy", "true");
  if (!container.querySelector("[data-detail-type]")) {
    container.innerHTML = "";
    setSearchStatus(t("Searching…"));
    setActiveSearchOption(0);
  }
  const current = () => ownsViewRequest("search", request) && state.currentProjectId === projectId;
  try {
    const result = await fetchJson(apiUrl(`/api/v1/search?project_id=${encodeURIComponent(projectId)}&q=${encodeURIComponent(query)}`));
    if (!current()) return;
    state._searchResultProject = projectId;
    state._searchResultQuery = query;
    renderSearchResults({ ...result, query });
  } catch (error) {
    if (!current()) return;
    state._searchResults = null;
    container.innerHTML = "";
    setActiveSearchOption(0);
    setSearchStatus("", { html: `<p>${esc(error.message)}</p><button class="secondary-btn" type="button" data-retry-search>${iconLabel("refresh", t("Retry"))}</button>` });
  } finally {
    if (current()) {
      state._searchBusy = false;
      container.setAttribute("aria-busy", "false");
      if (button) setButtonBusy(button, false, "Searching…", "Retry");
    }
  }
}

/* ---- Events ---- */

function setButtonBusy(button, busy, loadingCopy = "", idleCopy = "") {
  if (button.matches(".card, .list-row, .queue-item, .intent-entry, .decision-constraint, .timeline-entry, .relation-item, .detail-link, .decision-row, .brief-open, .link-button, .search-result, .tab, .project-picker-trigger")) return;
  button.disabled = busy;
  button.classList.toggle("action-busy", busy);
  button.setAttribute("aria-busy", String(busy));
  button.dataset.loadingCopy = loadingCopy;
  button.dataset.idleCopy = idleCopy;
  if (loadingCopy) setButtonLabel(button, t(busy ? loadingCopy : idleCopy));
}

function setProjectPickerBusy(busy) {
  el.projectPickerTrigger.disabled = busy;
  el.projectPickerTrigger.setAttribute("aria-busy", String(busy));
}

function headerMenus() {
  const triggers = [...document.querySelectorAll("[data-preferences-trigger]"), ...document.querySelectorAll("[data-resources-trigger]")];
  const menus = triggers.map(trigger => ({
    trigger, panel: document.getElementById(trigger.getAttribute("aria-controls")),
  })).filter(menu => menu.panel);
  return [...menus, { trigger: el.accountMenuTrigger, panel: el.accountActions }];
}

function headerMenuControls(menu) {
  return [...menu.panel.querySelectorAll("button, a[href]")].filter(node => !node.disabled && !node.hidden && node.getClientRects().length);
}

function closeHeaderMenu(menu, restoreFocus = false) {
  const wasOpen = menu.panel.classList.contains("is-open");
  menu.panel.classList.remove("is-open");
  menu.panel.inert = true;
  menu.trigger.setAttribute("aria-expanded", "false");
  if (wasOpen && restoreFocus) menu.trigger.focus();
}

function closeHeaderMenus(restoreFocus = false) {
  for (const menu of headerMenus()) closeHeaderMenu(menu, restoreFocus);
}

function toggleHeaderMenu(trigger, { focus = null } = {}) {
  const menu = headerMenus().find(entry => entry.trigger === trigger);
  if (!menu || trigger.disabled) return;
  const opening = !menu.panel.classList.contains("is-open");
  closeHeaderMenus();
  toggleProjectPicker(false);
  if (!opening) return;
  menu.panel.inert = false;
  menu.panel.classList.add("is-open");
  trigger.setAttribute("aria-expanded", "true");
  if (focus) {
    const controls = headerMenuControls(menu);
    (focus === "last" ? controls.at(-1) : controls[0])?.focus();
  }
}

function localizeWorkspace() {
  const pageScroll = window.scrollY;
  const sheetScroll = el.drawerContent.scrollTop;
  const expanded = [...document.querySelectorAll("details[open]")].map(node => node.dataset.archive || node.className);
  state._localizing = true;
  try {
    for (const button of document.querySelectorAll("[data-idle-copy]")) if (button.dataset.idleCopy) setButtonLabel(button, t(button.disabled ? button.dataset.loadingCopy : button.dataset.idleCopy));
    localizeViewLoadingCopy();
    const projectPending = Boolean(state._projectPending && ownsViewRequest("project", state._projectPending));
    el.detailContent.querySelector(".page-skeleton")?.setAttribute("aria-label", t("Loading continuation brief"));
    const pagePending = projectPending || el.detailPane.getAttribute("aria-busy") === "true";
    if (!projectPending) renderProjectSelector();
    if (!pagePending) {
      if (hasHistory()) renderView();
      else if (state.authenticated || state.visitor) renderEmptyProject();
    }
    if (state.page !== "project") renderSitePage();
    if (el.confirmDialog.open) localizeConfirm();
    updateDocumentTitle();
    if (sheetIsOpen()) {
      if (state._drawerPayload) el.drawerContent.innerHTML = buildDetailHtml(state._drawerPayload.type, state._drawerPayload.payload);
      renderSheetHeader(state._drawerPayload?.payload);
    }
    if (el.searchDialog.open) {
      if (state._searchResults) renderSearchResults(state._searchResults);
      else if (!el.searchInput.value.trim()) renderSearchSuggestions();
    }
    for (const node of document.querySelectorAll("details")) if (expanded.includes(node.dataset.archive || node.className)) node.open = true;
    window.scrollTo?.(0, pageScroll);
    el.drawerContent.scrollTop = sheetScroll;
    el.aboutVersion.textContent = t(state.config?.productVersion || "Unavailable");
    el.authError.textContent = t(state._authMessage || "");
    if (state._statusMessage && el.statusLine.classList.contains("is-visible")) el.statusLine.textContent = t(state._statusMessage);
    if (state.config) updateSyncChip();
    setTenonLoginLoading(el.tenonLogin.querySelector(".is-loading")?.dataset.loginMethod);
  } finally { state._localizing = false; }
}

function sheetFocusables() {
  return [...el.drawer.querySelectorAll("button, a[href], input, summary, [tabindex]")].filter(node => !node.disabled && !node.hidden && node.getAttribute("tabindex") !== "-1" && node.getClientRects().length);
}

async function applyRoute(route) {
  if (el.shell.inert && !sheetIsOpen()) return;
  if (isDialogRoute(route)) {
    if (state.visitor) showAuthGate();
    else openSettingsDialog(route.page, route.pane, { history: "none" });
    return;
  }
  closeSettingsDialog({ history: "none" });
  if (isSiteRoute(route)) {
    if (state.visitor) showAuthGate();
    else if (route.page === "team") await showTeam(route.team, route.pane);
    else if (route.page === "device") showDevice();
    else await showInvite(route.token);
    return;
  }
  if (!route.project) {
    if (hasHomePage() || !state.currentProjectId) {
      try { await openDefault({ history: "none" }); }
      catch (error) { setStatus(error.message, true); }
      return;
    }
  }
  leaveSitePage();
  const projectId = route.project || state.currentProjectId;
  if (projectId !== state.currentProjectId || projectId !== state._loadedProjectId) {
    state.activeTab = route.tab;
    state._settingsSection = route.section;
    setActiveTabUI();
    try { await loadProject(projectId, { detail: routedDetail(route, projectId), history: "none" }); }
    catch (error) { setStatus(error.message, true); }
    return;
  }
  const filtersChanged = route.tab === "snaps" && state._timeline
    && (state._timeline.intentId !== route.intent || state._timeline.author !== route.author);
  if (filtersChanged) resetTimeline(route.intent, route.author);
  const sectionChanged = route.tab === "settings" && state.activeTab === "settings" && (state._settingsSection || "") !== route.section;
  if (route.tab !== state.activeTab) switchTab(route.tab, { history: "none", section: route.section });
  else if (sectionChanged) {
    state._settingsSection = route.section;
    renderProjectBody();
    settlePage(el.detailContent, false);
  } else if (filtersChanged && hasHistory()) renderView();
  if (route.detail && DETAIL_PATHS[route.detailType]) {
    if (state.selectedDetail?.remoteId !== route.detail) {
      try { await openDetail(route.detailType, route.detail, { history: "none" }); }
      catch (error) { setStatus(error.message, true); }
    }
  } else if (sheetIsOpen()) closeDrawer({ history: "none" });
}

function bindEvents() {
  el.statusHome = el.statusLine.parentElement;
  // styles.css keeps the focus ring for keyboards. Shortcuts and bare modifiers do not count: they move no focus.
  document.addEventListener("pointerdown", () => { document.documentElement.dataset.input = "pointer"; }, true);
  document.addEventListener("keydown", (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey || ["Shift", "Meta", "Control", "Alt"].includes(event.key)) return;
    document.documentElement.dataset.input = "keyboard";
  }, true);

  el.drawer.inert = true;
  closeHeaderMenus();
  for (const menu of headerMenus()) menu.trigger.addEventListener("click", event => toggleHeaderMenu(menu.trigger, {focus: event.detail === 0 ? "first" : null}));
  document.addEventListener("click", event => {
    for (const menu of headerMenus()) if (!menu.panel.contains(event.target) && !menu.trigger.contains(event.target)) closeHeaderMenu(menu);
  });
  document.addEventListener("focusin", event => {
    for (const menu of headerMenus()) if (!menu.panel.contains(event.target) && !menu.trigger.contains(event.target)) closeHeaderMenu(menu);
    if (!el.projectPicker.contains(event.target)) toggleProjectPicker(false);
  });
  window.setInterval?.(() => { if (state.config && state.overview) updateSyncChip(); }, 60000);
  document.addEventListener("keydown", event => {
    const openMenu = headerMenus().find(entry => entry.panel.classList.contains("is-open"));
    if (event.key === "Escape" && openMenu) {
      event.preventDefault();
      event.stopImmediatePropagation();
      closeHeaderMenu(openMenu, true);
      return;
    }
    const menu = headerMenus().find(entry => entry.trigger.contains(event.target) || entry.panel.contains(event.target));
    if (!menu) return;
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!menu.panel.classList.contains("is-open")) {
      toggleHeaderMenu(menu.trigger, {focus: event.key === "ArrowUp" || event.key === "End" ? "last" : "first"});
      return;
    }
    const controls = headerMenuControls(menu);
    const current = controls.indexOf(document.activeElement);
    const next = event.key === "Home" ? 0 : event.key === "End" ? controls.length - 1 : current < 0 ? (event.key === "ArrowUp" ? controls.length - 1 : 0) : current + (event.key === "ArrowUp" ? -1 : 1);
    controls[(next + controls.length) % controls.length]?.focus();
  });
  const resizeDialogs = () => {
    document.documentElement.style.setProperty("--available-height", `${window.visualViewport?.height || innerHeight}px`);
    document.documentElement.style.setProperty("--available-width", `${window.visualViewport?.width || innerWidth}px`);
  };
  resizeDialogs();
  window.addEventListener("resize", resizeDialogs);
  window.visualViewport?.addEventListener("resize", resizeDialogs);
  for (const button of document.querySelectorAll("[data-language-switch]")) {
    button.addEventListener("click", () => window.IntHubI18n.setLanguage(window.IntHubI18n.language === "en" ? "zh-CN" : "en"));
  }
  for (const button of document.querySelectorAll("[data-language-select]")) button.addEventListener("click", () => window.IntHubI18n.setLanguage(button.dataset.languageSelect));
  window.addEventListener("inthub:language", localizeWorkspace);
  window.addEventListener("popstate", () => applyRoute(readRoute()));
  for (const trigger of document.querySelectorAll("[data-about-open]")) {
    trigger.addEventListener("click", () => {
      state._aboutReturnTrigger = headerMenus().find(menu => menu.panel.contains(trigger))?.trigger || trigger;
      closeHeaderMenus(true);
      el.aboutVersion.textContent = state.config?.productVersion || t("Unavailable");
      el.aboutDialog.showModal();
    });
  }
  el.aboutClose.addEventListener("click", () => el.aboutDialog.close());
  el.aboutDialog.addEventListener("close", () => {
    if (state._aboutReturnTrigger?.isConnected) state._aboutReturnTrigger.focus();
    state._aboutReturnTrigger = null;
  });

  el.searchTrigger.addEventListener("click", () => openSearch());
  // Pinyin and other IME compositions search once, when the text is committed.
  el.searchInput.addEventListener("input", (event) => { if (!event.isComposing) scheduleSearch(); });
  el.searchInput.addEventListener("compositionend", () => scheduleSearch());
  el.searchInput.addEventListener("keydown", (event) => {
    if (event.isComposing || event.keyCode === 229) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setActiveSearchOption((state._searchActive || 0) + (event.key === "ArrowDown" ? 1 : -1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      submitSearch();
    }
  });
  el.searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitSearch();
  });
  document.getElementById("search-close")?.addEventListener("click", closeSearch);
  el.searchStatus.addEventListener("click", (event) => {
    const retry = event.target.closest("[data-retry-search]");
    if (retry) runSearch(el.searchInput.value.trim(), retry);
  });
  el.searchResults.addEventListener("pointermove", (event) => {
    const option = event.target.closest("[role=option]");
    if (option && !option.classList.contains("is-active")) setActiveSearchOption(searchOptions().indexOf(option));
  });
  el.searchResults.addEventListener("click", (event) => {
    activateSearchOption(event.target.closest("[role=option]"));
  });
  el.searchDialog.addEventListener("click", (event) => {
    if (event.target === el.searchDialog) closeSearch();
  });
  el.searchDialog.addEventListener("close", () => {
    window.clearTimeout(state._searchTimer);
    beginViewRequest("search");
    state._searchBusy = false;
    const target = state._searchReturnFocus;
    state._searchReturnFocus = null;
    if (target?.isConnected && !sheetIsOpen()) target.focus();
  });

  el.tenonLogin.addEventListener("click", (event) => {
    const link = event.target.closest("[data-login-method]");
    if (!link) return;
    if (el.tenonLogin.querySelector(".is-loading")) {
      event.preventDefault();
      return;
    }
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    try { window.localStorage.setItem(LAST_LOGIN_METHOD, link.dataset.loginMethod); } catch { /* The marker is only a convenience. */ }
    setTenonLoginLoading(link.dataset.loginMethod);
  });

  window.addEventListener("pageshow", () => {
    setTenonLoginLoading();
    // Coming back from Tenon's deletion page restores the button.
    for (const button of document.querySelectorAll("[data-delete-account]")) setButtonBusy(button, false, "Opening account management…", "Delete account");
  });

  // Links between pages stay in the app; modified clicks keep their usual meaning.
  document.addEventListener("click", (event) => {
    const link = event.target.closest?.("a[data-route]");
    if (!link || event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    closeHeaderMenus(Boolean(link.closest(".header-menu")));
    toggleProjectPicker(false);
    const target = link.getAttribute("href");
    const dialog = dialogRoute(target);
    if (dialog && isDialogRoute(dialog) && !state.visitor) {
      openSettingsDialog(dialog.page, dialog.pane);
      return;
    }
    if (target !== `${window.location.pathname}${window.location.search}`) window.history.pushState({ inthub: "page" }, "", target);
    applyRoute(readRoute());
  });

  el.signInButton.addEventListener("click", () => showAuthGate("", { keepPage: true }));
  el.authStart.addEventListener("click", (event) => {
    const copy = event.target.closest?.("[data-copy]");
    if (copy) copyText(copy.dataset.copy, t("Command copied."));
  });
  el.authDismiss.addEventListener("click", dismissAuthGate);

  const siteInput = (event) => {
    const field = event.target;
    if (field?.name === "token-name" || field?.name === "token-days") {
      state._tokenDraft = { ...(state._tokenDraft || {}), [field.name === "token-name" ? "name" : "days"]: field.value };
      if (field.name === "token-name") setFieldError(field.form, "");
    } else if (field?.name === "invite-role") {
      state._inviteRole = field.value;
    } else if (field?.name === "device-code") {
      field.value = formatDeviceCode(field.value);
      setFieldError(field.form, "");
    } else if (field?.form?.matches?.("[data-team-form]")) {
      updateTeamDraft(field);
    } else if (field?.form?.matches?.("[data-team-settings-form]")) {
      state._team.edit = { name: field.form.elements["team-name"].value, slug: field.form.elements["team-slug"].value };
      setFieldError(field.form, "");
    }
  };
  const siteSubmit = (event) => {
    const form = event.target;
    const submit = form.matches?.("[data-token-form]") ? submitTokenForm
      : form.matches?.("[data-team-form]") ? createTeam
        : form.matches?.("[data-team-settings-form]") ? saveTeam
          : form.matches?.("[data-invite-form]") ? createInvite
            : form.matches?.("[data-device-form]") ? lookupDevice
              : null;
    if (!submit) return;
    event.preventDefault();
    submit(form);
  };
  const siteActions = {
    "[data-revoke-token]": (button) => confirmRevokeToken(button.dataset.revokeToken, button),
    "[data-copy-new-token]": () => state._newToken && copyText(state._newToken.token, t("Token copied.")),
    "[data-copy-invite]": () => state._newInvite && copyText(state._newInvite.url, t("Link copied.")),
    "[data-retry-tokens]": () => {
      state._tokens = null;
      state._tokensError = "";
      renderTokenList();
      return loadAccountTokens();
    },
    "[data-retry-site]": reloadSitePage,
    "[data-delete-account]": startAccountDeletion,
    "[data-revoke-invite]": (button) => revokeInvite(button.dataset.revokeInvite, button),
    "[data-remove-member]": (button) => confirmRemoveMember(button.dataset.removeMember, button),
    "[data-leave-team]": confirmLeaveTeam,
    "[data-delete-team]": confirmDeleteTeam,
    "[data-accept-invite]": acceptInvite,
    "[data-device-approve]": (button) => decideDevice(button, true),
    "[data-device-deny]": (button) => decideDevice(button, false),
  };
  const siteClick = (event) => {
    for (const [selector, action] of Object.entries(siteActions)) {
      const button = event.target.closest?.(selector);
      if (button) {
        action(button);
        return;
      }
    }
  };
  for (const root of [el.siteContent, el.settingsDialogBody]) {
    root.addEventListener("input", siteInput);
    root.addEventListener("submit", siteSubmit);
    root.addEventListener("click", siteClick);
  }
  el.siteContent.addEventListener("change", (event) => {
    if (event.target.matches?.("[data-member-role]")) changeMemberRole(event.target);
  });

  document.addEventListener("click", (event) => {
    const option = event.target.closest?.(".select-option");
    const trigger = event.target.closest?.(".select-trigger");
    if (option) chooseOption(option);
    else if (!trigger) closeSelect();
    else if (trigger.closest("[data-select]") === state._openSelect) closeSelect({ focus: true });
    else openSelect(trigger.closest("[data-select]"));
  });
  document.addEventListener("keydown", selectKeydown, true);
  document.addEventListener("focusin", (event) => { if (!state._openSelect?.contains(event.target)) closeSelect(); });
  document.addEventListener("scroll", (event) => { if (!event.target.closest?.(".select-menu")) closeSelect(); }, true);
  window.addEventListener("resize", () => closeSelect());

  el.settingsDialogClose.addEventListener("click", () => closeSettingsDialog());
  el.settingsDialog.addEventListener("close", () => closeSettingsDialog());
  // Only a press and release on the backdrop itself closes: a text selection dragged off the card ends there too.
  el.settingsDialog.addEventListener("pointerdown", (event) => { state._dialogPress = event.target === el.settingsDialog; });
  el.settingsDialog.addEventListener("click", (event) => {
    if (event.target === el.settingsDialog && state._dialogPress && !state._newToken) closeSettingsDialog();
  });
  for (const dialog of document.querySelectorAll("dialog")) dialog.addEventListener("close", placeStatusLine);

  el.detailContent.addEventListener("input", (event) => {
    if (event.target?.name === "project-name") updateRenameForm(event.target.form);
  });
  el.detailContent.addEventListener("submit", (event) => {
    const form = event.target.closest?.("[data-rename-form]");
    if (!form) return;
    event.preventDefault();
    renameCurrentProject(form);
  });

  el.confirmInput.addEventListener("input", () => {
    if (state._confirm?.expect === undefined) return;
    el.confirmOk.disabled = el.confirmInput.value !== state._confirm.expect;
    el.confirmError.hidden = true;
  });
  el.confirmForm.addEventListener("submit", (event) => {
    event.preventDefault();
    runConfirm();
  });
  el.confirmCancel.addEventListener("click", () => el.confirmDialog.close());
  // Escape does not abandon a request that is already running.
  el.confirmDialog.addEventListener("cancel", (event) => { if (state._confirmBusy) event.preventDefault(); });
  el.confirmDialog.addEventListener("close", () => {
    const target = state._confirm?.returnFocus;
    state._confirm = null;
    el.confirmInput.value = "";
    // The trigger may be gone (a revoked row, a deleted project): fall back to the list or the page.
    const fallback = state._dialog ? el.settingsDialogBody.querySelector?.("#token-list") || el.settingsDialogClose : state.page === "project" ? el.detailContent : el.siteContent;
    (target?.isConnected ? target : fallback).focus?.({ preventScroll: true });
  });

  el.logoutBtn.addEventListener("click", async () => {
    if (el.logoutBtn.disabled) return;
    setButtonBusy(el.logoutBtn, true, "Signing out…", "Sign out");
    try {
      await fetchJson(apiUrl("/api/v1/auth/logout"), { method: "POST" });
    } catch (error) {
      setStatus(error.message, true);
      return;
    } finally {
      setButtonBusy(el.logoutBtn, false, "Signing out…", "Sign out");
    }
    closeHeaderMenus();
    for (const view of ["projects", "project", "detail", "sheet", "search"]) beginViewRequest(view);
    closeDrawer({ history: "none" });
    state.projects = [];
    state._loadedProjectId = null;
    state.overview = null;
    state.handoff = null;
    state.account = null;
    state._teams = null;
    state._home = null;
    state._projectTeam = null;
    showAuthGate();
  });

  el.projectPickerTrigger.addEventListener("click", () => {
    toggleProjectPicker();
  });

  el.projectPickerDropdown.addEventListener("click", async (e) => {
    const option = e.target.closest(".project-picker-option");
    if (!option || state._projectBusy) return;
    toggleProjectPicker(false);
    const id = option.dataset.id;
    if (!id) return;
    if (id === state.currentProjectId && id === state._loadedProjectId) {
      if (state.page !== "project") {
        leaveSitePage();
        writeRoute("push");
        el.detailContent.focus?.({ preventScroll: true });
      }
      return;
    }
    leaveSitePage();
    state._projectBusy = true;
    setProjectPickerBusy(true);
    try {
      await loadProject(id, { history: "push" });
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      state._projectBusy = false;
      setProjectPickerBusy(false);
      el.projectPickerTrigger.focus();
    }
  });

  document.addEventListener("click", (e) => {
    if (!el.projectPicker.contains(e.target)) {
      toggleProjectPicker(false);
    }
    for (const filter of document.querySelectorAll(".timeline-filter[open]")) if (!filter.contains(e.target)) filter.open = false;
  });

  el.refreshBtn.addEventListener("click", async () => {
    if (el.refreshBtn.disabled) return;
    setButtonBusy(el.refreshBtn, true, "Refreshing project data", "Refresh project data");
    try {
      if (state.visitor) await loadProject(state.currentProjectId);
      else if (state.page === "project") await loadProjects({ ...readRoute(), detail: null });
      else {
        await refreshProjectList();
        await reloadSitePage();
      }
      closeHeaderMenus(true);
      setStatus(t("Project data refreshed."));
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      setButtonBusy(el.refreshBtn, false, "Refreshing project data", "Refresh project data");
    }
  });

  el.tabBar.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (tab && tab.dataset.tab) switchTab(tab.dataset.tab);
  });

  el.detailContent.addEventListener("toggle", (event) => {
    const archive = event.target.dataset?.archive;
    if (!archive) return;
    state._pageState ||= {};
    state._pageState[archive === "intents" ? "intentArchiveOpen" : "decisionArchiveOpen"] = event.target.open;
    if (archive === "intents" && event.target.open) {
      fetchMissingSnaps([...event.target.querySelectorAll("[data-latest-snap]")].map((node) => node.dataset.latestSnap));
    }
  }, true);

  // Flow nodes and Decision marks are SVG groups with role="button": Enter and Space open them.
  el.detailContent.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const mark = event.target.closest?.("svg [role=button][data-detail-type][data-remote-id]");
    if (!mark) return;
    event.preventDefault();
    openDetail(mark.dataset.detailType, mark.dataset.remoteId).catch((error) => setStatus(error.message, true));
  });

  document.addEventListener("click", async (e) => {
    if (e.target.closest("#search-dialog")) return;
    const retryInit = e.target.closest("[data-retry-init]");
    if (retryInit) {
      if (retryInit.disabled) return;
      setButtonBusy(retryInit, true, "Loading…", "Retry");
      try { await init(false); }
      finally { setButtonBusy(retryInit, false, "Loading…", "Retry"); }
      return;
    }
    const retryProject = e.target.closest("[data-retry-project]");
    if (retryProject) {
      if (retryProject.disabled) return;
      setButtonBusy(retryProject, true, "Loading…", "Retry");
      try { await loadProject(retryProject.dataset.retryProject); }
      catch (error) { setStatus(error.message, true); }
      finally { setButtonBusy(retryProject, false, "Loading…", "Retry"); }
      return;
    }
    const copy = e.target.closest("[data-copy]");
    if (copy) {
      await copyText(copy.dataset.copy, t("Command copied."));
      return;
    }
    if (e.target.closest("[data-copy-brief]")) {
      if (state.overview) await copyText(briefMarkdown(), t("Brief copied."));
      return;
    }
    const exportButton = e.target.closest("[data-export-project]");
    if (exportButton) {
      await exportCurrentProject(exportButton);
      return;
    }
    const deleteProjectButton = e.target.closest("[data-delete-project]");
    if (deleteProjectButton) {
      confirmDeleteProject(deleteProjectButton);
      return;
    }
    const visibilityButton = e.target.closest("[data-change-visibility]");
    if (visibilityButton) {
      confirmVisibility(visibilityButton.dataset.changeVisibility, visibilityButton);
      return;
    }
    const transferButton = e.target.closest("[data-transfer-project]");
    if (transferButton) {
      confirmTransfer(transferButton);
      return;
    }
    const jump = e.target.closest("[data-tab-jump]");
    if (jump) {
      switchTab(jump.dataset.tabJump);
      return;
    }
    const filter = e.target.closest("[data-timeline-intent]");
    if (filter) {
      setTimelineFilter({ intentId: filter.dataset.timelineIntent }, ".timeline-filter-trigger");
      return;
    }
    const authorFilter = e.target.closest("[data-timeline-author]");
    if (authorFilter) {
      setTimelineFilter({ author: authorFilter.dataset.timelineAuthor }, ".author-filter .timeline-filter-trigger");
      return;
    }
    if (e.target.closest("[data-retry-timeline]")) {
      if (state._timeline) state._timeline.error = "";
      renderView();
      return;
    }
    if (e.target.closest("[data-retry-history]")) {
      if (state._history) state._history.error = "";
      renderView();
      return;
    }
    const moreHistory = e.target.closest("#load-more-history");
    if (moreHistory) {
      if (moreHistory.disabled) return;
      const shown = el.detailContent.querySelectorAll(".history-row").length;
      moreHistory.disabled = true;
      moreHistory.textContent = t("Loading…");
      const scroll = window.scrollY;
      await loadHistoryPage();
      window.scrollTo?.(0, scroll);
      el.detailContent.querySelectorAll(".history-row")[shown]?.focus({ preventScroll: true });
      return;
    }
    if (e.target.closest("[data-flow-hide-ended]")) {
      state._flow ||= { hideEnded: false, focus: "", standalone: PAGE_SIZE };
      state._flow.hideEnded = !state._flow.hideEnded;
      renderView();
      el.detailContent.querySelector("[data-flow-hide-ended]")?.focus();
      return;
    }
    const flowFocus = e.target.closest("[data-flow-focus]");
    if (flowFocus) {
      showFlowFocus(flowFocus.dataset.flowFocus, { fromSheet: Boolean(flowFocus.closest("#drawer-content")) });
      return;
    }
    const moreSnaps = e.target.closest("#load-more-snaps");
    if (moreSnaps) {
      if (moreSnaps.disabled) return;
      const shown = el.detailContent.querySelectorAll(".timeline-entry").length;
      moreSnaps.disabled = true;
      moreSnaps.textContent = t("Loading…");
      const scroll = window.scrollY;
      await loadTimelinePage();
      window.scrollTo?.(0, scroll);
      el.detailContent.querySelectorAll(".timeline-entry")[shown]?.focus({ preventScroll: true });
      return;
    }
    const loadMore = e.target.closest("#load-more-intent-archive, #load-more-flow-standalone");
    if (loadMore) {
      const archive = loadMore.id === "load-more-intent-archive";
      const selector = archive ? ".intent-archive .list-row" : ".flow-card";
      const shown = el.detailContent.querySelectorAll(selector).length;
      state._pageState ||= {};
      if (archive) {
        state._pageState.intentArchive = (state._pageState.intentArchive || PAGE_SIZE) + PAGE_SIZE;
        state._pageState.intentArchiveOpen = true;
      } else {
        state._flow.standalone = (state._flow.standalone || PAGE_SIZE) + PAGE_SIZE;
      }
      const scroll = window.scrollY;
      renderView();
      window.scrollTo?.(0, scroll);
      el.detailContent.querySelectorAll(selector)[shown]?.focus({ preventScroll: true });
      return;
    }
    const card = e.target.closest("[data-detail-type][data-remote-id]");
    if (!card) return;
    const inSheet = Boolean(card.closest("#drawer-content"));
    try {
      if (card.dataset.retryDetail) await openDetail(card.dataset.detailType, card.dataset.remoteId, { mode: "replace", history: "replace" });
      else await openDetail(card.dataset.detailType, card.dataset.remoteId, { mode: inSheet ? "push" : "reset" });
    } catch (err) {
      setStatus(err.message, true);
    }
  });

  el.drawerClose.addEventListener("click", () => closeDrawer());
  el.drawerBack.addEventListener("click", () => sheetBack().catch((error) => setStatus(error.message, true)));
  el.drawerOverlay.addEventListener("click", (event) => { if (event.detail <= 1) closeDrawer(); });
  // Clicking the backdrop must not pull focus out of the sheet.
  el.drawerOverlay.addEventListener("mousedown", (event) => event.preventDefault());

  document.addEventListener("keydown", (event) => {
    if (el.aboutDialog.open || el.searchDialog.open || el.confirmDialog.open || el.settingsDialog.open) return;
    if (event.key === "Escape" && state.visitor && !el.authGate.classList.contains("is-hidden")) {
      event.preventDefault();
      dismissAuthGate();
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k" && !el.shell.inert && state.page === "project") {
      event.preventDefault();
      openSearch();
      return;
    }
    if (sheetIsOpen()) {
      if (event.key === "Escape") { event.preventDefault(); closeDrawer(); return; }
      if (event.key === "Tab") {
        const controls = sheetFocusables();
        const first = controls[0] || el.drawerClose;
        const last = controls.at(-1) || first;
        if (event.shiftKey && (document.activeElement === first || !el.drawer.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || !el.drawer.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
      }
      return;
    }
    if (el.shell.inert) return;
    const filter = event.target.closest?.(".timeline-filter");
    if (filter && ["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      filter.open = true;
      const options = [...filter.querySelectorAll(".timeline-filter-option")];
      const current = options.indexOf(document.activeElement);
      const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 : current < 0 ? (event.key === "ArrowUp" ? options.length - 1 : 0) : current + (event.key === "ArrowUp" ? -1 : 1);
      options[(next + options.length) % options.length]?.focus();
      return;
    }
    if (el.projectPicker.contains(event.target) && ["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      if (state._projectBusy) return;
      toggleProjectPicker(true);
      const options = [...el.projectPickerDropdown.querySelectorAll("[role=option]")];
      const current = options.indexOf(document.activeElement);
      const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 : current < 0 ? (event.key === "ArrowUp" ? options.length - 1 : 0) : current + (event.key === "ArrowUp" ? -1 : 1);
      options[(next + options.length) % options.length]?.focus();
      return;
    }
    const typing = event.target.matches?.("input, textarea, select, [contenteditable]");
    if (event.key === "/" && !typing && !event.metaKey && !event.ctrlKey && !event.altKey && state.page === "project") {
      event.preventDefault();
      openSearch();
      return;
    }
    if (event.key === "Escape") {
      if (filter?.open) { filter.open = false; filter.querySelector("summary")?.focus(); }
      else if (el.projectPickerDropdown.classList.contains("is-open")) { toggleProjectPicker(false); el.projectPickerTrigger.focus(); }
    }
  });
}

/* ---- Init ---- */

async function init(bind = true) {
  let authError = "";
  if (bind) bindEvents();
  if (!/Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "")) {
    for (const hint of document.querySelectorAll(".command-trigger kbd")) hint.textContent = "Ctrl K";
  }
  try {
    const response = await fetch(configUrl(), { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new ApiRequestError(t("Could not load data. Try again."), response.status, "CONFIG_UNAVAILABLE");
    state.config = await response.json();
    authError = callbackErrorMessage();
    const route = readRoute();
    state.activeTab = route.tab;
    state._settingsSection = route.section;
    setActiveTabUI();
    await loadCurrentAccount();
    if (state.config.authRequired && !state.account) {
      if (route.page !== "project" || !route.project || !(await openAsVisitor(route))) {
        showAuthGate(authError);
        return;
      }
      if (authError) setStatus(authError, true);
    } else {
      await loadProjects(route);
      hideAuthGate();
      if (isSiteRoute(route)) await applyRoute(route);
      else if (isDialogRoute(route)) openSettingsDialog(route.page, route.pane, { history: "replace" });
    }
    state._ready = true;
    if (route.search && state.currentProjectId && state.page === "project") openSearch(route.q);
  } catch (err) {
    if (err.status === 401 && state.config?.authRequired) {
      showAuthGate(authError);
      return;
    }
    const message = err instanceof ApiRequestError ? err.message : t("Could not load data. Try again.");
    setStatus(message, true);
    el.detailContent.innerHTML = emptyState({
      iconName: "blocker",
      title: t("Failed to initialize."),
      body: message,
      extra: `<button type="button" class="secondary-btn" data-retry-init>${iconLabel("refresh", t("Retry"))}</button>`,
    });
  }
}

init();

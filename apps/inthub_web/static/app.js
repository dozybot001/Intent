const { t } = window.IntHubI18n;
window.IntHubI18n.bindStatic(document.body);

/* ---- State ---- */

const TABS = ["overview", "intents", "snaps", "decisions"];
const DETAIL_PATHS = { intent: "intents", decision: "decisions", snap: "snaps" };
const PAGE_SIZE = 30;
const INSTALL_COMMAND = "curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/scripts/install.sh | bash";

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
  statusLine: document.getElementById("status-line"),
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
  tokenBtn: document.getElementById("token-btn"),
  deleteAccountBtn: document.getElementById("delete-account-btn"),
  tokenDialog: document.getElementById("token-dialog"),
  tokenOutput: document.getElementById("token-output"),
  tokenCopy: document.getElementById("token-copy"),
  accountControl: document.getElementById("account-control"),
  accountLabel: document.getElementById("account-label"),
  accountMode: document.getElementById("account-mode"),
  accountMenuTrigger: document.getElementById("account-menu-trigger"),
  accountActions: document.getElementById("account-actions"),
  settingsMenuTrigger: document.getElementById("settings-menu-trigger"),
  settingsMenu: document.getElementById("settings-menu"),
  authGate: document.getElementById("auth-gate"),
  authError: document.getElementById("auth-error"),
  tenonLogin: document.getElementById("tenon-login"),
  tenonLoginLabel: document.getElementById("tenon-login-label"),
  aboutDialog: document.getElementById("about-dialog"),
  aboutClose: document.getElementById("about-close"),
  aboutVersion: document.getElementById("about-version"),
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
};

function icon(name) {
  return `<svg viewBox="0 0 20 20" aria-hidden="true">${ICONS[name] || ""}</svg>`;
}

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

function originBadge(origin) {
  if (!origin) return "";
  return `<span class="chip">${esc(origin)}</span>`;
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
  constructor(message, status, code) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function fetchJson(url, options = {}) {
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
    );
    if (r.status === 401 && state.config?.authRequired) showAuthGate();
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

function setTenonLoginLoading(loading) {
  el.tenonLogin.classList.toggle("is-loading", loading);
  el.tenonLogin.setAttribute("aria-busy", String(loading));
  if (loading) {
    el.tenonLogin.setAttribute("aria-disabled", "true");
  } else {
    el.tenonLogin.removeAttribute("aria-disabled");
  }
  el.tenonLoginLabel.textContent = loading
    ? t("Connecting to Tenon…")
    : t("Sign in with Tenon");
}

function showAuthGate(message = "") {
  closeHeaderMenus();
  closeDrawer({ history: "none" });
  if (el.searchDialog.open) el.searchDialog.close();
  for (const view of ["projects", "project", "detail", "sheet", "search"]) beginViewRequest(view);
  el.detailContent.innerHTML = "";
  el.searchResults.innerHTML = "";
  el.searchInput.value = "";
  el.accountLabel.textContent = "";
  state._searchResults = null;
  state._detailCache = new Map();
  el.shell.inert = true;
  state._authMessage = window.IntHubI18n.keyFor(message);
  state.authenticated = false;
  el.shell.classList.add("is-locked");
  el.authGate.classList.remove("is-hidden");
  el.accountControl.classList.add("is-hidden");
  el.authError.textContent = message;
  el.authError.classList.toggle("is-hidden", !message);
  el.tenonLogin.classList.remove("is-hidden");
  const returnTo = `${window.location.pathname}${window.location.search}`;
  el.tenonLogin.href = `/auth/redirect?return_to=${encodeURIComponent(returnTo)}`;
  setTenonLoginLoading(false);
  window.setTimeout(() => el.tenonLogin.focus(), 0);
}

function hideAuthGate() {
  el.shell.inert = false;
  state.authenticated = true;
  el.shell.classList.remove("is-locked");
  el.authGate.classList.add("is-hidden");
  el.accountControl.classList.toggle("is-hidden", !state.config?.authRequired);
  el.accountMode.classList.remove("is-hidden");
  el.accountMode.textContent = t("Private session");
  el.tokenBtn.classList.remove("is-hidden");
  el.logoutBtn.classList.remove("is-hidden");
  el.accountMenuTrigger.disabled = false;
  const account = state.account;
  el.accountLabel.textContent = account ? account.display_name || `@${account.login}` : t("Private session");
  el.authError.textContent = "";
  el.authError.classList.add("is-hidden");
}

async function loadCurrentAccount() {
  if (state.config?.authMode !== "tenon") return;
  const result = await fetchJson(apiUrl("/api/v1/auth/me"));
  state.account = result.account;
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
  };
  return messages[code] || t("Sign-in could not be completed.");
}

/* ---- URL state ---- */

function readRoute() {
  const p = new URLSearchParams(window.location.search);
  const requestedTab = p.get("tab") || "overview";
  const q = p.get("q") || "";
  return {
    project: p.get("project"),
    tab: TABS.includes(requestedTab) ? requestedTab : "overview",
    detail: p.get("detail"),
    detailType: p.get("detailType"),
    q,
    search: requestedTab === "search" || Boolean(q),
  };
}

function routeUrl() {
  const p = new URLSearchParams();
  if (state.currentProjectId) p.set("project", state.currentProjectId);
  if (state.activeTab !== "overview") p.set("tab", state.activeTab);
  if (state.selectedDetail) {
    p.set("detail", state.selectedDetail.remoteId);
    p.set("detailType", state.selectedDetail.type);
  }
  const q = p.toString();
  return q ? `${window.location.pathname}?${q}` : window.location.pathname;
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

function setStatus(msg, isError = false) {
  state._statusMessage = window.IntHubI18n.keyFor(msg);
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

function switchTab(tab, { history = "push" } = {}) {
  if (!TABS.includes(tab)) return;
  if (state.activeTab === tab) {
    window.scrollTo?.({ top: 0, behavior: "smooth" });
    return;
  }
  closeDrawer({ history: "none" });
  state.activeTab = tab;
  setActiveTabUI();
  if (hasHistory()) renderView();
  writeRoute(history);
  window.scrollTo?.({ top: 0 });
}

/* ---- Data helpers ---- */

function hasHistory() {
  return Boolean(historySources(state.overview).length);
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

function latestSnapFor(intent) {
  return intent.latest_snap_id ? snapIndex().get(remoteId(intent.project_id, intent.latest_snap_id)) || null : null;
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

function parseCheckpoint(snap) {
  const what = extractCheckpointParts(snap?.what);
  const why = extractCheckpointParts(snap?.why);
  const fields = { ...why.fields, ...what.fields };
  const context = [what.structured ? what.context : "", why.context]
    .filter(Boolean)
    .filter((value, index, values) => values.indexOf(value) === index)
    .join(" · ");
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
  const checkpoint = parseCheckpoint(snap);
  const source = String(checkpoint.verified || snap?.what || "")
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
  const checkpoints = intents.map(intent => ({
    ...extractCheckpointParts(intent.latest_snap?.why).fields,
    ...extractCheckpointParts(intent.latest_snap?.what).fields,
  }));
  const incomplete = checkpoints.filter(checkpoint => !checkpoint.verified || !checkpoint.boundary || !checkpoint.next || !checkpoint.blocker).length;
  if (incomplete) return { ready: false, label: plural(incomplete, "{count} incomplete checkpoint", "{count} incomplete checkpoints") };
  const blocked = checkpoints.filter(checkpoint => !isClearBlocker(checkpoint.blocker)).length;
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

function commandSnippet(lines) {
  const text = lines.join("\n");
  return `<div class="snippet"><pre class="command-snippet">${esc(text)}</pre><button class="icon-button copy-button" type="button" data-copy="${esc(text)}" aria-label="${esc(t("Copy command"))}">${icon("copy")}</button></div>`;
}

function detailSection(title, body, count) {
  return `<section class="detail-section"><h3 class="detail-section-title">${esc(title)}${count === undefined ? "" : `<span class="count">${count}</span>`}</h3>${body}</section>`;
}

function relationItem(type, rId, id, title, meta, status) {
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
    ${meta ? `<span class="relation-meta">${esc(meta)}</span>` : ""}
    <span class="relation-side"><span class="row-id">${esc(id)}</span>${status ? statusBadge(status, type) : ""}</span>
  </button>`;
}

function collapsibleRelation(allItems, visibleCount) {
  if (!allItems.length) return "";
  const visible = allItems.slice(0, visibleCount);
  const rest = allItems.slice(visibleCount);
  let html = `<div class="relation-list">${visible.join("")}</div>`;
  if (rest.length) {
    html += `<details class="collapse-toggle"><summary>${esc(t("Show {count} more", {count: rest.length}))}</summary><div class="relation-list">${rest.join("")}</div></details>`;
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
    case "snaps":
      renderSnapsTab();
      break;
    case "decisions":
      renderDecisionsTab();
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
        </div>
        <button class="brief-open" type="button" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">${esc(t("Open Intent"))}${icon("arrow")}</button>
      </header>
      ${checkpointGrid(checkpoint)}
      ${checkpoint.constraints ? `<p class="checkpoint-note brief-constraints"><strong>${esc(t("Constraints:"))}</strong> ${esc(checkpoint.constraints)}</p>` : ""}
      <footer class="brief-foot">
        <span class="brief-foot-meta">
          ${snap
            ? `<span>${esc(t("Latest checkpoint"))} <span class="mono">${esc(snap.id)}</span></span><span>${esc(fmtDate(snap.created_at))}</span>${snap.origin ? `<span>${esc(snap.origin)}</span>` : ""}`
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
  return `
    <button class="list-row queue-item" type="button" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
      ${rowStatusIcon(intent.status)}
      <span class="row-main">
        <span class="row-title">${esc(intent.what)}</span>
        <span class="row-summary">${summary}</span>
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
          esc(t("Shared history")),
          `<span class="mono">${esc(shortRevision(history.revision))}</span>`,
          esc(history.last_synced_at ? t("Synced {time}", {time: relativeDate(history.last_synced_at)}) : t("Waiting for first sync")),
        ],
        actions: `
          <span class="health-pill${healthTone}">${icon(healthIcon)}${esc(health.label)}</span>
          <button class="button button-secondary" type="button" data-copy-brief>${icon("copy")}${esc(t("Copy brief"))}</button>`,
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
  if (!intents.length) lines.push(t("No active Intent defines the next move."), "");
  for (const intent of intents) {
    const checkpoint = parseCheckpoint(intent.latest_snap);
    lines.push(`## ${intent.what} (${intent.id})`, "");
    if (intent.why) lines.push(`${t("Why")}: ${intent.why}`, "");
    for (const [label, value] of [[t("Next"), checkpoint.next], [t("Blocker"), checkpoint.blocker], [t("Boundary"), checkpoint.boundary], [t("Verified"), checkpoint.verified]]) {
      lines.push(`- **${label}:** ${value || t("Not explicitly recorded in the latest Snap.")}`);
    }
    if (checkpoint.constraints) lines.push(`- **${t("Constraints:")}** ${checkpoint.constraints}`);
    lines.push("");
  }
  if (suspended.length) {
    lines.push(`## ${t("Suspended")}`, "", ...suspended.map((intent) => `- ${intent.what} (${intent.id})`), "");
  }
  lines.push(`## ${t("Active decisions")}`, "");
  lines.push(...(decisions.length ? decisions.map((decision) => `- ${decision.what} (${decision.id})`) : [t("N/A — no active Decision constrains future work.")]));
  return `${lines.join("\n").trim()}\n`;
}

/* Intents */

function intentEntry(intent) {
  const snap = latestSnapFor(intent);
  const snaps = (intent.snap_ids || []).length;
  const decisions = (intent.decision_ids || []).length;
  return `
    <button type="button" class="list-row intent-entry intent-entry-${esc(intent.status)}" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
      ${rowStatusIcon(intent.status)}
      <span class="row-main">
        <strong class="row-title intent-entry-title">${esc(intent.what)}</strong>
        ${intent.why ? `<span class="row-summary">${esc(truncate(intent.why, 220))}</span>` : ""}
      </span>
      <span class="row-meta">
        <span class="row-id">${esc(intent.id)}</span>
        <span class="row-meta-line"><span>${esc(plural(snaps, "{count} snap", "{count} snaps"))}</span><span>${esc(plural(decisions, "{count} decision", "{count} decisions"))}</span></span>
        <span>${esc(snap ? t("Updated {time}", {time: relativeDate(snap.created_at)}) : intent.latest_snap_id ? t("Checkpoint {id}", {id: intent.latest_snap_id}) : t("Checkpoint missing"))}</span>
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
            ? `<button type="button" class="load-more-btn" id="load-more-intent-archive">${esc(t("Load more ({count})", {count: archiveRemaining}))}</button>`
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
}

/* Timeline */

function timelineIntentKey(snap) {
  return remoteId(snap.project_id || projectIdFromRemoteId(snap.remote_id), snap.intent_id || "");
}

function timelineIntentOptions(snaps) {
  const options = new Map();
  for (const snap of snaps) {
    const key = timelineIntentKey(snap);
    const entry = options.get(key);
    if (entry) entry.count++;
    else options.set(key, { key, count: 1, label: intentForSnap(snap)?.what || snap.intent_id || t("Unlinked Intent") });
  }
  return [...options.values()];
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
      </span>
    </button>`;
}

function renderTimeline(snaps) {
  state._pageState ||= {};
  const shown = state._pageState.snaps || PAGE_SIZE;
  const visible = snaps.slice(0, shown);
  const groups = [];
  for (const snap of visible) {
    const date = timelineDate(snap.created_at);
    const current = groups.at(-1);
    if (!current || current.key !== date.key) {
      groups.push({ key: date.key, label: date.label, snaps: [snap] });
    } else {
      current.snaps.push(snap);
    }
  }

  const remaining = snaps.length - visible.length;
  return groups
    .map((group) => `
      <section class="timeline-group">
        <h2 class="timeline-day"><span>${esc(group.label)}</span><span>${group.snaps.length}</span></h2>
        <div class="timeline-events">${group.snaps.map(snapTimelineEntry).join("")}</div>
      </section>`)
    .join("")
    + (remaining > 0
      ? `<button type="button" class="load-more-btn" id="load-more-snaps">${esc(t("Load more ({count})", {count: remaining}))}</button>`
      : "");
}

function renderSnapsTab() {
  const allSnaps = state.overview.recent_snaps || [];
  if (!allSnaps.length) {
    el.detailContent.innerHTML = pageHeader({ title: t("Timeline") }) + emptyState({
      iconName: "timeline",
      title: t("No snaps synced yet."),
      body: t("Snaps are verified checkpoints. They appear here after the next push."),
    });
    return;
  }
  const options = timelineIntentOptions(allSnaps);
  if (state._timelineIntentKey && !options.some(option => option.key === state._timelineIntentKey)) state._timelineIntentKey = "";
  const selected = options.find(option => option.key === state._timelineIntentKey);
  const snaps = selected ? allSnaps.filter(snap => timelineIntentKey(snap) === selected.key) : allSnaps;
  const optionHtml = (key, label, count) => `<button type="button" class="timeline-filter-option${(state._timelineIntentKey || "") === key ? " is-selected" : ""}" data-timeline-intent="${esc(key)}" aria-pressed="${(state._timelineIntentKey || "") === key}"><span>${esc(label)}</span><small>${count}</small></button>`;
  const filter = `
    <div class="timeline-toolbar">
      <details class="timeline-filter">
        <summary class="timeline-filter-trigger" title="${esc(t("Filter timeline by Intent"))}"><span>${esc(selected ? truncate(selected.label, 44) : t("All Intents"))}</span>${icon("chevronDown")}</summary>
        <div class="timeline-filter-menu">${optionHtml("", t("All Intents"), allSnaps.length)}${options.map(option => optionHtml(option.key, option.label, option.count)).join("")}</div>
      </details>
    </div>`;
  el.detailContent.innerHTML = pageHeader({
    title: t("Timeline"),
    meta: [esc(plural(snaps.length, "{count} checkpoint", "{count} checkpoints")), esc(selected ? truncate(selected.label, 60) : t("All Intents"))],
    actions: filter,
  }) + `<div class="timeline">${renderTimeline(snaps)}</div>`;
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
  return `<div class="empty-state"><p>${esc(error.message)}</p><button type="button" class="secondary-btn" data-retry-detail="sheet" data-detail-type="${esc(type)}" data-remote-id="${esc(rId)}">${esc(t("Retry"))}</button></div>`;
}

function sheetIsOpen() {
  return el.drawer.classList.contains("open");
}

function renderSheetHeader(payload = null) {
  const entry = state._sheetStack?.at(-1);
  const labels = { intent: t("Intent"), snap: t("Snap"), decision: t("Decision") };
  const id = payload?.id || (entry ? entry.remoteId.split("__").slice(1).join("__") : "");
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
  return type === "intent"
    ? buildIntentDetailHtml(payload)
    : type === "decision"
      ? buildDecisionDetailHtml(payload)
      : buildSnapDetailHtml(payload);
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
    const payload = await fetchJson(apiUrl(`/api/v1/${DETAIL_PATHS[type]}/${encodeURIComponent(rId)}`));
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

  return `
    <div class="detail-header">
      ${detailMeta([statusBadge(intent.status), idChip(intent.id), originBadge(intent.origin), `<span>${esc(t("Created {time}", {time: fmtDate(intent.created_at)}))}</span>`])}
      <h2 class="detail-title" tabindex="-1">${esc(intent.what)}</h2>
    </div>
    ${intent.why ? detailSection(t("Why"), formatText(intent.why)) : ""}
    ${intent.reason ? detailSection(t("Reason"), formatText(intent.reason)) : ""}
    ${latest && ["active", "suspend"].includes(intent.status) ? detailSection(t("Latest checkpoint"), checkpointGrid(parseCheckpoint(latest), ["next", "blocker", "boundary", "verified"], " detail-checkpoint-grid")) : ""}
    ${detailSection(t("Snaps"), snapTimelineBody, allSnaps.length)}
    ${detailSection(t("Linked decisions"), decisionsBody, allIds.length)}
    ${rawToggle({ intent, snaps: payload.snaps, decisions: payload.decisions || [] })}`;
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
      ${detailMeta([statusBadge(decision.status, "decision"), idChip(decision.id), originBadge(decision.origin), `<span>${esc(t("Created {time}", {time: fmtDate(decision.created_at)}))}</span>`])}
      <h2 class="detail-title" tabindex="-1">${esc(decision.what)}</h2>
      <p class="detail-context decision-detail-scope">${esc(decision.status === "active" ? t("Current cross-Intent constraint") : t("Deprecated constraint history"))} · ${esc(scopeSummary)}</p>
    </div>
    ${detailSection(t("Why"), formatText(decision.why) || `<p>${esc(t("No why provided."))}</p>`)}
    ${decision.reason ? detailSection(t("Reason"), formatText(decision.reason)) : ""}
    ${detailSection(t("Affected Intents"), intentsBody, payload.intents.length)}
    ${rawToggle({ decision, intents: payload.intents })}`;
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
      ${detailMeta([stateBadge(status), idChip(snap.id), originBadge(snap.origin), `<span>${esc(fmtDate(snap.created_at))}</span>`])}
      <h2 class="detail-title detail-title-snap" tabindex="-1">${esc(conciseSnapTitle(snap, 110))}</h2>
      <p class="detail-context snap-detail-context">${esc(t("Semantic checkpoint for"))} ${parent}</p>
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

function renderSetupGuide(mode) {
  el.shell.classList.add("is-empty");
  const projectName = state.projects.find(p => p.id === state.currentProjectId)?.name;
  const shellArg = value => `'${String(value).replaceAll("'", "'\\''")}'`;
  const linkCmd = `itt remote add origin ${shellArg(state.config.apiBaseUrl)} --project ${projectName ? shellArg(projectName) : "PROJECT"}`;
  const steps = [];
  if (mode === "unlinked") {
    steps.push(
      { title: t("Install the Intent CLI"), desc: t("Requires Python 3.9+. Re-run any time to upgrade."), cmd: [INSTALL_COMMAND] },
      { title: t("Initialize your project"), desc: t("Run once per project; Git is optional."), cmd: ["itt init"] },
    );
  }
  if (state.config.authRequired) {
    steps.push({
      title: t("Sign in from the CLI"),
      desc: t("Create an access token, then paste it when the CLI asks. It is shown once."),
      cmd: [`itt auth login --api-base-url ${shellArg(state.config.apiBaseUrl)}`],
      token: true,
    });
  }
  steps.push({
    title: t("Link and push"),
    desc: mode === "unlinked"
      ? t("Choose a shared project name, then push its semantic history.")
      : t("Ensure CLI points here, then push the next snapshot."),
    cmd: [linkCmd, "itt push"],
  });

  el.detailContent.innerHTML = `
    <div class="setup-page setup-guide">
      ${pageHeader({
        eyebrow: mode === "unlinked" ? t("Welcome") : projectName || t("Project"),
        title: mode === "unlinked" ? t("Get started with IntHub") : t("Complete the first sync"),
        help: "setup",
        meta: [esc(t("Sync semantic history from the Intent CLI, then continue from the brief here."))],
      })}
      <ol class="setup-steps">
        ${steps.map((step) => `
          <li class="setup-step">
            <h3>${esc(step.title)}</h3>
            <p>${esc(step.desc)}</p>
            <div>
              ${commandSnippet(step.cmd)}
              ${step.token ? `<div class="setup-step-actions"><button class="button button-secondary" type="button" data-create-token>${icon("key")}${esc(t("Create access token"))}</button></div>` : ""}
            </div>
          </li>`).join("")}
      </ol>
    </div>`;
}

/* ---- Project selector ---- */

function renderProjectSelector() {
  if (!state.projects.length) {
    el.projectPickerTrigger.disabled = true;
    el.projectPickerLabel.textContent = t("No projects yet");
    el.projectPickerDropdown.innerHTML = "";
    return;
  }
  el.projectPickerTrigger.disabled = Boolean(state._projectBusy);
  const current = state.projects.find((p) => p.id === state.currentProjectId);
  el.projectPickerLabel.textContent = current
    ? current.name
    : state.projects[0].name;
  el.projectPickerDropdown.innerHTML = state.projects
    .map(
      (p) =>
        `<button type="button" role="option" aria-selected="${p.id === state.currentProjectId ? "true" : "false"}" class="project-picker-option${p.id === state.currentProjectId ? " is-selected" : ""}" data-id="${esc(p.id)}">
          <span class="project-picker-option-name">${esc(p.name)}</span>
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
  el.syncChip.title = ws ? fmtDate(ws.last_synced_at) : "";
  el.syncIndicator.classList.toggle("is-unsynced", !ws);
}

/* ---- Project loading ---- */

async function loadProject(projectId, { detail = null, history = "replace" } = {}) {
  const request = beginViewRequest("project");
  state._projectPending = request;
  const previous = {
    projectId: state._loadedProjectId || state.currentProjectId,
    overview: state.overview, handoff: state.handoff,
    pageState: state._pageState, timelineIntentKey: state._timelineIntentKey,
    searchResults: state._searchResults, detailCache: state._detailCache,
  };
  const switching = Boolean(state._loadedProjectId && state._loadedProjectId !== projectId);
  beginViewRequest("search");
  state._searchBusy = false;
  if (switching) {
    closeDrawer({ history: "none" });
    state.overview = null;
    state.handoff = null;
    state._searchResults = null;
    state._timelineIntentKey = "";
    state._pageState = {};
    state._detailCache = new Map();
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
      state._timelineIntentKey = previous.timelineIntentKey;
      state._searchResults = previous.searchResults;
      state._detailCache = previous.detailCache;
      renderProjectSelector();
      renderView();
    } else {
      el.detailContent.innerHTML = emptyState({
        iconName: "blocker",
        title: t("Could not load this project."),
        body: error.message,
        extra: `<button type="button" class="secondary-btn" data-retry-project="${esc(projectId)}">${esc(t("Retry"))}</button>`,
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

  el.intentCount.textContent = (overview.active_intents?.length || 0) + (overview.other_intents?.length || 0) || "";
  el.decisionCount.textContent = (overview.active_decisions?.length || 0) + (overview.deprecated_decisions?.length || 0) || "";
  el.snapCount.textContent = overview.total_snaps ?? overview.recent_snaps?.length ?? "";
  updateSyncChip();
  revealActiveTab();

  if (!hasHistory()) {
    renderSetupGuide("unsynced");
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

async function loadProjects(route = readRoute()) {
  const request = beginViewRequest("projects");
  const result = await fetchJson(apiUrl("/api/v1/projects"));
  if (!ownsViewRequest("projects", request)) return;
  state.projects = result.projects;

  const requested = route.project || state.config.defaultProjectId;
  state.currentProjectId =
    requested && state.projects.some((p) => p.id === requested)
      ? requested
      : state.projects[0]?.id || null;

  renderProjectSelector();

  if (!state.currentProjectId) {
    state.overview = null;
    state.handoff = null;
    updateSyncChip();
    renderSetupGuide("unlinked");
    writeRoute("replace");
    return;
  }

  const detail = route.detail && DETAIL_PATHS[route.detailType] && projectIdFromRemoteId(route.detail) === state.currentProjectId
    ? { type: route.detailType, remoteId: route.detail }
    : null;
  await loadProject(state.currentProjectId, { detail });
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

function setSearchStatus(message = "", { visible = true, html = "" } = {}) {
  el.searchStatus.innerHTML = html || esc(message);
  el.searchStatus.classList.toggle("visually-hidden", !visible);
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
    ["snaps", t("Timeline"), "timeline"],
    ["decisions", t("Decisions"), "decision"],
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
  setSearchStatus(plural(matches.length, "{count} result", "{count} results"), { visible: false });
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
    setSearchStatus("", { html: `<p>${esc(error.message)}</p><button class="secondary-btn" type="button" data-retry-search>${esc(t("Retry"))}</button>` });
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
  if (loadingCopy) button.textContent = t(busy ? loadingCopy : idleCopy);
}

function setProjectPickerBusy(busy) {
  el.projectPickerTrigger.disabled = busy;
  el.projectPickerTrigger.setAttribute("aria-busy", String(busy));
}

function headerMenus() {
  const triggers = [...document.querySelectorAll("[data-settings-trigger]"), ...document.querySelectorAll("[data-resources-trigger]")];
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

async function createAccessToken(button) {
  if (button.disabled) return;
  const idle = button === el.tokenBtn ? "Access token" : "Create access token";
  setButtonBusy(button, true, "Creating token…", idle);
  try {
    const issued = await fetchJson(apiUrl("/api/v1/auth/tokens"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "CLI token", ttl_seconds: 7776000 }),
    });
    el.tokenOutput.value = issued.token;
    state._tokenReturnFocus = button === el.tokenBtn ? el.accountMenuTrigger : button;
    closeHeaderMenus();
    el.tokenDialog.showModal();
    el.tokenOutput.select();
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    setButtonBusy(button, false, "Creating token…", idle);
    if (button !== el.tokenBtn) button.innerHTML = `${icon("key")}${esc(t(idle))}`;
  }
}

function localizeWorkspace() {
  const pageScroll = window.scrollY;
  const sheetScroll = el.drawerContent.scrollTop;
  const expanded = [...document.querySelectorAll("details[open]")].map(node => node.dataset.archive || node.className);
  state._localizing = true;
  try {
    for (const button of document.querySelectorAll("[data-idle-copy]")) if (button.dataset.idleCopy) button.textContent = t(button.disabled ? button.dataset.loadingCopy : button.dataset.idleCopy);
    localizeViewLoadingCopy();
    const projectPending = Boolean(state._projectPending && ownsViewRequest("project", state._projectPending));
    el.detailContent.querySelector(".page-skeleton")?.setAttribute("aria-label", t("Loading continuation brief"));
    const pagePending = projectPending || el.detailPane.getAttribute("aria-busy") === "true";
    if (!projectPending) renderProjectSelector();
    if (!pagePending) {
      if (hasHistory()) renderView();
      else if (state.authenticated) renderSetupGuide(state.projects.length ? "unsynced" : "unlinked");
    }
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
    el.accountMode.textContent = t("Private session");
    if (state._statusMessage && el.statusLine.classList.contains("is-visible")) el.statusLine.textContent = t(state._statusMessage);
    if (state.config) updateSyncChip();
    setTenonLoginLoading(el.tenonLogin.classList.contains("is-loading"));
  } finally { state._localizing = false; }
}

function sheetFocusables() {
  return [...el.drawer.querySelectorAll("button, a[href], input, summary, [tabindex]")].filter(node => !node.disabled && !node.hidden && node.getAttribute("tabindex") !== "-1" && node.getClientRects().length);
}

async function applyRoute(route) {
  if (el.shell.inert && !sheetIsOpen()) return;
  if (route.project && route.project !== state.currentProjectId && state.projects.some((project) => project.id === route.project)) {
    state.activeTab = route.tab;
    setActiveTabUI();
    const detail = route.detail && DETAIL_PATHS[route.detailType] ? { type: route.detailType, remoteId: route.detail } : null;
    try { await loadProject(route.project, { detail, history: "none" }); }
    catch (error) { setStatus(error.message, true); }
    return;
  }
  if (route.tab !== state.activeTab) switchTab(route.tab, { history: "none" });
  if (route.detail && DETAIL_PATHS[route.detailType]) {
    if (state.selectedDetail?.remoteId !== route.detail) {
      try { await openDetail(route.detailType, route.detail, { history: "none" }); }
      catch (error) { setStatus(error.message, true); }
    }
  } else if (sheetIsOpen()) closeDrawer({ history: "none" });
}

function bindEvents() {
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
    if (el.tenonLogin.classList.contains("is-loading")) {
      event.preventDefault();
      return;
    }
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    setTenonLoginLoading(true);
  });

  window.addEventListener("pageshow", () => {
    setTenonLoginLoading(false);
    setButtonBusy(el.deleteAccountBtn, false, "Opening account management…", "Delete account");
  });

  el.deleteAccountBtn.addEventListener("click", async () => {
    if (el.deleteAccountBtn.disabled) return;
    setButtonBusy(el.deleteAccountBtn, true, "Opening account management…", "Delete account");
    try {
      const result = await fetchJson(apiUrl("/api/auth/tenon/delete/start"), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      });
      window.location.assign(productDeletionDestination(result));
    } catch (error) {
      setStatus(error.message, true);
      setButtonBusy(el.deleteAccountBtn, false, "Opening account management…", "Delete account");
    }
  });

  el.tokenBtn.addEventListener("click", () => createAccessToken(el.tokenBtn));

  el.tokenCopy.addEventListener("click", async () => {
    if (el.tokenCopy.disabled) return;
    setButtonBusy(el.tokenCopy, true, "Copying…", "Copy token");
    try {
      await navigator.clipboard.writeText(el.tokenOutput.value);
      setStatus(t("Token copied."));
    } catch {
      el.tokenOutput.select();
      setStatus(t("Copy failed. Select and copy the token manually."), true);
    } finally {
      setButtonBusy(el.tokenCopy, false, "Copying…", "Copy token");
    }
  });

  el.tokenDialog.addEventListener("close", () => {
    el.tokenOutput.value = "";
    el.tokenCopy.textContent = t("Copy token");
    const target = state._tokenReturnFocus?.isConnected ? state._tokenReturnFocus : el.accountMenuTrigger;
    state._tokenReturnFocus = null;
    if (target.isConnected) target.focus();
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
    if (!id || id === state.currentProjectId) return;
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
      await loadProjects({ ...readRoute(), detail: null });
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
  }, true);

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
    const createToken = e.target.closest("[data-create-token]");
    if (createToken) {
      await createAccessToken(createToken);
      return;
    }
    const jump = e.target.closest("[data-tab-jump]");
    if (jump) {
      switchTab(jump.dataset.tabJump);
      return;
    }
    const filter = e.target.closest("[data-timeline-intent]");
    if (filter) {
      state._timelineIntentKey = filter.dataset.timelineIntent;
      state._pageState ||= {};
      state._pageState.snaps = PAGE_SIZE;
      renderView();
      el.detailContent.querySelector(".timeline-filter-trigger")?.focus();
      return;
    }
    const loadMore = e.target.closest("#load-more-snaps, #load-more-intent-archive");
    if (loadMore) {
      const snaps = loadMore.id === "load-more-snaps";
      const selector = snaps ? ".timeline-entry" : ".intent-archive .list-row";
      const shown = el.detailContent.querySelectorAll(selector).length;
      state._pageState ||= {};
      if (snaps) state._pageState.snaps = (state._pageState.snaps || PAGE_SIZE) + PAGE_SIZE;
      else {
        state._pageState.intentArchive = (state._pageState.intentArchive || PAGE_SIZE) + PAGE_SIZE;
        state._pageState.intentArchiveOpen = true;
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
    if (el.aboutDialog.open || el.tokenDialog.open || el.searchDialog.open) return;
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k" && !el.shell.inert) {
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
    if (event.key === "/" && !typing && !event.metaKey && !event.ctrlKey && !event.altKey) {
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
    setActiveTabUI();
    await loadCurrentAccount();
    await loadProjects(route);
    hideAuthGate();
    if (route.search && state.currentProjectId) openSearch(route.q);
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
      extra: `<button type="button" class="secondary-btn" data-retry-init>${esc(t("Retry"))}</button>`,
    });
  }
}

init();

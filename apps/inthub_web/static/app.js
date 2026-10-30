const { t } = window.IntHubI18n;
window.IntHubI18n.bindStatic(document.body);

/* ---- State ---- */

const TABS = ["overview", "intents", "flow", "snaps", "decisions"];
const DETAIL_PATHS = { intent: "intents", decision: "decisions", snap: "snaps" };
const PAGE_SIZE = 30;
// One timeline page from /projects/{id}/snaps; the overview only carries the newest Snaps.
const SNAP_PAGE_SIZE = 50;
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
  flow: '<path d="M5.5 3v14"/><circle cx="14.5" cy="13" r="2.2"/><path d="M5.5 6.2c0 3.8 9 2.6 9 4.6"/>',
  focus: '<circle cx="10" cy="10" r="2.6"/><path d="M10 2.8v3M10 14.2v3M2.8 10h3M14.2 10h3"/>',
  hide: '<path d="M3 10s2.6-5 7-5 7 5 7 5-2.6 5-7 5-7-5-7-5Z"/><path d="m4 16 12-12"/>',
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

function commandSnippet(lines) {
  const text = lines.join("\n");
  return `<div class="snippet"><pre class="command-snippet">${esc(text)}</pre><button class="icon-button copy-button" type="button" data-copy="${esc(text)}" aria-label="${esc(t("Copy command"))}">${icon("copy")}</button></div>`;
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
    case "flow":
      renderFlowTab();
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
  const { attention } = relationContext(intent);
  return `
    <button class="list-row queue-item" type="button" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
      ${rowStatusIcon(intent.status)}
      <span class="row-main">
        <span class="row-title">${esc(intent.what)}</span>
        <span class="row-summary">${summary}</span>
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
  // Only rows a reader can see ask for their latest Snap; the archive asks when it opens.
  fetchMissingSnaps([...active, ...suspended, ...(archiveOpen ? visibleArchive : [])].map(latestSnapRemoteId));
}

/* Flow: Intents as nodes, relations as lines */

const FLOW_GEOMETRY = { nodeW: 188, nodeH: 88, gapX: 56, gapY: 30, padX: 32, padY: 24, inset: 18, bandLabel: 30, bandRow: 22 };
const FLOW_NODE_DECISIONS = 4;
const FLOW_BAND_ROWS = 3;
// Where vertical runs may sit inside a gap, as a share of its width, and where lines may meet a node's side.
const FLOW_TRACKS = [0.5, 0.3, 0.7, 0.15, 0.85];
const FLOW_PORTS = {
  flow: [0, -12, 12, -24, 24, -36, 36],
  depends: [12, 24, 36, 0, -12, -24, -36],
  conflict: [-12, -24, -36, 0, 12, 24, 36],
};
const FLOW_LINE_ORDER = ["branch", "rejoin", "flow", "depends", "conflict"];

function flowTime(object) {
  const time = Date.parse(object?.created_at || "");
  return Number.isFinite(time) ? time : 0;
}

function byCreation(left, right) {
  return flowTime(left) - flowTime(right) || String(left.id).localeCompare(String(right.id));
}

// Lay out the Flow graph: logical columns and lanes, pixel boxes and routed lines. Pure, no DOM.
// - Columns follow creation time and never go back; a parent or predecessor also pushes the
//   later Intent at least one column right.
// - Lanes are rows. A successor continues its predecessor's lane; parts and derived Intents open
//   lanes below their parent. Branches from later columns sit nearer their lane, so a parent's
//   trunk only crosses lanes whose nodes all lie further right.
// - Lines run in the gaps between columns and rows, never through a node box.
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

  // Project-level (sourceless) Decisions sit in a band at the top, at the column of their time.
  const knownDecisions = (decisions || []).filter((decision) => decision?.id);
  const hasSource = (decision) => Boolean(decision.source_intent_id) && byId.has(decision.source_intent_id);
  const columnAt = (time) => order.reduce((col, intent) => (flowTime(intent) <= time ? Math.max(col, colOf.get(intent.id)) : col), 0);
  const bandColumns = new Map();
  for (const decision of (focusId || !placed.length ? [] : knownDecisions.filter((entry) => !hasSource(entry))).sort(byCreation)) {
    const col = columnAt(flowTime(decision));
    bandColumns.set(col, [...(bandColumns.get(col) || []), decision]);
  }
  const bandItems = [];
  for (const [col, list] of bandColumns) {
    const listed = list.length > FLOW_BAND_ROWS ? list.slice(0, FLOW_BAND_ROWS - 1) : list;
    listed.forEach((decision, row) => bandItems.push({ decision, col, row }));
    if (list.length > listed.length) bandItems.push({ decision: null, col, row: listed.length, more: list.length - listed.length });
  }
  const bandRows = bandItems.reduce((most, item) => Math.max(most, item.row + 1), 0);
  const bandHeight = bandRows ? g.bandLabel + bandRows * g.bandRow + 14 : 0;

  const colX = (col) => g.padX + col * (g.nodeW + g.gapX);
  const top = g.padY + bandHeight;
  const rowY = (row) => top + row * (g.nodeH + g.gapY);
  const nodes = order.map((intent) => {
    const x = colX(colOf.get(intent.id));
    const y = rowY(lanes[laneOf.get(intent.id)].row);
    const { kind, anchor } = placement.get(intent.id);
    return { id: intent.id, intent, col: colOf.get(intent.id), lane: lanes[laneOf.get(intent.id)].row, x, y,
      cx: x + g.nodeW / 2, cy: y + g.nodeH / 2, placement: kind, anchor, decisions: [] };
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
  // Lines meeting the same side of a node do so at their own height.
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
    const rowLine = from.cy <= to.cy ? to.y - g.gapY / 2 : to.y + g.nodeH + g.gapY / 2;
    const sx = track(besideSource, y1, rowLine, prefer);
    const tx = track(besideTarget, rowLine, y2, prefer);
    return [[exitX, y1], [sx, y1], [sx, rowLine], [tx, rowLine], [tx, y2], [enterX, y2]];
  };
  const branch = (from, to) => {
    const trunk = from.x + g.inset;
    if (to.placement === "child" && to.anchor === from.id) return [[trunk, from.y + g.nodeH], [trunk, to.cy], [to.x, to.cy]];
    // A part that carries on another lane: leave the parent into the gap row beside it, run down the gap
    // after its column, cross on the gap row beside the part and enter it from above or below.
    const down = to.y >= from.y;
    const startX = from.x + g.nodeW - g.inset;
    const enter = to.x + g.inset;
    const sourceRow = down ? from.y + g.nodeH + g.gapY / 2 : from.y - g.gapY / 2;
    const targetRow = to.y > from.y ? to.y - g.gapY / 2 : to.y + g.nodeH + g.gapY / 2;
    const gx = track(from.col + 1, sourceRow, targetRow, 0.5);
    return [[startX, down ? from.y + g.nodeH : from.y], [startX, sourceRow], [gx, sourceRow], [gx, targetRow], [enter, targetRow], [enter, to.y > from.y ? to.y : to.y + g.nodeH]];
  };

  const lines = [];
  const laneEnd = new Map(lanes.map((lane) => [lane.row, nodeOf.get(lane.nodes.at(-1)).x + g.nodeW]));
  const ends = (link) => [nodeOf.get(link.target), nodeOf.get(link.subject)];
  const about = (link) => ({ type: link.type, subject: link.subject, target: link.target, state: link.state });
  const carried = (from, to) => to.lane === from.lane && lanes[laneOf.get(to.id)].nodes[lanes[laneOf.get(to.id)].nodes.indexOf(to.id) - 1] === from.id;
  const forked = (from, to) => to.placement === "branch" && to.anchor === from.id;
  // Structure first: branches, rejoins and successions along or off a lane keep the centre ports.
  for (const link of relations) {
    const [from, to] = ends(link);
    if (PARENT_RELATIONS.has(link.type)) {
      if (to.placement === "child" && to.anchor === from.id) reserve(to, "left");
      lines.push({ ...about(link), kind: "branch", points: branch(from, to) });
      // A part that has ended (done or dropped) rejoins its parent's lane.
      if (link.type === "part_of" && ENDED_STATUSES.has(to.intent.status) && to.lane !== from.lane) {
        reserve(to, "right");
        // Its last few pixels turn back along the parent's lane, so it keeps clear of the column edge.
        const gx = track(to.col + 1, to.cy, from.cy, 0.3, FLOW_TRACKS.filter((share) => share >= 0.3));
        lines.push({ ...about(link), kind: "rejoin", points: [[to.x + g.nodeW, to.cy], [gx, to.cy], [gx, from.cy], [gx - 12, from.cy]] });
        laneEnd.set(from.lane, Math.max(laneEnd.get(from.lane), gx));
      }
    } else if (link.type === "succeeds" && (carried(from, to) || forked(from, to))) {
      reserve(from, "right");
      reserve(to, "left");
      const gx = carried(from, to) ? 0 : track(from.col + 1, from.cy, to.cy, 0.5);
      lines.push({ ...about(link), kind: "flow", arrow: true, points: carried(from, to)
        ? [[from.x + g.nodeW, from.cy], [to.x, to.cy]]
        : [[from.x + g.nodeW, from.cy], [gx, from.cy], [gx, to.cy], [to.x, to.cy]] });
    }
  }
  for (const type of ["succeeds", "depends_on", "conflicts_with"]) {
    for (const link of relations.filter((entry) => entry.type === type)) {
      const [from, to] = ends(link);
      if (type === "succeeds" && !carried(from, to) && !forked(from, to)) {
        lines.push({ ...about(link), kind: "flow", arrow: true, points: connect(from, to, "flow", 0.5) });
      } else if (type === "depends_on") {
        lines.push({ ...about(link), kind: "depends", arrow: true, points: connect(from, to, "depends", 0.3) });
      } else if (type === "conflicts_with") {
        lines.push({ ...about(link), kind: "conflict", points: connect(from, to, "conflict", 0.85) });
      }
    }
  }
  lines.sort((left, right) => FLOW_LINE_ORDER.indexOf(left.kind) - FLOW_LINE_ORDER.indexOf(right.kind));
  // A lane line only runs on where an ended part comes back to join it.
  const lifelines = lanes.map((lane) => {
    const last = nodeOf.get(lane.nodes.at(-1));
    const x2 = laneEnd.get(lane.row);
    return x2 > last.x + g.nodeW + 1 ? { row: lane.row, x1: last.x + g.nodeW, x2, y: last.cy } : null;
  }).filter(Boolean);

  // Decisions with a source sit on that Intent's node, oldest first; a longer list is counted.
  for (const decision of knownDecisions.filter((entry) => hasSource(entry) && nodeOf.has(entry.source_intent_id)).sort(byCreation)) {
    nodeOf.get(decision.source_intent_id).decisions.push(decision);
  }
  // A band label may run on until the next Decision in its row, up to two columns.
  const markers = bandItems.map((item) => {
    const next = bandItems.filter((other) => other.row === item.row && other.col > item.col).reduce((nearest, other) => Math.min(nearest, other.col), item.col + 2);
    return {
      decision: item.decision, more: item.more || 0, source: "", band: true,
      x: colX(item.col) + 8, y: g.padY + g.bandLabel + item.row * g.bandRow,
      width: Math.min((Math.min(next, item.col + 2) - item.col) * (g.nodeW + g.gapX) - 40, colX(maxCol) + g.nodeW - colX(item.col) - 8),
    };
  });
  for (const node of nodes) {
    const shown = node.decisions.slice(0, FLOW_NODE_DECISIONS);
    shown.forEach((decision, index) => {
      markers.push({ decision, source: node.id, x: node.x + g.nodeW - 18 - (shown.length - 1 - index) * 17, y: node.y + g.nodeH - 15 });
    });
  }

  const reach = Math.max(colX(maxCol) + g.nodeW + g.padX, ...lines.flatMap((line) => line.points.map((point) => point[0] + 16)), ...lifelines.map((line) => line.x2 + 16));
  return {
    geometry: g, hasRelations: links.length > 0, focus: focusId, relations, standalone,
    nodes: [...nodes].sort((left, right) => left.lane - right.lane || left.col - right.col),
    lines, lifelines, markers,
    width: nodes.length ? Math.ceil(reach) : 0,
    height: nodes.length ? Math.ceil(rowY(rows.length - 1) + g.nodeH + g.padY) : 0,
    columns: nodes.length ? maxCol + 1 : 0, lanes: rows.length,
    band: bandHeight ? { y: 10, height: g.padY + g.bandLabel + (bandRows - 1) * g.bandRow + 2, labelY: 31 } : null,
  };
}

const FLOW_WIDE = /[\u1100-\u115f\u2e80-\ua4cf\uac00-\ud7a3\uf900-\ufaff\ufe30-\ufe4f\uff00-\uff60\uffe0-\uffe6]/;

// SVG text does not wrap, so titles are fitted by an estimate that errs on the narrow side.
function flowTextWidth(text, size) {
  let units = 0;
  for (const char of String(text)) {
    units += FLOW_WIDE.test(char) ? 1 : char === " " ? 0.3 : /[ijlrtf.,:;'|!()[\]]/.test(char) ? 0.36 : /[A-Z0-9mwMW@#%&]/.test(char) ? 0.72 : 0.6;
  }
  return units * size;
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

function flowLines(text, maxWidth, size = 13, maxLines = 2) {
  const fits = (value) => flowTextWidth(value, size) <= maxWidth;
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

// An orthogonal polyline with rounded corners.
function flowPath(points, radius = 8) {
  const list = points.filter((point, index) => !index || point[0] !== points[index - 1][0] || point[1] !== points[index - 1][1]);
  if (list.length < 2) return "";
  let path = `M${flowNumber(list[0][0])} ${flowNumber(list[0][1])}`;
  for (let index = 1; index < list.length - 1; index++) {
    const [px, py] = list[index - 1];
    const [x, y] = list[index];
    const [nx, ny] = list[index + 1];
    const inLength = Math.hypot(x - px, y - py);
    const outLength = Math.hypot(nx - x, ny - y);
    const r = Math.min(radius, inLength / 2, outLength / 2);
    path += ` L${flowNumber(x - (x - px) / inLength * r)} ${flowNumber(y - (y - py) / inLength * r)}`
      + ` Q${flowNumber(x)} ${flowNumber(y)} ${flowNumber(x + (nx - x) / outLength * r)} ${flowNumber(y + (ny - y) / outLength * r)}`;
  }
  const [lx, ly] = list.at(-1);
  return `${path} L${flowNumber(lx)} ${flowNumber(ly)}`;
}

function flowEnd(points) {
  const [x, y] = points.at(-1);
  for (let index = points.length - 2; index >= 0; index--) {
    const [px, py] = points[index];
    const length = Math.hypot(x - px, y - py);
    if (length) return { x, y, ux: (x - px) / length, uy: (y - py) / length, length };
  }
  return { x, y, ux: 1, uy: 0, length: 0 };
}

function flowArrow(points, size) {
  const { x, y, ux, uy } = flowEnd(points);
  const bx = x - ux * size;
  const by = y - uy * size;
  const half = size * 0.55;
  return `M${flowNumber(x)} ${flowNumber(y)} L${flowNumber(bx - uy * half)} ${flowNumber(by + ux * half)} L${flowNumber(bx + uy * half)} ${flowNumber(by - ux * half)} Z`;
}

// Stop the stroke short of an arrow tip so a thick line never pokes through it.
function flowTrim(points, by) {
  const { ux, uy, length } = flowEnd(points);
  if (length <= by) return points;
  const list = points.map((point) => [...point]);
  list[list.length - 1] = [list.at(-1)[0] - ux * by, list.at(-1)[1] - uy * by];
  return list;
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
  const size = line.kind === "flow" ? 10 : 7;
  const d = flowPath(line.arrow ? flowTrim(line.points, size * 0.7) : line.points);
  const state = relationStateLabel(line.state);
  const title = `${line.subject} · ${relationLabel(line.type, "out")} · ${line.target}${state ? ` · ${state}` : ""}`;
  const settled = line.state === "resolved" ? " is-settled" : "";
  let mark = "";
  if (line.kind === "conflict") {
    const [mx, my] = flowMidpoint(line.points);
    mark = `<g class="flow-vs"><rect x="${flowNumber(mx - 12)}" y="${flowNumber(my - 8)}" width="24" height="16" rx="8"/><text x="${flowNumber(mx)}" y="${flowNumber(my + 3.5)}" text-anchor="middle">vs</text></g>`;
  }
  return `<g class="flow-line flow-${line.kind} flow-type-${line.type} tone-${flowLineTone(line)}${settled}"><title>${esc(title)}</title><path class="flow-hit-line" d="${d}"/><path class="flow-stroke" d="${d}"/>${line.arrow ? `<path class="flow-arrow" d="${flowArrow(line.points, size)}"/>` : ""}${mark}</g>`;
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

function flowNodeSvg(node, layout) {
  const g = layout.geometry;
  const intent = node.intent;
  const status = ["active", "suspend", "done", "cancelled"].includes(intent.status) ? intent.status : "unknown";
  const title = flowLines(intent.what || intent.id, g.nodeW - 24, 13, 2);
  const more = node.decisions.length - FLOW_NODE_DECISIONS;
  return `<g class="flow-node status-${status}${layout.focus === node.id ? " is-focus" : ""}" role="button" tabindex="0" data-detail-type="intent" data-remote-id="${esc(intent.remote_id || remoteId(intent.project_id, intent.id))}" aria-label="${esc(flowNodeLabel(node, layout))}" transform="translate(${flowNumber(node.x)} ${flowNumber(node.y)})">
    <title>${esc(intent.what || intent.id)}</title>
    <rect class="flow-node-ring" x="-4" y="-4" width="${g.nodeW + 8}" height="${g.nodeH + 8}" rx="14"/>
    <rect class="flow-node-box" width="${g.nodeW}" height="${g.nodeH}" rx="10"/>
    <circle class="flow-node-dot" cx="16" cy="18" r="3.5"/>
    <text class="flow-node-status" x="26" y="22">${esc(intentStatusLabel(intent.status))}</text>
    <text class="flow-node-id" x="${g.nodeW - 12}" y="22" text-anchor="end">${esc(intent.id)}</text>
    ${title.map((line, index) => `<text class="flow-node-title" x="12" y="${43 + index * 17}">${esc(line)}</text>`).join("")}
    <text class="flow-node-meta" x="12" y="${g.nodeH - 11}">${esc(plural((intent.snap_ids || []).length, "{count} snap", "{count} snaps"))}</text>
    ${more > 0 ? `<text class="flow-node-meta" x="${g.nodeW - 12 - FLOW_NODE_DECISIONS * 17}" y="${g.nodeH - 11}" text-anchor="end">+${more}</text>` : ""}
  </g>`;
}

function flowDecisionSvg(marker) {
  const { x, y } = marker;
  if (!marker.decision) return `<text class="flow-band-more" x="${flowNumber(x - 6)}" y="${flowNumber(y + 4)}">+${marker.more}</text>`;
  const decision = marker.decision;
  const diamond = (size) => `M${flowNumber(x)} ${flowNumber(y - size)} L${flowNumber(x + size)} ${flowNumber(y)} L${flowNumber(x)} ${flowNumber(y + size)} L${flowNumber(x - size)} ${flowNumber(y)} Z`;
  const label = `${t("Decision")} ${decision.id}: ${decision.what || ""} (${decisionStatusLabel(decision.status)}${marker.source ? "" : ` · ${t("Project-level")}`})`;
  // In the Project band a Decision also shows its words; on a node it is only a diamond.
  const text = marker.band ? flowLines(decision.what || decision.id, marker.width - 16, 12, 1)[0] || "" : "";
  const hitWidth = text ? 26 + flowTextWidth(text, 12) : 20;
  return `<g class="flow-decision${decision.status === "deprecated" ? " is-deprecated" : ""}" role="button" tabindex="0" data-detail-type="decision" data-remote-id="${esc(decision.remote_id || remoteId(decision.project_id, decision.id))}" aria-label="${esc(label)}">
    <title>${esc(`${decision.id} · ${decision.what || ""}`)}</title>
    <rect class="flow-hit" x="${flowNumber(x - 10)}" y="${flowNumber(y - 10)}" width="${flowNumber(hitWidth)}" height="20" rx="5"/>
    <path class="flow-decision-ring" d="${diamond(10)}"/>
    <path class="flow-decision-shape" d="${diamond(6)}"/>
    ${text ? `<text class="flow-band-text" x="${flowNumber(x + 14)}" y="${flowNumber(y + 4)}">${esc(text)}</text>` : ""}
  </g>`;
}

function renderFlowSvg(layout) {
  if (!layout.nodes.length) return "";
  const g = layout.geometry;
  const band = layout.band
    ? `<g class="flow-band" aria-hidden="true"><rect class="flow-band-box" x="10" y="${layout.band.y}" width="${layout.width - 20}" height="${flowNumber(layout.band.height)}" rx="10"/><text class="flow-band-label" x="${g.padX - 8}" y="${layout.band.labelY}">${esc(t("Project"))}</text></g>`
    : "";
  const lifelines = layout.lifelines.map((line) => `<path class="flow-lifeline" d="M${flowNumber(line.x1)} ${flowNumber(line.y)} H${flowNumber(line.x2)}"/>`).join("");
  const markersOf = (source) => layout.markers.filter((marker) => marker.source === source).map(flowDecisionSvg).join("");
  // Reading order: the project band, then each node followed by its own Decisions.
  const nodes = layout.nodes.map((node) => flowNodeSvg(node, layout) + markersOf(node.id)).join("");
  return `<svg class="flow-svg" width="${layout.width}" height="${layout.height}" viewBox="0 0 ${layout.width} ${layout.height}" role="group" aria-label="${esc(t("Flow between Intents"))}">
    ${band}
    <g class="flow-lines" aria-hidden="true">${lifelines}${layout.lines.map(flowLineSvg).join("")}</g>
    ${markersOf("")}
    ${nodes}
  </svg>`;
}

function flowLegend() {
  const sample = (className, d, extra = "") => `<svg class="flow-legend-sample" viewBox="0 0 32 16" aria-hidden="true"><g class="flow-line ${className}"><path class="flow-stroke" d="${d}"/>${extra}</g></svg>`;
  const items = [
    [sample("flow-branch flow-type-part_of tone-neutral", "M4 1V8Q4 13 9 13H30"), t("Part of")],
    [sample("flow-branch flow-type-derived_from tone-neutral", "M4 1V8Q4 13 9 13H30"), t("Derived from")],
    [sample("flow-flow flow-type-succeeds tone-neutral", "M2 8H22", '<path class="flow-arrow" d="M30 8L21 3V13Z"/>'), t("Succeeds")],
    [sample("flow-depends flow-type-depends_on tone-neutral", "M2 8H25", '<path class="flow-arrow" d="M30 8L24 4.5V11.5Z"/>'), t("Depends on")],
    [sample("flow-conflict flow-type-conflicts_with tone-neutral", "M1 8H31"), t("Conflicts with")],
    [sample("flow-depends tone-attention", "M2 8H30"), t("Needs attention")],
    [sample("flow-depends tone-settled", "M2 8H30"), t("Satisfied")],
    [sample("flow-depends tone-danger", "M2 8H30"), t("Broken")],
    [`<svg class="flow-legend-sample is-mark" viewBox="0 0 16 16" aria-hidden="true"><g class="flow-decision"><path class="flow-decision-shape" d="M8 2L14 8L8 14L2 8Z"/></g></svg>`, t("Decision")],
    [`<svg class="flow-legend-sample is-mark" viewBox="0 0 16 16" aria-hidden="true"><g class="flow-decision is-deprecated"><path class="flow-decision-shape" d="M8 2L14 8L8 14L2 8Z"/></g></svg>`, t("Deprecated")],
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
        <summary class="timeline-filter-trigger" title="${esc(t("Focus on one Intent and its direct relations"))}">${icon("focus")}<span>${esc(focused ? truncate(focused.what || focused.id, 36) : t("Focus on…"))}</span>${icon("chevronDown")}</summary>
        <div class="timeline-filter-menu">${option("", t("All Intents"))}${options.map((intent) => option(intent.id, intent.what || intent.id, intent.id)).join("")}</div>
      </details>
    </div>`;
}

function flowCard(intent, decisions) {
  const snaps = (intent.snap_ids || []).length;
  return `
    <button type="button" class="flow-card flow-card-${esc(intent.status)}" data-detail-type="intent" data-remote-id="${esc(intent.remote_id || remoteId(intent.project_id, intent.id))}">
      <span class="flow-card-top">${statusBadge(intent.status)}<span class="row-id">${esc(intent.id)}</span></span>
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
      ${layout.standalone.length > cards.length ? `<button type="button" class="load-more-btn" id="load-more-flow-standalone">${esc(t("Load more ({count})", {count: layout.standalone.length - cards.length}))}</button>` : ""}
    </section>` : "";
  el.detailContent.innerHTML = `<div class="flow-page">${header}${flowLegend()}${canvas}${standalone}</div>`;
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

function snapPageUrl(projectId, { offset = 0, limit = SNAP_PAGE_SIZE, intentId = "" } = {}) {
  const query = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (intentId) query.set("intent_id", intentId);
  return apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/snaps?${query}`);
}

function resetTimeline(intentId = "") {
  state._timeline = { projectId: state.currentProjectId, intentId, snaps: [], total: null, hasMore: false, loaded: false, loading: false, error: "" };
  return state._timeline;
}

// Pages are newest first; the server filters by Intent. A newer timeline (filter, project) owns the view.
async function loadTimelinePage() {
  const timeline = state._timeline;
  if (!timeline || timeline.loading || (timeline.loaded && !timeline.hasMore)) return;
  timeline.loading = true;
  timeline.error = "";
  try {
    const page = await fetchJson(snapPageUrl(timeline.projectId, { offset: timeline.snaps.length, intentId: timeline.intentId }));
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
  renderView();
  if (refocus) el.detailContent.querySelector(".timeline-filter-trigger")?.focus();
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

function renderTimeline(timeline) {
  const groups = [];
  for (const snap of timeline.snaps) {
    const date = timelineDate(snap.created_at);
    const current = groups.at(-1);
    if (!current || current.key !== date.key) {
      groups.push({ key: date.key, label: date.label, snaps: [snap] });
    } else {
      current.snaps.push(snap);
    }
  }

  const remaining = Math.max(0, (timeline.total ?? timeline.snaps.length) - timeline.snaps.length);
  const more = timeline.hasMore
    ? `<button type="button" class="load-more-btn" id="load-more-snaps"${timeline.loading ? ' disabled aria-busy="true"' : ""}>${esc(timeline.loading ? t("Loading…") : t("Load more ({count})", {count: remaining}))}</button>`
    : "";
  return groups
    .map((group) => `
      <section class="timeline-group">
        <h2 class="timeline-day"><span>${esc(group.label)}</span><span>${group.snaps.length}</span></h2>
        <div class="timeline-events">${group.snaps.map(snapTimelineEntry).join("")}</div>
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
  if (timeline.intentId && !options.some((option) => option.key === timeline.intentId)) timeline = resetTimeline("");
  const selected = options.find((option) => option.key === timeline.intentId);
  const optionHtml = (key, label, count) => `<button type="button" class="timeline-filter-option${timeline.intentId === key ? " is-selected" : ""}" data-timeline-intent="${esc(key)}" aria-pressed="${timeline.intentId === key}"><span>${esc(label)}</span><small>${count}</small></button>`;
  const filter = `
    <div class="timeline-toolbar">
      <details class="timeline-filter">
        <summary class="timeline-filter-trigger" title="${esc(t("Filter timeline by Intent"))}"><span>${esc(selected ? truncate(selected.label, 44) : t("All Intents"))}</span>${icon("chevronDown")}</summary>
        <div class="timeline-filter-menu">${optionHtml("", t("All Intents"), total)}${options.map((option) => optionHtml(option.key, option.label, option.count)).join("")}</div>
      </details>
    </div>`;
  const count = timeline.total ?? (selected ? selected.count : total);
  const body = !timeline.loaded
    ? timeline.error
      ? `<div class="empty-state"><p>${esc(timeline.error)}</p><button type="button" class="secondary-btn" data-retry-timeline>${esc(t("Retry"))}</button></div>`
      : viewLoadingHtml()
    : timeline.snaps.length
      ? renderTimeline(timeline)
      : `<div class="inline-empty">${esc(t("No snaps synced yet."))}</div>`;
  el.detailContent.innerHTML = pageHeader({
    title: t("Timeline"),
    meta: [esc(plural(count, "{count} checkpoint", "{count} checkpoints")), esc(selected ? truncate(selected.label, 60) : t("All Intents"))],
    actions: filter,
  }) + `<div class="timeline" aria-busy="${timeline.loading || !timeline.loaded && !timeline.error}">${body}</div>`;
  if (!timeline.loaded && !timeline.loading && !timeline.error) loadTimelinePage();
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
      ${detailMeta([statusBadge(intent.status), idChip(intent.id), originBadge(intent.origin), `<span>${esc(t("Created {time}", {time: fmtDate(intent.created_at)}))}</span>`])}
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
      ${detailMeta([statusBadge(decision.status, "decision"), idChip(decision.id), originBadge(decision.origin), `<span>${esc(t("Created {time}", {time: fmtDate(decision.created_at)}))}</span>`])}
      <h2 class="detail-title" tabindex="-1">${esc(decision.what)}</h2>
      <p class="detail-context decision-detail-scope">${esc(decision.status === "active" ? t("Current cross-Intent constraint") : t("Deprecated constraint history"))} · ${esc(scopeSummary)}</p>
    </div>
    ${detailSection(t("Why"), formatText(decision.why) || `<p>${esc(t("No why provided."))}</p>`)}
    ${decision.reason ? detailSection(t("Reason"), formatText(decision.reason)) : ""}
    ${decisionSourceSection(payload)}
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
    pageState: state._pageState, timeline: state._timeline, flow: state._flow,
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
  state._snapFailed = new Set();
  // The timeline pages again from the new revision, keeping the reader's Intent filter.
  resetTimeline(state._timeline?.projectId === projectId ? state._timeline.intentId : "");

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
      resetTimeline(filter.dataset.timelineIntent);
      renderView();
      el.detailContent.querySelector(".timeline-filter-trigger")?.focus();
      return;
    }
    if (e.target.closest("[data-retry-timeline]")) {
      if (state._timeline) state._timeline.error = "";
      renderView();
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

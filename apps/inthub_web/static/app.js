const { t } = window.IntHubI18n;
window.IntHubI18n.bindStatic(document.body);

/* ---- State ---- */

const TABS = ["overview", "intents", "snaps", "decisions", "search"];
const DETAIL_PATHS = { intent: "intents", decision: "decisions", snap: "snaps" };

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
  publicProfile: null,
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
  syncChip: document.getElementById("sync-chip"),
  syncIndicator: document.getElementById("sync-indicator"),
  apiChip: document.getElementById("api-chip"),
  tabBar: document.querySelector(".tab-bar"),
  sidebarKicker: document.getElementById("sidebar-kicker"),
  sidebarTitle: document.getElementById("sidebar-title"),
  sidebarBody: document.getElementById("sidebar-body"),
  detailPane: document.getElementById("detail-pane"),
  detailContent: document.getElementById("detail-content"),
  backBtn: document.getElementById("back-btn"),
  statusLine: document.getElementById("status-line"),
  intentCount: document.getElementById("intent-count"),
  decisionCount: document.getElementById("decision-count"),
  snapCount: document.getElementById("snap-count"),
  drawer: document.getElementById("drawer"),
  drawerOverlay: document.getElementById("drawer-overlay"),
  drawerClose: document.getElementById("drawer-close"),
  drawerContent: document.getElementById("drawer-content"),
  logoutBtn: document.getElementById("logout-btn"),
  tokenBtn: document.getElementById("token-btn"),
  tokenDialog: document.getElementById("token-dialog"),
  tokenOutput: document.getElementById("token-output"),
  tokenCopy: document.getElementById("token-copy"),
  accountControl: document.getElementById("account-control"),
  accountAvatar: document.getElementById("account-avatar"),
  accountLabel: document.getElementById("account-label"),
  accountMode: document.getElementById("account-mode"),
  accountMenuTrigger: document.getElementById("account-menu-trigger"),
  accountActions: document.getElementById("account-actions"),
  authGate: document.getElementById("auth-gate"),
  authError: document.getElementById("auth-error"),
  tenonLogin: document.getElementById("tenon-login"),
  tenonLoginLabel: document.getElementById("tenon-login-label"),
  navHealth: document.getElementById("nav-health"),
  navContextLabel: document.getElementById("nav-context-label"),
  brandLinks: document.querySelectorAll("[data-brand-link]"),
  aboutDialog: document.getElementById("about-dialog"),
  aboutClose: document.getElementById("about-close"),
  aboutVersion: document.getElementById("about-version"),
};

/* ---- Helpers ---- */

function esc(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function fmtDate(v) {
  if (!v) return "\u2014";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  const pad = (part) => String(part).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function relativeDate(v) {
  if (!v) return t("Never synced");
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return String(v);
  const seconds = Math.round((d.getTime() - Date.now()) / 1000);
  const abs = Math.abs(seconds);
  const formatter = new Intl.RelativeTimeFormat(window.IntHubI18n.language, { numeric: "auto" });
  if (abs < 60) return formatter.format(seconds, "second");
  if (abs < 3600) return formatter.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return formatter.format(Math.round(seconds / 3600), "hour");
  if (abs < 2592000) return formatter.format(Math.round(seconds / 86400), "day");
  return fmtDate(v);
}

function shortCommit(v) {
  return v ? v.slice(0, 8) : "\u2014";
}

function truncate(v, n = 140) {
  if (!v || v.length <= n) return v || "";
  return v.slice(0, n).trimEnd() + "\u2026";
}

function accountInitials(account) {
  const label = String(account?.display_name || account?.login || "IntHub").trim();
  const compact = label.replace(/\s+/g, "");
  if (!compact) return "IH";
  if (/[^\u0000-\u00ff]/.test(compact)) return Array.from(compact).slice(0, 2).join("");
  const words = label.split(/\s+/).filter(Boolean);
  if (words.length > 1) {
    return `${words[0][0]}${words.at(-1)[0]}`.toUpperCase();
  }
  return compact.slice(0, 2).toUpperCase();
}

function accountAvatarTone(account) {
  const seed = String(account?.login || account?.display_name || "inthub");
  const hash = Array.from(seed).reduce((total, char) => total + char.codePointAt(0), 0);
  return String(hash % 4);
}

function formatText(v) {
  if (!v) return "";
  const safe = esc(v);
  const hasChinese = /\u3002/.test(safe);
  const splitter = hasChinese ? "\u3002" : /(?<=\.)\s+/;
  const suffix = hasChinese ? "\u3002" : "";
  const parts = safe
    .split(splitter)
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length <= 1) return `<p>${safe}</p>`;
  return parts
    .map((p) => `<p>${p.replace(/\uff1b/g, "\uff1b<br>")}${suffix}</p>`)
    .join("");
}

function statusBadge(status) {
  const cls = status ? ` status-${status}` : "";
  return `<span class="badge${cls}">${esc(intentStatusLabel(status))}</span>`;
}

function originBadge(origin) {
  if (!origin) return "";
  const slug = origin.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `<span class="badge origin-${slug}">${esc(origin)}</span>`;
}

function dirtyBadge(dirty) {
  return dirty
    ? `<span class="badge warn">${esc(t("dirty"))}</span>`
    : `<span class="badge good">${esc(t("clean"))}</span>`;
}

function remoteId(wksId, objId) {
  return `${wksId}__${objId}`;
}

function workspaceIdFromRemoteId(rId) {
  return String(rId || "").split("__", 1)[0] || "";
}

function apiUrl(path) {
  if (state.config?.publicMode) {
    const slug = encodeURIComponent(state.config.publicProfileSlug);
    const publicPrefix = `/api/v1/public-profiles/${slug}`;
    if (path === "/api/v1") return `${state.config.apiBaseUrl}${publicPrefix}`;
    if (path.startsWith("/api/v1/")) {
      return `${state.config.apiBaseUrl}${publicPrefix}${path.slice("/api/v1".length)}`;
    }
  }
  return `${state.config.apiBaseUrl}${path}`;
}

function configUrl() {
  return window.location.pathname === "/showcase" || window.location.pathname.startsWith("/showcase/")
    ? "/showcase/config.json"
    : "/config.json";
}

// A newer action owns its view. Late responses may finish, but cannot replace it.
function beginViewRequest(view) {
  state._requestVersions ||= {};
  return state._requestVersions[view] = (state._requestVersions[view] || 0) + 1;
}

function ownsViewRequest(view, request) {
  return state._requestVersions?.[view] === request;
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
  state.authenticated = true;
  el.shell.classList.remove("is-locked");
  el.authGate.classList.add("is-hidden");
  const publicMode = Boolean(state.config?.publicMode);
  el.shell.classList.toggle("is-public-view", publicMode);
  el.accountControl.classList.toggle(
    "is-hidden",
    !(state.config?.authRequired || publicMode),
  );
  el.accountMode.classList.toggle("is-hidden", !publicMode);
  el.tokenBtn.classList.toggle("is-hidden", publicMode);
  el.logoutBtn.classList.toggle("is-hidden", publicMode);
  el.accountMenuTrigger.disabled = publicMode;
  const account = state.account;
  el.accountLabel.textContent = account
    ? state.publicProfile?.title || account.display_name || `@${account.login}`
    : t("Private session");
  el.accountAvatar.textContent = accountInitials(account);
  el.accountAvatar.dataset.tone = accountAvatarTone(account);
  el.authError.textContent = "";
  el.authError.classList.add("is-hidden");
}

async function loadCurrentAccount() {
  if (state.config?.authMode !== "tenon") return;
  const result = await fetchJson(apiUrl("/api/v1/auth/me"));
  state.account = result.account;
}

async function loadPublicProfile() {
  const result = await fetchJson(apiUrl("/api/v1"));
  state.publicProfile = result.profile;
  state.account = result.profile.account;
  el.projectPickerEyebrow.textContent = t("Public collection");
  el.navContextLabel.textContent = t("Published memory");
  for (const link of el.brandLinks) link.href = "/showcase";
  document.title = `${result.profile.title} · IntHub`;
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
  return {
    project: p.get("project"),
    tab: p.get("tab") || "overview",
    detail: p.get("detail"),
    detailType: p.get("detailType"),
    q: p.get("q") || "",
  };
}

function writeRoute() {
  const p = new URLSearchParams();
  if (state.currentProjectId) p.set("project", state.currentProjectId);
  if (state.activeTab !== "overview") p.set("tab", state.activeTab);
  if (state.selectedDetail) {
    p.set("detail", state.selectedDetail.remoteId);
    p.set("detailType", state.selectedDetail.type);
  }
  if (state.searchQuery) p.set("q", state.searchQuery);
  const q = p.toString();
  window.history.replaceState(
    {},
    "",
    q ? `${window.location.pathname}?${q}` : window.location.pathname,
  );
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
    if (!isError) el.statusLine.classList.remove("is-visible");
  }, 2600);
}

/* ---- Tab switching ---- */

async function switchTab(tab) {
  if (!TABS.includes(tab)) return;
  if (state.activeTab === tab && state.overview) {
    if (tab !== "overview") returnToList();
    if (tab === "search") document.getElementById("search-input")?.focus();
    return;
  }
  beginViewRequest("detail");
  beginViewRequest("search");
  state._searchBusy = false;
  state._detailPayload = null;
  state.selectedDetail = null;
  state.activeTab = tab;
  el.shell.dataset.activeTab = tab;
  el.shell.classList.remove("detail-open");
  closeDrawer();
  for (const btn of el.tabBar.querySelectorAll(".tab")) {
    btn.classList.toggle("is-active", btn.dataset.tab === tab);
    if (btn.dataset.tab === tab) btn.setAttribute("aria-current", "page");
    else btn.removeAttribute("aria-current");
  }
  renderSidebar();
  writeRoute();

  if (tab === "overview") {
    state.selectedDetail = null;
    if (state.overview) renderProjectSummary();
    else clearDetail(t("Link a project to build a continuation brief."));
    return;
  }

  if (tab === "search") {
    state.selectedDetail = null;
    el.detailContent.innerHTML = renderSearchWelcome();
    window.setTimeout(() => document.getElementById("search-input")?.focus(), 0);
    return;
  }

  // Keep list and detail in sync for object views.
  const firstCard = el.sidebarBody.querySelector("[data-detail-type][data-remote-id]");
  if (firstCard) {
    const tabButton = el.tabBar.querySelector(`[data-tab="${tab}"]`);
    if (tabButton) setButtonBusy(tabButton, true);
    try {
      await openDetail(firstCard.dataset.detailType, firstCard.dataset.remoteId, { reveal: false });
    } catch (error) { setStatus(error.message, true); }
    finally { if (tabButton) setButtonBusy(tabButton, false); }
  } else clearDetail(t("No object is available in this view."));
}

/* ---- Selected card sync ---- */

function syncSelected() {
  for (const node of document.querySelectorAll(
    "[data-detail-type][data-remote-id]",
  )) {
    const sel =
      state.selectedDetail &&
      node.dataset.detailType === state.selectedDetail.type &&
      node.dataset.remoteId === state.selectedDetail.remoteId;
    node.classList.toggle("is-selected", Boolean(sel));
    if (sel) node.setAttribute("aria-current", "true");
    else node.removeAttribute("aria-current");
  }
}

/* ---- Render helpers ---- */

function commandSnippet(lines) {
  return `<pre class="command-snippet">${esc(lines.join("\n"))}</pre>`;
}

function detailSection(title, body) {
  return `<div class="detail-section"><h4 class="detail-section-title">${esc(title)}</h4>${body}</div>`;
}

function kvRow(label, value) {
  return `<div class="detail-kv-row"><span class="detail-kv-label">${esc(label)}</span><span class="detail-kv-value">${esc(value)}</span></div>`;
}

function linkButton(type, rId, label, meta) {
  return `<button type="button" class="detail-link" data-detail-type="${esc(type)}" data-remote-id="${esc(rId)}"><span class="detail-link-label">${esc(label)}</span>${meta ? `<span class="detail-link-meta">${esc(meta)}</span>` : ""}</button>`;
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
    <span class="relation-id"><span class="badge">${esc(id)}</span>${status ? statusBadge(status) : ""}</span>
    <span class="relation-title">${esc(title)}</span>
    ${meta ? `<span class="relation-meta">${esc(meta)}</span>` : ""}
  </button>`;
}

function relatedLinks(items, emptyMsg) {
  return items.length
    ? `<div class="detail-link-list">${items.join("")}</div>`
    : `<div class="empty-state">${esc(emptyMsg)}</div>`;
}

function rawToggle(data) {
  return `<details class="raw-toggle"><summary>${esc(t("Raw JSON"))}</summary><pre class="raw-pre">${esc(JSON.stringify(data, null, 2))}</pre></details>`;
}

/* ---- Sidebar rendering ---- */

function renderSidebar() {
  if (!state.overview) {
    el.sidebarBody.innerHTML =
      `<div class="empty-state">${esc(t("Loading project data…"))}</div>`;
    return;
  }
  switch (state.activeTab) {
    case "overview":
      el.sidebarKicker.textContent = t("Current work");
      el.sidebarTitle.textContent = t("Continuation queue");
      renderContinuationQueue();
      break;
    case "intents":
      el.sidebarKicker.textContent = t("Semantic goals");
      el.sidebarTitle.textContent = t("Intents");
      renderIntentsTab();
      break;
    case "decisions":
      el.sidebarKicker.textContent = t("Project constraints");
      el.sidebarTitle.textContent = t("Decisions");
      renderDecisionsTab();
      break;
    case "snaps":
      el.sidebarKicker.textContent = t("Semantic history");
      el.sidebarTitle.textContent = t("Timeline");
      renderSnapsTab();
      break;
    case "search":
      el.sidebarKicker.textContent = t("Find context");
      el.sidebarTitle.textContent = t("Search");
      renderSearchTab();
      break;
  }
  syncSelected();
}

function queueItem(intent, section) {
  const snap = intent.latest_snap;
  const summary = snap?.what || intent.why || t("No continuation checkpoint recorded.");
  return `
    <button class="queue-item" type="button" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
      <span class="queue-item-title">${esc(intent.what)}</span>
      <span class="queue-item-summary">${esc(truncate(summary, 150))}</span>
      <span class="queue-item-meta">
        ${statusBadge(intent.status)}
        <span class="badge">${esc(intent.id)}</span>
        ${snap ? `<span class="badge">${esc(snap.id)}</span>` : `<span class="badge warn">${esc(t("checkpoint missing"))}</span>`}
      </span>
    </button>`;
}

function renderContinuationQueue() {
  const active = state.handoff?.intents || [];
  const suspended = state.handoff?.suspended_intents || [];
  const activeBody = active.length
    ? active.map((intent) => queueItem(intent, "active")).join("")
    : `<div class="queue-empty">${esc(t("No active Intent. The project has no explicit current objective."))}</div>`;
  const suspendedBody = suspended.length
    ? suspended.map((intent) => queueItem(intent, "suspended")).join("")
    : `<div class="queue-empty">${esc(t("No suspended work waiting to resume."))}</div>`;

  el.sidebarBody.innerHTML = `
    <section class="queue-group">
      <div class="queue-heading">${esc(t("Active"))} · ${active.length}</div>
      ${activeBody}
    </section>
    <section class="queue-group">
      <div class="queue-heading">${esc(t("Suspended"))} · ${suspended.length}</div>
      ${suspendedBody}
    </section>`;
}


const PAGE_SIZE = 30;

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

  if (!total) {
    el.sidebarBody.innerHTML =
      `<div class="empty-state">${esc(t("No intents."))}</div>`;
    return;
  }

  if (!state._pageState) state._pageState = {};
  const archiveShown = state._pageState.intentArchive || PAGE_SIZE;
  const archived = [...completed, ...cancelled, ...otherHistory];
  const visibleArchive = archived.slice(0, archiveShown);
  const visibleIds = new Set(visibleArchive.map((intent) => intent.remote_id));
  const visibleCompleted = completed.filter((intent) => visibleIds.has(intent.remote_id));
  const visibleCancelled = cancelled.filter((intent) => visibleIds.has(intent.remote_id));
  const visibleOther = otherHistory.filter((intent) => visibleIds.has(intent.remote_id));
  const archiveRemaining = archived.length - visibleArchive.length;

  const archive = archived.length
    ? `<details class="object-archive intent-archive">
        <summary>
          <span>
            <strong>${esc(t("Resolved history"))}</strong>
          </span>
          <span class="object-archive-count">${archived.length}</span>
        </summary>
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

  el.sidebarBody.innerHTML = `
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

  const loadMore = document.getElementById("load-more-intent-archive");
  if (loadMore) {
    loadMore.addEventListener("click", () => {
      state._pageState.intentArchive = archiveShown + PAGE_SIZE;
      renderSidebar();
      document.querySelector(".intent-archive")?.setAttribute("open", "");
    });
  }
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

function intentEntry(intent) {
  const decisions = intent.decision_ids || [];
  const checkpoint = intent.latest_snap_id
    ? t("Checkpoint {id}", {id: intent.latest_snap_id})
    : t("Checkpoint missing");
  return `
    <button type="button" class="intent-entry intent-entry-${esc(intent.status)}" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
      <span class="intent-entry-topline">
        <span class="intent-lifecycle"><i aria-hidden="true"></i>${esc(intentStatusLabel(intent.status))}</span>
        <span class="intent-entry-id">${esc(intent.id)}</span>
      </span>
      <strong class="intent-entry-title">${esc(intent.what)}</strong>
      ${intent.why ? `<span class="intent-entry-summary">${esc(truncate(intent.why, 132))}</span>` : ""}
      <span class="intent-entry-context">
        <span class="${intent.latest_snap_id ? "has-checkpoint" : "missing-checkpoint"}">${esc(checkpoint)}</span>
        <span>${esc(t("{count} decisions", {count: decisions.length}))}</span>
      </span>
    </button>`;
}

function intentGroup(label, intents, tone, emptyMessage = "") {
  const body = intents.length
    ? `<div class="object-group-list">${intents.map(intentEntry).join("")}</div>`
    : `<div class="object-group-empty">${esc(emptyMessage)}</div>`;
  return `
    <section class="object-group intent-group intent-group-${esc(tone)}">
      <header class="object-group-header">
        <span class="object-group-title"><i aria-hidden="true"></i>${esc(label)}</span>
        <span class="object-group-count">${intents.length}</span>
      </header>
      ${body}
    </section>`;
}

function intentSubgroup(label, intents, tone) {
  if (!intents.length) return "";
  return `
    <section class="object-subgroup object-subgroup-${esc(tone)}">
      <header><span>${esc(label)}</span><span>${intents.length}</span></header>
      <div class="object-group-list">${intents.map(intentEntry).join("")}</div>
    </section>`;
}

function overviewIntents() {
  return [
    ...(state.overview?.active_intents || []),
    ...(state.overview?.other_intents || []),
  ];
}

function decisionScope(decision) {
  const ids = decision.intent_ids || [];
  const linked = overviewIntents().filter((intent) =>
    intent.workspace_id === decision.workspace_id && ids.includes(intent.id),
  );
  return {
    count: ids.length,
    titles: linked.map((intent) => intent.what),
  };
}

function decisionConstraint(decision, index, deprecated = false) {
  const scope = decisionScope(decision);
  const scopeLabel = scope.count
    ? t("{count} linked Intents", {count: scope.count})
    : t("No Intent scope recorded");
  const scopePreview = scope.titles.length
    ? truncate(scope.titles.join(" · "), 94)
    : scope.count
      ? truncate((decision.intent_ids || []).join(" · "), 94)
      : t("Open the Decision to inspect its recorded rationale.");
  return `
    <button type="button" class="decision-constraint${deprecated ? " is-deprecated" : ""}" data-detail-type="decision" data-remote-id="${esc(decision.remote_id)}">
      <span class="decision-sequence" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
      <span class="decision-constraint-body">
        <span class="decision-constraint-topline">
          <span>${deprecated ? t("Deprecated") : t("Current constraint")}</span>
          <span class="decision-id">${esc(decision.id)}</span>
        </span>
        <strong class="decision-constraint-title">${esc(decision.what)}</strong>
        ${decision.why ? `<span class="decision-constraint-why">${esc(truncate(decision.why, 132))}</span>` : ""}
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

  if (!active.length && !deprecated.length) {
    el.sidebarBody.innerHTML =
      `<div class="empty-state">${esc(t("No decisions."))}</div>`;
    return;
  }

  const activeHtml = active.length
    ? active.map((decision, index) => decisionConstraint(decision, index)).join("")
    : `<div class="object-group-empty">${esc(t("No active cross-Intent constraints."))}</div>`;
  const deprecatedHtml = deprecated.length
    ? `<details class="object-archive decision-archive">
        <summary>
          <span>
            <strong>${esc(t("Deprecated history"))}</strong>
          </span>
          <span class="object-archive-count">${deprecated.length}</span>
        </summary>
        <div class="object-archive-body decision-archive-body">
          ${deprecated.map((decision, index) => decisionConstraint(decision, index, true)).join("")}
        </div>
      </details>`
    : "";

  el.sidebarBody.innerHTML = `
    <section class="object-group decision-group">
      <header class="object-group-header">
        <span class="object-group-title heading-with-help"><i aria-hidden="true"></i>${esc(t("Active constraints"))}<button class="help-trigger" data-help="decisions" type="button" aria-label="${esc(t("Explanation"))}" aria-expanded="false"><span aria-hidden="true">i</span></button></span>
        <span class="object-group-count">${active.length}</span>
      </header>
      <div class="decision-constraint-list">${activeHtml}</div>
    </section>
    ${deprecatedHtml}`;
}

function intentForSnap(snap) {
  const intents = [
    ...(state.overview?.active_intents || []),
    ...(state.overview?.other_intents || []),
  ];
  return intents.find((intent) =>
    intent.id === snap.intent_id && intent.workspace_id === snap.workspace_id,
  ) || (!snap.workspace_id ? intents.find((intent) => intent.id === snap.intent_id) : null) || null;
}

function timelineIntentKey(snap) {
  return remoteId(snap.workspace_id || workspaceIdFromRemoteId(snap.remote_id), snap.intent_id || "");
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
          year: date.getFullYear() === today.getFullYear() ? undefined : "numeric",
        }).format(date);
  return {
    key,
    label,
    time: new Intl.DateTimeFormat(window.IntHubI18n.language, {
      hour: "2-digit",
      minute: "2-digit",
    }).format(date),
    datetime: date.toISOString(),
  };
}

function timelineState(checkpoint) {
  if (checkpoint.blocker && !isClearBlocker(checkpoint.blocker)) {
    return { className: " is-blocked", label: t("Blocked") };
  }
  if (!checkpoint.next) {
    return { className: " is-incomplete", label: t("Next missing") };
  }
  if (checkpoint.blocker && isClearBlocker(checkpoint.blocker)) {
    return { className: " is-ready", label: t("Unblocked") };
  }
  return { className: "", label: t("Checkpoint") };
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
      <span class="timeline-node" aria-hidden="true"></span>
      <span class="timeline-entry-body">
        <span class="timeline-entry-topline">
          <time datetime="${esc(recordedAt.datetime)}">${esc(recordedAt.time)}</time>
          <span class="timeline-entry-id">${esc(snap.id)}</span>
          <span class="timeline-entry-state">${esc(status.label)}</span>
        </span>
        <strong class="timeline-entry-title">${esc(conciseSnapTitle(snap))}</strong>
        ${supportingValue ? `<span class="timeline-entry-summary"><i>${esc(supportingLabel)}</i>${esc(truncate(supportingValue, 104))}</span>` : ""}
        <span class="timeline-entry-intent">${esc(intent ? truncate(intent.what, 72) : snap.intent_id || t("Unlinked Intent"))}</span>
      </span>
    </button>`;
}

function renderTimeline(snaps) {
  if (!state._pageState) state._pageState = {};
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
  el.sidebarBody.innerHTML = groups
    .map((group) => `
      <section class="timeline-group">
        <header class="timeline-day">
          <span>${esc(group.label)}</span>
          <span>${group.snaps.length}</span>
        </header>
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
    el.sidebarBody.innerHTML =
      `<div class="empty-state">${esc(t("No snaps synced yet."))}</div>`;
    return;
  }
  const options = timelineIntentOptions(allSnaps);
  if (state._timelineIntentKey && !options.some(option => option.key === state._timelineIntentKey)) state._timelineIntentKey = "";
  const selected = options.find(option => option.key === state._timelineIntentKey);
  const snaps = selected ? allSnaps.filter(snap => timelineIntentKey(snap) === selected.key) : allSnaps;
  renderTimeline(snaps);
  const optionHtml = (key, label, count) => `<button type="button" class="timeline-filter-option${(state._timelineIntentKey || "") === key ? " is-selected" : ""}" data-timeline-intent="${esc(key)}" aria-pressed="${(state._timelineIntentKey || "") === key}"><span>${esc(label)}</span><small>${count}</small></button>`;
  el.sidebarBody.innerHTML = `
    <div class="timeline-toolbar">
      <details class="timeline-filter">
        <summary class="timeline-filter-trigger" aria-label="${esc(t("Filter timeline by Intent"))}"><span>${esc(selected ? truncate(selected.label, 44) : t("All Intents"))}</span><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg></summary>
        <div class="timeline-filter-menu">${optionHtml("", t("All Intents"), allSnaps.length)}${options.map(option => optionHtml(option.key, option.label, option.count)).join("")}</div>
      </details>
      <span class="timeline-result-count">${esc(t("{count} checkpoints", {count: snaps.length}))}</span>
    </div>` + el.sidebarBody.innerHTML;
  // Replacing the toolbar also replaces child nodes; use delegation for pagination.
}

function renderSearchTab() {
  el.sidebarBody.innerHTML = `
    <h3 class="search-heading heading-with-help">${esc(t("Search"))}<button class="help-trigger" data-help="search" type="button" aria-label="${esc(t("Explanation"))}" aria-expanded="false"><span aria-hidden="true">i</span></button></h3>
    <form class="search-bar" id="search-form">
      <input type="search" id="search-input" aria-label="${esc(t("Search project memory"))}" placeholder="${esc(t("Goal, boundary, decision…"))}" value="${esc(state._searchDraft ?? state.searchQuery)}" autocomplete="off">
      <button type="submit">${esc(t("Go"))}</button>
    </form>
    <div id="search-results">
      <div class="empty-state">${esc(t("Type a query and press Go."))}</div>
    </div>`;

  document.getElementById("search-input").addEventListener("input", event => {state._searchDraft = event.target.value;});

  document
    .getElementById("search-form")
    .addEventListener("submit", async (e) => {
      e.preventDefault();
      const q = document.getElementById("search-input").value.trim();
      await runSearch(q, e.target.querySelector("button[type=submit]"));
    });

  if (state._localizing) {
    if (state._searchResults) renderSearchResults(state._searchResults);
    return;
  }
  if (state._searchResults && state._searchResultProject === state.currentProjectId && state._searchResultQuery === state.searchQuery) renderSearchResults(state._searchResults);
  else if (state.searchQuery && state.currentProjectId) runSearch(state.searchQuery, document.getElementById("search-form").querySelector("button[type=submit]"));
}

async function runSearch(query, button) {
  if (state._searchBusy) return;
  state.searchQuery = query;
  state._searchDraft = query;
  writeRoute();
  const container = document.getElementById("search-results");
  if (!query || !state.currentProjectId) {
    state._searchResults = null;
    if (container) container.innerHTML = `<div class="empty-state">${esc(t("Type a query and press Go."))}</div>`;
    return;
  }
  const projectId = state.currentProjectId;
  const request = beginViewRequest("search");
  state._searchBusy = true;
  if (button) setButtonBusy(button, true, "Searching…", "Go");
  if (container) {
    container.setAttribute("aria-busy", "true");
    container.innerHTML = `<div class="empty-state loading">${esc(t("Searching…"))}</div>`;
  }
  const current = () => ownsViewRequest("search", request) && state.activeTab === "search" && state.currentProjectId === projectId;
  try {
    const result = await fetchJson(apiUrl(`/api/v1/search?project_id=${encodeURIComponent(projectId)}&q=${encodeURIComponent(query)}`));
    if (!current()) return;
    state._searchResultProject = projectId;
    state._searchResultQuery = query;
    renderSearchResults(result);
  } catch (error) {
    if (!current()) return;
    state._searchResults = null;
    if (container) container.innerHTML = `<div class="empty-state"><p>${esc(error.message)}</p><button class="secondary-btn" type="button" data-retry-search>${esc(t("Retry"))}</button></div>`;
  } finally {
    if (current()) {
      state._searchBusy = false;
      container?.setAttribute("aria-busy", "false");
      if (button) setButtonBusy(button, false, "Searching…", "Go");
    }
  }
}

function renderSearchWelcome() {
  return `
    <section class="overview-empty">
      <div>
        <span class="overview-empty-mark">⌕</span>
        <h2 class="heading-with-help">${esc(t("Search the reason behind the work."))}<button class="help-trigger" data-help="search" type="button" aria-label="${esc(t("Explanation"))}" aria-expanded="false"><span aria-hidden="true">i</span></button></h2>
      </div>
    </section>`;
}

function renderSearchResults(result) {
  state._searchResults = result;
  const container = document.getElementById("search-results");
  if (!container || state.activeTab !== "search") return;
  if (!result.matches?.length) {
    container.innerHTML =
      `<div class="empty-state">${esc(t("No matches found."))}</div>`;
    return;
  }
  container.innerHTML = result.matches
    .map((m) => {
      const title = m.object_type === "snap"
        ? conciseSnapTitle(m)
        : m.what || m.title || m.id;
      return `
        <button type="button" class="card" data-detail-type="${esc(m.object_type)}" data-remote-id="${esc(m.remote_id)}">
          <span class="card-title">${esc(title)}</span>
          <span class="card-body">${esc(m.object_type)} \u00b7 ${esc(m.status ? intentStatusLabel(m.status) : "\u2014")}</span>
          <span class="card-meta">
            <span class="badge">${esc(m.id)}</span>
          </span>
        </button>`;
    })
    .join("");
  syncSelected();
}

/* ---- Detail pane ---- */

function clearDetail(msg = t("Select an object to inspect.")) {
  beginViewRequest("detail");
  state._detailPayload = null;
  el.detailContent.innerHTML = `<div class="empty-state">${esc(msg)}</div>`;
  state.selectedDetail = null;
  el.shell.classList.remove("detail-open");
  syncSelected();
}

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

function checkpointCell(key, label, value) {
  const missing = !value;
  const clearBlocker = key === "blocker" && isClearBlocker(value);
  return `
    <section class="checkpoint checkpoint-${esc(key)}${missing ? " is-missing" : ""}${clearBlocker ? " is-clear" : ""}">
      <span class="checkpoint-label">${esc(label)}</span>
      <p class="checkpoint-value">${missing ? t("Not explicitly recorded in the latest Snap.") : esc(value)}</p>
    </section>`;
}

function continuationCard(intent, index) {
  const checkpoint = parseCheckpoint(intent.latest_snap);

  return `
    <article class="brief-card">
      <header class="brief-card-head">
        <div>
          <span class="brief-index">Intent ${String(index + 1).padStart(2, "0")} · ${esc(intentStatusLabel(intent.status))}</span>
          <h2>${esc(intent.what)}</h2>
          ${intent.why ? `<p class="brief-why">${esc(intent.why)}</p>` : ""}
        </div>
        <button class="brief-open" type="button" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">${esc(t("Open Intent ↗"))}</button>
      </header>
      <div class="checkpoint-grid">
        ${checkpointCell("next", t("Next"), checkpoint.next)}
        ${checkpointCell("blocker", t("Blocker"), checkpoint.blocker)}
        ${checkpointCell("boundary", t("Boundary"), checkpoint.boundary)}
        ${checkpointCell("verified", t("Verified"), checkpoint.verified)}
      </div>
    </article>`;
}

function decisionRows(decisions) {
  if (!decisions.length) {
    return `<div class="queue-empty">${esc(t("N/A — no active Decision constrains future work."))}</div>`;
  }
  return decisions
    .map((decision) => `
      <button class="decision-row" type="button" data-detail-type="decision" data-remote-id="${esc(decision.remote_id)}">
        <span>
          <strong>${esc(decision.what)}</strong>
          ${decision.why ? `<small>${esc(truncate(decision.why, 120))}</small>` : ""}
        </span>
        <span class="badge">${esc(decision.id)}</span>
      </button>`)
    .join("");
}

function workspaceRows(workspaces) {
  if (!workspaces.length) {
    return `<div class="queue-empty">${esc(t("No workspace has completed a first sync."))}</div>`;
  }
  return workspaces
    .map((workspace) => `
      <div class="workspace-row">
        <span>
          <strong>${esc(workspace.branch || t("Detached workspace"))}</strong>
          <small>${esc(shortCommit(workspace.head_commit))} · ${esc(relativeDate(workspace.last_synced_at))}</small>
        </span>
        ${dirtyBadge(workspace.dirty)}
      </div>`)
    .join("");
}

function continuationHealth(intents) {
  if (!intents.length) return { ready: false, label: t("No active objective") };
  const checkpoints = intents.map(intent => ({
    ...extractCheckpointParts(intent.latest_snap?.why).fields,
    ...extractCheckpointParts(intent.latest_snap?.what).fields,
  }));
  const incomplete = checkpoints.filter(checkpoint => !checkpoint.verified || !checkpoint.boundary || !checkpoint.next || !checkpoint.blocker).length;
  if (incomplete) return { ready: false, label: t("{count} incomplete checkpoints", {count: incomplete}) };
  const blocked = checkpoints.filter(checkpoint => !isClearBlocker(checkpoint.blocker)).length;
  if (blocked) return { ready: false, label: t("{count} blocked objectives", {count: blocked}) };
  return { ready: true, label: t("Ready to continue") };
}

function renderProjectSummary() {
  const project = state.overview.project;
  const workspaces = state.overview.workspaces || [];
  const intents = state.handoff?.intents || [];
  const decisions = state.handoff?.active_decisions || [];
  const latestSync = workspaces
    .map((workspace) => workspace.last_synced_at)
    .filter(Boolean)
    .sort()
    .at(-1);
  const health = continuationHealth(intents);
  const publicDescription = state.config?.publicMode
    ? state.publicProfile?.description
    : "";

  const brief = intents.length
    ? `<div class="brief-stack">${intents.map(continuationCard).join("")}</div>`
    : `
      <section class="overview-empty">
        <div>
          <span class="overview-empty-mark">I</span>
          <h2>${esc(t("No active Intent defines the next move."))}</h2>
          <p>${esc(t("History is available, but IntHub cannot name the current goal until an active Intent and a self-contained checkpoint are synced."))}</p>
        </div>
      </section>`;

  el.detailContent.innerHTML = `
    <div class="continuation-page">
      <header class="continuation-hero">
        <div>
          <span class="overview-eyebrow">${state.config?.publicMode ? t("Public semantic history") : t("Continuation brief")}</span>
          <h1 class="continuation-title">${esc(project.name)}</h1>
          ${publicDescription ? `<p class="public-profile-description">${esc(publicDescription)}</p>` : ""}
          <div class="project-repo">
            <span>${esc(project.repo.provider || "git")}</span>
            <span>·</span>
            <span>${esc(project.repo.owner)}/${esc(project.repo.name)}</span>
            <span>·</span>
            <span>${esc(t("{count} workspaces", {count: workspaces.length}))}</span>
          </div>
        </div>
        <div class="hero-health${health.ready ? "" : " is-warning"}">
          <strong>${esc(health.label)}</strong>
          <span>${latestSync ? `${esc(t("Updated"))} ${esc(relativeDate(latestSync))}` : t("Waiting for first sync")}</span>
        </div>
      </header>

      ${brief}

      <div class="support-grid">
        <section class="support-card">
          <header class="support-card-head">
            <h3>${esc(t("Active decisions"))}</h3>
            <span>${esc(t("{count} constraints", {count: decisions.length}))}</span>
          </header>
          <div class="decision-list">${decisionRows(decisions)}</div>
        </section>
        <section class="support-card">
          <header class="support-card-head">
            <h3>${esc(t("Workspace health"))}</h3>
            <span>${esc(t("{count} sources", {count: workspaces.length}))}</span>
          </header>
          <div class="workspace-list">${workspaceRows(workspaces)}</div>
        </section>
      </div>
    </div>`;
}

function openDrawer() {
  if (!el.drawer.classList.contains("open")) state._drawerTrigger = document.activeElement;
  el.drawer.inert = false;
  el.drawer.classList.add("open");
  el.drawerOverlay.classList.add("open");
  el.drawer.setAttribute("aria-hidden", "false");
  el.drawer.setAttribute("role", "dialog");
  el.drawer.setAttribute("aria-modal", "true");
  for (const node of document.querySelectorAll(".app-header, .main")) node.inert = true;
  el.drawerClose.focus();
}

function closeDrawer() {
  const wasOpen = el.drawer.classList.contains("open");
  beginViewRequest("drawer");
  state._drawerPayload = null;
  el.drawer.classList.remove("open");
  el.drawerOverlay.classList.remove("open");
  el.drawer.setAttribute("aria-hidden", "true");
  el.drawer.inert = true;
  el.drawer.removeAttribute("aria-modal");
  for (const node of document.querySelectorAll(".app-header, .main")) node.inert = false;
  el.drawerContent.innerHTML = "";
  if (wasOpen) {
    if (state._drawerTrigger?.isConnected && !state._drawerTrigger.disabled) state._drawerTrigger.focus();
    else el.detailContent.focus();
  }
  state._drawerTrigger = null;
}

async function openInDrawer(type, rId) {
  if (!DETAIL_PATHS[type]) return;
  const request = beginViewRequest("drawer");
  state._drawerPayload = null;
  el.drawerContent.innerHTML = `<div class="empty-state loading">${esc(t("Loading…"))}</div>`;
  openDrawer();
  try {
    const payload = await fetchJson(apiUrl(`/api/v1/${DETAIL_PATHS[type]}/${encodeURIComponent(rId)}`));
    if (!ownsViewRequest("drawer", request) || !el.drawer.classList.contains("open")) return;
    state._drawerPayload = {type, payload};
    const target = el.drawerContent;
    if (type === "intent") renderIntentDetailTo(target, payload);
    else if (type === "decision") renderDecisionDetailTo(target, payload);
    else renderSnapDetailTo(target, payload);
  } catch (error) {
    if (!ownsViewRequest("drawer", request)) return;
    el.drawerContent.innerHTML = detailErrorHtml(error, type, rId, "drawer");
    throw error;
  }
}

function detailErrorHtml(error, type, rId, target = "detail") {
  return `<div class="empty-state"><p>${esc(error.message)}</p><button type="button" class="secondary-btn" data-retry-detail="${esc(target)}" data-detail-type="${esc(type)}" data-remote-id="${esc(rId)}">${esc(t("Retry"))}</button></div>`;
}

function returnToList() {
  el.shell.classList.remove("detail-open");
  const selected = [...el.sidebarBody.querySelectorAll("[data-detail-type][data-remote-id]")].find(node => node.dataset.remoteId === state.selectedDetail?.remoteId && node.dataset.detailType === state.selectedDetail?.type);
  selected?.focus();
}

async function resolveProjectIdForRemoteId(rId) {
  const workspaceId = workspaceIdFromRemoteId(rId);
  if (!workspaceId) return state.currentProjectId;

  if (!state._workspaceProjectMap) state._workspaceProjectMap = {};
  if (state._workspaceProjectMap[workspaceId]) {
    return state._workspaceProjectMap[workspaceId];
  }

  const currentWorkspaces = state.overview?.workspaces || [];
  for (const ws of currentWorkspaces) {
    state._workspaceProjectMap[ws.workspace_id] = state.currentProjectId;
  }
  if (currentWorkspaces.some((ws) => ws.workspace_id === workspaceId)) {
    return state.currentProjectId;
  }

  for (const project of state.projects) {
    if (project.id === state.currentProjectId) continue;
    const overview = await fetchJson(apiUrl(`/api/v1/projects/${project.id}/overview`));
    for (const ws of overview.workspaces || []) {
      state._workspaceProjectMap[ws.workspace_id] = project.id;
    }
    if ((overview.workspaces || []).some((ws) => ws.workspace_id === workspaceId)) {
      return project.id;
    }
  }

  return null;
}

async function openDetail(type, rId, { reveal = true } = {}) {
  if (!DETAIL_PATHS[type]) return;
  const request = beginViewRequest("detail");
  let targetProjectId;
  try { targetProjectId = await resolveProjectIdForRemoteId(rId); }
  catch (error) {
    if (!ownsViewRequest("detail", request)) return;
    state.selectedDetail = {type, remoteId: rId};
    state._detailPayload = null;
    if (reveal) el.shell.classList.add("detail-open");
    el.detailContent.innerHTML = detailErrorHtml(error, type, rId);
    syncSelected();
    writeRoute();
    throw error;
  }
  if (!ownsViewRequest("detail", request)) return;
  if (targetProjectId && targetProjectId !== state.currentProjectId) {
    await loadProject(targetProjectId, { detail: { type, remoteId: rId }, reveal });
    return;
  }

  state.selectedDetail = { type, remoteId: rId };
  state._detailPayload = null;
  if (reveal) el.shell.classList.add("detail-open");
  el.detailContent.innerHTML = `<div class="empty-state loading">${esc(t("Loading…"))}</div>`;
  el.detailPane.scrollTop = 0;
  syncSelected();

  try {
    const payload = await fetchJson(apiUrl(`/api/v1/${DETAIL_PATHS[type]}/${encodeURIComponent(rId)}`));
    if (!ownsViewRequest("detail", request)) return;
    state._detailPayload = {type, payload};
    if (type === "intent") renderIntentDetail(payload);
    else if (type === "decision") renderDecisionDetail(payload);
    else renderSnapDetail(payload);
    syncSelected();
    writeRoute();
  } catch (error) {
    if (!ownsViewRequest("detail", request)) return;
    el.detailContent.innerHTML = detailErrorHtml(error, type, rId);
    writeRoute();
    throw error;
  }
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

function buildIntentDetailHtml(payload) {
  const intent = payload.intent;
  const activeIds = activeDecisionIds();

  const dMap = allDecisionsMap();
  for (const decision of payload.decisions || []) {
    dMap[decision.id] = decision;
    if (decision.status === "active") activeIds.add(decision.id);
  }
  const allIds = intent.decision_ids || [];
  const activeLinks = allIds
    .filter((dId) => activeIds.has(dId))
    .map((dId) =>
      relationItem(
        "decision",
        remoteId(payload.workspace_id, dId),
        dId,
        dMap[dId]?.what || dId,
        dMap[dId]?.why || "",
        "active",
      ),
    );
  const deprecatedLinks = allIds
    .filter((dId) => !activeIds.has(dId))
    .map((dId) =>
      relationItem(
        "decision",
        remoteId(payload.workspace_id, dId),
        dId,
        dMap[dId]?.what || dId,
        dMap[dId]?.why || "",
        "deprecated",
      ),
    );

  const allDecisionLinks = [...activeLinks, ...deprecatedLinks];
  const decisionsBody = allDecisionLinks.length
    ? collapsibleRelation(allDecisionLinks, 5, t("more decision(s)"))
    : `<div class="empty-state">${esc(t("No decisions linked."))}</div>`;

  const allSnaps = [...payload.snaps].reverse();
  const snapLinks = allSnaps.map((s) =>
    relationItem(
      "snap",
      remoteId(payload.workspace_id, s.id),
      s.id,
      conciseSnapTitle(s),
      truncate(s.why || "", 80),
    ),
  );

  const snapTimelineBody = snapLinks.length
    ? collapsibleRelation(snapLinks, 5, t("older snap(s)"))
    : `<div class="empty-state">${esc(t("No snaps recorded."))}</div>`;

  return `
    <div class="detail-header">
      <span class="detail-id">${esc(intent.id)} \u00b7 Intent</span>
      <h2 class="detail-title">${esc(intent.what)}</h2>
      <div class="detail-meta">
        ${statusBadge(intent.status)}
        ${originBadge(intent.origin)}
        <span class="badge">${esc(fmtDate(intent.created_at))}</span>
      </div>
    </div>
    ${intent.why ? detailSection(t("Why"), formatText(intent.why)) : ""}
    ${detailSection(t("Snap Timeline (") + allSnaps.length + ")", snapTimelineBody)}
    ${detailSection(t("Linked Decisions (") + allIds.length + ")", decisionsBody)}
    ${rawToggle({ intent, snaps: payload.snaps, decisions: payload.decisions || [] })}`;
}

function renderIntentDetail(payload) {
  el.detailContent.innerHTML = buildIntentDetailHtml(payload);
}

function renderIntentDetailTo(target, payload) {
  target.innerHTML = buildIntentDetailHtml(payload);
}

function collapsibleRelation(allItems, visibleCount, moreLabel) {
  if (!allItems.length) return "";
  const visible = allItems.slice(0, visibleCount);
  const rest = allItems.slice(visibleCount);
  let html = `<div class="relation-list">${visible.join("")}</div>`;
  if (rest.length) {
    html += `<details class="collapse-toggle"><summary>${rest.length} ${moreLabel}</summary><div class="relation-list">${rest.join("")}</div></details>`;
  }
  return html;
}

function buildDecisionDetailHtml(payload) {
  const decision = payload.decision;
  const linkedCount = payload.intents.length;
  const scopeSummary = linkedCount
    ? t("Applies to {count} linked Intents.", {count: linkedCount})
    : t("No Intent scope is recorded.");
  const intentLinks = payload.intents.map((i) =>
    relationItem(
      "intent",
      remoteId(payload.workspace_id, i.id),
      i.id,
      i.what || i.title || i.id,
      truncate(i.why || "", 80),
      i.status,
    ),
  );

  const intentsBody = intentLinks.length
    ? collapsibleRelation(intentLinks, 5, t("more intent(s)"))
    : `<div class="empty-state">${esc(t("No linked intents."))}</div>`;

  return `
    <div class="detail-header">
      <span class="detail-id">${esc(decision.id)} \u00b7 Decision</span>
      <h2 class="detail-title">${esc(decision.what)}</h2>
      <p class="decision-detail-scope">${decision.status === "active" ? t("Current cross-Intent constraint") : t("Deprecated constraint history")} \u00b7 ${esc(scopeSummary)}</p>
      <div class="detail-meta">
        ${statusBadge(decision.status)}
        ${originBadge(decision.origin)}
        <span class="badge">${esc(fmtDate(decision.created_at))}</span>
      </div>
    </div>
    ${detailSection(t("Why"), formatText(decision.why) || `<p>${esc(t("No why provided."))}</p>`)}
    ${decision.reason ? detailSection(t("Reason"), formatText(decision.reason)) : ""}
    ${detailSection(t("Affected Intents (") + payload.intents.length + ")", intentsBody)}
    ${rawToggle({ decision, intents: payload.intents })}`;
}

function renderDecisionDetail(payload) {
  el.detailContent.innerHTML = buildDecisionDetailHtml(payload);
}

function renderDecisionDetailTo(target, payload) {
  target.innerHTML = buildDecisionDetailHtml(payload);
}

function buildSnapDetailHtml(payload) {
  const snap = payload.snap;
  const checkpoint = parseCheckpoint(snap);
  const status = timelineState(checkpoint);
  const parentTitle = payload.intent?.what || t("an unlinked Intent");
  const parentLink = payload.intent
    ? `<div class="relation-list">${relationItem(
        "intent",
        remoteId(payload.workspace_id, payload.intent.id),
        payload.intent.id,
        payload.intent.what || payload.intent.id,
        truncate(payload.intent.why || "", 80),
        payload.intent.status,
      )}</div>`
    : `<div class="empty-state">${esc(t("No linked intent."))}</div>`;

  return `
    <div class="detail-header detail-header-snap">
      <span class="detail-id">${esc(snap.id)} \u00b7 Snap</span>
      <h2 class="detail-title detail-title-snap">${esc(conciseSnapTitle(snap, 110))}</h2>
      <p class="snap-detail-context">${esc(t("Semantic checkpoint for"))} <strong>${esc(parentTitle)}</strong></p>
      <div class="detail-meta">
        <span class="badge snap-state${status.className}">${esc(status.label)}</span>
        ${originBadge(snap.origin)}
        <span class="badge">${esc(fmtDate(snap.created_at))}</span>
      </div>
    </div>
    ${detailSection(
      t("Continuation checkpoint"),
      `<div class="checkpoint-grid detail-checkpoint-grid">
        ${checkpointCell("verified", t("Verified"), checkpoint.verified)}
        ${checkpointCell("boundary", t("Boundary"), checkpoint.boundary)}
        ${checkpointCell("next", t("Next"), checkpoint.next)}
        ${checkpointCell("blocker", t("Blocker"), checkpoint.blocker)}
      </div>
      ${checkpoint.constraints ? `<p class="checkpoint-note"><strong>${esc(t("Constraints:"))}</strong> ${esc(checkpoint.constraints)}</p>` : ""}
      ${checkpoint.context ? `<p class="checkpoint-note">${esc(checkpoint.context)}</p>` : ""}`,
    )}
    ${detailSection(t("Parent Intent"), parentLink)}
    ${rawToggle({ snap, intent: payload.intent })}`;
}

function renderSnapDetail(payload) {
  el.detailContent.innerHTML = buildSnapDetailHtml(payload);
}

function renderSnapDetailTo(target, payload) {
  target.innerHTML = buildSnapDetailHtml(payload);
}

/* ---- Setup guide ---- */

function renderSetupGuide(mode) {
  if (state.config?.publicMode) {
    el.sidebarBody.innerHTML = `
      <div class="setup-guide public-empty-state">
        <h3>${esc(t("No published project yet"))}</h3>
        <p>${esc(t("This profile exists, but no project is currently included in its public collection."))}</p>
      </div>`;
    return;
  }
  const linkCmd = state.config.authRequired
    ? "itt hub link"
    : `itt hub link --api-base-url ${state.config.apiBaseUrl}`;
  const authPrefix = state.config.authRequired
    ? [`itt auth login --api-base-url ${state.config.apiBaseUrl}`]
    : [];
  let steps = [];

  if (mode === "unlinked") {
    steps = [
      { title: t("1. Initialize"), desc: t("Run once per repo."), cmd: ["itt init"] },
      {
        title: t("2. Link & Sync"),
        desc: t("Point CLI here, create binding, push snapshot."),
        cmd: [...authPrefix, linkCmd, "itt push"],
      },
    ];
  } else {
    steps = [
      {
        title: t("1. Link & Sync"),
        desc: t("Ensure CLI points here, then push the next snapshot."),
        cmd: [...authPrefix, linkCmd, "itt push"],
      },
      {
        title: t("2. Sync Again Later"),
        desc: t("Push new semantic history after more work."),
        cmd: ["itt push"],
      },
    ];
  }

  el.sidebarBody.innerHTML = `
    <div class="setup-guide">
      <h3 class="heading-with-help">${mode === "unlinked" ? t("Get started with IntHub") : t("Complete the first sync")}<button class="help-trigger" data-help="setup" type="button" aria-label="${esc(t("Explanation"))}" aria-expanded="false"><span aria-hidden="true">i</span></button></h3>
      ${steps
        .map(
          (s) => `
        <div class="setup-step">
          <h4 class="heading-with-help">${esc(s.title)}<button class="help-trigger" data-help-copy="${esc(s.desc)}" type="button" aria-label="${esc(t("Explanation"))}" aria-expanded="false"><span aria-hidden="true">i</span></button></h4>
          ${commandSnippet(s.cmd)}
        </div>`,
        )
        .join("")}
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
    ? `${current.name} · ${current.repo.owner}/${current.repo.name}`
    : state.projects[0].name;
  el.projectPickerDropdown.innerHTML = state.projects
    .map(
      (p) =>
        `<button type="button" role="option" aria-selected="${p.id === state.currentProjectId ? "true" : "false"}" class="project-picker-option${p.id === state.currentProjectId ? " is-selected" : ""}" data-id="${esc(p.id)}">
          <span class="project-picker-option-name">${esc(p.name)}</span>
          <span class="project-picker-option-repo">${esc(p.repo.owner)}/${esc(p.repo.name)}</span>
        </button>`,
    )
    .join("");
}

function toggleProjectPicker(open) {
  const isOpen = open ?? !el.projectPickerDropdown.classList.contains("is-open");
  el.projectPickerDropdown.classList.toggle("is-open", isOpen);
  el.projectPickerTrigger.classList.toggle("is-open", isOpen);
  el.projectPickerTrigger.setAttribute("aria-expanded", String(isOpen));
}

/* ---- Project loading ---- */

async function loadProject(projectId, { detail = null, reveal = false } = {}) {
  const request = beginViewRequest("project");
  const previous = {
    projectId: state._loadedProjectId || state.currentProjectId,
    overview: state.overview, handoff: state.handoff,
    selectedDetail: state.selectedDetail, detailPayload: state._detailPayload,
    pageState: state._pageState, timelineIntentKey: state._timelineIntentKey,
    searchResults: state._searchResults, detailOpen: el.shell.classList.contains("detail-open"),
  };
  const switching = Boolean(state._loadedProjectId && state._loadedProjectId !== projectId);
  beginViewRequest("detail");
  beginViewRequest("search");
  state._searchBusy = false;
  closeDrawer();
  if (switching) {
    state.overview = null;
    state.handoff = null;
    state._detailPayload = null;
    state._searchResults = null;
    state._timelineIntentKey = "";
    state._pageState = {};
    state.selectedDetail = null;
    el.shell.classList.remove("detail-open");
  }
  if (detail) state.selectedDetail = detail;
  state.currentProjectId = projectId;
  renderProjectSelector();

  if (!state.overview) {
    el.sidebarBody.innerHTML = `
      <div class="skeleton-list" aria-label="${esc(t("Loading project data"))}">
        <i></i><i></i><i></i>
      </div>`;
    el.detailContent.innerHTML = `
      <div class="overview-skeleton" aria-label="${esc(t("Loading continuation brief"))}">
        <i></i><i></i><i></i><i></i>
      </div>`;
  }

  let overview;
  let handoff;
  try {
    [overview, handoff] = await Promise.all([
      fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/overview`)),
      fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/handoff`)),
    ]);
  } catch (error) {
    if (!ownsViewRequest("project", request)) return;
    if (previous.overview) {
      state.currentProjectId = previous.projectId;
      state.overview = previous.overview;
      state.handoff = previous.handoff;
      state.selectedDetail = previous.selectedDetail;
      state._detailPayload = previous.detailPayload;
      state._pageState = previous.pageState;
      state._timelineIntentKey = previous.timelineIntentKey;
      state._searchResults = previous.searchResults;
      el.shell.classList.toggle("detail-open", previous.detailOpen);
      renderProjectSelector();
      renderSidebar();
      if (state.activeTab === "overview") renderProjectSummary();
      else if (state.activeTab === "search") el.detailContent.innerHTML = renderSearchWelcome();
      else if (previous.detailPayload) {
        const {type, payload} = previous.detailPayload;
        el.detailContent.innerHTML = type === "intent" ? buildIntentDetailHtml(payload) : type === "decision" ? buildDecisionDetailHtml(payload) : buildSnapDetailHtml(payload);
      } else clearDetail(error.message);
    } else {
      el.sidebarBody.innerHTML = `<div class="empty-state">${esc(error.message)}</div>`;
      el.detailContent.innerHTML = `<div class="empty-state"><p>${esc(error.message)}</p><button type="button" class="secondary-btn" data-retry-project="${esc(projectId)}">${esc(t("Retry"))}</button></div>`;
    }
    throw error;
  }
  if (!ownsViewRequest("project", request)) return;
  state._loadedProjectId = projectId;
  state.overview = overview;
  state.handoff = handoff;
  if (!state._workspaceProjectMap) state._workspaceProjectMap = {};
  for (const ws of overview.workspaces || []) {
    state._workspaceProjectMap[ws.workspace_id] = projectId;
  }

  el.intentCount.textContent = (overview.active_intents?.length || 0) + (overview.other_intents?.length || 0) || "";
  el.decisionCount.textContent = (overview.active_decisions?.length || 0) + (overview.deprecated_decisions?.length || 0) || "";
  el.snapCount.textContent = overview.total_snaps ?? overview.recent_snaps?.length ?? "";

  const ws = [...(overview.workspaces || [])]
    .sort((left, right) => String(right.last_synced_at || "").localeCompare(String(left.last_synced_at || "")))[0];
  el.syncChip.textContent = ws
    ? `${state.config?.publicMode ? t("Updated") : t("Synced")} ${relativeDate(ws.last_synced_at)}`
    : t("Not synced");
  el.syncChip.title = ws ? fmtDate(ws.last_synced_at) : "";
  el.syncIndicator.classList.toggle("is-unsynced", !ws);

  const missingNext = (handoff.intents || []).filter((intent) => !parseCheckpoint(intent.latest_snap).next).length;
  el.navHealth.textContent = (handoff.intents || []).length
    ? t("{count} active · {missing} missing next", {count: handoff.intents.length, missing: missingNext})
    : t("No active objective");

  if (!overview.workspaces?.length) {
    renderSetupGuide("unsynced");
    clearDetail(t("Complete the first sync to populate data."));
    writeRoute();
    return;
  }

  renderSidebar();
  setStatus(
    state.config?.publicMode
      ? t("{name} · public read-only view", {name: overview.project.name})
      : t("{name} is up to date", {name: overview.project.name}),
  );

  if (state.activeTab === "overview") {
    state.selectedDetail = null;
    renderProjectSummary();
  } else if (state.activeTab === "search" && !state.selectedDetail) {
    state.selectedDetail = null;
    el.detailContent.innerHTML = renderSearchWelcome();
  } else if (state.selectedDetail) {
    try {
      await openDetail(
        state.selectedDetail.type,
        state.selectedDetail.remoteId,
        { reveal },
      );
    } catch (error) { setStatus(error.message, true); }
  } else {
    const firstCard = el.sidebarBody.querySelector("[data-detail-type][data-remote-id]");
    if (firstCard) {
      await openDetail(firstCard.dataset.detailType, firstCard.dataset.remoteId, { reveal: false });
    } else {
      clearDetail(t("No object is available in this view."));
    }
  }

  writeRoute();
}

async function loadProjects() {
  const request = beginViewRequest("projects");
  const result = await fetchJson(apiUrl("/api/v1/projects"));
  if (!ownsViewRequest("projects", request)) return;
  state.projects = result.projects;

  const route = readRoute();
  const requested = route.project || state.config.defaultProjectId;
  state.currentProjectId =
    requested && state.projects.some((p) => p.id === requested)
      ? requested
      : state.projects[0]?.id || null;

  renderProjectSelector();

  if (!state.currentProjectId) {
    state.overview = null;
    state.handoff = null;
    el.navHealth.textContent = t("No project linked");
    el.syncChip.textContent = t("Waiting for first project");
    el.syncIndicator.classList.add("is-unsynced");
    setStatus(t("No projects linked yet."));
    renderSetupGuide("unlinked");
    clearDetail(t("Link a project to get started."));
    writeRoute();
    return;
  }

  await loadProject(state.currentProjectId);
}

/* ---- Events ---- */

function setButtonBusy(button, busy, loadingCopy = "", idleCopy = "") {
  button.disabled = busy;
  button.classList.toggle("is-busy", busy);
  button.setAttribute("aria-busy", String(busy));
  button.dataset.loadingCopy = loadingCopy;
  button.dataset.idleCopy = idleCopy;
  if (loadingCopy) button.textContent = t(busy ? loadingCopy : idleCopy);
}

function localizeWorkspace() {
  const draft = document.getElementById("search-input")?.value;
  const focusedId = document.activeElement?.id;
  const editing = document.activeElement?.matches("input");
  const selectionStart = document.activeElement?.selectionStart;
  const selectionEnd = document.activeElement?.selectionEnd;
  const sidebarScroll = el.sidebarBody.scrollTop;
  const detailScroll = el.detailPane.scrollTop;
  const expanded = [...document.querySelectorAll("details[open]")].map(node => node.className);
  state._localizing = true;
  try {
    renderProjectSelector();
    if (state.overview?.workspaces?.length) {
      if (!state._searchBusy) renderSidebar();
      if (state.activeTab === "overview") renderProjectSummary();
      else if (state.activeTab === "search" && !state.selectedDetail) el.detailContent.innerHTML = renderSearchWelcome();
      else if (state._detailPayload) {
        const {type, payload} = state._detailPayload;
        el.detailContent.innerHTML = type === "intent" ? buildIntentDetailHtml(payload) : type === "decision" ? buildDecisionDetailHtml(payload) : buildSnapDetailHtml(payload);
      }
      if (el.drawer.classList.contains("open") && state._drawerPayload) {
        const {type, payload} = state._drawerPayload;
        el.drawerContent.innerHTML = type === "intent" ? buildIntentDetailHtml(payload) : type === "decision" ? buildDecisionDetailHtml(payload) : buildSnapDetailHtml(payload);
      }
    } else if (state.authenticated) renderSetupGuide(state.projects.length ? "unsynced" : "unlinked");
    const input = document.getElementById("search-input");
    if (input && draft !== undefined) input.value = draft;
    for (const node of document.querySelectorAll("details")) if (expanded.includes(node.className)) node.open = true;
    el.sidebarBody.scrollTop = sidebarScroll;
    el.detailPane.scrollTop = detailScroll;
    const focus = document.getElementById(focusedId);
    if (focus && editing) {
      focus.focus();
      if (selectionStart !== undefined) focus.setSelectionRange?.(selectionStart, selectionEnd);
    }
    for (const button of document.querySelectorAll("[data-idle-copy]")) {
      if (button.dataset.idleCopy) button.textContent = t(button.disabled ? button.dataset.loadingCopy : button.dataset.idleCopy);
    }
    for (const node of document.querySelectorAll(".empty-state.loading")) node.textContent = t(node.closest("#search-results") ? "Searching…" : "Loading…");
    el.aboutVersion.textContent = t(state.config?.productVersion || "Unavailable");
    el.authError.textContent = t(state._authMessage || "");
    if (state._statusMessage) el.statusLine.textContent = t(state._statusMessage);
    if (state.config?.publicMode) {
      el.projectPickerEyebrow.textContent = t("Public collection");
      el.navContextLabel.textContent = t("Published memory");
    }
    const ws = [...(state.overview?.workspaces || [])].sort((a, b) => String(b.last_synced_at || "").localeCompare(String(a.last_synced_at || "")))[0];
    el.syncChip.textContent = ws ? `${t(state.config?.publicMode ? "Updated" : "Synced")} ${relativeDate(ws.last_synced_at)}` : t("Not synced");
    const active = state.handoff?.intents || [];
    el.navHealth.textContent = active.length ? t("{count} active · {missing} missing next", {count: active.length, missing: active.filter(intent => !parseCheckpoint(intent.latest_snap).next).length}) : t("No active objective");
    setTenonLoginLoading(el.tenonLogin.classList.contains("is-loading"));
  } finally { state._localizing = false; }
}

function bindEvents() {
  el.drawer.inert = true;
  const closeAccountMenu = () => {
    el.accountActions.classList.remove("is-open");
    el.accountMenuTrigger.setAttribute("aria-expanded", "false");
  };
  el.accountMenuTrigger.addEventListener("click", () => {
    const open = !el.accountActions.classList.contains("is-open");
    el.accountActions.classList.toggle("is-open", open);
    el.accountMenuTrigger.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", event => { if (!el.accountControl.contains(event.target)) closeAccountMenu(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape" && el.accountActions.classList.contains("is-open")) { closeAccountMenu(); el.accountMenuTrigger.focus(); } });
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
  window.addEventListener("inthub:language", localizeWorkspace);
  for (const trigger of document.querySelectorAll("[data-about-open]")) {
    trigger.addEventListener("click", () => {
      el.aboutVersion.textContent = state.config?.productVersion || t("Unavailable");
      el.aboutDialog.showModal();
    });
  }
  el.aboutClose.addEventListener("click", () => el.aboutDialog.close());
  el.searchTrigger.addEventListener("click", () => switchTab("search"));

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
  });

  el.tokenBtn.addEventListener("click", async () => {
    if (el.tokenBtn.disabled) return;
    setButtonBusy(el.tokenBtn, true, "Creating token…", "Access token");
    try {
      const issued = await fetchJson(apiUrl("/api/v1/auth/tokens"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "CLI token", ttl_seconds: 7776000 }),
      });
      el.tokenOutput.value = issued.token;
      closeAccountMenu();
      el.tokenDialog.showModal();
      el.tokenOutput.select();
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      setButtonBusy(el.tokenBtn, false, "Creating token…", "Access token");
    }
  });

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
    closeAccountMenu();
    for (const view of ["projects", "project", "detail", "drawer", "search"]) beginViewRequest(view);
    closeDrawer();
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
    setButtonBusy(el.projectPickerTrigger, true);
    try {
      await loadProject(id);
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      state._projectBusy = false;
      setButtonBusy(el.projectPickerTrigger, false);
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
    el.refreshBtn.disabled = true;
    el.refreshBtn.classList.add("is-spinning");
    el.refreshBtn.setAttribute("aria-label", t("Refreshing project data"));
    try {
      await loadProjects();
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      el.refreshBtn.disabled = false;
      el.refreshBtn.classList.remove("is-spinning");
      el.refreshBtn.setAttribute("aria-label", t("Refresh project data"));
    }
  });

  el.tabBar.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (tab && tab.dataset.tab) switchTab(tab.dataset.tab);
  });

  el.backBtn.addEventListener("click", returnToList);

  document.addEventListener("click", async (e) => {
    const retryInit = e.target.closest("[data-retry-init]");
    if (retryInit) {
      if (retryInit.disabled) return;
      setButtonBusy(retryInit, true, "Loading…", "Retry");
      try { await init(false); }
      finally { setButtonBusy(retryInit, false, "Loading…", "Retry"); }
      return;
    }
    const retrySearch = e.target.closest("[data-retry-search]");
    if (retrySearch) {
      await runSearch(state.searchQuery, document.getElementById("search-form")?.querySelector("button[type=submit]"));
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
    const filter = e.target.closest("[data-timeline-intent]");
    if (filter) {
      state._timelineIntentKey = filter.dataset.timelineIntent;
      state._pageState ||= {};
      state._pageState.snaps = PAGE_SIZE;
      renderSidebar();
      el.sidebarBody.scrollTop = 0;
      const selectedStillVisible = [...el.sidebarBody.querySelectorAll("[data-detail-type][data-remote-id]")].some(node => node.dataset.remoteId === state.selectedDetail?.remoteId);
      if (!selectedStillVisible) {
        const first = el.sidebarBody.querySelector("[data-detail-type][data-remote-id]");
        if (first) {
          try { await openDetail(first.dataset.detailType, first.dataset.remoteId, {reveal: false}); }
          catch (error) { setStatus(error.message, true); }
        }
      }
      el.sidebarBody.querySelector(".timeline-filter-trigger")?.focus();
      return;
    }
    if (e.target.closest("#load-more-snaps")) {
      state._pageState ||= {};
      state._pageState.snaps = (state._pageState.snaps || PAGE_SIZE) + PAGE_SIZE;
      const scroll = el.sidebarBody.scrollTop;
      renderSidebar();
      el.sidebarBody.scrollTop = scroll;
      return;
    }
    const card = e.target.closest("[data-detail-type][data-remote-id]");
    if (!card) return;
    if (card.disabled) return;
    setButtonBusy(card, true);
    const inDetailPane = card.closest("#detail-content") || card.closest("#drawer-content");
    try {
      if (card.dataset.retryDetail === "detail") {
        await openDetail(card.dataset.detailType, card.dataset.remoteId);
      } else if (inDetailPane || state.activeTab === "overview") {
        await openInDrawer(card.dataset.detailType, card.dataset.remoteId);
      } else {
        closeDrawer();
        await openDetail(card.dataset.detailType, card.dataset.remoteId);
      }
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      setButtonBusy(card, false);
    }
  });

  el.drawerClose.addEventListener("click", closeDrawer);
  el.drawerOverlay.addEventListener("click", closeDrawer);

  document.addEventListener("keydown", (event) => {
    if (el.aboutDialog.open || el.tokenDialog.open) return;
    if (el.drawer.classList.contains("open")) {
      if (event.key === "Escape") { event.preventDefault(); closeDrawer(); return; }
      if (event.key === "Tab") {
        const controls = [...el.drawer.querySelectorAll("button, a[href], input, summary, [tabindex]")].filter(node => !node.disabled && !node.hidden && node.getAttribute("tabindex") !== "-1" && node.getClientRects().length);
        const first = controls[0] || el.drawerClose;
        const last = controls.at(-1) || first;
        if (event.shiftKey && (document.activeElement === first || !el.drawer.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || !el.drawer.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
      }
      return;
    }
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
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      switchTab("search");
      return;
    }
    if (event.key === "Escape") {
      if (filter?.open) { filter.open = false; filter.querySelector("summary")?.focus(); }
      else if (el.projectPickerDropdown.classList.contains("is-open")) { toggleProjectPicker(false); el.projectPickerTrigger.focus(); }
      else if (el.shell.classList.contains("detail-open")) returnToList();
    }
  });

}

/* ---- Init ---- */

async function init(bind = true) {
  let authError = "";
  if (bind) bindEvents();
  try {
    state.config = await fetch(configUrl()).then((r) => r.json());
    authError = callbackErrorMessage();
    const route = readRoute();

    if (route.tab && TABS.includes(route.tab)) state.activeTab = route.tab;
    if (route.detail && DETAIL_PATHS[route.detailType]) {
      if (state.activeTab === "overview") {
        const detailTab = { intent: "intents", snap: "snaps", decision: "decisions" }[route.detailType];
        if (detailTab) state.activeTab = detailTab;
      }
      state.selectedDetail = {
        remoteId: route.detail,
        type: route.detailType,
      };
      el.shell.classList.add("detail-open");
    }
    state.searchQuery = route.q;
    if (state.searchQuery && state.activeTab === "overview") state.activeTab = "search";
    el.shell.dataset.activeTab = state.activeTab;

    for (const btn of el.tabBar.querySelectorAll(".tab")) {
      btn.classList.toggle("is-active", btn.dataset.tab === state.activeTab);
      if (btn.dataset.tab === state.activeTab) btn.setAttribute("aria-current", "page");
      else btn.removeAttribute("aria-current");
    }

    if (state.config.publicMode) await loadPublicProfile();
    else await loadCurrentAccount();
    await loadProjects();
    hideAuthGate();
  } catch (err) {
    if (err.status === 401 && state.config?.authRequired) {
      showAuthGate(authError);
      return;
    }
    setStatus(err.message, true);
    el.detailContent.innerHTML =
      `<div class="empty-state"><p>${esc(t("Failed to initialize."))}</p><p>${esc(err.message)}</p><button type="button" class="secondary-btn" data-retry-init>${esc(t("Retry"))}</button></div>`;
  }
}

init();

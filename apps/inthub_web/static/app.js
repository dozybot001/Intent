/* ---- State ---- */

const TABS = ["overview", "intents", "snaps", "decisions", "search"];

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
  authGate: document.getElementById("auth-gate"),
  authError: document.getElementById("auth-error"),
  authDescription: document.getElementById("auth-description"),
  authFootnote: document.getElementById("auth-footnote"),
  githubLogin: document.getElementById("github-login"),
  githubLoginLabel: document.getElementById("github-login-label"),
  navHealth: document.getElementById("nav-health"),
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
  if (!v) return "Never synced";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return String(v);
  const seconds = Math.round((d.getTime() - Date.now()) / 1000);
  const abs = Math.abs(seconds);
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
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
  return `<span class="badge${cls}">${esc(status || "")}</span>`;
}

function originBadge(origin) {
  if (!origin) return "";
  const slug = origin.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `<span class="badge origin-${slug}">${esc(origin)}</span>`;
}

function dirtyBadge(dirty) {
  return dirty
    ? '<span class="badge warn">dirty</span>'
    : '<span class="badge good">clean</span>';
}

function remoteId(wksId, objId) {
  return `${wksId}__${objId}`;
}

function workspaceIdFromRemoteId(rId) {
  return String(rId || "").split("__", 1)[0] || "";
}

function apiUrl(path) {
  return `${state.config.apiBaseUrl}${path}`;
}

class ApiRequestError extends Error {
  constructor(message, status, code) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function fetchJson(url, options = {}) {
  const r = await fetch(url, { credentials: "same-origin", ...options });
  let p;
  try {
    p = await r.json();
  } catch {
    throw new ApiRequestError("IntHub returned an invalid response.", r.status, "INVALID_RESPONSE");
  }
  if (!r.ok || p.ok === false) {
    const error = new ApiRequestError(
      p?.error?.message || "Request failed",
      r.status,
      p?.error?.code,
    );
    if (r.status === 401 && state.config?.authRequired) showAuthGate();
    throw error;
  }
  return p.result;
}

function showAuthGate(message = "") {
  state.authenticated = false;
  el.shell.classList.add("is-locked");
  el.authGate.classList.remove("is-hidden");
  el.accountControl.classList.add("is-hidden");
  el.authError.textContent = message;
  el.authError.classList.toggle("is-hidden", !message);
  el.githubLogin.classList.remove("is-hidden");
  const returnTo = `${window.location.pathname}${window.location.search}`;
  el.githubLogin.href = `/api/v1/auth/github/start?return_to=${encodeURIComponent(returnTo)}`;
  el.githubLoginLabel.textContent = "Continue with GitHub";
  el.authDescription.textContent =
    "Use your GitHub identity to sign in or create your IntHub account.";
  el.authFootnote.textContent =
    "IntHub stores its own revocable browser session and never stores your GitHub access token.";
  window.setTimeout(() => el.githubLogin.focus(), 0);
}

function hideAuthGate() {
  state.authenticated = true;
  el.shell.classList.remove("is-locked");
  el.authGate.classList.add("is-hidden");
  el.accountControl.classList.toggle("is-hidden", !state.config?.authRequired);
  const account = state.account;
  el.accountLabel.textContent = account
    ? account.display_name || `@${account.login}`
    : "Private session";
  el.accountAvatar.textContent = accountInitials(account);
  el.accountAvatar.dataset.tone = accountAvatarTone(account);
  el.authError.textContent = "";
  el.authError.classList.add("is-hidden");
}

async function loadCurrentAccount() {
  if (state.config?.authMode !== "github") return;
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
    github_denied: "GitHub sign-in was cancelled.",
    invalid_state: "That sign-in attempt expired. Please try again.",
    github_failed: "GitHub sign-in could not be completed. Please try again.",
  };
  return messages[code] || "Sign-in could not be completed.";
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
  state.activeTab = tab;
  el.shell.dataset.activeTab = tab;
  el.shell.classList.remove("detail-open");
  closeDrawer();
  for (const btn of el.tabBar.querySelectorAll(".tab")) {
    btn.classList.toggle("is-active", btn.dataset.tab === tab);
  }
  renderSidebar();
  writeRoute();

  if (tab === "overview") {
    state.selectedDetail = null;
    if (state.overview) renderProjectSummary();
    else clearDetail("Link a project to build a continuation brief.");
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
    try {
      await openDetail(firstCard.dataset.detailType, firstCard.dataset.remoteId);
    } catch {}
  }
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
  return `<details class="raw-toggle"><summary>Raw JSON</summary><pre class="raw-pre">${esc(JSON.stringify(data, null, 2))}</pre></details>`;
}

/* ---- Sidebar rendering ---- */

function renderSidebar() {
  if (!state.overview) {
    el.sidebarBody.innerHTML =
      '<div class="empty-state">Loading project data\u2026</div>';
    return;
  }
  switch (state.activeTab) {
    case "overview":
      el.sidebarKicker.textContent = "Current work";
      el.sidebarTitle.textContent = "Continuation queue";
      renderContinuationQueue();
      break;
    case "intents":
      el.sidebarKicker.textContent = "Semantic goals";
      el.sidebarTitle.textContent = "Intents";
      renderIntentsTab();
      break;
    case "decisions":
      el.sidebarKicker.textContent = "Project constraints";
      el.sidebarTitle.textContent = "Decisions";
      renderDecisionsTab();
      break;
    case "snaps":
      el.sidebarKicker.textContent = "Semantic history";
      el.sidebarTitle.textContent = "Timeline";
      renderSnapsTab();
      break;
    case "search":
      el.sidebarKicker.textContent = "Find context";
      el.sidebarTitle.textContent = "Search";
      renderSearchTab();
      break;
  }
  syncSelected();
}

function queueItem(intent, section) {
  const snap = intent.latest_snap;
  const summary = snap?.what || intent.why || "No continuation checkpoint recorded.";
  return `
    <button class="queue-item" type="button" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
      <span class="queue-item-title">${esc(intent.what)}</span>
      <span class="queue-item-summary">${esc(truncate(summary, 150))}</span>
      <span class="queue-item-meta">
        ${statusBadge(intent.status)}
        <span class="badge">${esc(intent.id)}</span>
        ${snap ? `<span class="badge">${esc(snap.id)}</span>` : '<span class="badge warn">checkpoint missing</span>'}
      </span>
    </button>`;
}

function renderContinuationQueue() {
  const active = state.handoff?.intents || [];
  const suspended = state.handoff?.suspended_intents || [];
  const activeBody = active.length
    ? active.map((intent) => queueItem(intent, "active")).join("")
    : '<div class="queue-empty">No active Intent. The project has no explicit current objective.</div>';
  const suspendedBody = suspended.length
    ? suspended.map((intent) => queueItem(intent, "suspended")).join("")
    : '<div class="queue-empty">No suspended work waiting to resume.</div>';

  el.sidebarBody.innerHTML = `
    <section class="queue-group">
      <div class="queue-heading">Active · ${active.length}</div>
      ${activeBody}
    </section>
    <section class="queue-group">
      <div class="queue-heading">Suspended · ${suspended.length}</div>
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
      '<div class="empty-state">No intents.</div>';
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
            <strong>Resolved history</strong>
            <small>Completed and cancelled objectives</small>
          </span>
          <span class="object-archive-count">${archived.length}</span>
        </summary>
        <div class="object-archive-body">
          ${intentSubgroup("Completed", visibleCompleted, "done")}
          ${intentSubgroup("Cancelled", visibleCancelled, "cancelled")}
          ${intentSubgroup("Other", visibleOther, "history")}
          ${archiveRemaining > 0
            ? `<button type="button" class="load-more-btn" id="load-more-intent-archive">Load more (${archiveRemaining})</button>`
            : ""}
        </div>
      </details>`
    : "";

  el.sidebarBody.innerHTML = `
    ${intentGroup(
      "Active objectives",
      active,
      "active",
      "No active objective. Resume a suspended Intent or record a new one.",
    )}
    ${suspended.length
      ? intentGroup("Suspended", suspended, "suspend")
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
    active: "In progress",
    suspend: "On hold",
    done: "Completed",
    cancelled: "Cancelled",
  }[status] || status || "Unknown";
}

function intentEntry(intent) {
  const decisions = intent.decision_ids || [];
  const checkpoint = intent.latest_snap_id
    ? `Checkpoint ${intent.latest_snap_id}`
    : "Checkpoint missing";
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
        <span>${decisions.length} decision${decisions.length === 1 ? "" : "s"}</span>
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
    ? `${scope.count} linked Intent${scope.count === 1 ? "" : "s"}`
    : "No Intent scope recorded";
  const scopePreview = scope.titles.length
    ? truncate(scope.titles.join(" · "), 94)
    : scope.count
      ? truncate((decision.intent_ids || []).join(" · "), 94)
      : "Open the Decision to inspect its recorded rationale.";
  return `
    <button type="button" class="decision-constraint${deprecated ? " is-deprecated" : ""}" data-detail-type="decision" data-remote-id="${esc(decision.remote_id)}">
      <span class="decision-sequence" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
      <span class="decision-constraint-body">
        <span class="decision-constraint-topline">
          <span>${deprecated ? "Deprecated" : "Current constraint"}</span>
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
      '<div class="empty-state">No decisions.</div>';
    return;
  }

  const activeHtml = active.length
    ? active.map((decision, index) => decisionConstraint(decision, index)).join("")
    : '<div class="object-group-empty">No active cross-Intent constraints.</div>';
  const deprecatedHtml = deprecated.length
    ? `<details class="object-archive decision-archive">
        <summary>
          <span>
            <strong>Deprecated history</strong>
            <small>Retired constraints kept for traceability</small>
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
        <span class="object-group-title"><i aria-hidden="true"></i>Active constraints</span>
        <span class="object-group-count">${active.length}</span>
      </header>
      <p class="object-group-intro">Rules that remain binding across linked objectives.</p>
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
  ) || intents.find((intent) => intent.id === snap.intent_id) || null;
}

function timelineDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { key: "undated", label: "Undated", time: "—", datetime: "" };
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
    ? "Today"
    : key === dayKey(yesterday)
      ? "Yesterday"
      : new Intl.DateTimeFormat(undefined, {
          month: "short",
          day: "numeric",
          year: date.getFullYear() === today.getFullYear() ? undefined : "numeric",
        }).format(date);
  return {
    key,
    label,
    time: new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    }).format(date),
    datetime: date.toISOString(),
  };
}

function timelineState(checkpoint) {
  if (checkpoint.blocker && !isClearBlocker(checkpoint.blocker)) {
    return { className: " is-blocked", label: "Blocked" };
  }
  if (!checkpoint.next) {
    return { className: " is-incomplete", label: "Next missing" };
  }
  if (checkpoint.blocker && isClearBlocker(checkpoint.blocker)) {
    return { className: " is-ready", label: "Unblocked" };
  }
  return { className: "", label: "Checkpoint" };
}

function snapTimelineEntry(snap) {
  const checkpoint = parseCheckpoint(snap);
  const recordedAt = timelineDate(snap.created_at);
  const status = timelineState(checkpoint);
  const intent = intentForSnap(snap);
  const supportingValue = checkpoint.next || checkpoint.boundary || snap.why || "";
  const supportingLabel = checkpoint.next
    ? "Next"
    : checkpoint.boundary
      ? "Boundary"
      : "Context";
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
        <span class="timeline-entry-intent">${esc(intent ? truncate(intent.what, 72) : snap.intent_id || "Unlinked Intent")}</span>
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
      ? `<button type="button" class="load-more-btn" id="load-more-snaps">Load more (${remaining})</button>`
      : "");

  const loadMore = document.getElementById("load-more-snaps");
  if (loadMore) {
    loadMore.addEventListener("click", () => {
      state._pageState.snaps = shown + PAGE_SIZE;
      renderSidebar();
    });
  }
}

function renderSnapsTab() {
  const snaps = state.overview.recent_snaps || [];
  if (!snaps.length) {
    el.sidebarBody.innerHTML =
      '<div class="empty-state">No snaps synced yet.</div>';
    return;
  }
  renderTimeline(snaps);
}

function renderSearchTab() {
  el.sidebarBody.innerHTML = `
    <form class="search-bar" id="search-form">
      <input type="search" id="search-input" aria-label="Search project memory" placeholder="Goal, boundary, decision\u2026" value="${esc(state.searchQuery)}" autocomplete="off">
      <button type="submit">Go</button>
    </form>
    <div id="search-results">
      <div class="empty-state">Type a query and press Go.</div>
    </div>`;

  document
    .getElementById("search-form")
    .addEventListener("submit", async (e) => {
      e.preventDefault();
      const q = document.getElementById("search-input").value.trim();
      state.searchQuery = q;
      writeRoute();
      if (!q || !state.currentProjectId) return;
      try {
        const result = await fetchJson(
          apiUrl(
            `/api/v1/search?project_id=${encodeURIComponent(state.currentProjectId)}&q=${encodeURIComponent(q)}`,
          ),
        );
        renderSearchResults(result);
      } catch (err) {
        document.getElementById("search-results").innerHTML =
          `<div class="empty-state">${esc(err.message)}</div>`;
      }
    });

  if (state.searchQuery && state.currentProjectId) {
    fetchJson(
      apiUrl(
        `/api/v1/search?project_id=${encodeURIComponent(state.currentProjectId)}&q=${encodeURIComponent(state.searchQuery)}`,
      ),
    )
      .then(renderSearchResults)
      .catch(() => {});
  }
}

function renderSearchWelcome() {
  return `
    <section class="overview-empty">
      <div>
        <span class="overview-empty-mark">⌕</span>
        <h2>Search the reason behind the work.</h2>
        <p>Find Intent goals, Snap checkpoints and Decisions inside the current project. Use <strong>Cmd/Ctrl+K</strong> from anywhere to return here.</p>
      </div>
    </section>`;
}

function renderSearchResults(result) {
  const container = document.getElementById("search-results") || el.sidebarBody;
  if (!result.matches?.length) {
    container.innerHTML =
      '<div class="empty-state">No matches found.</div>';
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
          <span class="card-body">${esc(m.object_type)} \u00b7 ${esc(m.status || "\u2014")}</span>
          <span class="card-meta">
            <span class="badge">${esc(m.id)}</span>
          </span>
        </button>`;
    })
    .join("");
  syncSelected();
}

/* ---- Detail pane ---- */

function clearDetail(msg = "Select an object to inspect.") {
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
  if (!source) return `${snap?.id || "Snap"} checkpoint`;

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
      <p class="checkpoint-value">${missing ? "Not explicitly recorded in the latest Snap." : esc(value)}</p>
    </section>`;
}

function continuationCard(intent, index) {
  const checkpoint = parseCheckpoint(intent.latest_snap);

  return `
    <article class="brief-card">
      <header class="brief-card-head">
        <div>
          <span class="brief-index">Intent ${String(index + 1).padStart(2, "0")} · ${esc(intent.status)}</span>
          <h2>${esc(intent.what)}</h2>
          ${intent.why ? `<p class="brief-why">${esc(intent.why)}</p>` : ""}
        </div>
        <button class="brief-open" type="button" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">Open Intent ↗</button>
      </header>
      <div class="checkpoint-grid">
        ${checkpointCell("next", "Next", checkpoint.next)}
        ${checkpointCell("blocker", "Blocker", checkpoint.blocker)}
        ${checkpointCell("boundary", "Boundary", checkpoint.boundary)}
        ${checkpointCell("verified", "Verified", checkpoint.verified)}
      </div>
    </article>`;
}

function decisionRows(decisions) {
  if (!decisions.length) {
    return '<div class="queue-empty">N/A — no active Decision constrains future work.</div>';
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
    return '<div class="queue-empty">No workspace has completed a first sync.</div>';
  }
  return workspaces
    .map((workspace) => `
      <div class="workspace-row">
        <span>
          <strong>${esc(workspace.branch || "Detached workspace")}</strong>
          <small>${esc(shortCommit(workspace.head_commit))} · ${esc(relativeDate(workspace.last_synced_at))}</small>
        </span>
        ${dirtyBadge(workspace.dirty)}
      </div>`)
    .join("");
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
  const hasDirtyWorkspace = workspaces.some((workspace) => workspace.dirty);

  const brief = intents.length
    ? `<div class="brief-stack">${intents.map(continuationCard).join("")}</div>`
    : `
      <section class="overview-empty">
        <div>
          <span class="overview-empty-mark">I</span>
          <h2>No active Intent defines the next move.</h2>
          <p>History is available, but IntHub cannot name the current goal until an active Intent and a self-contained checkpoint are synced.</p>
        </div>
      </section>`;

  el.detailContent.innerHTML = `
    <div class="continuation-page">
      <header class="continuation-hero">
        <div>
          <span class="overview-eyebrow">Continuation brief</span>
          <h1 class="continuation-title">${esc(project.name)}</h1>
          <div class="project-repo">
            <span>${esc(project.repo.provider || "git")}</span>
            <span>·</span>
            <span>${esc(project.repo.owner)}/${esc(project.repo.name)}</span>
            <span>·</span>
            <span>${workspaces.length} workspace${workspaces.length === 1 ? "" : "s"}</span>
          </div>
        </div>
        <div class="hero-health${hasDirtyWorkspace ? " is-warning" : ""}">
          <strong>${hasDirtyWorkspace ? "Working tree changes synced" : "Continuity is in sync"}</strong>
          <span>${latestSync ? `Updated ${relativeDate(latestSync)}` : "Waiting for first sync"}</span>
        </div>
      </header>

      ${brief}

      <div class="support-grid">
        <section class="support-card">
          <header class="support-card-head">
            <h3>Active decisions</h3>
            <span>${decisions.length} constraint${decisions.length === 1 ? "" : "s"}</span>
          </header>
          <div class="decision-list">${decisionRows(decisions)}</div>
        </section>
        <section class="support-card">
          <header class="support-card-head">
            <h3>Workspace health</h3>
            <span>${workspaces.length} source${workspaces.length === 1 ? "" : "s"}</span>
          </header>
          <div class="workspace-list">${workspaceRows(workspaces)}</div>
        </section>
      </div>
    </div>`;
}

function openDrawer() {
  el.drawer.classList.add("open");
  el.drawerOverlay.classList.add("open");
  el.drawer.setAttribute("aria-hidden", "false");
}

function closeDrawer() {
  el.drawer.classList.remove("open");
  el.drawerOverlay.classList.remove("open");
  el.drawer.setAttribute("aria-hidden", "true");
  el.drawerContent.innerHTML = "";
}

async function openInDrawer(type, rId) {
  el.drawerContent.innerHTML = '<div class="empty-state loading">Loading\u2026</div>';
  openDrawer();

  const pathMap = { intent: "intents", decision: "decisions", snap: "snaps" };
  const payload = await fetchJson(apiUrl(`/api/v1/${pathMap[type]}/${rId}`));

  const target = el.drawerContent;
  if (type === "intent") renderIntentDetailTo(target, payload);
  else if (type === "decision") renderDecisionDetailTo(target, payload);
  else renderSnapDetailTo(target, payload);
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

async function openDetail(type, rId) {
  const targetProjectId = await resolveProjectIdForRemoteId(rId);
  if (targetProjectId && targetProjectId !== state.currentProjectId) {
    state.selectedDetail = { type, remoteId: rId };
    await loadProject(targetProjectId);
    return;
  }

  state.selectedDetail = { type, remoteId: rId };
  el.shell.classList.add("detail-open");
  el.detailContent.innerHTML = '<div class="empty-state loading">Loading\u2026</div>';
  el.detailPane.scrollTop = 0;
  syncSelected();

  const pathMap = { intent: "intents", decision: "decisions", snap: "snaps" };
  const payload = await fetchJson(apiUrl(`/api/v1/${pathMap[type]}/${rId}`));

  if (type === "intent") renderIntentDetail(payload);
  else if (type === "decision") renderDecisionDetail(payload);
  else renderSnapDetail(payload);

  syncSelected();
  writeRoute();
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
    ? collapsibleRelation(allDecisionLinks, 5, "more decision(s)")
    : '<div class="empty-state">No decisions linked.</div>';

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
    ? collapsibleRelation(snapLinks, 5, "older snap(s)")
    : '<div class="empty-state">No snaps recorded.</div>';

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
    ${intent.why ? detailSection("Why", formatText(intent.why)) : ""}
    ${detailSection("Snap Timeline (" + allSnaps.length + ")", snapTimelineBody)}
    ${detailSection("Linked Decisions (" + allIds.length + ")", decisionsBody)}
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
    ? `Applies to ${linkedCount} linked Intent${linkedCount === 1 ? "" : "s"}.`
    : "No Intent scope is recorded.";
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
    ? collapsibleRelation(intentLinks, 5, "more intent(s)")
    : '<div class="empty-state">No linked intents.</div>';

  return `
    <div class="detail-header">
      <span class="detail-id">${esc(decision.id)} \u00b7 Decision</span>
      <h2 class="detail-title">${esc(decision.what)}</h2>
      <p class="decision-detail-scope">${decision.status === "active" ? "Current cross-Intent constraint" : "Deprecated constraint history"} \u00b7 ${esc(scopeSummary)}</p>
      <div class="detail-meta">
        ${statusBadge(decision.status)}
        ${originBadge(decision.origin)}
        <span class="badge">${esc(fmtDate(decision.created_at))}</span>
      </div>
    </div>
    ${detailSection("Why", formatText(decision.why) || `<p>No why provided.</p>`)}
    ${decision.reason ? detailSection("Reason", formatText(decision.reason)) : ""}
    ${detailSection("Affected Intents (" + payload.intents.length + ")", intentsBody)}
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
  const parentTitle = payload.intent?.what || "an unlinked Intent";
  const parentLink = payload.intent
    ? `<div class="relation-list">${relationItem(
        "intent",
        remoteId(payload.workspace_id, payload.intent.id),
        payload.intent.id,
        payload.intent.what || payload.intent.id,
        truncate(payload.intent.why || "", 80),
        payload.intent.status,
      )}</div>`
    : '<div class="empty-state">No linked intent.</div>';

  return `
    <div class="detail-header detail-header-snap">
      <span class="detail-id">${esc(snap.id)} \u00b7 Snap</span>
      <h2 class="detail-title detail-title-snap">${esc(conciseSnapTitle(snap, 110))}</h2>
      <p class="snap-detail-context">Semantic checkpoint for <strong>${esc(parentTitle)}</strong></p>
      <div class="detail-meta">
        <span class="badge snap-state${status.className}">${esc(status.label)}</span>
        ${originBadge(snap.origin)}
        <span class="badge">${esc(fmtDate(snap.created_at))}</span>
      </div>
    </div>
    ${detailSection(
      "Continuation checkpoint",
      `<div class="checkpoint-grid detail-checkpoint-grid">
        ${checkpointCell("verified", "Verified", checkpoint.verified)}
        ${checkpointCell("boundary", "Boundary", checkpoint.boundary)}
        ${checkpointCell("next", "Next", checkpoint.next)}
        ${checkpointCell("blocker", "Blocker", checkpoint.blocker)}
      </div>
      ${checkpoint.constraints ? `<p class="checkpoint-note"><strong>Constraints:</strong> ${esc(checkpoint.constraints)}</p>` : ""}
      ${checkpoint.context ? `<p class="checkpoint-note">${esc(checkpoint.context)}</p>` : ""}`,
    )}
    ${detailSection("Parent Intent", parentLink)}
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
  const linkCmd = state.config.authRequired
    ? "itt hub link"
    : `itt hub link --api-base-url ${state.config.apiBaseUrl}`;
  const authPrefix = state.config.authRequired
    ? [`itt auth login --api-base-url ${state.config.apiBaseUrl}`]
    : [];
  let steps = [];

  if (mode === "unlinked") {
    steps = [
      { title: "1. Initialize", desc: "Run once per repo.", cmd: ["itt init"] },
      {
        title: "2. Link & Sync",
        desc: "Point CLI here, create binding, push snapshot.",
        cmd: [...authPrefix, linkCmd, "itt push"],
      },
    ];
  } else {
    steps = [
      {
        title: "1. Link & Sync",
        desc: "Ensure CLI points here, then push the next snapshot.",
        cmd: [...authPrefix, linkCmd, "itt push"],
      },
      {
        title: "2. Sync Again Later",
        desc: "Push new semantic history after more work.",
        cmd: ["itt push"],
      },
    ];
  }

  el.sidebarBody.innerHTML = `
    <div class="setup-guide">
      <h3>${mode === "unlinked" ? "Get started with IntHub" : "Complete the first sync"}</h3>
      <p>Run these commands where your .intent/ data lives.</p>
      ${steps
        .map(
          (s) => `
        <div class="setup-step">
          <h4>${esc(s.title)}</h4>
          <p>${esc(s.desc)}</p>
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
    el.projectPickerLabel.textContent = "No projects yet";
    el.projectPickerDropdown.innerHTML = "";
    return;
  }
  el.projectPickerTrigger.disabled = false;
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

async function loadProject(projectId) {
  state.currentProjectId = projectId;
  renderProjectSelector();

  if (!state.overview) {
    el.sidebarBody.innerHTML = `
      <div class="skeleton-list" aria-label="Loading project data">
        <i></i><i></i><i></i>
      </div>`;
    el.detailContent.innerHTML = `
      <div class="overview-skeleton" aria-label="Loading continuation brief">
        <i></i><i></i><i></i><i></i>
      </div>`;
  }

  const [overview, handoff] = await Promise.all([
    fetchJson(apiUrl(`/api/v1/projects/${projectId}/overview`)),
    fetchJson(apiUrl(`/api/v1/projects/${projectId}/handoff`)),
  ]);
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
    ? `Synced ${relativeDate(ws.last_synced_at)}`
    : "Not synced";
  el.syncChip.title = ws ? fmtDate(ws.last_synced_at) : "";
  el.syncIndicator.classList.toggle("is-unsynced", !ws);

  const missingNext = (handoff.intents || []).filter((intent) => !parseCheckpoint(intent.latest_snap).next).length;
  el.navHealth.textContent = (handoff.intents || []).length
    ? `${handoff.intents.length} active · ${missingNext} missing next`
    : "No active objective";

  if (!overview.workspaces?.length) {
    renderSetupGuide("unsynced");
    clearDetail("Complete the first sync to populate data.");
    writeRoute();
    return;
  }

  renderSidebar();
  setStatus(
    `${overview.project.name} is up to date`,
  );

  if (state.activeTab === "overview") {
    state.selectedDetail = null;
    renderProjectSummary();
  } else if (state.activeTab === "search") {
    state.selectedDetail = null;
    el.detailContent.innerHTML = renderSearchWelcome();
  } else if (state.selectedDetail) {
    try {
      await openDetail(
        state.selectedDetail.type,
        state.selectedDetail.remoteId,
      );
    } catch {
      state.selectedDetail = null;
      renderProjectSummary();
    }
  } else {
    const firstCard = el.sidebarBody.querySelector("[data-detail-type][data-remote-id]");
    if (firstCard) {
      await openDetail(firstCard.dataset.detailType, firstCard.dataset.remoteId);
    } else {
      clearDetail("No object is available in this view.");
    }
  }

  writeRoute();
}

async function loadProjects() {
  const result = await fetchJson(apiUrl("/api/v1/projects"));
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
    el.navHealth.textContent = "No project linked";
    el.syncChip.textContent = "Waiting for first project";
    el.syncIndicator.classList.add("is-unsynced");
    setStatus("No projects linked yet.");
    renderSetupGuide("unlinked");
    clearDetail("Link a project to get started.");
    writeRoute();
    return;
  }

  await loadProject(state.currentProjectId);
}

/* ---- Events ---- */

function bindEvents() {
  el.searchTrigger.addEventListener("click", () => switchTab("search"));

  el.tokenBtn.addEventListener("click", async () => {
    el.tokenBtn.disabled = true;
    try {
      const issued = await fetchJson(apiUrl("/api/v1/auth/tokens"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "CLI token", ttl_seconds: 7776000 }),
      });
      el.tokenOutput.value = issued.token;
      el.tokenDialog.showModal();
      el.tokenOutput.select();
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      el.tokenBtn.disabled = false;
    }
  });

  el.tokenCopy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(el.tokenOutput.value);
      el.tokenCopy.textContent = "Copied";
    } catch {
      el.tokenOutput.select();
    }
  });

  el.tokenDialog.addEventListener("close", () => {
    el.tokenOutput.value = "";
    el.tokenCopy.textContent = "Copy token";
  });

  el.logoutBtn.addEventListener("click", async () => {
    try {
      await fetchJson(apiUrl("/api/v1/auth/logout"), { method: "POST" });
    } catch {}
    state.projects = [];
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
    if (!option) return;
    toggleProjectPicker(false);
    const id = option.dataset.id;
    if (!id || id === state.currentProjectId) return;
    try {
      state.selectedDetail = null;
      state.overview = null;
      state.handoff = null;
      await loadProject(id);
    } catch (err) {
      setStatus(err.message, true);
    }
  });

  document.addEventListener("click", (e) => {
    if (!el.projectPicker.contains(e.target)) {
      toggleProjectPicker(false);
    }
  });

  el.refreshBtn.addEventListener("click", async () => {
    el.refreshBtn.disabled = true;
    el.refreshBtn.classList.add("is-spinning");
    el.refreshBtn.setAttribute("aria-label", "Refreshing project data");
    try {
      await loadProjects();
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      el.refreshBtn.disabled = false;
      el.refreshBtn.classList.remove("is-spinning");
      el.refreshBtn.setAttribute("aria-label", "Refresh project data");
    }
  });

  el.tabBar.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (tab && tab.dataset.tab) switchTab(tab.dataset.tab);
  });

  el.backBtn.addEventListener("click", () => {
    el.shell.classList.remove("detail-open");
  });

  document.addEventListener("click", async (e) => {
    const card = e.target.closest("[data-detail-type][data-remote-id]");
    if (!card) return;
    const inDetailPane = card.closest("#detail-content") || card.closest("#drawer-content");
    try {
      if (inDetailPane || state.activeTab === "overview") {
        await openInDrawer(card.dataset.detailType, card.dataset.remoteId);
      } else {
        closeDrawer();
        await openDetail(card.dataset.detailType, card.dataset.remoteId);
      }
    } catch (err) {
      setStatus(err.message, true);
    }
  });

  el.drawerClose.addEventListener("click", closeDrawer);
  el.drawerOverlay.addEventListener("click", closeDrawer);

  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      switchTab("search");
      return;
    }
    if (event.key === "Escape") {
      if (el.drawer.classList.contains("open")) closeDrawer();
      else toggleProjectPicker(false);
    }
  });

}

/* ---- Init ---- */

async function init() {
  let authError = "";
  try {
    state.config = await fetch("/config.json").then((r) => r.json());
    authError = callbackErrorMessage();
    const route = readRoute();

    if (route.tab && TABS.includes(route.tab)) state.activeTab = route.tab;
    if (route.detail && route.detailType) {
      if (state.activeTab === "overview") {
        const detailTab = { intent: "intents", snap: "snaps", decision: "decisions" }[route.detailType];
        if (detailTab) state.activeTab = detailTab;
      }
      state.selectedDetail = {
        remoteId: route.detail,
        type: route.detailType,
      };
    }
    state.searchQuery = route.q;
    if (state.searchQuery && state.activeTab === "overview") state.activeTab = "search";
    el.shell.dataset.activeTab = state.activeTab;

    for (const btn of el.tabBar.querySelectorAll(".tab")) {
      btn.classList.toggle("is-active", btn.dataset.tab === state.activeTab);
    }

    bindEvents();
    await loadCurrentAccount();
    await loadProjects();
    hideAuthGate();
  } catch (err) {
    if (err.status === 401 && state.config?.authRequired) {
      showAuthGate(authError);
      return;
    }
    setStatus(err.message, true);
    el.detailContent.innerHTML =
      '<div class="empty-state">Failed to initialize.</div>';
  }
}

init();

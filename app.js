/* ---- State ---- */

const TABS = ["intents", "decisions", "snaps"];

const state = {
  config: null,
  projects: [],
  currentProjectId: null,
  activeTab: "intents",
  selectedDetail: null,
  searchQuery: "",
  overview: null,
};

const el = {
  shell: document.getElementById("shell"),
  projectPicker: document.getElementById("project-picker"),
  projectPickerTrigger: document.getElementById("project-picker-trigger"),
  projectPickerLabel: document.getElementById("project-picker-label"),
  projectPickerDropdown: document.getElementById("project-picker-dropdown"),
  refreshBtn: document.getElementById("refresh-btn"),
  syncChip: document.getElementById("sync-chip"),
  apiChip: document.getElementById("api-chip"),
  tabBar: document.querySelector(".tab-bar"),
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
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString();
}

function shortCommit(v) {
  return v ? v.slice(0, 8) : "\u2014";
}

function truncate(v, n = 140) {
  if (!v || v.length <= n) return v || "";
  return v.slice(0, n).trimEnd() + "\u2026";
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
  if (state.config?.static) return `${path.replace(/^\//, "")}.json`;
  return `${state.config.apiBaseUrl}${path}`;
}

async function fetchJson(url) {
  const r = await fetch(url);
  const p = await r.json();
  if (!r.ok || p.ok === false) {
    throw new Error(p?.error?.message || "Request failed");
  }
  return p.result;
}

/* ---- URL state ---- */

function readRoute() {
  const p = new URLSearchParams(window.location.search);
  return {
    project: p.get("project"),
    tab: p.get("tab") || "intents",
    detail: p.get("detail"),
    detailType: p.get("detailType"),
    q: p.get("q") || "",
  };
}

function writeRoute() {
  const p = new URLSearchParams();
  if (state.currentProjectId) p.set("project", state.currentProjectId);
  if (state.activeTab !== "intents") p.set("tab", state.activeTab);
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
}

/* ---- Tab switching ---- */

async function switchTab(tab) {
  state.activeTab = tab;
  for (const btn of el.tabBar.querySelectorAll(".tab")) {
    btn.classList.toggle("is-active", btn.dataset.tab === tab);
  }
  renderSidebar();
  writeRoute();

  // Auto-open first item
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
  const cls = status === "deprecated" ? " rel-deprecated" : status === "done" ? " rel-muted" : "";
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
    case "intents":
      renderIntentsTab();
      break;
    case "decisions":
      renderDecisionsTab();
      break;
    case "snaps":
      renderSnapsTab();
      break;
    case "search":
      renderSearchTab();
      break;
  }
  syncSelected();
}


function intentCard(intent) {
  const cls = intent.status === "done" ? " card-muted" : "";
  return `
    <article class="card${cls}" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
      <h4 class="card-title">${esc(intent.what)}</h4>
      ${intent.why ? `<p class="card-body">${esc(truncate(intent.why, 140))}</p>` : ""}
      <div class="card-meta">
        <span class="badge">${esc(intent.id)}</span>
        ${statusBadge(intent.status)}
        ${originBadge(intent.origin)}
      </div>
    </article>`;
}

const PAGE_SIZE = 30;

function renderPaged(container, items, renderFn, tabKey) {
  if (!state._pageState) state._pageState = {};
  const shown = state._pageState[tabKey] || PAGE_SIZE;

  const visible = items.slice(0, shown);
  const remaining = items.length - visible.length;

  container.innerHTML = visible.map(renderFn).join("")
    + (remaining > 0
      ? `<button type="button" class="load-more-btn" id="load-more-${tabKey}">Load more (${remaining})</button>`
      : "");

  const btn = document.getElementById(`load-more-${tabKey}`);
  if (btn) {
    btn.addEventListener("click", () => {
      state._pageState[tabKey] = shown + PAGE_SIZE;
      renderSidebar();
    });
  }
}

function renderIntentsTab() {
  const all = [...(state.overview.active_intents || []), ...(state.overview.other_intents || [])];

  if (!all.length) {
    el.sidebarBody.innerHTML =
      '<div class="empty-state">No intents.</div>';
    return;
  }

  renderPaged(el.sidebarBody, [...all].reverse(), intentCard, "intents");
}

function decisionCard(d) {
  const cls = d.status === "deprecated" ? " card-deprecated" : "";
  return `
    <article class="card${cls}" data-detail-type="decision" data-remote-id="${esc(d.remote_id)}">
      <h4 class="card-title">${esc(d.what)}</h4>
      ${d.why ? `<p class="card-body">${esc(truncate(d.why, 140))}</p>` : ""}
      <div class="card-meta">
        <span class="badge">${esc(d.id)}</span>
        ${statusBadge(d.status)}
        ${originBadge(d.origin)}
      </div>
    </article>`;
}

function renderDecisionsTab() {
  const active = [...(state.overview.active_decisions || [])].reverse();
  const deprecated = [...(state.overview.deprecated_decisions || [])].reverse();

  if (!active.length && !deprecated.length) {
    el.sidebarBody.innerHTML =
      '<div class="empty-state">No decisions.</div>';
    return;
  }

  const activeHtml = active.map(decisionCard).join("");
  const deprecatedHtml = deprecated.length
    ? `<details class="collapse-toggle is-deprecated"><summary>${deprecated.length} deprecated</summary>${deprecated.map(decisionCard).join("")}</details>`
    : "";

  el.sidebarBody.innerHTML = activeHtml + deprecatedHtml;
}

function snapCard(snap) {
  return `
    <article class="card" data-detail-type="snap" data-remote-id="${esc(snap.remote_id)}">
      <h4 class="card-title">${esc(snap.what)}</h4>
      ${snap.why ? `<p class="card-body">${esc(truncate(snap.why, 140))}</p>` : ""}
      <div class="card-meta">
        <span class="badge">${esc(snap.id)}</span>
        ${originBadge(snap.origin)}
      </div>
    </article>`;
}

function renderSnapsTab() {
  const snaps = state.overview.recent_snaps || [];
  if (!snaps.length) {
    el.sidebarBody.innerHTML =
      '<div class="empty-state">No snaps synced yet.</div>';
    return;
  }
  renderPaged(el.sidebarBody, snaps, snapCard, "snaps");
}

function renderSearchTab() {
  el.sidebarBody.innerHTML = `
    <form class="search-bar" id="search-form">
      <input type="search" id="search-input" placeholder="Search title, summary, rationale\u2026" value="${esc(state.searchQuery)}">
      <button type="submit">Go</button>
    </form>
    <div id="search-results">
      <div class="empty-state">Type a query and press Go.</div>
    </div>`;

  document
    .getElementById("search-form")
    .addEventListener("submit", async (e) => {
    // Static mode: client-side search
    if (state.config?.static) {
      e.preventDefault();
      const q = document.getElementById("search-input").value.trim();
      state.searchQuery = q;
      writeRoute();
      if (!q || !state.currentProjectId) return;
      try {
        const idx = await fetchJson(apiUrl(`/api/v1/projects/${state.currentProjectId}/search-index`));
        const lower = q.toLowerCase();
        const matches = idx.items.filter(item =>
          (item.what || "").toLowerCase().includes(lower) ||
          (item.why || "").toLowerCase().includes(lower) ||
          (item.id || "").toLowerCase().includes(lower)
        );
        renderSearchResults({ matches });
      } catch (err) {
        document.getElementById("search-results").innerHTML =
          `<div class="empty-state">${esc(err.message)}</div>`;
      }
      return;
    }
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

function renderSearchResults(result) {
  const container = el.sidebarBody;
  if (!result.matches?.length) {
    container.innerHTML =
      '<div class="empty-state">No matches found.</div>';
    return;
  }
  container.innerHTML = result.matches
    .map(
      (m) => `
    <article class="card" data-detail-type="${esc(m.object_type)}" data-remote-id="${esc(m.remote_id)}">
      <h4 class="card-title">${esc(m.what || m.title || m.id)}</h4>
      <p class="card-body">${esc(m.object_type)} \u00b7 ${esc(m.status || "\u2014")}</p>
      <div class="card-meta">
        <span class="badge">${esc(m.id)}</span>
      </div>
    </article>`,
    )
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

function renderProjectSummary() {
  const p = state.overview.project;
  const ws = state.overview.workspaces || [];

  el.detailContent.innerHTML = `
    <div class="detail-header">
      <span class="detail-id">Project</span>
      <h2 class="detail-title">${esc(p.name)}</h2>
      <div class="detail-meta">
        <span class="badge">${esc(p.repo.owner)}/${esc(p.repo.name)}</span>
        <span class="badge">${ws.length} workspace(s)</span>
      </div>
    </div>
    ${
      ws.length
        ? detailSection(
            "Workspaces",
            ws
              .map(
                (w) => `
            <div class="workspace-row">
              <strong>${esc(w.branch || "\u2014")}</strong>
              ${dirtyBadge(w.dirty)}
              <span class="badge">${esc(fmtDate(w.last_synced_at))}</span>
            </div>`,
              )
              .join(""),
          )
        : ""
    }
    ${detailSection(
      "Stats",
      `<div class="detail-kv">
        ${kvRow("Active Intents", String(state.overview.active_intents?.length || 0))}
        ${kvRow("Active Decisions", String(state.overview.active_decisions?.length || 0))}
        ${kvRow("Recent Snaps", String(state.overview.recent_snaps?.length || 0))}
      </div>`,
    )}
    <div class="empty-state">Select an object from the left panel to inspect.</div>`;
}

function openDrawer() {
  el.drawer.classList.add("open");
  el.drawerOverlay.classList.add("open");
}

function closeDrawer() {
  el.drawer.classList.remove("open");
  el.drawerOverlay.classList.remove("open");
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
      s.what || s.title || s.id,
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
    ${rawToggle({ intent, snaps: payload.snaps })}`;
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
    <div class="detail-header">
      <span class="detail-id">${esc(snap.id)} \u00b7 Snap</span>
      <h2 class="detail-title">${esc(snap.what)}</h2>
      <div class="detail-meta">
        ${originBadge(snap.origin)}
        <span class="badge">${esc(fmtDate(snap.created_at))}</span>
      </div>
    </div>
    ${detailSection("Why", formatText(snap.why) || `<p>No why provided.</p>`)}
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
  const linkCmd = `itt hub link --api-base-url ${state.config.apiBaseUrl}`;
  let steps = [];

  if (mode === "unlinked") {
    steps = [
      { title: "1. Initialize", desc: "Run once per repo.", cmd: ["itt init"] },
      {
        title: "2. Link & Sync",
        desc: "Point CLI here, create binding, push snapshot.",
        cmd: [linkCmd, "itt hub sync"],
      },
    ];
  } else {
    steps = [
      {
        title: "1. Link & Sync",
        desc: "Ensure CLI points here, then push the next snapshot.",
        cmd: [linkCmd, "itt hub sync"],
      },
      {
        title: "2. Sync Again Later",
        desc: "Push new semantic history after more work.",
        cmd: ["itt hub sync"],
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
        `<button class="project-picker-option${p.id === state.currentProjectId ? " is-selected" : ""}" data-id="${esc(p.id)}">
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
}

/* ---- Project loading ---- */

async function loadProject(projectId) {
  state.currentProjectId = projectId;
  renderProjectSelector();

  const overview = await fetchJson(apiUrl(`/api/v1/projects/${projectId}/overview`));
  state.overview = overview;
  if (!state._workspaceProjectMap) state._workspaceProjectMap = {};
  for (const ws of overview.workspaces || []) {
    state._workspaceProjectMap[ws.workspace_id] = projectId;
  }

  el.intentCount.textContent = (overview.active_intents?.length || 0) + (overview.other_intents?.length || 0) || "";
  el.decisionCount.textContent = (overview.active_decisions?.length || 0) + (overview.deprecated_decisions?.length || 0) || "";
  el.snapCount.textContent = overview.total_snaps ?? overview.recent_snaps?.length ?? "";

  const ws = overview.workspaces?.[0];
  el.syncChip.textContent = ws
    ? `Synced ${fmtDate(ws.last_synced_at)}`
    : "Not synced";

  if (!overview.workspaces?.length) {
    renderSetupGuide("unsynced");
    clearDetail("Complete the first sync to populate data.");
    writeRoute();
    return;
  }

  renderSidebar();
  setStatus(
    `${overview.project.name} \u00b7 ${overview.workspaces.length} workspace(s)`,
  );

  if (state.selectedDetail) {
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
    renderProjectSummary();
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
    el.refreshBtn.textContent = "Refreshing…";
    try {
      await loadProjects();
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      el.refreshBtn.disabled = false;
      el.refreshBtn.textContent = "Refresh";
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
      if (inDetailPane) {
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

}

/* ---- Init ---- */

async function init() {
  try {
    state.config = await fetch("config.json").then((r) => r.json());
    const route = readRoute();
    if (state.config.static) {
      el.refreshBtn.style.display = "none";
      el.apiChip.textContent = "Static Site";
    } else {
      el.apiChip.textContent = state.config.apiBaseUrl;
    }

    if (route.tab && TABS.includes(route.tab)) state.activeTab = route.tab;
    if (route.detail && route.detailType) {
      state.selectedDetail = {
        remoteId: route.detail,
        type: route.detailType,
      };
    }
    state.searchQuery = route.q;

    for (const btn of el.tabBar.querySelectorAll(".tab")) {
      btn.classList.toggle("is-active", btn.dataset.tab === state.activeTab);
    }

    bindEvents();
    await loadProjects();
  } catch (err) {
    setStatus(err.message, true);
    el.detailContent.innerHTML =
      '<div class="empty-state">Failed to initialize.</div>';
  }
}

init();

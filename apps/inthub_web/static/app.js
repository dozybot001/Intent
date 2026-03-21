/* ---- State ---- */

const TABS = ["handoff", "intents", "decisions", "snaps", "search"];

const state = {
  config: null,
  projects: [],
  currentProjectId: null,
  activeTab: "handoff",
  selectedDetail: null,
  searchQuery: "",
  overview: null,
  handoff: null,
};

const el = {
  shell: document.getElementById("shell"),
  projectSelect: document.getElementById("project-select"),
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

function dirtyBadge(dirty) {
  return dirty
    ? '<span class="badge warn">dirty</span>'
    : '<span class="badge good">clean</span>';
}

function remoteId(wksId, objId) {
  return `${wksId}__${objId}`;
}

function apiUrl(path) {
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
    tab: p.get("tab") || "handoff",
    detail: p.get("detail"),
    detailType: p.get("detailType"),
    q: p.get("q") || "",
  };
}

function writeRoute() {
  const p = new URLSearchParams();
  if (state.currentProjectId) p.set("project", state.currentProjectId);
  if (state.activeTab !== "handoff") p.set("tab", state.activeTab);
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

function switchTab(tab) {
  state.activeTab = tab;
  for (const btn of el.tabBar.querySelectorAll(".tab")) {
    btn.classList.toggle("is-active", btn.dataset.tab === tab);
  }
  renderSidebar();
  writeRoute();
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
    case "handoff":
      renderHandoffTab();
      break;
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

function renderHandoffTab() {
  if (!state.handoff) {
    el.sidebarBody.innerHTML =
      '<div class="empty-state">No handoff data.</div>';
    return;
  }

  const decisions = state.handoff.active_decisions || [];
  const intents = state.handoff.intents || [];

  if (!intents.length) {
    el.sidebarBody.innerHTML =
      '<div class="empty-state">No active intents. The workspace is idle.</div>';
    return;
  }

  el.sidebarBody.innerHTML = `
    <div class="sidebar-section">
      <span class="section-label">Active Intents (${intents.length})</span>
      ${intents
        .map(
          (intent) => `
        <article class="card" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
          <h4 class="card-title">${esc(intent.title)}</h4>
          <p class="card-body">${esc(truncate(intent.latest_snap?.summary || intent.rationale || intent.source_query || "", 200))}</p>
          <div class="card-meta">
            <span class="badge">${esc(intent.id)}</span>
            ${intent.latest_snap?.origin ? `<span class="badge">${esc(intent.latest_snap.origin)}</span>` : ""}
            <span class="badge">${decisions.length} constraints</span>
          </div>
        </article>`,
        )
        .join("")}
    </div>`;
}

function intentCard(intent) {
  return `
    <article class="card" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
      <h4 class="card-title">${esc(intent.title)}</h4>
      <p class="card-body">${esc(intent.source_query || intent.rationale || "")}</p>
      <div class="card-meta">
        <span class="badge">${esc(intent.id)}</span>
        <span class="badge">${esc(intent.status)}</span>
        <span class="badge">${intent.decision_ids?.length || 0} decisions</span>
      </div>
    </article>`;
}

function renderIntentsTab() {
  const active = state.overview.active_intents || [];
  const others = state.overview.other_intents || [];

  if (!active.length && !others.length) {
    el.sidebarBody.innerHTML =
      '<div class="empty-state">No intents.</div>';
    return;
  }

  const activeHtml = active.length
    ? `<div class="sidebar-section">
        <span class="section-label">Active (${active.length})</span>
        ${[...active].reverse().map(intentCard).join("")}
       </div>`
    : "";

  const othersHtml = others.length
    ? `<details class="collapse-toggle">
        <summary>${others.length} completed / suspended</summary>
        ${[...others].reverse().map(intentCard).join("")}
       </details>`
    : "";

  el.sidebarBody.innerHTML = activeHtml + othersHtml;
}

function renderDecisionsTab() {
  const active = state.overview.active_decisions || [];
  const deprecated = state.overview.deprecated_decisions || [];

  if (!active.length && !deprecated.length) {
    el.sidebarBody.innerHTML =
      '<div class="empty-state">No decisions.</div>';
    return;
  }

  const activeHtml = [...active].reverse()
    .map(
      (d) => `
    <article class="card" data-detail-type="decision" data-remote-id="${esc(d.remote_id)}">
      <h4 class="card-title">${esc(d.title)}</h4>
      <p class="card-body">${d.intent_ids?.length || 0} linked intents</p>
      <div class="card-meta">
        <span class="badge">${esc(d.id)}</span>
      </div>
    </article>`,
    )
    .join("");

  const deprecatedHtml = deprecated.length
    ? `<details class="collapse-toggle is-deprecated">
        <summary>${deprecated.length} deprecated decision(s)</summary>
        ${[...deprecated].reverse()
          .map(
            (d) => `
          <article class="card" data-detail-type="decision" data-remote-id="${esc(d.remote_id)}">
            <h4 class="card-title">${esc(d.title)}</h4>
            <div class="card-meta">
              <span class="badge">${esc(d.id)}</span>
              <span class="badge warn">deprecated</span>
            </div>
          </article>`,
          )
          .join("")}
       </details>`
    : "";

  el.sidebarBody.innerHTML = activeHtml + deprecatedHtml;
}

function renderSnapsTab() {
  const snaps = state.overview.recent_snaps || [];
  if (!snaps.length) {
    el.sidebarBody.innerHTML =
      '<div class="empty-state">No snaps synced yet.</div>';
    return;
  }
  el.sidebarBody.innerHTML = snaps
    .map(
      (snap) => `
    <article class="card" data-detail-type="snap" data-remote-id="${esc(snap.remote_id)}">
      <h4 class="card-title">${esc(snap.title)}</h4>
      <p class="card-body">${esc(truncate(snap.summary || "", 140))}</p>
      <div class="card-meta">
        <span class="badge">${esc(snap.id)}</span>
        <span class="badge">${esc(snap.intent_id || "")}</span>
        ${snap.origin ? `<span class="badge">${esc(snap.origin)}</span>` : ""}
        <span class="badge">${esc(fmtDate(snap.created_at))}</span>
      </div>
    </article>`,
    )
    .join("");
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
  const container = document.getElementById("search-results");
  if (!result.matches?.length) {
    container.innerHTML =
      '<div class="empty-state">No matches found.</div>';
    return;
  }
  container.innerHTML = result.matches
    .map(
      (m) => `
    <article class="card" data-detail-type="${esc(m.object_type)}" data-remote-id="${esc(m.remote_id)}">
      <h4 class="card-title">${esc(m.title || m.id)}</h4>
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
              <span class="badge">${esc(shortCommit(w.head_commit))}</span>
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

async function openDetail(type, rId) {
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

function activeDecisionIds() {
  const ids = new Set();
  for (const d of state.overview?.active_decisions || []) {
    ids.add(d.id);
  }
  return ids;
}

function renderIntentDetail(payload) {
  const intent = payload.intent;
  const latestSnap = payload.snaps[payload.snaps.length - 1];
  const activeIds = activeDecisionIds();

  const allIds = intent.decision_ids || [];
  const activeLinks = allIds
    .filter((dId) => activeIds.has(dId))
    .map((dId) =>
      linkButton(
        "decision",
        remoteId(payload.workspace_id, dId),
        dId,
        "active constraint",
      ),
    );
  const deprecatedLinks = allIds
    .filter((dId) => !activeIds.has(dId))
    .map((dId) =>
      linkButton(
        "decision",
        remoteId(payload.workspace_id, dId),
        dId,
        "deprecated",
      ),
    );

  const decisionsBody =
    activeLinks.length || deprecatedLinks.length
      ? `${activeLinks.length ? `<div class="detail-link-list">${activeLinks.join("")}</div>` : '<div class="empty-state">No active constraints.</div>'}
         ${deprecatedLinks.length ? `<details class="collapse-toggle is-deprecated"><summary>${deprecatedLinks.length} deprecated</summary><div class="detail-link-list">${deprecatedLinks.join("")}</div></details>` : ""}`
      : '<div class="empty-state">No decisions linked.</div>';

  const allSnaps = [...payload.snaps].reverse();
  const recentSnaps = allSnaps.slice(0, 5);
  const olderSnaps = allSnaps.slice(5);

  const recentSnapLinks = recentSnaps.map((s) =>
    linkButton(
      "snap",
      remoteId(payload.workspace_id, s.id),
      s.title || s.id,
      truncate(s.summary || "", 60),
    ),
  );
  const olderSnapLinks = olderSnaps.map((s) =>
    linkButton(
      "snap",
      remoteId(payload.workspace_id, s.id),
      s.title || s.id,
      truncate(s.summary || "", 60),
    ),
  );

  const snapTimelineBody = allSnaps.length
    ? `<div class="detail-link-list">${recentSnapLinks.join("")}</div>
       ${olderSnapLinks.length ? `<details class="collapse-toggle"><summary>${olderSnaps.length} older snap(s)</summary><div class="detail-link-list">${olderSnapLinks.join("")}</div></details>` : ""}`
    : '<div class="empty-state">No snaps recorded.</div>';

  el.detailContent.innerHTML = `
    <div class="detail-header">
      <span class="detail-id">${esc(intent.id)} \u00b7 Intent</span>
      <h2 class="detail-title">${esc(intent.title)}</h2>
      <div class="detail-meta">
        <span class="badge">${esc(intent.status)}</span>
        ${payload.git.branch ? `<span class="badge">${esc(payload.git.branch)}</span>` : ""}
      </div>
    </div>
    ${detailSection("Latest Summary", formatText(latestSnap?.summary) || `<p>No snap summary yet.</p>`)}
    ${latestSnap?.origin ? detailSection("Origin", `<p>${esc(latestSnap.origin)}</p>`) : ""}
    ${intent.rationale ? detailSection("Rationale", formatText(intent.rationale)) : ""}
    ${intent.source_query ? detailSection("Source Query", formatText(intent.source_query)) : ""}
    ${detailSection("Linked Decisions", decisionsBody)}
    ${detailSection("Snap Timeline (" + allSnaps.length + ")", snapTimelineBody)}
    ${detailSection(
      "Git Context",
      `<div class="detail-kv">
        ${kvRow("Workspace", payload.workspace_id)}
        ${kvRow("Branch", payload.git.branch || "\u2014")}
        ${kvRow("Commit", shortCommit(payload.git.head_commit))}
        ${kvRow("Synced at", fmtDate(payload.synced_at))}
      </div>`,
    )}
    ${rawToggle({ intent, snaps: payload.snaps })}`;
}

function collapsibleLinks(allLinks, visibleCount, olderLabel) {
  if (!allLinks.length) return "";
  const visible = allLinks.slice(0, visibleCount);
  const rest = allLinks.slice(visibleCount);
  let html = `<div class="detail-link-list">${visible.join("")}</div>`;
  if (rest.length) {
    html += `<details class="collapse-toggle"><summary>${rest.length} ${olderLabel}</summary><div class="detail-link-list">${rest.join("")}</div></details>`;
  }
  return html;
}

function renderDecisionDetail(payload) {
  const decision = payload.decision;
  const intentLinks = payload.intents.map((i) =>
    linkButton(
      "intent",
      remoteId(payload.workspace_id, i.id),
      i.title || i.id,
      i.status,
    ),
  );

  const intentsBody = intentLinks.length
    ? collapsibleLinks(intentLinks, 5, "more intent(s)")
    : '<div class="empty-state">No linked intents.</div>';

  el.detailContent.innerHTML = `
    <div class="detail-header">
      <span class="detail-id">${esc(decision.id)} \u00b7 Decision</span>
      <h2 class="detail-title">${esc(decision.title)}</h2>
      <div class="detail-meta">
        <span class="badge">${esc(decision.status)}</span>
        <span class="badge">${payload.intents.length} linked intents</span>
      </div>
    </div>
    ${detailSection("Rationale", formatText(decision.rationale) || `<p>No rationale provided.</p>`)}
    ${decision.deprecated_reason ? detailSection("Deprecated Reason", formatText(decision.deprecated_reason)) : ""}
    ${detailSection("Affected Intents (" + payload.intents.length + ")", intentsBody)}
    ${detailSection(
      "Scope",
      `<div class="detail-kv">
        ${kvRow("Workspace", payload.workspace_id)}
        ${kvRow("Status", decision.status || "\u2014")}
        ${kvRow("Linked intents", String(payload.intents.length))}
        ${kvRow("Synced at", fmtDate(payload.synced_at))}
      </div>`,
    )}
    ${rawToggle({ decision, intents: payload.intents })}`;
}

function renderSnapDetail(payload) {
  const snap = payload.snap;
  const parentLink = payload.intent
    ? relatedLinks(
        [
          linkButton(
            "intent",
            remoteId(payload.workspace_id, payload.intent.id),
            payload.intent.title || payload.intent.id,
            payload.intent.status,
          ),
        ],
        "",
      )
    : '<div class="empty-state">No linked intent.</div>';

  el.detailContent.innerHTML = `
    <div class="detail-header">
      <span class="detail-id">${esc(snap.id)} \u00b7 Snap</span>
      <h2 class="detail-title">${esc(snap.title)}</h2>
      <div class="detail-meta">
        <span class="badge">${esc(snap.status)}</span>
        <span class="badge">${esc(snap.intent_id || "\u2014")}</span>
      </div>
    </div>
    ${detailSection("Summary", formatText(snap.summary) || `<p>No summary.</p>`)}
    ${snap.origin ? detailSection("Origin", `<p>${esc(snap.origin)}</p>`) : ""}
    ${snap.query ? detailSection("Query", formatText(snap.query)) : ""}
    ${snap.rationale ? detailSection("Rationale", formatText(snap.rationale)) : ""}
    ${detailSection("Feedback", formatText(snap.feedback) || `<p>No feedback recorded.</p>`)}
    ${detailSection("Parent Intent", parentLink)}
    ${detailSection(
      "Git Context",
      `<div class="detail-kv">
        ${kvRow("Workspace", payload.workspace_id)}
        ${kvRow("Branch", payload.git.branch || "\u2014")}
        ${kvRow("Commit", shortCommit(payload.git.head_commit))}
        ${kvRow("Synced at", fmtDate(payload.synced_at))}
      </div>`,
    )}
    ${rawToggle({ snap, intent: payload.intent })}`;
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
    el.projectSelect.disabled = true;
    el.projectSelect.innerHTML =
      '<option value="">No projects yet</option>';
    return;
  }
  el.projectSelect.disabled = false;
  el.projectSelect.innerHTML = state.projects
    .map(
      (p) =>
        `<option value="${esc(p.id)}"${p.id === state.currentProjectId ? " selected" : ""}>${esc(p.name)} \u00b7 ${esc(p.repo.owner)}/${esc(p.repo.name)}</option>`,
    )
    .join("");
}

/* ---- Project loading ---- */

async function loadProject(projectId) {
  state.currentProjectId = projectId;
  renderProjectSelector();

  const [overview, handoff] = await Promise.all([
    fetchJson(apiUrl(`/api/v1/projects/${projectId}/overview`)),
    fetchJson(apiUrl(`/api/v1/projects/${projectId}/handoff`)),
  ]);

  state.overview = overview;
  state.handoff = handoff;

  el.intentCount.textContent = overview.active_intents?.length || "";
  el.decisionCount.textContent = overview.active_decisions?.length || "";
  el.snapCount.textContent = overview.recent_snaps?.length || "";

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
  el.projectSelect.addEventListener("change", async (e) => {
    if (!e.target.value) return;
    try {
      state.selectedDetail = null;
      state.overview = null;
      state.handoff = null;
      await loadProject(e.target.value);
    } catch (err) {
      setStatus(err.message, true);
    }
  });

  el.refreshBtn.addEventListener("click", async () => {
    el.refreshBtn.disabled = true;
    el.refreshBtn.textContent = "Refreshing…";
    try {
      await Promise.all([
        loadProjects(),
        new Promise((r) => setTimeout(r, 1000)),
      ]);
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
    try {
      await openDetail(card.dataset.detailType, card.dataset.remoteId);
    } catch (err) {
      setStatus(err.message, true);
    }
  });
}

/* ---- Init ---- */

async function init() {
  try {
    state.config = await fetch("/config.json").then((r) => r.json());
    const route = readRoute();
    el.apiChip.textContent = state.config.apiBaseUrl;

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

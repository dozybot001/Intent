const state = {
  config: null,
  projects: [],
  currentProjectId: null,
  selectedDetail: null,
  searchQuery: "",
};

const elements = {
  statusLine: document.querySelector("#status-line"),
  apiChip: document.querySelector("#api-chip"),
  projectSelect: document.querySelector("#project-select"),
  projectTitle: document.querySelector("#project-title"),
  repoLink: document.querySelector("#repo-link"),
  projectStats: document.querySelector("#project-stats"),
  workspaceGrid: document.querySelector("#workspace-grid"),
  setupGuide: document.querySelector("#setup-guide"),
  intentList: document.querySelector("#intent-list"),
  decisionList: document.querySelector("#decision-list"),
  snapList: document.querySelector("#snap-list"),
  handoffList: document.querySelector("#handoff-list"),
  detailView: document.querySelector("#detail-view"),
  searchForm: document.querySelector("#search-form"),
  searchInput: document.querySelector("#search-input"),
  searchResults: document.querySelector("#search-results"),
  refreshButton: document.querySelector("#refresh-button"),
  intentCount: document.querySelector("#intent-count"),
  decisionCount: document.querySelector("#decision-count"),
  snapCount: document.querySelector("#snap-count"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDate(value) {
  if (!value) {
    return "Unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function shortCommit(value) {
  return value ? value.slice(0, 8) : "No commit";
}

function dirtyBadge(dirty) {
  return dirty ? '<span class="badge warn">Dirty workspace</span>' : '<span class="badge good">Clean workspace</span>';
}

function remoteObjectId(workspaceId, localObjectId) {
  return `${workspaceId}__${localObjectId}`;
}

function readRouteState() {
  const params = new URLSearchParams(window.location.search);
  const detail = params.get("detail");
  const detailType = params.get("detailType");
  return {
    projectId: params.get("project"),
    detail: detail && detailType ? { remoteId: detail, type: detailType } : null,
    query: params.get("q") || "",
  };
}

function writeRouteState() {
  const params = new URLSearchParams();
  if (state.currentProjectId) {
    params.set("project", state.currentProjectId);
  }
  if (state.selectedDetail?.remoteId && state.selectedDetail?.type) {
    params.set("detail", state.selectedDetail.remoteId);
    params.set("detailType", state.selectedDetail.type);
  }
  if (state.searchQuery) {
    params.set("q", state.searchQuery);
  }
  const query = params.toString();
  const nextUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
  window.history.replaceState({}, "", nextUrl);
}

function apiUrl(path) {
  return `${state.config.apiBaseUrl}${path}`;
}

async function fetchJson(url) {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok || payload.ok === false) {
    const message = payload?.error?.message || `Request failed for ${url}`;
    throw new Error(message);
  }
  return payload.result;
}

function updateStatus(message, isError = false) {
  elements.statusLine.textContent = message;
  elements.statusLine.classList.toggle("muted", !isError);
  elements.statusLine.classList.toggle("is-error", isError);
}

function renderEmpty(container, message) {
  container.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
}

function commandSnippet(lines) {
  return `<pre class="command-snippet">${escapeHtml(lines.join("\n"))}</pre>`;
}

function keyValueRow(label, value) {
  return `
    <div class="detail-kv-row">
      <span class="detail-kv-label">${escapeHtml(label)}</span>
      <span class="detail-kv-value">${escapeHtml(value)}</span>
    </div>
  `;
}

function detailSection(title, body) {
  return `
    <section class="detail-section">
      <h4>${escapeHtml(title)}</h4>
      <div class="detail-section-body">${body}</div>
    </section>
  `;
}

function detailLink(type, remoteId, label, meta = "") {
  return `
    <button type="button" class="detail-link" data-detail-type="${escapeHtml(type)}" data-remote-id="${escapeHtml(remoteId)}">
      <span class="detail-link-label">${escapeHtml(label)}</span>
      ${meta ? `<span class="detail-link-meta">${escapeHtml(meta)}</span>` : ""}
    </button>
  `;
}

function renderRelatedLinks(items, emptyMessage) {
  if (!items.length) {
    return `<div class="empty-state">${escapeHtml(emptyMessage)}</div>`;
  }
  return `<div class="detail-link-list">${items.join("")}</div>`;
}

function statCard(label, value, note) {
  return `
    <article class="stat-card">
      <p class="section-kicker">${escapeHtml(label)}</p>
      <p class="stat-value">${escapeHtml(value)}</p>
      <p>${escapeHtml(note)}</p>
    </article>
  `;
}

function objectCard(kind, item, subtitle, extra = "") {
  const detailType = kind === "handoff" ? "intent" : kind;
  return `
    <article class="${kind === "handoff" ? "handoff-card" : "object-card"}"
      data-detail-type="${escapeHtml(detailType)}"
      data-remote-id="${escapeHtml(item.remote_id)}">
      <h4>${escapeHtml(item.title || item.id)}</h4>
      <p>${escapeHtml(subtitle)}</p>
      <div class="object-meta">
        <span class="badge">${escapeHtml(item.id)}</span>
        <span class="badge">${escapeHtml(item.workspace_id)}</span>
        ${extra}
      </div>
    </article>
  `;
}

function clearDetail(message = "Select an intent, decision, or snap to inspect its remote detail.") {
  elements.detailView.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
}

function clearSearch(message = "Search results will appear here.") {
  elements.searchResults.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
}

function renderSetupGuide(mode, project = null) {
  if (!mode) {
    elements.setupGuide.hidden = true;
    elements.setupGuide.innerHTML = "";
    return;
  }

  const loginCmd = `itt hub login --api-base-url ${state.config.apiBaseUrl}`;
  let title = "";
  let intro = "";
  let cards = [];

  if (mode === "unlinked") {
    title = "Start sending semantic history into IntHub";
    intro = "This project has not been linked from any local Intent workspace yet. Run the following commands where your .intent/ data lives.";
    cards = [
      {
        title: "1. Initialize the local workspace",
        body: "Only needed once per repo.",
        command: commandSnippet([
          "itt init",
        ]),
      },
      {
        title: "2. Configure IntHub access",
        body: "Point the local CLI at this IntHub API.",
        command: commandSnippet([
          loginCmd,
        ]),
      },
      {
        title: "3. Link and send the first batch",
        body: "Create the remote binding, then push your current semantic snapshot.",
        command: commandSnippet([
          "itt hub link",
          "itt hub sync",
        ]),
      },
    ];
  } else if (mode === "unsynced") {
    title = `Finish the first sync for ${project?.name || "this project"}`;
    intro = "The project has been linked, but IntHub has not received any workspace snapshot yet. Push one batch from the linked local repo to populate overview, handoff, and search.";
    cards = [
      {
        title: "1. Make sure the CLI points to this IntHub API",
        body: "If you already ran login earlier, you can skip this.",
        command: commandSnippet([
          loginCmd,
        ]),
      },
      {
        title: "2. Push the first semantic snapshot",
        body: "Run this in the linked local Intent workspace.",
        command: commandSnippet([
          "itt hub sync",
        ]),
      },
    ];
  }

  elements.setupGuide.hidden = false;
  elements.setupGuide.innerHTML = `
    <div class="section-head">
      <div>
        <p class="section-kicker">Onboarding</p>
        <h2>${escapeHtml(title)}</h2>
      </div>
    </div>
    <p class="setup-intro">${escapeHtml(intro)}</p>
    <div class="setup-grid">
      ${cards.map((card) => `
        <article class="setup-card">
          <h3>${escapeHtml(card.title)}</h3>
          <p>${escapeHtml(card.body)}</p>
          ${card.command}
        </article>
      `).join("")}
    </div>
  `;
}

function syncSelectedCards() {
  for (const node of document.querySelectorAll("[data-detail-type][data-remote-id]")) {
    const isSelected = state.selectedDetail
      && node.dataset.detailType === state.selectedDetail.type
      && node.dataset.remoteId === state.selectedDetail.remoteId;
    node.classList.toggle("is-selected", Boolean(isSelected));
  }
}

function renderProjectSelector() {
  if (!state.projects.length) {
    elements.projectSelect.disabled = true;
    elements.projectSelect.innerHTML = '<option value="">No projects synced yet</option>';
    return;
  }
  elements.projectSelect.disabled = false;
  elements.projectSelect.innerHTML = state.projects.map((project) => `
    <option value="${escapeHtml(project.id)}"${project.id === state.currentProjectId ? " selected" : ""}>
      ${escapeHtml(project.name)} · ${escapeHtml(project.repo.owner)}/${escapeHtml(project.repo.name)}
    </option>
  `).join("");
}

function renderOverview(overview) {
  const project = overview.project;
  elements.projectTitle.textContent = project.name;
  elements.repoLink.href = `https://github.com/${project.repo.owner}/${project.repo.name}`;
  elements.repoLink.textContent = `${project.repo.owner}/${project.repo.name}`;

  elements.projectStats.innerHTML = [
    statCard("Repo", `${project.repo.owner}/${project.repo.name}`, project.repo.provider),
    statCard("Workspaces", overview.workspaces.length, "Latest synced workspace states"),
    statCard("Active Intents", overview.active_intents.length, "Current goal boundaries"),
    statCard("Active Decisions", overview.active_decisions.length, "Long-lived constraints"),
  ].join("");

  if (!overview.workspaces.length) {
    renderEmpty(elements.workspaceGrid, "No workspace has synced into this project yet.");
    renderSetupGuide("unsynced", project);
  } else {
    renderSetupGuide(null);
    elements.workspaceGrid.innerHTML = overview.workspaces.map((workspace) => `
      <article class="workspace-card">
        <p class="section-kicker">${escapeHtml(workspace.workspace_id)}</p>
        <p><strong>${escapeHtml(workspace.branch || "No branch")}</strong> · ${escapeHtml(shortCommit(workspace.head_commit))}</p>
        <div class="workspace-meta">
          ${dirtyBadge(workspace.dirty)}
          <span class="badge">${escapeHtml(formatDate(workspace.last_synced_at))}</span>
        </div>
      </article>
    `).join("");
  }

  elements.intentCount.textContent = overview.active_intents.length;
  elements.decisionCount.textContent = overview.active_decisions.length;
  elements.snapCount.textContent = overview.recent_snaps.length;

  elements.intentList.innerHTML = overview.active_intents.length
    ? overview.active_intents.map((intent) => objectCard(
      "intent",
      intent,
      `${intent.branch || "No branch"} · ${shortCommit(intent.head_commit)}`,
      `${dirtyBadge(intent.dirty)}`
    )).join("")
    : '<div class="empty-state">No active intents in the latest synced workspaces.</div>';

  elements.decisionList.innerHTML = overview.active_decisions.length
    ? overview.active_decisions.map((decision) => objectCard(
      "decision",
      decision,
      `${decision.intent_ids.length} linked intents`
    )).join("")
    : '<div class="empty-state">No active decisions in the latest synced workspaces.</div>';

  elements.snapList.innerHTML = overview.recent_snaps.length
    ? overview.recent_snaps.map((snap) => objectCard(
      "snap",
      snap,
      snap.summary || "No summary provided",
      `<span class="badge">${escapeHtml(formatDate(snap.created_at))}</span>`
    )).join("")
    : '<div class="empty-state">No snaps have been synced yet.</div>';

  updateStatus(`Viewing ${project.name} across ${overview.workspaces.length} synced workspaces.`);
}

function renderHandoff(handoff) {
  if (!handoff.intents.length) {
    renderEmpty(elements.handoffList, "No active handoff items for this project.");
    return;
  }
  elements.handoffList.innerHTML = handoff.intents.map((intent) => objectCard(
    "intent",
    intent,
    intent.latest_snap?.summary || intent.rationale || intent.source_query || "No latest summary",
    `
      <span class="badge">${escapeHtml(intent.git.branch || "No branch")}</span>
      ${dirtyBadge(intent.git.dirty)}
      <span class="badge">${escapeHtml(formatDate(intent.synced_at))}</span>
    `
  )).join("");
}

function renderDetailCard(title, body, meta = "", raw = null) {
  elements.detailView.innerHTML = `
    <article class="detail-card">
      <h3 class="detail-title">${escapeHtml(title)}</h3>
      <div class="detail-body">
        ${body}
        <div class="detail-meta">${meta}</div>
        ${raw ? `
          <details class="detail-raw-toggle">
            <summary>Open raw payload</summary>
            <pre class="detail-pre">${escapeHtml(JSON.stringify(raw, null, 2))}</pre>
          </details>
        ` : ""}
      </div>
    </article>
  `;
  syncSelectedCards();
}

function renderIntentDetail(payload) {
  const intent = payload.intent;
  const latestSnap = payload.snaps[payload.snaps.length - 1];
  const decisionLinks = (intent.decision_ids || []).map((decisionId) => (
    detailLink(
      "decision",
      remoteObjectId(payload.workspace_id, decisionId),
      decisionId,
      "linked constraint"
    )
  ));
  const snapLinks = [...payload.snaps].reverse().map((snap) => (
    detailLink(
      "snap",
      remoteObjectId(payload.workspace_id, snap.id),
      snap.title || snap.id,
      snap.summary || snap.status || "snap"
    )
  ));
  renderDetailCard(
    `${intent.id} · ${intent.title}`,
    [
      detailSection(
        "Current read",
        `
          <p>${escapeHtml(latestSnap?.summary || "No snap summary yet.")}</p>
          <p>${escapeHtml(intent.rationale || "No rationale recorded.")}</p>
        `
      ),
      detailSection(
        "Source query",
        `<p>${escapeHtml(intent.source_query || "No source query recorded.")}</p>`
      ),
      detailSection(
        "Linked decisions",
        renderRelatedLinks(decisionLinks, "No active decisions are linked to this intent.")
      ),
      detailSection(
        "Snap timeline",
        renderRelatedLinks(snapLinks, "No snaps have been recorded for this intent yet.")
      ),
      detailSection(
        "Git context",
        `
          <div class="detail-kv-grid">
            ${keyValueRow("Workspace", payload.workspace_id)}
            ${keyValueRow("Branch", payload.git.branch || "No branch")}
            ${keyValueRow("Head commit", shortCommit(payload.git.head_commit))}
            ${keyValueRow("Synced at", formatDate(payload.synced_at))}
          </div>
        `
      ),
    ].join(""),
    `
      <span class="badge">${escapeHtml(intent.status)}</span>
      <span class="badge">${escapeHtml(payload.workspace_id)}</span>
      <span class="badge">${escapeHtml(payload.git.branch || "No branch")}</span>
      ${dirtyBadge(payload.git.dirty)}
      <span class="badge">${escapeHtml(formatDate(payload.synced_at))}</span>
    `,
    { intent: payload.intent, snaps: payload.snaps }
  );
}

function renderDecisionDetail(payload) {
  const decision = payload.decision;
  const intentLinks = payload.intents.map((intent) => (
    detailLink(
      "intent",
      remoteObjectId(payload.workspace_id, intent.id),
      intent.title || intent.id,
      intent.status || "intent"
    )
  ));
  renderDetailCard(
    `${decision.id} · ${decision.title}`,
    [
      detailSection(
        "Decision rationale",
        `<p>${escapeHtml(decision.rationale || "No rationale provided.")}</p>`
      ),
      detailSection(
        "Affected intents",
        renderRelatedLinks(intentLinks, "No linked intents were returned for this decision.")
      ),
      detailSection(
        "Scope",
        `
          <div class="detail-kv-grid">
            ${keyValueRow("Workspace", payload.workspace_id)}
            ${keyValueRow("Status", decision.status || "unknown")}
            ${keyValueRow("Linked intents", String(payload.intents.length))}
            ${keyValueRow("Synced at", formatDate(payload.synced_at))}
          </div>
        `
      ),
    ].join(""),
    `
      <span class="badge">${escapeHtml(decision.status)}</span>
      <span class="badge">${escapeHtml(payload.workspace_id)}</span>
      <span class="badge">${escapeHtml(payload.intents.length)} linked intents</span>
      <span class="badge">${escapeHtml(formatDate(payload.synced_at))}</span>
    `,
    { decision: payload.decision, intents: payload.intents }
  );
}

function renderSnapDetail(payload) {
  const snap = payload.snap;
  const parentIntentLink = payload.intent
    ? renderRelatedLinks([
      detailLink(
        "intent",
        remoteObjectId(payload.workspace_id, payload.intent.id),
        payload.intent.title || payload.intent.id,
        payload.intent.status || "intent"
      ),
    ], "")
    : `<div class="empty-state">This snap does not have a linked intent in the latest synced state.</div>`;
  renderDetailCard(
    `${snap.id} · ${snap.title}`,
    [
      detailSection(
        "Summary",
        `<p>${escapeHtml(snap.summary || "No summary provided.")}</p>`
      ),
      detailSection(
        "Feedback",
        `<p>${escapeHtml(snap.feedback || "No feedback recorded.")}</p>`
      ),
      detailSection(
        "Parent intent",
        parentIntentLink
      ),
      detailSection(
        "Git context",
        `
          <div class="detail-kv-grid">
            ${keyValueRow("Workspace", payload.workspace_id)}
            ${keyValueRow("Branch", payload.git.branch || "No branch")}
            ${keyValueRow("Head commit", shortCommit(payload.git.head_commit))}
            ${keyValueRow("Synced at", formatDate(payload.synced_at))}
          </div>
        `
      ),
    ].join(""),
    `
      <span class="badge">${escapeHtml(snap.status)}</span>
      <span class="badge">${escapeHtml(payload.workspace_id)}</span>
      <span class="badge">${escapeHtml(payload.intent?.title || snap.intent_id || "No linked intent")}</span>
      <span class="badge">${escapeHtml(formatDate(payload.synced_at))}</span>
    `,
    { snap: payload.snap, intent: payload.intent }
  );
}

function renderSearchResults(result) {
  if (!result.matches.length) {
    clearSearch("No objects matched that query.");
    return;
  }
  elements.searchResults.innerHTML = result.matches.map((match) => objectCard(
    match.object_type,
    match,
    `${match.object_type} · ${match.status || "unknown"}`
  )).join("");
  syncSelectedCards();
}

async function openDetail(type, remoteId, options = {}) {
  const path = type === "decision"
    ? `/api/v1/decisions/${remoteId}`
    : type === "snap"
      ? `/api/v1/snaps/${remoteId}`
      : `/api/v1/intents/${remoteId}`;
  const payload = await fetchJson(apiUrl(path));
  state.selectedDetail = { type, remoteId };
  if (type === "decision") {
    renderDecisionDetail(payload);
  } else if (type === "snap") {
    renderSnapDetail(payload);
  } else {
    renderIntentDetail(payload);
  }
  syncSelectedCards();
  if (!options.skipUrlUpdate) {
    writeRouteState();
  }
}

async function runSearch(query, options = {}) {
  state.searchQuery = (query || "").trim();
  elements.searchInput.value = state.searchQuery;
  if (!state.currentProjectId || !state.searchQuery) {
    clearSearch();
    if (!options.skipUrlUpdate) {
      writeRouteState();
    }
    return;
  }
  const result = await fetchJson(
    apiUrl(`/api/v1/search?project_id=${encodeURIComponent(state.currentProjectId)}&q=${encodeURIComponent(state.searchQuery)}`)
  );
  renderSearchResults(result);
  if (!options.skipUrlUpdate) {
    writeRouteState();
  }
}

async function loadProject(projectId, options = {}) {
  const preserveDetail = Boolean(options.preserveDetail && state.selectedDetail);
  const preserveSearch = Boolean(options.preserveSearch && state.searchQuery);
  state.currentProjectId = projectId;
  renderProjectSelector();

  if (!preserveDetail) {
    state.selectedDetail = null;
    clearDetail();
  }
  if (!preserveSearch) {
    state.searchQuery = "";
    elements.searchInput.value = "";
    clearSearch();
  }
  writeRouteState();

  const [overview, handoff] = await Promise.all([
    fetchJson(apiUrl(`/api/v1/projects/${projectId}/overview`)),
    fetchJson(apiUrl(`/api/v1/projects/${projectId}/handoff`)),
  ]);
  renderOverview(overview);
  renderHandoff(handoff);
  syncSelectedCards();

  if (preserveDetail && state.selectedDetail) {
    try {
      await openDetail(state.selectedDetail.type, state.selectedDetail.remoteId, { skipUrlUpdate: true });
    } catch (_error) {
      state.selectedDetail = null;
      clearDetail("The selected object is no longer available in the latest synced state.");
    }
  }

  if (preserveSearch && state.searchQuery) {
    try {
      await runSearch(state.searchQuery, { skipUrlUpdate: true });
    } catch (_error) {
      clearSearch("Search could not be restored from the current URL state.");
    }
  }

  writeRouteState();
}

async function loadProjects() {
  const result = await fetchJson(apiUrl("/api/v1/projects"));
  state.projects = result.projects;
  const requested = readRouteState().projectId || state.config.defaultProjectId;
  state.currentProjectId = requested && state.projects.some((project) => project.id === requested)
    ? requested
    : state.projects[0]?.id || null;
  renderProjectSelector();

  if (!state.currentProjectId) {
    updateStatus("No project has been linked and synced into IntHub yet.");
    elements.projectTitle.textContent = "No synced projects yet";
    elements.repoLink.removeAttribute("href");
    elements.repoLink.textContent = "Repository";
    renderSetupGuide("unlinked");
    renderEmpty(elements.projectStats, "Run hub link and hub sync first.");
    renderEmpty(elements.workspaceGrid, "No workspace data yet.");
    renderEmpty(elements.intentList, "No active intents yet.");
    renderEmpty(elements.decisionList, "No active decisions yet.");
    renderEmpty(elements.snapList, "No snaps yet.");
    renderEmpty(elements.handoffList, "No handoff data yet.");
    clearDetail("Once a project syncs, selecting an object will show its remote detail here.");
    clearSearch();
    writeRouteState();
    return;
  }

  await loadProject(state.currentProjectId, {
    preserveDetail: Boolean(state.selectedDetail),
    preserveSearch: Boolean(state.searchQuery),
  });
}

async function handleSearch(event) {
  event.preventDefault();
  if (!state.currentProjectId) {
    return;
  }
  await runSearch(elements.searchInput.value);
}

function bindEvents() {
  elements.projectSelect.addEventListener("change", async (event) => {
    const projectId = event.target.value;
    if (!projectId) {
      return;
    }
    try {
      await loadProject(projectId);
    } catch (error) {
      updateStatus(error.message, true);
    }
  });

  elements.refreshButton.addEventListener("click", async () => {
    try {
      await loadProjects();
    } catch (error) {
      updateStatus(error.message, true);
    }
  });

  elements.searchForm.addEventListener("submit", async (event) => {
    try {
      await handleSearch(event);
    } catch (error) {
      updateStatus(error.message, true);
    }
  });

  document.addEventListener("click", async (event) => {
    const card = event.target.closest("[data-detail-type][data-remote-id]");
    if (!card) {
      return;
    }
    try {
      await openDetail(card.dataset.detailType, card.dataset.remoteId);
    } catch (error) {
      updateStatus(error.message, true);
    }
  });
}

async function init() {
  try {
    state.config = await fetch("/config.json").then((response) => response.json());
    const route = readRouteState();
    state.selectedDetail = route.detail;
    state.searchQuery = route.query;
    elements.searchInput.value = route.query;
    elements.apiChip.textContent = state.config.apiBaseUrl;
    bindEvents();
    await loadProjects();
  } catch (error) {
    updateStatus(error.message, true);
    clearDetail("Failed to initialize the read-only IntHub app.");
  }
}

init();

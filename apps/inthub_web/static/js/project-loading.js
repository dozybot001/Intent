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

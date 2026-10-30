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

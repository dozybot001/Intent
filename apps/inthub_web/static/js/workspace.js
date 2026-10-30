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

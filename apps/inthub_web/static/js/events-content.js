function bindProjectEvents() {
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
    state._teams = null;
    state._home = null;
    state._projectTeam = null;
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
    if (!id) return;
    if (id === state.currentProjectId && id === state._loadedProjectId) {
      if (state.page !== "project") {
        leaveSitePage();
        writeRoute("push");
        el.detailContent.focus?.({ preventScroll: true });
      }
      return;
    }
    leaveSitePage();
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
      if (state.visitor) await loadProject(state.currentProjectId);
      else if (state.page === "project") await loadProjects({ ...readRoute(), detail: null });
      else {
        await refreshProjectList();
        await reloadSitePage();
      }
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
}

function bindContentClicks() {
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
    const exportButton = e.target.closest("[data-export-project]");
    if (exportButton) {
      await exportCurrentProject(exportButton);
      return;
    }
    const deleteProjectButton = e.target.closest("[data-delete-project]");
    if (deleteProjectButton) {
      confirmDeleteProject(deleteProjectButton);
      return;
    }
    const visibilityButton = e.target.closest("[data-change-visibility]");
    if (visibilityButton) {
      confirmVisibility(visibilityButton.dataset.changeVisibility, visibilityButton);
      return;
    }
    const transferButton = e.target.closest("[data-transfer-project]");
    if (transferButton) {
      confirmTransfer(transferButton);
      return;
    }
    const jump = e.target.closest("[data-tab-jump]");
    if (jump) {
      switchTab(jump.dataset.tabJump);
      return;
    }
    const filter = e.target.closest("[data-timeline-intent]");
    if (filter) {
      setTimelineFilter({ intentId: filter.dataset.timelineIntent }, ".timeline-filter-trigger");
      return;
    }
    const authorFilter = e.target.closest("[data-timeline-author]");
    if (authorFilter) {
      setTimelineFilter({ author: authorFilter.dataset.timelineAuthor }, ".author-filter .timeline-filter-trigger");
      return;
    }
    if (e.target.closest("[data-retry-timeline]")) {
      if (state._timeline) state._timeline.error = "";
      renderView();
      return;
    }
    if (e.target.closest("[data-retry-history]")) {
      if (state._history) state._history.error = "";
      renderView();
      return;
    }
    const moreHistory = e.target.closest("#load-more-history");
    if (moreHistory) {
      if (moreHistory.disabled) return;
      const shown = el.detailContent.querySelectorAll(".history-row").length;
      moreHistory.disabled = true;
      moreHistory.textContent = t("Loading…");
      const scroll = window.scrollY;
      await loadHistoryPage();
      window.scrollTo?.(0, scroll);
      el.detailContent.querySelectorAll(".history-row")[shown]?.focus({ preventScroll: true });
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
}

function bindKeyboardEvents() {
  el.drawerClose.addEventListener("click", () => closeDrawer());
  el.drawerBack.addEventListener("click", () => sheetBack().catch((error) => setStatus(error.message, true)));
  el.drawerOverlay.addEventListener("click", (event) => { if (event.detail <= 1) closeDrawer(); });
  // Clicking the backdrop must not pull focus out of the sheet.
  el.drawerOverlay.addEventListener("mousedown", (event) => event.preventDefault());

  document.addEventListener("keydown", (event) => {
    if (el.aboutDialog.open || el.searchDialog.open || el.confirmDialog.open || el.settingsDialog.open) return;
    if (event.key === "Escape" && state.visitor && !el.authGate.classList.contains("is-hidden")) {
      event.preventDefault();
      dismissAuthGate();
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k" && !el.shell.inert && state.page === "project") {
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
    if (event.key === "/" && !typing && !event.metaKey && !event.ctrlKey && !event.altKey && state.page === "project") {
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

function bindEvents() {
  bindShellEvents();
  bindSearchEvents();
  bindAuthEvents();
  bindSiteEvents();
  bindConfirmEvents();
  bindProjectEvents();
  bindContentClicks();
  bindKeyboardEvents();
}

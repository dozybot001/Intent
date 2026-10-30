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
    // A local hub is the user's own: the hosted service's terms say nothing about it.
    el.siteFooter.hidden = !state.config.authRequired;
    authError = callbackErrorMessage();
    const route = readRoute();
    state.activeTab = route.tab;
    state._settingsSection = route.section;
    setActiveTabUI();
    await loadCurrentAccount();
    if (state.config.authRequired && !state.account) {
      if (route.page !== "project" || !route.project || !(await openAsVisitor(route))) {
        showAuthGate(authError);
        return;
      }
      if (authError) setStatus(authError, true);
    } else {
      await loadProjects(route);
      hideAuthGate();
      if (isSiteRoute(route)) await applyRoute(route);
      else if (isDialogRoute(route)) openSettingsDialog(route.page, route.pane, { history: "replace" });
    }
    state._ready = true;
    if (route.search && state.currentProjectId && state.page === "project") openSearch(route.q);
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
      extra: `<button type="button" class="secondary-btn" data-retry-init>${iconLabel("refresh", t("Retry"))}</button>`,
    });
  }
}

init();

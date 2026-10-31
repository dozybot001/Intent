function bindShellEvents() {
  el.statusHome = el.statusLine.parentElement;
  // styles.css keeps the focus ring for keyboards. Shortcuts and bare modifiers do not count: they move no focus.
  document.addEventListener("pointerdown", () => { document.documentElement.dataset.input = "pointer"; }, true);
  document.addEventListener("keydown", (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey || ["Shift", "Meta", "Control", "Alt"].includes(event.key)) return;
    document.documentElement.dataset.input = "keyboard";
  }, true);

  el.drawer.inert = true;
  closeHeaderMenus();
  for (const menu of headerMenus()) menu.trigger.addEventListener("click", event => toggleHeaderMenu(menu.trigger, {focus: event.detail === 0 ? "first" : null}));
  document.addEventListener("click", event => {
    for (const menu of headerMenus()) if (!menu.panel.contains(event.target) && !menu.trigger.contains(event.target)) closeHeaderMenu(menu);
  });
  document.addEventListener("focusin", event => {
    for (const menu of headerMenus()) if (!menu.panel.contains(event.target) && !menu.trigger.contains(event.target)) closeHeaderMenu(menu);
    if (!el.projectPicker.contains(event.target)) toggleProjectPicker(false);
  });
  window.setInterval?.(() => { if (state.config && state.overview) updateSyncChip(); }, 60000);
  document.addEventListener("keydown", event => {
    const openMenu = headerMenus().find(entry => entry.panel.classList.contains("is-open"));
    if (event.key === "Escape" && openMenu) {
      event.preventDefault();
      event.stopImmediatePropagation();
      closeHeaderMenu(openMenu, true);
      return;
    }
    const menu = headerMenus().find(entry => entry.trigger.contains(event.target) || entry.panel.contains(event.target));
    if (!menu) return;
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!menu.panel.classList.contains("is-open")) {
      toggleHeaderMenu(menu.trigger, {focus: event.key === "ArrowUp" || event.key === "End" ? "last" : "first"});
      return;
    }
    const controls = headerMenuControls(menu);
    const current = controls.indexOf(document.activeElement);
    const next = event.key === "Home" ? 0 : event.key === "End" ? controls.length - 1 : current < 0 ? (event.key === "ArrowUp" ? controls.length - 1 : 0) : current + (event.key === "ArrowUp" ? -1 : 1);
    controls[(next + controls.length) % controls.length]?.focus();
  });
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
  for (const button of document.querySelectorAll("[data-language-select]")) button.addEventListener("click", () => window.IntHubI18n.setLanguage(button.dataset.languageSelect));
  window.addEventListener("inthub:language", localizeWorkspace);
  window.addEventListener("inthub:language", followShowcaseLanguage);
  window.addEventListener("popstate", () => applyRoute(readRoute()));
  for (const trigger of document.querySelectorAll("[data-about-open]")) {
    trigger.addEventListener("click", () => {
      state._aboutReturnTrigger = headerMenus().find(menu => menu.panel.contains(trigger))?.trigger || trigger;
      closeHeaderMenus(true);
      el.aboutVersion.textContent = state.config?.productVersion || t("Unavailable");
      el.aboutDialog.showModal();
    });
  }
  el.aboutClose.addEventListener("click", () => el.aboutDialog.close());
  el.aboutDialog.addEventListener("close", () => {
    if (state._aboutReturnTrigger?.isConnected) state._aboutReturnTrigger.focus();
    state._aboutReturnTrigger = null;
  });
}

function bindSearchEvents() {
  el.searchTrigger.addEventListener("click", () => openSearch());
  // Pinyin and other IME compositions search once, when the text is committed.
  el.searchInput.addEventListener("input", (event) => { if (!event.isComposing) scheduleSearch(); });
  el.searchInput.addEventListener("compositionend", () => scheduleSearch());
  el.searchInput.addEventListener("keydown", (event) => {
    if (event.isComposing || event.keyCode === 229) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setActiveSearchOption((state._searchActive || 0) + (event.key === "ArrowDown" ? 1 : -1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      submitSearch();
    }
  });
  el.searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitSearch();
  });
  document.getElementById("search-close")?.addEventListener("click", closeSearch);
  el.searchStatus.addEventListener("click", (event) => {
    const retry = event.target.closest("[data-retry-search]");
    if (retry) runSearch(el.searchInput.value.trim(), retry);
  });
  el.searchResults.addEventListener("pointermove", (event) => {
    const option = event.target.closest("[role=option]");
    if (option && !option.classList.contains("is-active")) setActiveSearchOption(searchOptions().indexOf(option));
  });
  el.searchResults.addEventListener("click", (event) => {
    activateSearchOption(event.target.closest("[role=option]"));
  });
  el.searchDialog.addEventListener("click", (event) => {
    if (event.target === el.searchDialog) closeSearch();
  });
  el.searchDialog.addEventListener("close", () => {
    window.clearTimeout(state._searchTimer);
    beginViewRequest("search");
    state._searchBusy = false;
    const target = state._searchReturnFocus;
    state._searchReturnFocus = null;
    if (target?.isConnected && !sheetIsOpen()) target.focus();
  });
}

function bindAuthEvents() {
  el.tenonLogin.addEventListener("click", (event) => {
    const link = event.target.closest("[data-login-method]");
    if (!link) return;
    if (el.tenonLogin.querySelector(".is-loading")) {
      event.preventDefault();
      return;
    }
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    try { window.localStorage.setItem(LAST_LOGIN_METHOD, link.dataset.loginMethod); } catch { /* The marker is only a convenience. */ }
    setTenonLoginLoading(link.dataset.loginMethod);
  });

  window.addEventListener("pageshow", () => {
    setTenonLoginLoading();
    // Coming back from Tenon's deletion page restores the button.
    for (const button of document.querySelectorAll("[data-delete-account]")) setButtonBusy(button, false, "Opening account management…", "Delete account");
  });

  // Links between pages stay in the app; modified clicks keep their usual meaning.
  document.addEventListener("click", (event) => {
    const link = event.target.closest?.("a[data-route]");
    if (!link || event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    closeHeaderMenus(Boolean(link.closest(".header-menu")));
    toggleProjectPicker(false);
    const target = link.getAttribute("href");
    const dialog = dialogRoute(target);
    if (dialog && isDialogRoute(dialog) && !state.visitor) {
      openSettingsDialog(dialog.page, dialog.pane);
      return;
    }
    if (target !== `${window.location.pathname}${window.location.search}`) window.history.pushState({ inthub: "page" }, "", target);
    applyRoute(readRoute());
  });

  el.signInButton.addEventListener("click", () => showAuthGate("", { keepPage: true }));
  el.authStart.addEventListener("click", (event) => {
    const copy = event.target.closest?.("[data-copy]");
    if (copy) copyText(copy.dataset.copy, t("Command copied."));
  });
  el.authDismiss.addEventListener("click", dismissAuthGate);
}

function bindSiteEvents() {
  const siteInput = (event) => {
    const field = event.target;
    if (field?.name === "token-name" || field?.name === "token-days") {
      state._tokenDraft = { ...(state._tokenDraft || {}), [field.name === "token-name" ? "name" : "days"]: field.value };
      if (field.name === "token-name") setFieldError(field.form, "");
    } else if (field?.name === "invite-role") {
      state._inviteRole = field.value;
    } else if (field?.name === "device-code") {
      field.value = formatDeviceCode(field.value);
      setFieldError(field.form, "");
    } else if (field?.form?.matches?.("[data-team-form]")) {
      updateTeamDraft(field);
    } else if (field?.form?.matches?.("[data-team-settings-form]")) {
      state._team.edit = { name: field.form.elements["team-name"].value, slug: field.form.elements["team-slug"].value };
      setFieldError(field.form, "");
    }
  };
  const siteSubmit = (event) => {
    const form = event.target;
    const submit = form.matches?.("[data-token-form]") ? submitTokenForm
      : form.matches?.("[data-team-form]") ? createTeam
        : form.matches?.("[data-team-settings-form]") ? saveTeam
          : form.matches?.("[data-invite-form]") ? createInvite
            : form.matches?.("[data-device-form]") ? lookupDevice
              : null;
    if (!submit) return;
    event.preventDefault();
    submit(form);
  };
  const siteActions = {
    "[data-revoke-token]": (button) => confirmRevokeToken(button.dataset.revokeToken, button),
    "[data-copy-new-token]": () => state._newToken && copyText(state._newToken.token, t("Token copied.")),
    "[data-copy-invite]": () => state._newInvite && copyText(state._newInvite.url, t("Link copied.")),
    "[data-retry-tokens]": () => {
      state._tokens = null;
      state._tokensError = "";
      renderTokenList();
      return loadAccountTokens();
    },
    "[data-retry-site]": reloadSitePage,
    "[data-delete-account]": startAccountDeletion,
    "[data-revoke-invite]": (button) => revokeInvite(button.dataset.revokeInvite, button),
    "[data-remove-member]": (button) => confirmRemoveMember(button.dataset.removeMember, button),
    "[data-leave-team]": confirmLeaveTeam,
    "[data-delete-team]": confirmDeleteTeam,
    "[data-accept-invite]": acceptInvite,
    "[data-device-approve]": (button) => decideDevice(button, true),
    "[data-device-deny]": (button) => decideDevice(button, false),
  };
  const siteClick = (event) => {
    for (const [selector, action] of Object.entries(siteActions)) {
      const button = event.target.closest?.(selector);
      if (button) {
        action(button);
        return;
      }
    }
  };
  for (const root of [el.siteContent, el.settingsDialogBody]) {
    root.addEventListener("input", siteInput);
    root.addEventListener("submit", siteSubmit);
    root.addEventListener("click", siteClick);
  }
  el.siteContent.addEventListener("change", (event) => {
    if (event.target.matches?.("[data-member-role]")) changeMemberRole(event.target);
  });

  document.addEventListener("click", (event) => {
    const option = event.target.closest?.(".select-option");
    const trigger = event.target.closest?.(".select-trigger");
    if (option) chooseOption(option);
    else if (!trigger) closeSelect();
    else if (trigger.closest("[data-select]") === state._openSelect) closeSelect({ focus: true });
    else openSelect(trigger.closest("[data-select]"));
  });
  document.addEventListener("keydown", selectKeydown, true);
  document.addEventListener("focusin", (event) => { if (!state._openSelect?.contains(event.target)) closeSelect(); });
  document.addEventListener("scroll", (event) => { if (!event.target.closest?.(".select-menu")) closeSelect(); }, true);
  window.addEventListener("resize", () => closeSelect());

  el.settingsDialogClose.addEventListener("click", () => closeSettingsDialog());
  el.settingsDialog.addEventListener("close", () => closeSettingsDialog());
  // Only a press and release on the backdrop itself closes: a text selection dragged off the card ends there too.
  el.settingsDialog.addEventListener("pointerdown", (event) => { state._dialogPress = event.target === el.settingsDialog; });
  el.settingsDialog.addEventListener("click", (event) => {
    if (event.target === el.settingsDialog && state._dialogPress && !state._newToken) closeSettingsDialog();
  });
  for (const dialog of document.querySelectorAll("dialog")) dialog.addEventListener("close", placeStatusLine);
}

function bindConfirmEvents() {
  el.detailContent.addEventListener("input", (event) => {
    if (event.target?.name === "project-name") updateRenameForm(event.target.form);
  });
  el.detailContent.addEventListener("submit", (event) => {
    const form = event.target.closest?.("[data-rename-form]");
    if (!form) return;
    event.preventDefault();
    renameCurrentProject(form);
  });

  el.confirmInput.addEventListener("input", () => {
    if (state._confirm?.expect === undefined) return;
    el.confirmOk.disabled = el.confirmInput.value !== state._confirm.expect;
    el.confirmError.hidden = true;
  });
  el.confirmForm.addEventListener("submit", (event) => {
    event.preventDefault();
    runConfirm();
  });
  el.confirmCancel.addEventListener("click", () => el.confirmDialog.close());
  // Escape does not abandon a request that is already running.
  el.confirmDialog.addEventListener("cancel", (event) => { if (state._confirmBusy) event.preventDefault(); });
  el.confirmDialog.addEventListener("close", () => {
    const target = state._confirm?.returnFocus;
    state._confirm = null;
    el.confirmInput.value = "";
    // The trigger may be gone (a revoked row, a deleted project): fall back to the list or the page.
    const fallback = state._dialog ? el.settingsDialogBody.querySelector?.("#token-list") || el.settingsDialogClose : state.page === "project" ? el.detailContent : el.siteContent;
    (target?.isConnected ? target : fallback).focus?.({ preventScroll: true });
  });
}

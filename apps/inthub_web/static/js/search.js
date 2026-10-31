/* ---- Search palette ---- */

function openSearch(query = null) {
  if (el.shell.inert && !sheetIsOpen()) return;
  if (sheetIsOpen()) closeDrawer();
  closeHeaderMenus();
  toggleProjectPicker(false);
  if (!el.searchDialog.open) {
    state._searchReturnFocus = document.activeElement;
    el.searchDialog.showModal();
  }
  if (query !== null) el.searchInput.value = query;
  el.searchInput.focus();
  el.searchInput.select?.();
  if (el.searchInput.value.trim()) runSearch(el.searchInput.value.trim());
  else renderSearchSuggestions();
}

function closeSearch() {
  if (el.searchDialog.open) el.searchDialog.close();
}

function searchOptions() {
  return [...el.searchResults.querySelectorAll("[role=option]")];
}

function setSearchStatus(message = "", { visible = true, html = "", note = false } = {}) {
  el.searchStatus.innerHTML = html || esc(message);
  el.searchStatus.classList.toggle("visually-hidden", !visible);
  el.searchStatus.classList.toggle("is-note", note);
}

// The server returns at most 50 matches; say so instead of implying that is everything.
function searchSummary(result) {
  const shown = (result?.matches || []).length;
  const total = Number(result?.total) || shown;
  if (result?.truncated && total > shown) {
    return { text: t("Showing {shown} of {total} — refine the search", {shown, total}), visible: true };
  }
  return { text: plural(shown, "{count} result", "{count} results"), visible: false };
}

function searchGroup(key, label, optionsHtml) {
  return `<div role="group" aria-labelledby="search-group-${key}"><div class="search-group-label" id="search-group-${key}" role="presentation">${esc(label)}</div>${optionsHtml}</div>`;
}

function setActiveSearchOption(index) {
  const options = searchOptions();
  el.searchInput.setAttribute("aria-expanded", String(options.length > 0));
  if (!options.length) {
    el.searchInput.removeAttribute("aria-activedescendant");
    return;
  }
  const next = (index + options.length) % options.length;
  options.forEach((option, position) => {
    option.classList.toggle("is-active", position === next);
    option.setAttribute("aria-selected", String(position === next));
  });
  el.searchInput.setAttribute("aria-activedescendant", options[next].id);
  options[next].scrollIntoView?.({ block: "nearest" });
  state._searchActive = next;
}

async function activateSearchOption(option) {
  if (!option) return;
  closeSearch();
  if (option.dataset.tabJump) {
    switchTab(option.dataset.tabJump);
    return;
  }
  try {
    await openDetail(option.dataset.detailType, option.dataset.remoteId);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function renderSearchSuggestions() {
  const tabs = [
    ["overview", t("Overview"), "overview"],
    ["intents", t("Intents"), "intent"],
    ["flow", t("Flow"), "flow"],
    ["snaps", t("Timeline"), "timeline"],
    ["history", t("History"), "history"],
    ["decisions", t("Decisions"), "decision"],
    ...(canManageProject() ? [["settings", t("Settings"), "settings"]] : []),
  ];
  const active = state.handoff?.intents || [];
  let index = 0;
  const option = (attributes, iconName, title, meta = "", side = "") => `
    <div class="search-result" role="option" id="search-option-${index++}" aria-selected="false" ${attributes}>
      ${icon(iconName)}
      <span class="search-result-title">${title}</span>
      ${meta ? `<span class="search-result-meta">${esc(meta)}</span>` : ""}
      ${side ? `<span class="search-result-side">${esc(side)}</span>` : ""}
    </div>`;
  const synced = Boolean(state.overview) && hasHistory();
  el.searchResults.innerHTML = `
    ${active.length ? searchGroup("active", t("Active work"), active.map((intent) => option(`data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}"`, "intent", esc(intent.what), parseCheckpoint(intent.latest_snap).next ? `${t("Next")} · ${truncate(parseCheckpoint(intent.latest_snap).next, 90)}` : "", intent.id)).join("")) : ""}
    ${synced ? searchGroup("goto", t("Go to"), tabs.map(([tab, label, iconName]) => option(`data-tab-jump="${tab}"`, iconName, esc(label))).join("")) : ""}`;
  setSearchStatus(synced ? "" : t("Link a project to search its history."), { visible: !synced });
  setActiveSearchOption(0);
}

function renderSearchResults(result) {
  state._searchResults = result;
  if (!el.searchDialog.open && !state._localizing) return;
  const matches = result.matches || [];
  const query = result.query || state.searchQuery;
  if (!matches.length) {
    el.searchResults.innerHTML = "";
    setSearchStatus(t("No matches found."));
    setActiveSearchOption(0);
    return;
  }
  const groups = [
    ["intent", t("Intents")],
    ["snap", t("Checkpoints")],
    ["decision", t("Decisions")],
  ];
  let index = 0;
  el.searchResults.innerHTML = groups
    .map(([type, label]) => {
      const items = matches.filter((m) => m.object_type === type);
      if (!items.length) return "";
      return searchGroup(type, label, items.map((m) => {
        const title = type === "snap" ? conciseSnapTitle(m) : m.what || m.title || m.id;
        const meta = type === "snap"
          ? intentForSnap(m)?.what || m.intent_id || ""
          : `${type === "decision" ? decisionStatusLabel(m.status) : intentStatusLabel(m.status)}${m.why ? ` · ${truncate(m.why, 90)}` : ""}`;
        return `
          <div class="search-result" role="option" id="search-option-${index++}" aria-selected="false" data-detail-type="${esc(m.object_type)}" data-remote-id="${esc(m.remote_id)}">
            ${icon(type)}
            <span class="search-result-title">${highlight(title, query)}</span>
            <span class="search-result-meta">${esc(meta)}</span>
            <span class="search-result-side">${esc(shortId(m.id))}</span>
          </div>`;
      }).join(""));
    })
    .join("");
  const summary = searchSummary(result);
  setSearchStatus(summary.text, { visible: summary.visible, note: summary.visible });
  setActiveSearchOption(0);
}

async function submitSearch() {
  const query = el.searchInput.value.trim();
  window.clearTimeout(state._searchTimer);
  const fresh = !query || (state._searchResults && state._searchResultQuery === query
    && state._searchResultProject === state.currentProjectId && !state._searchBusy);
  if (!fresh) {
    await runSearch(query);
    if (el.searchInput.value.trim() !== query) return;
  }
  activateSearchOption(el.searchResults.querySelector("[role=option].is-active"));
}

function scheduleSearch(delay = 180) {
  window.clearTimeout(state._searchTimer);
  state._searchTimer = window.setTimeout(() => runSearch(el.searchInput.value.trim()), delay);
}

async function runSearch(query, button = null) {
  state.searchQuery = query;
  const container = el.searchResults;
  const projectId = state.currentProjectId;
  const request = beginViewRequest("search");
  if (!query || !projectId) {
    state._searchBusy = false;
    state._searchResults = null;
    renderSearchSuggestions();
    return;
  }
  state._searchBusy = true;
  if (button) setButtonBusy(button, true, "Searching…", "Retry");
  container.setAttribute("aria-busy", "true");
  if (!container.querySelector("[data-detail-type]")) {
    container.innerHTML = "";
    setSearchStatus(t("Searching…"));
    setActiveSearchOption(0);
  }
  const current = () => ownsViewRequest("search", request) && state.currentProjectId === projectId;
  try {
    const result = await fetchJson(apiUrl(`/api/v1/search?project_id=${encodeURIComponent(projectId)}&q=${encodeURIComponent(query)}`));
    if (!current()) return;
    state._searchResultProject = projectId;
    state._searchResultQuery = query;
    renderSearchResults({ ...result, query });
  } catch (error) {
    if (!current()) return;
    state._searchResults = null;
    container.innerHTML = "";
    setActiveSearchOption(0);
    setSearchStatus("", { html: `<p>${esc(error.message)}</p><button class="secondary-btn" type="button" data-retry-search>${iconLabel("refresh", t("Retry"))}</button>` });
  } finally {
    if (current()) {
      state._searchBusy = false;
      container.setAttribute("aria-busy", "false");
      if (button) setButtonBusy(button, false, "Searching…", "Retry");
    }
  }
}

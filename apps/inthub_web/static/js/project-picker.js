/* ---- Project selector ---- */

function renderProjectSelector() {
  updateDocumentTitle();
  const showcase = isShowcase(state.currentProjectId) && state.page !== "home";
  el.projectPicker.classList.toggle("is-static", state.visitor && !showcase);
  if (!state.projects.length) {
    el.projectPickerTrigger.disabled = true;
    el.projectPickerLabel.textContent = t("No projects yet");
    el.projectPickerDropdown.innerHTML = "";
    return;
  }
  // A visitor reads the one project the link named; only a showcase has anything to pick from.
  el.projectPickerTrigger.disabled = Boolean(state._projectBusy) || (state.visitor && !showcase);
  const onHome = state.page === "home";
  const selected = onHome ? null : state.currentProjectId;
  const home = hasHomePage();
  el.projectPickerLabel.textContent = onHome || (home && !currentProject())
    ? t("All projects")
    : (currentProject() || state.projects[0]).full_name;
  const allProjects = home
    ? `<a role="option" aria-selected="${onHome}" class="project-picker-option project-picker-home${onHome ? " is-selected" : ""}" href="/" data-route>
        ${icon("grid")}<span class="project-picker-option-name">${esc(t("All projects"))}</span>
      </a>`
    : "";
  el.projectPickerDropdown.innerHTML = (showcase ? showcaseOptions() : "") + allProjects + state.projects
    .filter((p) => !(showcase && isShowcase(p.id)))
    .map(
      (p) =>
        `<button type="button" role="option" aria-selected="${p.id === selected ? "true" : "false"}" class="project-picker-option${p.id === selected ? " is-selected" : ""}" data-id="${esc(p.id)}">
          <span class="project-picker-option-name">${esc(p.full_name)}</span>
          <span class="project-picker-option-repo">${esc(p.last_synced_at ? t("Synced {time}", {time: relativeDate(p.last_synced_at)}) : t("Shared history"))}</span>
        </button>`,
    )
    .join("");
}

function toggleProjectPicker(open) {
  const isOpen = open ?? !el.projectPickerDropdown.classList.contains("is-open");
  if (isOpen) closeHeaderMenus();
  el.projectPickerDropdown.classList.toggle("is-open", isOpen);
  el.projectPickerTrigger.classList.toggle("is-open", isOpen);
  el.projectPickerTrigger.setAttribute("aria-expanded", String(isOpen));
}

function updateSyncChip() {
  const ws = [...historySources(state.overview)]
    .sort((left, right) => String(right.last_synced_at || "").localeCompare(String(left.last_synced_at || "")))[0];
  el.syncChip.textContent = ws
    ? t("Synced {time}", {time: relativeDate(ws.last_synced_at)})
    : state.currentProjectId ? t("Not synced") : t("Waiting for first project");
  if (ws) el.syncChip.dataset.tip = fmtDate(ws.last_synced_at);
  else delete el.syncChip.dataset.tip;
  el.syncIndicator.classList.toggle("is-unsynced", !ws);
}

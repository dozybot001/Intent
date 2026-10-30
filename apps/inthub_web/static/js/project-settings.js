/* Project settings: the Settings tab. */

function projectNameProblem(name) {
  if (!name) return t("Enter a project name.");
  if ([...name].length > PROJECT_NAME_MAX) return t("Use {count} characters or fewer.", { count: PROJECT_NAME_MAX });
  if (/[\\/\u0000-\u001f\u007f]/.test(name)) return t("Project names cannot contain slashes or control characters.");
  if (name === "." || name === "..") return t("Choose a name other than . or ..");
  return "";
}

// What the rename field shows: the owner's draft (kept across re-renders) and its problem, if any.
function renameState(project) {
  const draft = state._renameDraft?.projectId === project.id ? state._renameDraft : null;
  const value = draft ? draft.value : project.name;
  const name = value.trim();
  const problem = draft?.error || (name === project.name ? "" : projectNameProblem(name));
  return { value, problem, ready: !problem && name !== project.name };
}

function projectOwner() {
  return state.overview?.project?.owner || null;
}

function isTeamProject() {
  return projectOwner()?.type === "team";
}

function projectSettingsSection() {
  const section = state._settingsSection;
  return section === "danger" || (section === "members" && isTeamProject()) ? section : "general";
}

function renderProjectSettings() {
  const project = currentProject();
  if (!project) return;
  const section = projectSettingsSection();
  const link = (name) => projectPath(project.id, { tab: "settings", ...(name === "general" ? {} : { section: name }) });
  el.detailContent.innerHTML = settingsLayout({
    label: t("Project settings"),
    items: [
      { label: t("General"), icon: "sliders", href: link("general"), current: section === "general" },
      ...(isTeamProject() ? [{ label: t("Members"), icon: "users", href: link("members"), current: section === "members" }] : []),
      { label: t("Danger zone"), icon: "blocker", href: link("danger"), current: section === "danger" },
    ],
    pane: { general: projectGeneralPane, members: projectMembersPane, danger: projectDangerPane }[section](project),
  });
  if (section === "members" && state._projectTeam?.id !== projectOwner().id) loadProjectTeam();
  if (section === "danger" && state.config?.authRequired && !state._teams && !state._teamsError) loadTeams();
}

function projectGeneralPane(project) {
  const rename = renameState(project);
  const visibility = state.overview?.project?.visibility;
  return `
    ${settingsBlock("general", t("General"), `
      <form class="settings-form" data-rename-form novalidate>
        <label class="field-label" for="project-name">${esc(t("Project name"))}</label>
        <div class="field-row">
          <input class="text-field" id="project-name" name="project-name" type="text" value="${esc(rename.value)}" autocomplete="off" autocapitalize="off" spellcheck="false" aria-describedby="project-name-error project-name-note"${rename.problem ? ' aria-invalid="true"' : ""}>
          <button class="button button-secondary" type="submit" data-rename-submit${rename.ready ? "" : " disabled"}>${iconLabel("edit", t("Rename"))}</button>
        </div>
        <p class="field-error" id="project-name-error" role="alert"${rename.problem ? "" : " hidden"}>${esc(rename.problem)}</p>
        <p class="field-note" id="project-name-note">${tHtml("Clones on itt 7.3 or later follow the new name on their next push or pull. Older versions report {code} until they upgrade.", { code: "<code>REMOTE_CHANGED</code>" })}</p>
      </form>`)}
    ${state.config?.authRequired ? settingsBlock("visibility", t("Visibility"), settingsList(settingsRow({
      title: esc(visibility === "public" ? t("Public") : t("Private")),
      meta: esc(visibility === "public"
        ? t("Anyone on the internet can read this project. Only members can push.")
        : t("Only people with access to this project can read it.")),
      control: `<button class="button button-secondary" type="button" data-change-visibility="${visibility === "public" ? "private" : "public"}">${visibility === "public" ? iconLabel("lock", t("Make private")) : iconLabel("globe", t("Make public"))}</button>`,
    }))) : ""}
    ${settingsBlock("export", t("Export"), settingsList(settingsRow({
      title: esc(t("Download project data")),
      meta: esc(t("The current semantic snapshot and the revision list as JSON: everything itt pull can restore.")),
      control: `<button class="button button-secondary" type="button" data-export-project>${iconLabel("download", t("Download export"))}</button>`,
    })))}`;
}

async function loadProjectTeam() {
  const owner = projectOwner();
  if (!owner?.id) return;
  state._projectTeam = { id: owner.id, data: null, error: "" };
  const team = state._projectTeam;
  try {
    team.data = await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(owner.id)}`));
  } catch (error) {
    team.error = error.message;
  }
  if (state._projectTeam !== team || state.page !== "project" || state.activeTab !== "settings") return;
  const list = el.detailContent.querySelector?.("#project-team");
  if (list) list.innerHTML = projectTeamHtml();
  else renderView();
}

function projectTeamHtml() {
  const team = state._projectTeam?.id === projectOwner().id ? state._projectTeam : null;
  if (team?.error) return `<p class="inline-empty">${esc(team.error)}</p>`;
  return team?.data ? settingsList(team.data.members.map((member) => memberRow(member, false)).join("")) : viewLoadingHtml();
}

function projectMembersPane() {
  const owner = projectOwner();
  return settingsBlock("project-members", t("Members"), `<div class="settings-slot" id="project-team">${projectTeamHtml()}</div>`,
    tHtml("Everyone in {team} works on this project. Manage them on the team page.", { team: `<a href="${esc(teamPath(owner.slug))}" data-route>${esc(owner.name)}</a>` }));
}

function transferTargets() {
  const owner = projectOwner();
  const teams = (state._teams || []).filter((team) => team.role === "admin" && team.id !== owner?.id);
  return [
    ...teams.map((team) => ({ value: team.id, label: team.name })),
    ...(owner?.type === "team" ? [{ value: "account", label: t("My account") }] : []),
  ];
}

function transferControlHtml() {
  const targets = transferTargets();
  if (!state._teams && !state._teamsError) return `<span class="settings-role">${esc(t("Loading…"))}</span>`;
  if (!targets.length) return `<a class="settings-link" href="${SETTINGS_PATHS.teams}" data-route>${icon("plus")}${esc(t("Create a team"))}</a>`;
  return `${selectField({ id: "transfer-target", value: targets[0].value, options: targets, label: t("New owner"), className: "transfer-select" })}
    <button class="button button-danger" type="button" data-transfer-project>${iconLabel("transfer", t("Transfer"))}</button>`;
}

function renderTransferControl() {
  const control = el.detailContent.querySelector?.("#transfer-control");
  if (control) control.innerHTML = transferControlHtml();
  else renderView();
}

function projectDangerPane() {
  return settingsBlock("danger", t("Danger zone"), settingsList(`
    ${state.config?.authRequired ? settingsRow({
      title: esc(t("Transfer this project")),
      meta: esc(t("Moves it to a team you administer, or back to your account. Clones follow on their next push or pull.")),
      control: `<div class="transfer-control" id="transfer-control">${transferControlHtml()}</div>`,
    }) : ""}
    ${settingsRow({
      title: esc(t("Delete this project")),
      meta: esc(t("Removes the project and its semantic history from this hub. Local .intent data is not touched.")),
      control: `<button class="button button-danger" type="button" data-delete-project>${iconLabel("trash", t("Delete project"))}</button>`,
    })}`));
}

function updateRenameForm(form) {
  const project = currentProject();
  const input = form?.elements?.["project-name"];
  if (!project || !input) return;
  state._renameDraft = { projectId: project.id, value: input.value, error: "" };
  const rename = renameState(project);
  setFieldError(form, rename.problem);
  form.querySelector("[data-rename-submit]").disabled = !rename.ready;
}

function renameErrorMessage(error, name) {
  if (error.code === "NAME_TAKEN") return t("A project named {name} already exists.", { name });
  if (error.code === "INVALID_INPUT" && error.detail) return error.detail;
  return error.message;
}

async function renameProject(projectId, name) {
  const result = await fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/rename`), {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ name }),
  });
  const { id, name: newName, full_name: fullName } = result.project;
  // The URL carries the ID, so it stays; the picker, the title and the brief take the new name.
  state.projects = state.projects.map((project) => project.id === id ? { ...project, name: newName, full_name: fullName } : project);
  if (state.overview?.project && state._loadedProjectId === id) state.overview.project = { ...state.overview.project, name: newName, full_name: fullName };
  renderProjectSelector();
  return result.project;
}

async function renameCurrentProject(form) {
  const project = currentProject();
  const input = form.elements["project-name"];
  const button = form.querySelector("[data-rename-submit]");
  if (!project || !input || !button || button.disabled) return;
  const name = input.value.trim();
  if (projectNameProblem(name) || name === project.name) {
    updateRenameForm(form);
    return;
  }
  setButtonBusy(button, true, "Renaming…", "Rename");
  try {
    const renamed = await renameProject(project.id, name);
    state._renameDraft = null;
    if (state.activeTab === "settings" && state.page === "project") renderView();
    el.detailContent.querySelector?.("#project-name")?.focus();
    setStatus(t("Renamed to {name}.", { name: renamed.name }));
  } catch (error) {
    state._renameDraft = { projectId: project.id, value: input.value, error: renameErrorMessage(error, name) };
    setButtonBusy(button, false, "Renaming…", "Rename");
    setFieldError(form, state._renameDraft.error);
    button.disabled = true;
    input.focus();
  }
}

function confirmVisibility(visibility, trigger = null) {
  const project = currentProject();
  if (!project) return;
  const going = visibility === "public";
  // The server stops on a likely credential once; confirming after that warning is the decision to publish anyway.
  let acknowledged = false;
  openConfirm({
    title: () => (going ? t("Make {name} public?", { name: project.name }) : t("Make {name} private?", { name: project.name })),
    body: () => (going
      ? t("Anyone on the internet will be able to read all its Intents, Snaps, Decisions and history. Author emails stay hidden from visitors. People who already read it may keep it.")
      : t("Only people with access to this project will be able to read it. Visitors lose access at once.")),
    ...(going ? {
      label: () => tHtml("Type {name} to confirm.", { name: `<strong class="confirm-name">${esc(project.name)}</strong>` }),
      expect: project.name,
    } : { tone: "neutral" }),
    action: going ? "Make public" : "Make private",
    icon: going ? "globe" : "lock",
    busy: "Saving…",
    run: (typed) => changeVisibility(project.id, visibility, typed, acknowledged),
    message: (error) => {
      if (error.code !== "POSSIBLE_SECRETS") return serverMessage(error);
      acknowledged = true;
      const objects = (error.details?.objects || []).map((object) => `${object.id} (${object.kinds.map((kind) => t(kind)).join(", ")})`);
      return t("These may contain credentials: {list}. Check them first. Confirming again publishes anyway.", { list: objects.join(", ") });
    },
    returnFocus: trigger,
  });
}

async function changeVisibility(projectId, visibility, confirm, acknowledgeSecrets = false) {
  await fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/visibility`), {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ visibility, confirm, ...(acknowledgeSecrets ? { acknowledge_secrets: true } : {}) }),
  });
  state.projects = state.projects.map((project) => project.id === projectId ? { ...project, visibility } : project);
  if (state.overview?.project) state.overview.project = { ...state.overview.project, visibility };
  if (state.activeTab === "settings") renderView();
  setStatus(visibility === "public" ? t("This project is now public.") : t("This project is now private."));
}

function transferErrorMessage(error) {
  if (error.code === "NAME_TAKEN") return t("A project with this name already exists there.");
  if (error.code === "TEAM_NOT_FOUND") return t("Choose a team you administer.");
  return serverMessage(error);
}

function confirmTransfer(trigger = null) {
  const project = currentProject();
  const select = el.detailContent.querySelector?.(".transfer-select input");
  const target = transferTargets().find((entry) => entry.value === select?.value);
  if (!project || !target) return;
  openConfirm({
    title: () => t("Transfer {name} to {target}?", { name: project.name, target: target.label }),
    body: () => t("Who can read, push and manage it changes with the owner. Its ID stays, so clones follow on their next push or pull."),
    label: () => tHtml("Type {name} to confirm.", { name: `<strong class="confirm-name">${esc(project.name)}</strong>` }),
    expect: project.name,
    action: "Transfer project",
    icon: "transfer",
    busy: "Transferring…",
    run: (typed) => transferProject(project.id, target, typed),
    message: transferErrorMessage,
    returnFocus: trigger,
  });
}

async function transferProject(projectId, target, confirm) {
  await fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/transfer`), {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ team_id: target.value === "account" ? null : target.value, confirm }),
  });
  setStatus(t("Transferred to {target}.", { target: target.label }));
  state._teams = null;
  state._projectTeam = null;
  await refreshProjectList();
  // Not awaited: the dialog closes as soon as the project has moved, while it reloads under its new owner.
  loadProject(projectId, { history: "replace" }).catch((error) => setStatus(error.message, true));
}

function exportFileName(name) {
  // Keep the name readable (spaces, CJK); drop only what file systems refuse.
  const safe = String(name || "").replace(/[\\/:*?"<>|\u0000-\u001f\u007f]/g, "-").replace(/^\.+/, "").trim();
  return `${safe || "project"}.inthub-export.json`;
}

function downloadFile(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function exportCurrentProject(button) {
  const project = currentProject();
  if (!project || button.disabled) return;
  setButtonBusy(button, true, "Preparing export…", "Download export");
  try {
    const data = await fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(project.id)}/export`));
    downloadFile(exportFileName(data.project?.name || project.name), `${JSON.stringify(data, null, 2)}\n`, "application/json");
    setStatus(t("Export downloaded."));
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setButtonBusy(button, false, "Preparing export…", "Download export");
    button.innerHTML = `${icon("download")}<span>${esc(t("Download export"))}</span>`;
  }
}

function confirmDeleteProject(trigger = null) {
  const project = currentProject();
  if (!project) return;
  openConfirm({
    title: () => t("Delete {name}?", { name: project.name }),
    body: () => t("This removes the project and its semantic history from this hub. Local .intent data is not touched. This cannot be undone."),
    label: () => tHtml("Type {name} to confirm.", { name: `<strong class="confirm-name">${esc(project.name)}</strong>` }),
    expect: project.name,
    action: "Delete project",
    icon: "trash",
    busy: "Deleting…",
    run: (typed) => deleteProject(project.id, typed),
    returnFocus: trigger,
  });
}

async function deleteProject(projectId, confirm) {
  await fetchJson(apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/delete`), {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ confirm }),
  });
  const name = state.projects.find((project) => project.id === projectId)?.name || "";
  state.projects = state.projects.filter((project) => project.id !== projectId);
  state._renameDraft = null;
  setStatus(t("Deleted {name}.", { name }));
  // Go on to another project, to the list of them, or to the empty state when none is left.
  closeDrawer({ history: "none" });
  forgetProject();
  state.activeTab = "overview";
  setActiveTabUI();
  // Not awaited: the dialog closes as soon as the project is gone, while the next one loads.
  openDefault().catch((error) => setStatus(error.message, true));
}

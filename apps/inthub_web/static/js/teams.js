/* Teams: the list in Settings, and each team's own page. */

async function loadTeams() {
  const request = beginViewRequest("teams");
  state._teamsError = "";
  try {
    const result = await fetchJson(apiUrl("/api/v1/teams"));
    if (!ownsViewRequest("teams", request)) return;
    state._teams = result.teams || [];
  } catch (error) {
    if (!ownsViewRequest("teams", request)) return;
    state._teamsError = error.message;
  }
  if (state._dialog === "settings" && state._pane === "teams") renderTeamList();
  else if (state.page === "project" && state.activeTab === "settings") renderTransferControl();
}

// Latin names give a URL to start from; others leave it for the person to type.
function slugFromName(name) {
  const latin = String(name || "").normalize("NFKD").replace(/[̀-ͯ]/g, "");
  if (/[^\x00-\x7f]/.test(latin)) return "";
  return latin.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 39).replace(/^-+|-+$/g, "");
}

function teamSlugProblem(slug) {
  if (!slug) return t("Enter a team URL.");
  return TEAM_SLUG.test(slug) ? "" : t("Use lowercase letters, digits and hyphens, up to 39 characters, with no hyphen at either end.");
}

function teamNameProblem(name) {
  if (!name) return t("Enter a team name.");
  return [...name].length > 80 ? t("Use {count} characters or fewer.", { count: 80 }) : "";
}

function teamRow(team) {
  return `
    <a class="settings-row settings-row-link" href="${esc(teamPath(team.slug))}" data-route>
      <div class="settings-row-copy">
        <strong>${esc(team.name)}</strong>
        <p class="settings-meta">${metaParts([
          team.slug,
          roleLabel(team.role),
          plural(team.members, "{count} member", "{count} members"),
          plural(team.projects, "{count} project", "{count} projects"),
        ])}</p>
      </div>
      <div class="settings-row-control">${icon("chevron")}</div>
    </a>`;
}

function teamFields(idPrefix, name, slug) {
  return `
    <div class="settings-field">
      <label class="field-label" for="${idPrefix}-name">${esc(t("Team name"))}</label>
      <input class="text-field" id="${idPrefix}-name" name="team-name" type="text" value="${esc(name)}" maxlength="80" autocomplete="off" aria-describedby="${idPrefix}-error">
    </div>
    <div class="settings-field">
      <label class="field-label" for="${idPrefix}-slug">${esc(t("Team URL"))}</label>
      <input class="text-field" id="${idPrefix}-slug" name="team-slug" type="text" value="${esc(slug)}" maxlength="39" autocomplete="off" autocapitalize="off" spellcheck="false" aria-describedby="${idPrefix}-error">
    </div>`;
}

function teamListHtml() {
  const teams = state._teams;
  if (state._teamsError) return `<div class="inline-empty settings-retry"><p>${esc(state._teamsError)}</p><button type="button" class="secondary-btn" data-retry-site>${iconLabel("refresh", t("Retry"))}</button></div>`;
  if (!teams) return viewLoadingHtml();
  return teams.length ? settingsList(teams.map(teamRow).join("")) : `<p class="inline-empty">${esc(t("You are not in a team yet."))}</p>`;
}

function renderTeamList() {
  const list = el.settingsDialogBody.querySelector?.("#team-list");
  if (list) list.innerHTML = teamListHtml();
  else renderSettingsDialog();
}

function teamsPane() {
  const draft = state._teamDraft || { name: "", slug: "" };
  return `
    ${settingsBlock("teams", t("Teams"), `<div class="settings-slot" id="team-list">${teamListHtml()}</div>`)}
    ${settingsBlock("new-team", t("New team"), `
      <form class="settings-form team-form" data-team-form novalidate>
        ${teamFields("new-team", draft.name, draft.slug)}
        <button class="button button-primary" type="submit">${iconLabel("plus", t("Create team"))}</button>
        <p class="field-error" id="new-team-error" role="alert" hidden></p>
        <p class="field-note">${esc(t("Lowercase letters, digits and hyphens. Team projects use it in the CLI as team/project."))}</p>
      </form>`)}`;
}

function updateTeamDraft(field) {
  const draft = state._teamDraft ||= { name: "", slug: "", edited: false };
  if (field.name === "team-name") {
    draft.name = field.value;
    if (!draft.edited) {
      draft.slug = slugFromName(field.value);
      const slug = field.form?.elements?.["team-slug"];
      if (slug) slug.value = draft.slug;
    }
  } else {
    draft.slug = field.value;
    draft.edited = Boolean(field.value);
  }
  setFieldError(field.form, "");
}

// The team form's values, or null after marking the field at fault.
function checkTeamForm(form) {
  const name = form.elements["team-name"].value.trim();
  const slug = form.elements["team-slug"].value.trim();
  const nameProblem = teamNameProblem(name);
  const problem = nameProblem || teamSlugProblem(slug);
  setFieldError(form, problem, form.elements[nameProblem ? "team-name" : "team-slug"]);
  return problem ? null : { name, slug };
}

function teamErrorMessage(error, slug) {
  if (error.code === "NAME_TAKEN") return t("The team URL {slug} is taken.", { slug });
  if (error.code === "TEAM_LIMIT") return t("You have reached the limit on teams.");
  return serverMessage(error);
}

async function createTeam(form) {
  const button = form.querySelector("[type=submit]");
  const values = checkTeamForm(form);
  if (!button || button.disabled || !values) return;
  setButtonBusy(button, true, "Creating team…", "Create team");
  try {
    const created = await fetchJson(apiUrl("/api/v1/teams"), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(values) });
    state._teams = null;
    setStatus(t("Created {name}.", { name: created.team.name }));
    window.history.pushState({ inthub: "page" }, "", teamPath(created.team.slug));
    await showTeam(created.team.slug, "members", { history: "none" });
  } catch (error) {
    setFieldError(form, teamErrorMessage(error, values.slug), form.elements["team-slug"]);
    setButtonBusy(button, false, "Creating team…", "Create team");
  }
}

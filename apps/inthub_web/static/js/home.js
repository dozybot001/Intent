/* Home: every project the viewer works on. */

function listedProjects() {
  return state.projects.filter((project) => !project.transient);
}

// Without a default project, two or more projects need a page of their own at /.
function hasHomePage() {
  return !state.visitor && !defaultProjectId() && listedProjects().length >= 2;
}

async function showHome({ history = "replace" } = {}) {
  closeOverlays();
  const arriving = state.page !== "home";
  setPage("home");
  writeRoute(history);
  renderHomePage();
  settlePage(el.siteContent, arriving);
  await loadHome();
}

async function loadHome() {
  const request = beginViewRequest("site");
  state._homeError = "";
  try {
    const result = await fetchJson(apiUrl("/api/v1/home"));
    if (!ownsViewRequest("site", request)) return;
    state._home = result.projects || [];
  } catch (error) {
    if (!ownsViewRequest("site", request)) return;
    state._homeError = error.message;
  }
  if (state.page === "home") renderHomePage();
}

function homeRow(project) {
  const synced = project.last_synced_at ? t("Synced {time}", { time: relativeDate(project.last_synced_at) }) : t("Not synced");
  return `
    <a class="list-row home-row" href="${esc(projectPath(project.id))}" data-route>
      <span class="row-main">
        <strong class="row-title">${esc(project.full_name)}</strong>
        <span class="row-byline">
          <span>${esc(t("{count} active", { count: project.active_intents || 0 }))}</span>
          ${project.blocked_intents ? stateBadge({ key: "blocked", label: t("{count} blocked", { count: project.blocked_intents }) }) : ""}
        </span>
      </span>
      <span class="row-meta">
        ${state.config?.authRequired ? visibilityBadge(project.visibility) : ""}
        <span>${esc(synced)}</span>
      </span>
    </a>`;
}

function renderHomePage() {
  const body = state._homeError
    ? sitePageError(state._homeError)
    : state._home
      ? `<div class="list-card">${state._home.map(homeRow).join("")}</div>`
      : viewLoadingHtml();
  el.siteContent.innerHTML = `<div class="home-page">${pageHeader({ title: t("Projects") })}${body}</div>`;
}

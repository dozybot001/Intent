/* ---- URL state ---- */

// Intent's own history, published once per language.
const SHOWCASE_PROJECTS = { en: "proj_4f7efd975d4a", "zh-CN": "proj_58cc87cb15eb" };

function readRoute() {
  const p = new URLSearchParams(window.location.search);
  const requestedTab = p.get("tab") || "overview";
  const q = p.get("q") || "";
  const path = window.location.pathname.replace(/\/+$/, "");
  const dialog = dialogRoute(path);
  const team = path.match(/^\/teams\/([^/]+)(?:\/(projects|settings))?$/);
  return {
    page: dialog?.page || (team ? "team" : path === "/invite" ? "invite" : path === "/device" ? "device" : "project"),
    pane: dialog?.pane || (team ? team[2] || "members" : ""),
    team: team ? team[1] : "",
    token: p.get("token") || "",
    project: path === "/showcase" ? SHOWCASE_PROJECTS[window.IntHubI18n.language] : p.get("project"),
    tab: TABS.includes(requestedTab) ? requestedTab : "overview",
    section: p.get("section") || "",
    intent: p.get("intent") || "",
    author: p.get("author") || "",
    detail: p.get("detail"),
    detailType: p.get("detailType"),
    q,
    search: requestedTab === "search" || Boolean(q),
  };
}

// Which dialog pane a path opens, if any.
function dialogRoute(path) {
  for (const [page, panes] of Object.entries(DIALOG_PATHS)) {
    const pane = Object.keys(panes).find((name) => panes[name] === path);
    if (pane) return { page, pane };
  }
  return null;
}

function teamPath(slug, pane = "members") {
  return `/teams/${encodeURIComponent(slug)}${pane === "members" ? "" : `/${pane}`}`;
}

function projectPath(projectId, query = {}) {
  return `/?${new URLSearchParams({ project: projectId, ...query })}`;
}

function routeUrl() {
  if (state._dialog) return DIALOG_PATHS[state._dialog][state._pane];
  if (state.page === "team") return teamPath(state._team.slug, state._team.pane);
  if (state.page === "invite") return `/invite${window.location.search}`;
  if (state.page === "device") return "/device";
  if (state.page === "home") return "/";
  const p = new URLSearchParams();
  if (state.currentProjectId) p.set("project", state.currentProjectId);
  if (state.activeTab !== "overview") p.set("tab", state.activeTab);
  if (state.activeTab === "settings" && state._settingsSection && state._settingsSection !== "general") p.set("section", state._settingsSection);
  const timeline = state.activeTab === "snaps" && state._timeline?.projectId === state.currentProjectId ? state._timeline : null;
  if (timeline?.intentId) p.set("intent", timeline.intentId);
  if (timeline?.author) p.set("author", timeline.author);
  if (state.selectedDetail) {
    p.set("detail", state.selectedDetail.remoteId);
    p.set("detailType", state.selectedDetail.type);
  }
  const q = p.toString();
  return q ? `/?${q}` : "/";
}

// "push" creates a browser history entry, "replace" updates the current one,
// "none" is used while applying an entry that the browser already restored.
function writeRoute(mode = "replace", entry = "page") {
  if (mode === "none") return "none";
  const url = routeUrl();
  if (mode === "push" && window.history.pushState && url !== `${window.location.pathname}${window.location.search}`) {
    window.history.pushState({ inthub: entry, sheetPushed: entry === "sheet" }, "", url);
    return "pushed";
  }
  const previous = window.history.state || {};
  const sheetPushed = entry === "sheet" && previous.inthub === "sheet" && Boolean(previous.sheetPushed);
  window.history.replaceState({ ...previous, inthub: entry, sheetPushed }, "", url);
  return "replaced";
}

/* ---- Status ---- */

// A modal dialog leaves the page inert and under its backdrop, so the message moves into the top one.
function placeStatusLine() {
  const parent = [...document.querySelectorAll("dialog[open]")].at(-1) || el.statusHome;
  if (parent && el.statusLine.parentElement !== parent) parent.append(el.statusLine);
}

function setStatus(msg, isError = false) {
  state._statusMessage = window.IntHubI18n.keyFor(msg);
  placeStatusLine();
  el.statusLine.textContent = msg;
  el.statusLine.classList.toggle("muted", !isError);
  el.statusLine.classList.toggle("is-error", isError);
  el.statusLine.classList.add("is-visible");
  window.clearTimeout(setStatus._timer);
  setStatus._timer = window.setTimeout(() => {
    el.statusLine.classList.remove("is-visible");
  }, isError ? 6000 : 2600);
}

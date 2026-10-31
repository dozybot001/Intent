/* Showcase: Intent's own history, published once per language. */

const SHOWCASE_PROJECTS = { en: "proj_4f7efd975d4a", "zh-CN": "proj_58cc87cb15eb" };
const SHOWCASE_LANGUAGES = { en: "English", "zh-CN": "中文" };

function isShowcase(projectId) {
  return Object.values(SHOWCASE_PROJECTS).includes(projectId);
}

function showcaseProject() {
  return SHOWCASE_PROJECTS[window.IntHubI18n.language];
}

// A showcase speaks the page's language, so a link to either version opens the matching one.
function routedProject(path, requested) {
  return path === "/showcase" || isShowcase(requested) ? showcaseProject() : requested;
}

// Picking a version picks the page's language, and the project follows.
function showcaseOptions() {
  return Object.entries(SHOWCASE_LANGUAGES).map(([language, label]) => {
    const selected = SHOWCASE_PROJECTS[language] === state.currentProjectId;
    return `<button type="button" role="option" aria-selected="${selected}" class="project-picker-option${selected ? " is-selected" : ""}" data-language="${language}">
      <span class="project-picker-option-name">${esc(label)}</span>
      <span class="project-picker-option-repo">${esc(t("Showcase"))}</span>
    </button>`;
  }).join("");
}

async function openShowcaseVersion(projectId) {
  if (!state.projects.some((project) => project.id === projectId)) {
    const project = await fetchLinkedProject(projectId);
    if (!project) throw new Error(t("This project does not exist, or you cannot see it."));
    state.projects = state.visitor ? [project] : [...state.projects, project];
  }
  await loadProject(projectId, { history: "replace" });
}

function showcaseOutOfStep() {
  return state.page === "project" && isShowcase(state.currentProjectId) && state.currentProjectId !== showcaseProject();
}

// The language changed under an open showcase: move to the matching version, on the same tab.
async function followShowcaseLanguage() {
  if (state._projectBusy || !showcaseOutOfStep()) return;
  state._projectBusy = true;
  setProjectPickerBusy(true);
  try {
    while (showcaseOutOfStep()) await openShowcaseVersion(showcaseProject());
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    state._projectBusy = false;
    setProjectPickerBusy(false);
  }
}

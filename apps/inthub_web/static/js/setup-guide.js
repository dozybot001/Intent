/* ---- Setup guide ---- */

// A project with no history. Readers cannot push, so a guide to pushing would mislead them.
// Its Settings tab works all the same: a project can be renamed, made public or deleted before its first push.
function renderEmptyProject() {
  if (state.activeTab === "settings" && canManageProject()) {
    renderView();
    return;
  }
  const project = state.overview?.project;
  if (state.visitor || ["read", "public"].includes(project?.permission)) {
    el.shell.classList.add("is-empty");
    el.detailContent.innerHTML = emptyState({
      iconName: "intent",
      title: currentProject()?.full_name || "",
      body: t("Nothing has been published yet."),
    });
    return;
  }
  renderSetupGuide(state.projects.length ? "unsynced" : "unlinked");
}

function renderSetupGuide(mode) {
  el.shell.classList.add("is-empty");
  const projectName = currentProject()?.full_name;
  const linkCmd = `itt remote add origin ${shellArg(state.config.apiBaseUrl)} --project ${projectName ? shellArg(projectName) : "PROJECT"}`;
  const hosted = String(state.config.apiBaseUrl || "").replace(/\/+$/, "") === HOSTED_INTHUB;
  const steps = [];
  if (mode === "unlinked") {
    steps.push(
      { title: t("Install the Intent CLI"), desc: t("Requires Python 3.9+. Re-run any time to upgrade."), cmd: [INSTALL_COMMAND] },
      // Without the Skill an agent never records anything.
      { title: t("Add the agent skill"), desc: t("Needs Node.js. Installs for Claude Code and Codex; add -a cursor and so on for other agents."), cmd: [SKILL_COMMAND] },
      { title: t("Initialize your project"), desc: t("Detects the agent you use, or asks; --host codex / claude-code overrides that. Git is optional."), cmd: ["itt init"] },
    );
  }
  if (state.config.authRequired) {
    steps.push({
      title: t("Sign in from the CLI"),
      desc: t("It shows a code; approve it in the browser."),
      cmd: [hosted ? "itt auth login" : `itt auth login --api-base-url ${shellArg(state.config.apiBaseUrl)}`],
    });
  }
  if (hosted && mode === "unlinked") {
    // The hosted site is the CLI default: a push alone creates the project, named after the directory.
    steps.push({
      title: t("Push"),
      desc: t("Creates the project under this directory's name and pushes its semantic history."),
      cmd: ["itt push"],
      optional: { desc: t("Optional: to use a different project name, link it first."), cmd: [linkCmd] },
    });
  } else {
    // Any other endpoint (IntHub Local, a self-hosted hub) and an existing project need the remote first.
    steps.push({
      title: t("Link and push"),
      desc: mode === "unlinked"
        ? t("Choose a shared project name, then push its semantic history.")
        : t("Ensure CLI points here, then push."),
      cmd: [linkCmd, "itt push"],
    });
  }

  el.detailContent.innerHTML = `
    <div class="setup-page setup-guide">
      ${pageHeader({
        eyebrow: mode === "unlinked" ? t("Welcome") : projectName || t("Project"),
        title: mode === "unlinked" ? t("Get started with IntHub") : t("Complete the first sync"),
        help: "setup",
        meta: [esc(t("Sync semantic history from the Intent CLI, then continue from the brief here."))],
        // The tabs stay hidden until there is something to show, and Settings is the one that works before that.
        actions: mode === "unsynced" && canManageProject()
          ? `<a class="button button-secondary" href="${esc(projectPath(state.currentProjectId, { tab: "settings" }))}" data-route>${iconLabel("settings", t("Project settings"))}</a>`
          : "",
      })}
      <ol class="setup-steps">
        ${steps.map((step) => `
          <li class="setup-step">
            <h3>${esc(step.title)}</h3>
            <p>${esc(step.desc)}</p>
            <div>
              ${commandSnippet(step.cmd)}
              ${step.optional ? `<p class="setup-step-note">${esc(step.optional.desc)}</p>${commandSnippet(step.optional.cmd)}` : ""}
            </div>
          </li>`).join("")}
      </ol>
      <p class="setup-resume">${esc(t("Once the project hooks are trusted, tell the agent “Resume this project through Intent.” to continue later."))}</p>
    </div>`;
}

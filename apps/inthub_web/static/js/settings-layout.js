/* ---- Site pages ---- */

function currentProject() {
  return state.projects.find((project) => project.id === state.currentProjectId) || null;
}

function updateDocumentTitle() {
  const project = currentProject();
  const lead = state._dialog ? dialogTitle() : {
    project: project?.full_name,
    home: t("Projects"),
    team: state._team?.data?.team?.name || state._team?.slug,
    invite: t("Team invite"),
    device: t("Connect a device"),
  }[state.page];
  document.title = lead ? `${lead} · IntHub` : "IntHub";
}

// A translated sentence whose placeholders are markup; the sentence itself is escaped.
function tHtml(key, markup) {
  const text = t(key, Object.fromEntries(Object.keys(markup).map((name) => [name, `\u0001${name}\u0001`])));
  return esc(text).replace(/\u0001(\w+)\u0001/g, (_, name) => markup[name]);
}

function calendarDate(v) {
  const d = new Date(v);
  if (!v || Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat(window.IntHubI18n.language, { year: "numeric", month: "short", day: "numeric" }).format(d);
}

function roleLabel(role) {
  return { admin: t("Admin"), member: t("Member"), viewer: t("Viewer") }[role] || role;
}

function visibilityBadge(visibility) {
  return `<span class="status-pill visibility-pill">${esc(visibility === "public" ? t("Public") : t("Private"))}</span>`;
}

// A monogram: the page only loads its own images, and Tenon accounts carry no avatar URL.
function monogram(name) {
  return `<span class="monogram" aria-hidden="true">${esc([...String(name || "").trim()][0]?.toUpperCase() || "?")}</span>`;
}

// One layout for the Account and Settings dialog, a team and the project's Settings tab: a nav of links and one pane at a time.
function settingsLayout({ title = "", label, items, pane }) {
  return `
    <div class="settings-layout">
      ${title ? `<h1 class="page-title settings-title">${esc(title)}</h1>` : ""}
      <nav class="settings-nav" aria-label="${esc(label)}">
        ${items.map((item) => `<a class="settings-nav-item" href="${esc(item.href)}" data-route${item.current ? ' aria-current="page"' : ""}>${icon(item.icon)}<span>${esc(item.label)}</span></a>`).join("")}
      </nav>
      <div class="settings-pane">${pane}</div>
    </div>`;
}

// Title, hairline, then rows: every block starts and ends on the pane's edges.
function settingsBlock(id, title, body, lead = "") {
  return `
    <section class="settings-block" aria-labelledby="settings-${id}">
      <h2 class="settings-block-title" id="settings-${id}">${esc(title)}</h2>
      ${lead ? `<p class="settings-lead">${lead}</p>` : ""}
      ${body}
    </section>`;
}

// Title and description on the left, the control on the right. Title and meta arrive escaped.
function settingsRow({ title, meta = "", control = "", before = "" }) {
  return `
    <div class="settings-row">
      ${before}
      <div class="settings-row-copy"><strong>${title}</strong>${meta ? `<p class="settings-meta">${meta}</p>` : ""}</div>
      ${control ? `<div class="settings-row-control">${control}</div>` : ""}
    </div>`;
}

function settingsList(rows) {
  return `<div class="settings-list">${rows}</div>`;
}

function metaParts(parts) {
  return parts.filter(Boolean).map((part) => `<span>${esc(part)}</span>`).join("");
}

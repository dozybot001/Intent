/* ---- Shared render pieces ---- */

function pageHeader({ eyebrow = "", title, help = "", meta = [], actions = "" }) {
  const heading = `<h1 class="page-title">${esc(title)}</h1>`;
  return `
    <header class="page-header">
      <div class="page-heading">
        ${eyebrow ? `<span class="eyebrow">${esc(eyebrow)}</span>` : ""}
        ${help ? `<div class="heading-with-help">${heading}${helpButton(help)}</div>` : heading}
        ${meta.length ? `<p class="page-meta">${meta.map((item) => `<span>${item}</span>`).join("")}</p>` : ""}
      </div>
      ${actions ? `<div class="page-actions">${actions}</div>` : ""}
    </header>`;
}

function sectionHeader(title, count, extra = "") {
  return `<header class="section-header"><h2 class="section-title">${esc(title)}${count === undefined ? "" : `<span class="count">${count}</span>`}</h2>${extra}</header>`;
}

function helpButton(topic) {
  return `<button class="help-trigger" data-help="${esc(topic)}" type="button" aria-label="${esc(t("Explanation"))}" aria-expanded="false"><span aria-hidden="true">i</span></button>`;
}

function emptyState({ iconName = "intent", title = "", body = "", extra = "" }) {
  return `
    <div class="empty-state">
      <span class="empty-icon">${icon(iconName)}</span>
      ${title ? `<h3>${esc(title)}</h3>` : ""}
      ${body ? `<p>${esc(body)}</p>` : ""}
      ${extra}
    </div>`;
}

// Each hyphenated word (--depends-on, -g, claude-code) is one inline block, so a narrow screen never breaks a
// line after its hyphen; a word wider than the line still wraps inside its block. Copy uses the plain text.
function shellArg(value) {
  return `'${String(value).replaceAll("'", "'\\''")}'`;
}

function commandSnippet(lines) {
  const text = lines.join("\n");
  const shown = esc(text).replace(/\S*-\S*/g, (word) => `<span class="command-word">${word}</span>`);
  return `<div class="snippet"><pre class="command-snippet">${shown}</pre><button class="icon-button copy-button" type="button" data-copy="${esc(text)}" aria-label="${esc(t("Copy command"))}">${icon("copy")}</button></div>`;
}

function detailSection(title, body, count) {
  return `<section class="detail-section"><h3 class="detail-section-title">${esc(title)}${count === undefined ? "" : `<span class="count">${count}</span>`}</h3>${body}</section>`;
}

function relationItem(type, rId, id, title, meta, status, badge = "") {
  const cls = status === "deprecated"
    ? " rel-deprecated"
    : status === "cancelled"
      ? " rel-cancelled"
      : status === "done"
        ? " rel-muted"
        : "";
  return `<button type="button" class="relation-item${cls}" data-detail-type="${esc(type)}" data-remote-id="${esc(rId)}">
    <span class="row-icon">${icon(type)}</span>
    <span class="relation-title">${esc(title)}</span>
    ${meta || badge ? `<span class="relation-meta">${badge}${esc(meta)}</span>` : ""}
    <span class="relation-side"><span class="row-id">${esc(id)}</span>${status ? statusBadge(status, type) : ""}</span>
  </button>`;
}

function collapsibleRelation(allItems, visibleCount) {
  if (!allItems.length) return "";
  const visible = allItems.slice(0, visibleCount);
  const rest = allItems.slice(visibleCount);
  let html = `<div class="relation-list">${visible.join("")}</div>`;
  if (rest.length) {
    html += `<details class="collapse-toggle"><summary>${icon("chevron")}<span>${esc(t("Show {count} more", {count: rest.length}))}</span></summary><div class="relation-list">${rest.join("")}</div></details>`;
  }
  return html;
}

function rawToggle(data) {
  return `<details class="raw-toggle"><summary>${icon("chevron")}${esc(t("Raw JSON"))}</summary><pre class="raw-pre">${esc(JSON.stringify(data, null, 2))}</pre></details>`;
}

/* ---- Views ---- */

function renderView() {
  if (!state.overview) return;
  el.shell.classList.remove("is-empty");
  switch (state.activeTab) {
    case "intents":
      renderIntentsTab();
      break;
    case "flow":
      renderFlowTab();
      break;
    case "snaps":
      renderSnapsTab();
      break;
    case "history":
      renderHistoryTab();
      break;
    case "decisions":
      renderDecisionsTab();
      break;
    case "settings":
      renderProjectSettings();
      break;
    default:
      renderProjectSummary();
  }
  syncSelected();
}

function syncSelected() {
  const root = state._sheetStack?.[0];
  for (const node of el.detailContent.querySelectorAll("[data-detail-type][data-remote-id]")) {
    const selected = Boolean(root) && node.dataset.detailType === root.type && node.dataset.remoteId === root.remoteId;
    node.classList.toggle("is-selected", selected);
    if (selected) node.setAttribute("aria-current", "true");
    else node.removeAttribute("aria-current");
  }
}

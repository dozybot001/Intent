/* Decisions */

function decisionConstraint(decision, index, deprecated = false) {
  const scope = decisionScope(decision);
  const scopeLabel = scope.count
    ? plural(scope.count, "{count} linked Intent", "{count} linked Intents")
    : t("No Intent scope recorded");
  const scopePreview = scope.titles.length
    ? truncate(scope.titles.join(" · "), 120)
    : scope.count
      ? truncate((decision.intent_ids || []).join(" · "), 120)
      : t("Open the Decision to inspect its recorded rationale.");
  return `
    <button type="button" class="list-row decision-row decision-constraint${deprecated ? " is-deprecated" : ""}" data-detail-type="decision" data-remote-id="${esc(decision.remote_id)}">
      <span class="decision-index" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
      <span class="row-main">
        <strong class="row-title decision-constraint-title">${esc(decision.what)}</strong>
        ${decision.why ? `<span class="row-summary">${esc(truncate(decision.why, 220))}</span>` : ""}
        ${deprecated && decision.reason ? `<span class="row-summary"><b>${esc(t("Reason"))}</b> ${esc(truncate(decision.reason, 200))}</span>` : ""}
        <span class="decision-scope">
          <strong>${esc(scopeLabel)}</strong>
          <span>${esc(scopePreview)}</span>
        </span>
        ${rowByline(decision)}
      </span>
    </button>`;
}

function renderDecisionsTab() {
  const active = [...(state.overview.active_decisions || [])].reverse();
  const deprecated = [...(state.overview.deprecated_decisions || [])].reverse();
  const header = pageHeader({
    title: t("Decisions"),
    help: "decisions",
    meta: active.length || deprecated.length
      ? [esc(t("{count} in effect", {count: active.length})), esc(t("{count} deprecated", {count: deprecated.length}))]
      : [],
  });

  if (!active.length && !deprecated.length) {
    el.detailContent.innerHTML = header + emptyState({
      iconName: "decision",
      title: t("No decisions."),
      body: t("Decisions are durable rules that bind future Intents, such as an architecture choice or a product constraint."),
      extra: commandSnippet(['itt decision create "Rule" --why "Reason"']),
    });
    return;
  }

  const activeHtml = active.length
    ? `<div class="list-card decision-constraint-list">${active.map((decision, index) => decisionConstraint(decision, index)).join("")}</div>`
    : `<div class="object-group-empty">${esc(t("No active cross-Intent constraints."))}</div>`;
  const archiveOpen = state._pageState?.decisionArchiveOpen ?? false;
  const deprecatedHtml = deprecated.length
    ? `<details class="object-archive decision-archive" data-archive="decisions"${archiveOpen ? " open" : ""}>
        <summary>${icon("chevron")}<span>${esc(t("Deprecated history"))}</span><span class="object-archive-count">${deprecated.length}</span></summary>
        <div class="list-card decision-archive-body">
          ${deprecated.map((decision, index) => decisionConstraint(decision, index, true)).join("")}
        </div>
      </details>`
    : "";

  el.detailContent.innerHTML = `
    ${header}
    <section class="object-group decision-group">
      <header class="object-group-header">
        <h2 class="object-group-title">${esc(t("Active constraints"))}</h2>
        <span class="object-group-count">${active.length}</span>
      </header>
      ${activeHtml}
    </section>
    ${deprecatedHtml}`;
}

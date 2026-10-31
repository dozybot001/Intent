/* Overview: the continuation brief */

function relatedIntentId(intent, row) {
  return row.intent.remote_id || remoteId(intent.project_id || state.currentProjectId, row.intent.id);
}

// Where the goal sits, and only the relations someone has to act on, each named in words.
function briefRelations(intent) {
  const { parent, attention } = relationContext(intent);
  if (!parent && !attention.length) return "";
  const item = (row, badge) => `
    <li class="brief-relation">
      ${badge}
      <span class="brief-relation-label">${esc(relationLabel(row.type, row.direction))}</span>
      <button class="brief-relation-target" type="button" data-detail-type="intent" data-remote-id="${esc(relatedIntentId(intent, row))}">${esc(row.intent.what || row.intent.id)}</button>
      <span class="brief-relation-id">${esc(shortId(row.intent.id))}</span>
    </li>`;
  return `<ul class="brief-relations" aria-label="${esc(t("Relations"))}">
    ${parent ? item(parent, ATTENTION_STATES.has(parent.state) ? relationBadge(parent.state, parent) : "") : ""}
    ${attention.map((row) => item(row, relationBadge(row.state, row))).join("")}
  </ul>`;
}

function continuationCard(intent) {
  const snap = intent.latest_snap;
  const checkpoint = parseCheckpoint(snap);
  const snapRemoteId = snap ? remoteId(intent.project_id, snap.id) : "";
  return `
    <article class="brief-card">
      <header class="brief-card-head">
        <div>
          <div class="brief-meta">
            ${statusBadge(intent.status)}
            ${idChip(intent.id)}
            ${snap ? `<span>${esc(t("Updated {time}", {time: relativeDate(snap.created_at)}))}</span>` : `<span>${esc(t("Checkpoint missing"))}</span>`}
          </div>
          <h3 class="brief-title">${esc(intent.what)}</h3>
          ${intent.why ? `<p class="brief-why">${esc(intent.why)}</p>` : ""}
          ${briefRelations(intent)}
        </div>
        <button class="brief-open" type="button" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">${esc(t("Open Intent"))}${icon("arrow")}</button>
      </header>
      ${checkpointGrid(checkpoint)}
      ${checkpoint.constraints ? `<p class="checkpoint-note brief-constraints"><strong>${esc(t("Constraints:"))}</strong> ${esc(checkpoint.constraints)}</p>` : ""}
      <footer class="brief-foot">
        <span class="brief-foot-meta">
          ${snap
            ? `<span>${esc(t("Latest checkpoint"))} <span class="mono">${esc(shortId(snap.id))}</span></span><span>${esc(fmtDate(snap.created_at))}</span>${byline(snap) ? `<span>${esc(byline(snap))}</span>` : ""}${verifiedBadge(snap)}`
            : `<span>${esc(t("No continuation checkpoint recorded."))}</span>`}
        </span>
        ${snap ? `<button class="link-button" type="button" data-detail-type="snap" data-remote-id="${esc(snapRemoteId)}">${esc(t("View checkpoint"))}${icon("arrow")}</button>` : ""}
      </footer>
    </article>`;
}

function pausedRow(intent) {
  const snap = intent.latest_snap;
  const checkpoint = parseCheckpoint(snap);
  const summary = checkpoint.next
    ? `<b>${esc(t("Next"))}</b> ${esc(truncate(checkpoint.next, 200))}`
    : esc(truncate(intent.why || t("No continuation checkpoint recorded."), 200));
  const { attention } = relationContext(intent);
  return `
    <button class="list-row queue-item" type="button" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
      ${rowStatusIcon(intent.status)}
      <span class="row-main">
        <span class="row-title">${esc(intent.what)}</span>
        <span class="row-summary">${summary}</span>
        ${rowByline(intent)}
        ${attention.length ? `<span class="row-relations">${attention.map((row) => `<span class="row-relation">${relationBadge(row.state, row)}<span>${esc(relationLabel(row.type, row.direction))} ${esc(row.intent.id)}</span></span>`).join("")}</span>` : ""}
      </span>
      <span class="row-meta">
        <span class="row-id">${esc(shortId(intent.id))}</span>
        ${snap ? `<span>${esc(t("Updated {time}", {time: relativeDate(snap.created_at)}))}</span>` : ""}
      </span>
    </button>`;
}

function decisionRows(decisions, limit = 5) {
  if (!decisions.length) {
    return `<div class="inline-empty">${esc(t("N/A — no active Decision constrains future work."))}</div>`;
  }
  return `<div class="list-card">${decisions
    .slice(0, limit)
    .map((decision, index) => `
      <button class="list-row decision-row" type="button" data-detail-type="decision" data-remote-id="${esc(decision.remote_id)}">
        <span class="decision-index">${String(index + 1).padStart(2, "0")}</span>
        <span class="row-main">
          <span class="row-title">${esc(decision.what)}</span>
          ${decision.why ? `<span class="row-summary">${esc(truncate(decision.why, 160))}</span>` : ""}
          ${rowByline(decision)}
        </span>
      </button>`)
    .join("")}</div>`;
}

function activityRows(snaps) {
  if (!snaps.length) return `<div class="inline-empty">${esc(t("No snaps synced yet."))}</div>`;
  return `<div class="list-card">${snaps
    .map((snap) => {
      const intent = intentForSnap(snap);
      return `
        <button class="list-row activity-row" type="button" data-detail-type="snap" data-remote-id="${esc(snap.remote_id)}">
          <span class="activity-time">${esc(shortDay(snap.created_at))}</span>
          <span class="row-main">
            <span class="row-title">${esc(conciseSnapTitle(snap))}</span>
            <span class="row-summary">${esc(intent ? intent.what : snap.intent_id || t("Unlinked Intent"))}</span>
          </span>
        </button>`;
    })
    .join("")}</div>`;
}

// Who owns the project and who can read it. Only hosted hubs have owners; a local hub has neither.
function projectOwnerMeta(project) {
  if (!state.config?.authRequired) return [];
  const owner = project.owner;
  const member = project.permission !== "public";
  return [
    ...(owner?.name ? [owner.type === "team" && member ? `<a class="meta-link" href="${esc(teamPath(owner.slug))}" data-route>${esc(owner.name)}</a>` : esc(owner.name)] : []),
    visibilityBadge(project.visibility),
  ];
}

function renderProjectSummary() {
  const project = state.overview.project;
  const history = state.overview.history || {};
  const intents = state.handoff?.intents || [];
  const suspended = state.handoff?.suspended_intents || [];
  const decisions = state.handoff?.active_decisions || [];
  const health = continuationHealth(intents);
  const healthTone = health.ready ? "" : intents.length ? " is-warning" : " is-neutral";
  const healthIcon = health.ready ? "clear" : intents.length ? "blocker" : "intent";

  const brief = intents.length
    ? `<div class="brief-stack">${intents.map(continuationCard).join("")}</div>`
    : emptyState({
        iconName: "intent",
        title: t("No active Intent defines the next move."),
        body: t("History is available, but IntHub cannot name the current goal until an active Intent and a self-contained checkpoint are synced."),
      });

  el.detailContent.innerHTML = `
    <div class="continuation-page">
      ${pageHeader({
        eyebrow: t("Continuation brief"),
        title: project.name,
        meta: [
          ...projectOwnerMeta(project),
          esc(t("Shared history")),
          `<span class="mono">${esc(shortRevision(history.revision))}</span>`,
          esc(history.last_synced_at ? t("Synced {time}", {time: relativeDate(history.last_synced_at)}) : t("Waiting for first sync")),
        ],
        actions: `
          <span class="health-pill${healthTone}">${icon(healthIcon)}${esc(health.label)}</span>
          <button class="button button-secondary" type="button" data-copy-brief>${iconLabel("copy", t("Copy brief"))}</button>`,
      })}

      <section class="section">
        ${sectionHeader(t("Active work"), intents.length)}
        ${brief}
      </section>

      ${suspended.length ? `
        <section class="section">
          ${sectionHeader(t("Suspended"), suspended.length)}
          <div class="list-card">${suspended.map(pausedRow).join("")}</div>
        </section>` : ""}

      <div class="overview-columns">
        <section class="section">
          ${sectionHeader(t("Active decisions"), decisions.length, decisions.length > 5 ? `<button class="link-button" type="button" data-tab-jump="decisions">${esc(t("View all"))}${icon("arrow")}</button>` : "")}
          ${decisionRows([...decisions].reverse())}
        </section>
        <section class="section">
          ${sectionHeader(t("Recent activity"), undefined, state.overview.recent_snaps?.length ? `<button class="link-button" type="button" data-tab-jump="snaps">${esc(t("View timeline"))}${icon("arrow")}</button>` : "")}
          ${activityRows((state.overview.recent_snaps || []).slice(0, 6))}
        </section>
      </div>
    </div>`;
}

function briefMarkdown() {
  const project = state.overview.project;
  const history = state.overview.history || {};
  const intents = state.handoff?.intents || [];
  const suspended = state.handoff?.suspended_intents || [];
  const decisions = state.handoff?.active_decisions || [];
  const lines = [
    `# ${project.name} · ${t("Continuation brief")}`,
    "",
    `${t("Shared history")} ${shortRevision(history.revision)} · ${t("Synced {time}", {time: fmtDate(history.last_synced_at)})}`,
    "",
  ];
  // The same relations the cards show: the parent, then blockers, conflicts and pending handovers.
  const relationLine = (row) => `${row.intent.what || row.intent.id} (${row.intent.id})${ATTENTION_STATES.has(row.state) ? ` · ${relationStateLabel(row.state, row)}` : ""}`;
  if (!intents.length) lines.push(t("No active Intent defines the next move."), "");
  for (const intent of intents) {
    const checkpoint = parseCheckpoint(intent.latest_snap);
    const { parent, attention } = relationContext(intent);
    lines.push(`## ${intent.what} (${intent.id})`, "");
    if (intent.why) lines.push(`${t("Why")}: ${intent.why}`, "");
    for (const row of [parent, ...attention].filter(Boolean)) lines.push(`- **${relationLabel(row.type, row.direction)}:** ${relationLine(row)}`);
    for (const [label, value] of [[t("Next"), checkpoint.next], [t("Blocker"), checkpoint.blocker], [t("Boundary"), checkpoint.boundary], [t("Verified"), checkpoint.verified]]) {
      lines.push(`- **${label}:** ${value || t("Not explicitly recorded in the latest Snap.")}`);
    }
    if (checkpoint.constraints) lines.push(`- **${t("Constraints:")}** ${checkpoint.constraints}`);
    lines.push("");
  }
  if (suspended.length) {
    lines.push(`## ${t("Suspended")}`, "", ...suspended.map((intent) => {
      const { attention } = relationContext(intent);
      return `- ${intent.what} (${intent.id})${attention.map((row) => `; ${relationLabel(row.type, row.direction)} ${relationLine(row)}`).join("")}`;
    }), "");
  }
  lines.push(`## ${t("Active decisions")}`, "");
  lines.push(...(decisions.length ? decisions.map((decision) => `- ${decision.what} (${decision.id})`) : [t("N/A — no active Decision constrains future work.")]));
  return `${lines.join("\n").trim()}\n`;
}

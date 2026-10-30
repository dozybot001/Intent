/* History */

// Who pushed: the signed-in account when there is one, else what the CLI declared.
function pushedBy(revision) {
  return revision?.pushed_by?.name || revision?.pushed_by?.login || revision?.pusher?.name || revision?.pusher?.email || "";
}

function joinList(items) {
  if (items.length < 2) return items[0] || "";
  return t("{items} and {last}", { items: items.slice(0, -1).join(t(", ")), last: items.at(-1) });
}

// One sentence for a revision: "Added 2 Intents and 5 Snaps; changed 1 Decision".
function revisionSummary(summary = {}) {
  const counts = (kind) => joinList([
    ["intents", "{count} Intent", "{count} Intents"],
    ["snaps", "{count} Snap", "{count} Snaps"],
    ["decisions", "{count} Decision", "{count} Decisions"],
  ].filter(([collection]) => summary[`${collection}_${kind}`]).map(([collection, one, other]) => plural(summary[`${collection}_${kind}`], one, other)));
  const added = counts("added");
  const changed = counts("changed");
  if (added && changed) return t("Added {added}; changed {changed}", { added, changed });
  if (added) return t("Added {items}", { items: added });
  return changed ? t("Changed {items}", { items: changed }) : t("No semantic changes");
}

function revisionPageUrl(projectId, offset = 0, limit = REVISION_PAGE_SIZE) {
  return apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/revisions?${new URLSearchParams({ offset: String(offset), limit: String(limit) })}`);
}

function resetHistory() {
  state._history = { projectId: state.currentProjectId, revisions: [], total: null, hasMore: false, loaded: false, loading: false, error: "" };
  return state._history;
}

async function loadHistoryPage() {
  const history = state._history;
  if (!history || history.loading || (history.loaded && !history.hasMore)) return;
  history.loading = true;
  history.error = "";
  try {
    const page = await fetchJson(revisionPageUrl(history.projectId, history.revisions.length));
    if (state._history !== history) return;
    const seen = new Set(history.revisions.map((entry) => entry.revision));
    history.revisions.push(...(page?.revisions || []).filter((entry) => !seen.has(entry.revision)));
    history.total = Number.isFinite(page?.total) ? page.total : history.revisions.length;
    history.hasMore = Boolean(page?.has_more) && Boolean((page?.revisions || []).length);
    history.loaded = true;
  } catch (error) {
    if (state._history !== history) return;
    history.error = error.message || t("Could not load data. Try again.");
  } finally {
    history.loading = false;
  }
  if (state._history === history && state.activeTab === "history" && state.overview && state.currentProjectId === history.projectId) renderView();
}

function revisionRow(revision, projectId) {
  const who = pushedBy(revision);
  return `
    <button type="button" class="list-row history-row" data-detail-type="revision" data-remote-id="${esc(remoteId(projectId, revision.revision))}">
      <span class="row-main">
        <strong class="row-title">${esc(revisionSummary(revision.summary))}</strong>
        <span class="row-byline">
          ${who ? `<span>${esc(who)}</span>` : ""}
          <span data-tip="${esc(fmtDate(revision.created_at))}">${esc(relativeDate(revision.created_at))}</span>
          ${revision.parent ? "" : `<span class="chip">${esc(t("First push"))}</span>`}
        </span>
      </span>
      <span class="row-id">${esc(shortRevision(revision.revision))}</span>
    </button>`;
}

function renderHistoryTab() {
  let history = state._history;
  if (!history || history.projectId !== state.currentProjectId) history = resetHistory();
  const header = pageHeader({
    title: t("History"),
    help: "history",
    meta: history.total ? [esc(plural(history.total, "{count} push", "{count} pushes"))] : [],
  });
  if (history.loaded && !history.revisions.length) {
    el.detailContent.innerHTML = header + emptyState({
      iconName: "history",
      title: t("No pushes yet."),
      body: t("Each push is one revision: what changed, who pushed it and when."),
      extra: commandSnippet(["itt push"]),
    });
    return;
  }
  const remaining = Math.max(0, (history.total ?? history.revisions.length) - history.revisions.length);
  const list = groupByDay(history.revisions).map((group) => `
    <section class="history-group">
      <h2 class="history-day"><span>${esc(group.label)}</span><span>${group.items.length}</span></h2>
      <div class="list-card">${group.items.map((revision) => revisionRow(revision, history.projectId)).join("")}</div>
    </section>`).join("");
  const body = !history.loaded
    ? history.error
      ? `<div class="empty-state"><p>${esc(history.error)}</p><button type="button" class="secondary-btn" data-retry-history>${iconLabel("refresh", t("Retry"))}</button></div>`
      : viewLoadingHtml()
    : list
      + (history.error ? `<p class="timeline-error" role="alert">${esc(history.error)}</p>` : "")
      + (history.hasMore ? `<button type="button" class="load-more-btn" id="load-more-history"${history.loading ? ' disabled aria-busy="true"' : ""}>${iconLabel("chevronDown", history.loading ? t("Loading…") : t("Load more ({count})", {count: remaining}))}</button>` : "");
  el.detailContent.innerHTML = `${header}<div class="history" aria-busy="${history.loading || !history.loaded && !history.error}">${body}</div>`;
  if (!history.loaded && !history.loading && !history.error) loadHistoryPage();
}

function revisionObjectRow(type, object, projectId) {
  const title = type === "snap" ? conciseSnapTitle(object) : object.what || object.id;
  return relationItem(type, remoteId(projectId, object.id), object.id, title, byline(object), type === "snap" ? "" : object.status);
}

function revisionChange(change, type, projectId) {
  if (change.field === "status") {
    const label = (status) => (type === "decision" ? decisionStatusLabel(status) : intentStatusLabel(status));
    return `<li><span>${esc(label(change.from))} → ${esc(label(change.to))}</span>${change.reason ? `<span class="revision-reason">${esc(change.reason)}</span>` : ""}</li>`;
  }
  const target = `<button type="button" class="revision-target" data-detail-type="intent" data-remote-id="${esc(remoteId(projectId, change.intent))}">${esc(change.intent)}</button>`;
  return `<li><span>${tHtml(change.action === "removed" ? "Removed: {relation} {intent}" : "Added: {relation} {intent}", { relation: esc(relationLabel(change.type, "out")), intent: target })}</span></li>`;
}

function revisionChangedRow(type, item, projectId) {
  return `<div class="revision-changed">
    ${revisionObjectRow(type, item.object, projectId)}
    <ul class="revision-changes">${item.changes.map((change) => revisionChange(change, type, projectId)).join("")}</ul>
  </div>`;
}

// Each list stops at 200 entries while the summary stays exact, so a long push says what it left out.
function revisionList(rows, total) {
  const hidden = total - rows.length;
  return collapsibleRelation(rows, 8) + (hidden > 0 ? `<p class="revision-more">${esc(t("{count} more not shown", {count: hidden}))}</p>` : "");
}

function buildRevisionDetailHtml(payload) {
  const summary = payload.summary || {};
  const changes = payload.changes || {};
  const projectId = payload.project_id;
  const who = pushedBy(payload);
  const collections = [
    ["intents", "intent", t("Added Intents")],
    ["snaps", "snap", t("Added Snaps")],
    ["decisions", "decision", t("Added Decisions")],
  ];
  const sections = collections.map(([collection, type, title]) => {
    const total = summary[`${collection}_added`] || 0;
    const rows = (changes[collection]?.added || []).map((object) => revisionObjectRow(type, object, projectId));
    return total ? detailSection(title, revisionList(rows, total), total) : "";
  });
  const changed = collections.flatMap(([collection, type]) => (changes[collection]?.changed || []).map((item) => revisionChangedRow(type, item, projectId)));
  const changedTotal = collections.reduce((sum, [collection]) => sum + (summary[`${collection}_changed`] || 0), 0);
  if (changedTotal) sections.push(detailSection(t("Changed"), revisionList(changed, changedTotal), changedTotal));
  return `
    <div class="detail-header">
      ${detailMeta([
        payload.parent ? "" : `<span class="chip">${esc(t("First push"))}</span>`,
        idChip(shortRevision(payload.revision)),
        who ? `<span>${esc(t("Pushed by {name}", {name: who}))}</span>` : "",
        `<span>${esc(fmtDate(payload.created_at))}</span>`,
      ])}
      <h2 class="detail-title" tabindex="-1">${esc(revisionSummary(summary))}</h2>
    </div>
    ${sections.join("") || `<div class="inline-empty">${esc(t("This push added and changed nothing."))}</div>`}
    ${rawToggle(payload)}`;
}

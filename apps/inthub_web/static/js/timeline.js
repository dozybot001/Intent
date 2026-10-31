/* Timeline */

function snapNumber(id) {
  return Number(String(id || "").match(/(\d+)$/)?.[1] || 0);
}

// Filter choices come from the Intents, not from loaded pages, so every Intent with Snaps is reachable.
// Most recently active first: Snap IDs grow with time inside a project.
function timelineIntentOptions(intents) {
  return (intents || [])
    .filter((intent) => (intent.snap_ids || []).length)
    .map((intent) => ({ key: intent.id, count: intent.snap_ids.length, label: intent.what || intent.id, latest: snapNumber(intent.latest_snap_id || intent.snap_ids.at(-1)) }))
    .sort((left, right) => right.latest - left.latest || left.label.localeCompare(right.label));
}

function snapPageUrl(projectId, { offset = 0, limit = SNAP_PAGE_SIZE, intentId = "", author = "" } = {}) {
  const query = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (intentId) query.set("intent_id", intentId);
  if (author) query.set("author", author);
  return apiUrl(`/api/v1/projects/${encodeURIComponent(projectId)}/snaps?${query}`);
}

function resetTimeline(intentId = "", author = "") {
  state._timeline = { projectId: state.currentProjectId, intentId, author, snaps: [], total: null, hasMore: false, loaded: false, loading: false, error: "" };
  return state._timeline;
}

// A link can carry the timeline's filters; they apply when that project's timeline first opens.
function routedTimelineFilters(projectId) {
  const route = readRoute();
  return route.tab === "snaps" && (!route.project || route.project === projectId)
    ? { intentId: route.intent, author: route.author }
    : { intentId: "", author: "" };
}

function setTimelineFilter(change, trigger) {
  const current = state._timeline;
  resetTimeline(change.intentId ?? current?.intentId ?? "", change.author ?? current?.author ?? "");
  renderView();
  writeRoute("push");
  el.detailContent.querySelector(trigger)?.focus();
}

// Pages are newest first; the server filters by Intent. A newer timeline (filter, project) owns the view.
async function loadTimelinePage() {
  const timeline = state._timeline;
  if (!timeline || timeline.loading || (timeline.loaded && !timeline.hasMore)) return;
  timeline.loading = true;
  timeline.error = "";
  try {
    const page = await fetchJson(snapPageUrl(timeline.projectId, { offset: timeline.snaps.length, intentId: timeline.intentId, author: timeline.author }));
    if (state._timeline !== timeline) return;
    const seen = new Set(timeline.snaps.map((snap) => snap.remote_id));
    for (const snap of page?.snaps || []) {
      const entry = { ...snap, remote_id: snap.remote_id || remoteId(snap.project_id || timeline.projectId, snap.id) };
      if (seen.has(entry.remote_id)) continue;
      seen.add(entry.remote_id);
      timeline.snaps.push(entry);
      rememberSnap(entry);
    }
    timeline.total = Number.isFinite(page?.total) ? page.total : timeline.snaps.length;
    timeline.hasMore = Boolean(page?.has_more) && Boolean((page?.snaps || []).length);
    timeline.loaded = true;
  } catch (error) {
    if (state._timeline !== timeline) return;
    timeline.error = error.message || t("Could not load data. Try again.");
  } finally {
    timeline.loading = false;
  }
  if (state._timeline !== timeline || state.activeTab !== "snaps" || !state.overview || state.currentProjectId !== timeline.projectId) return;
  const refocus = document.activeElement?.closest?.(".timeline-filter-trigger");
  const author = Boolean(refocus?.closest?.(".author-filter"));
  renderView();
  if (refocus) el.detailContent.querySelector(author ? ".author-filter .timeline-filter-trigger" : ".timeline-filter-trigger")?.focus();
}

function timelineDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { key: "undated", label: t("Undated"), time: "—", datetime: "" };
  }
  const dayKey = (entry) => [
    entry.getFullYear(),
    String(entry.getMonth() + 1).padStart(2, "0"),
    String(entry.getDate()).padStart(2, "0"),
  ].join("-");
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const key = dayKey(date);
  const label = key === dayKey(today)
    ? t("Today")
    : key === dayKey(yesterday)
      ? t("Yesterday")
      : new Intl.DateTimeFormat(window.IntHubI18n.language, {
          month: "short",
          day: "numeric",
          weekday: "short",
          year: date.getFullYear() === today.getFullYear() ? undefined : "numeric",
        }).format(date);
  return {
    key,
    label,
    time: new Intl.DateTimeFormat(window.IntHubI18n.language, {
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(date),
    datetime: date.toISOString(),
  };
}

function snapTimelineEntry(snap) {
  const checkpoint = parseCheckpoint(snap);
  const recordedAt = timelineDate(snap.created_at);
  const status = timelineState(checkpoint);
  const intent = intentForSnap(snap);
  const supportingValue = checkpoint.next || checkpoint.boundary || snap.why || "";
  const supportingLabel = checkpoint.next
    ? t("Next")
    : checkpoint.boundary
      ? t("Boundary")
      : t("Context");
  return `
    <button type="button" class="timeline-entry${status.className}" data-detail-type="snap" data-remote-id="${esc(snap.remote_id)}">
      <time datetime="${esc(recordedAt.datetime)}">${esc(recordedAt.time)}</time>
      <span class="timeline-node" aria-hidden="true"></span>
      <span class="timeline-entry-body">
        <span class="timeline-entry-topline">
          ${idChip(snap.id)}
          ${status.key === "blocked" ? stateBadge(status) : ""}
          <span class="timeline-entry-time-inline">${esc(recordedAt.time)}</span>
          <span class="timeline-entry-intent">${esc(intent ? intent.what : snap.intent_id || t("Unlinked Intent"))}</span>
        </span>
        <strong class="timeline-entry-title">${esc(conciseSnapTitle(snap, 120))}</strong>
        ${supportingValue ? `<span class="timeline-entry-summary"><i>${esc(supportingLabel)}</i>${esc(truncate(supportingValue, 240))}</span>` : ""}
        ${rowByline(snap)}
      </span>
    </button>`;
}

// Consecutive items of one local day, for the Timeline and History lists.
function groupByDay(items) {
  const groups = [];
  for (const item of items) {
    const date = timelineDate(item.created_at);
    const current = groups.at(-1);
    if (current?.key === date.key) current.items.push(item);
    else groups.push({ key: date.key, label: date.label, items: [item] });
  }
  return groups;
}

function renderTimeline(timeline) {
  const groups = groupByDay(timeline.snaps);
  const remaining = Math.max(0, (timeline.total ?? timeline.snaps.length) - timeline.snaps.length);
  const more = timeline.hasMore
    ? `<button type="button" class="load-more-btn" id="load-more-snaps"${timeline.loading ? ' disabled aria-busy="true"' : ""}>${iconLabel("chevronDown", timeline.loading ? t("Loading…") : t("Load more ({count})", {count: remaining}))}</button>`
    : "";
  return groups
    .map((group) => `
      <section class="timeline-group">
        <h2 class="timeline-day"><span>${esc(group.label)}</span><span>${group.items.length}</span></h2>
        <div class="timeline-events">${group.items.map(snapTimelineEntry).join("")}</div>
      </section>`)
    .join("")
    + (timeline.error ? `<p class="timeline-error" role="alert">${esc(timeline.error)}</p>` : "")
    + more;
}

function renderSnapsTab() {
  const total = state.overview.total_snaps ?? (state.overview.recent_snaps || []).length;
  if (!total) {
    el.detailContent.innerHTML = pageHeader({ title: t("Timeline") }) + emptyState({
      iconName: "timeline",
      title: t("No snaps synced yet."),
      body: t("Snaps are verified checkpoints. They appear here once they reach main."),
    });
    return;
  }
  let timeline = state._timeline;
  if (!timeline || timeline.projectId !== state.currentProjectId) timeline = resetTimeline("");
  const options = timelineIntentOptions(overviewIntents());
  // The author menu only appears once a project has two authors; a filter nothing can clear is dropped.
  const authors = (state.overview.authors || []).length >= 2 ? state.overview.authors : [];
  const staleIntent = timeline.intentId && !options.some((option) => option.key === timeline.intentId);
  const staleAuthor = timeline.author && !authors.some((entry) => entry.key === timeline.author);
  if (staleIntent || staleAuthor) {
    timeline = resetTimeline(staleIntent ? "" : timeline.intentId, staleAuthor ? "" : timeline.author);
    writeRoute("replace");
  }
  const selected = options.find((option) => option.key === timeline.intentId);
  const author = authors.find((entry) => entry.key === timeline.author);
  const optionHtml = (attribute, value, chosen, label, count) => `<button type="button" class="timeline-filter-option${chosen === value ? " is-selected" : ""}" ${attribute}="${esc(value)}" aria-pressed="${chosen === value}"><span>${esc(label)}</span><small>${count}</small></button>`;
  const filter = `
    <div class="timeline-toolbar">
      <details class="timeline-filter">
        <summary class="timeline-filter-trigger" data-tip="${esc(t("Filter timeline by Intent"))}">${icon("intent")}<span>${esc(selected ? truncate(selected.label, 44) : t("All Intents"))}</span>${icon("chevronDown")}</summary>
        <div class="timeline-filter-menu">${optionHtml("data-timeline-intent", "", timeline.intentId, t("All Intents"), total)}${options.map((option) => optionHtml("data-timeline-intent", option.key, timeline.intentId, option.label, option.count)).join("")}</div>
      </details>
      ${authors.length ? `<details class="timeline-filter author-filter">
        <summary class="timeline-filter-trigger" data-tip="${esc(t("Filter timeline by author"))}">${icon("user")}<span>${esc(author ? truncate(author.name, 28) : t("All authors"))}</span>${icon("chevronDown")}</summary>
        <div class="timeline-filter-menu">${optionHtml("data-timeline-author", "", timeline.author, t("All authors"), total)}${authors.map((entry) => optionHtml("data-timeline-author", entry.key, timeline.author, entry.name, entry.snaps)).join("")}</div>
      </details>` : ""}
    </div>`;
  const count = timeline.total ?? (selected ? selected.count : author ? author.snaps : total);
  const body = !timeline.loaded
    ? timeline.error
      ? `<div class="empty-state"><p>${esc(timeline.error)}</p><button type="button" class="secondary-btn" data-retry-timeline>${iconLabel("refresh", t("Retry"))}</button></div>`
      : viewLoadingHtml()
    : timeline.snaps.length
      ? renderTimeline(timeline)
      : `<div class="inline-empty">${esc(selected || author ? t("No checkpoints match these filters.") : t("No snaps synced yet."))}</div>`;
  el.detailContent.innerHTML = pageHeader({
    title: t("Timeline"),
    meta: [
      esc(plural(count, "{count} checkpoint", "{count} checkpoints")),
      esc(selected ? truncate(selected.label, 60) : t("All Intents")),
      ...(author ? [esc(truncate(author.name, 40))] : []),
    ],
    actions: filter,
  }) + `<div class="timeline" aria-busy="${timeline.loading || !timeline.loaded && !timeline.error}">${body}</div>`;
  if (!timeline.loaded && !timeline.loading && !timeline.error) loadTimelinePage();
}

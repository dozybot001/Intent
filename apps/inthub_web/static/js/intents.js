/* Intents */

function latestSnapRemoteId(intent) {
  return intent.latest_snap_id ? remoteId(intent.project_id, intent.latest_snap_id) : "";
}

function intentEntry(intent) {
  const snaps = (intent.snap_ids || []).length;
  const decisions = (intent.decision_ids || []).length;
  const latest = latestSnapRemoteId(intent);
  return `
    <button type="button" class="list-row intent-entry intent-entry-${esc(intent.status)}" data-detail-type="intent" data-remote-id="${esc(intent.remote_id)}">
      ${rowStatusIcon(intent.status)}
      <span class="row-main">
        <strong class="row-title intent-entry-title">${esc(intent.what)}</strong>
        ${intent.why ? `<span class="row-summary">${esc(truncate(intent.why, 220))}</span>` : ""}
        ${rowByline(intent)}
      </span>
      <span class="row-meta">
        <span class="row-id">${esc(shortId(intent.id))}</span>
        <span class="row-meta-line"><span>${esc(plural(snaps, "{count} snap", "{count} snaps"))}</span><span>${esc(plural(decisions, "{count} decision", "{count} decisions"))}</span></span>
        <span${latest ? ` data-latest-snap="${esc(latest)}"` : ""}>${esc(latestSnapCopy(intent))}</span>
      </span>
    </button>`;
}

function intentGroup(label, intents, tone, emptyMessage = "") {
  const body = intents.length
    ? `<div class="list-card object-group-list">${intents.map(intentEntry).join("")}</div>`
    : `<div class="object-group-empty">${esc(emptyMessage)}</div>`;
  return `
    <section class="object-group intent-group intent-group-${esc(tone)}">
      <header class="object-group-header">
        <h2 class="object-group-title">${esc(label)}</h2>
        <span class="object-group-count">${intents.length}</span>
      </header>
      ${body}
    </section>`;
}

function intentSubgroup(label, intents, tone) {
  if (!intents.length) return "";
  return `
    <section class="object-subgroup object-subgroup-${esc(tone)}">
      <header><span>${esc(label)}</span> · <span>${intents.length}</span></header>
      <div class="list-card object-group-list">${intents.map(intentEntry).join("")}</div>
    </section>`;
}

function renderIntentsTab() {
  const active = state.overview.active_intents || [];
  const other = [...(state.overview.other_intents || [])].reverse();
  const suspended = other.filter((intent) => intent.status === "suspend");
  const completed = other.filter((intent) => intent.status === "done");
  const cancelled = other.filter((intent) => intent.status === "cancelled");
  const otherHistory = other.filter((intent) =>
    !["suspend", "done", "cancelled"].includes(intent.status),
  );
  const total = active.length + other.length;
  const header = pageHeader({
    title: t("Intents"),
    meta: total ? [esc(plural(total, "{count} intent", "{count} intents")), esc(t("{count} active", {count: active.length}))] : [],
  });

  if (!total) {
    el.detailContent.innerHTML = header + emptyState({
      iconName: "intent",
      title: t("No intents."),
      body: t("An Intent is one goal with its own outcome. Agents record them while they work."),
      extra: commandSnippet(['itt intent create "Goal" --why "Reason"']),
    });
    return;
  }

  state._pageState ||= {};
  const archiveShown = state._pageState.intentArchive || PAGE_SIZE;
  const archived = [...completed, ...cancelled, ...otherHistory];
  const visibleArchive = archived.slice(0, archiveShown);
  const visibleIds = new Set(visibleArchive.map((intent) => intent.remote_id));
  const visibleCompleted = completed.filter((intent) => visibleIds.has(intent.remote_id));
  const visibleCancelled = cancelled.filter((intent) => visibleIds.has(intent.remote_id));
  const visibleOther = otherHistory.filter((intent) => visibleIds.has(intent.remote_id));
  const archiveRemaining = archived.length - visibleArchive.length;
  const archiveOpen = state._pageState.intentArchiveOpen ?? (!active.length && !suspended.length);

  const archive = archived.length
    ? `<details class="object-archive intent-archive" data-archive="intents"${archiveOpen ? " open" : ""}>
        <summary>${icon("chevron")}<span>${esc(t("Resolved history"))}</span><span class="object-archive-count">${archived.length}</span></summary>
        <div class="object-archive-body">
          ${intentSubgroup(t("Completed"), visibleCompleted, "done")}
          ${intentSubgroup(t("Cancelled"), visibleCancelled, "cancelled")}
          ${intentSubgroup(t("Other"), visibleOther, "history")}
          ${archiveRemaining > 0
            ? `<button type="button" class="load-more-btn" id="load-more-intent-archive">${iconLabel("chevronDown", t("Load more ({count})", {count: archiveRemaining}))}</button>`
            : ""}
        </div>
      </details>`
    : "";

  el.detailContent.innerHTML = `
    ${header}
    ${intentGroup(
      t("Active objectives"),
      active,
      "active",
      t("No active objective. Resume a suspended Intent or record a new one."),
    )}
    ${suspended.length
      ? intentGroup(t("Suspended"), suspended, "suspend")
      : ""}
    ${archive}`;
  // Only rows a reader can see ask for their latest Snap; the archive asks when it opens.
  fetchMissingSnaps([...active, ...suspended, ...(archiveOpen ? visibleArchive : [])].map(latestSnapRemoteId));
}

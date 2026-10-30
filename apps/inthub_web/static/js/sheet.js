/* ---- Detail sheet ---- */

function detailErrorHtml(error, type, rId) {
  return `<div class="empty-state"><p>${esc(error.message)}</p><button type="button" class="secondary-btn" data-retry-detail="sheet" data-detail-type="${esc(type)}" data-remote-id="${esc(rId)}">${iconLabel("refresh", t("Retry"))}</button></div>`;
}

function sheetIsOpen() {
  return el.drawer.classList.contains("open");
}

function renderSheetHeader(payload = null) {
  const entry = state._sheetStack?.at(-1);
  const labels = { intent: t("Intent"), snap: t("Snap"), decision: t("Decision"), revision: t("Revision") };
  const raw = payload?.id || (entry ? entry.remoteId.split("__").slice(1).join("__") : "");
  const id = entry?.type === "revision" ? shortRevision(raw) : raw;
  el.drawerTitle.innerHTML = entry ? `${esc(labels[entry.type] || "")} · <b class="mono">${esc(id)}</b>` : esc(t("Details"));
  el.drawerBack.classList.toggle("is-hidden", (state._sheetStack?.length || 0) < 2);
}

function openDrawer() {
  closeHeaderMenus();
  toggleProjectPicker(false);
  if (!sheetIsOpen()) state._drawerTrigger = document.activeElement;
  el.drawer.inert = false;
  el.drawer.classList.add("open");
  el.drawerOverlay.classList.add("open");
  el.drawer.setAttribute("aria-hidden", "false");
  el.drawer.setAttribute("aria-modal", "true");
  for (const node of document.querySelectorAll(".app-header, .page")) node.inert = true;
  el.drawerClose.focus();
}

function closeDrawer({ history = "auto" } = {}) {
  const wasOpen = sheetIsOpen();
  beginViewRequest("sheet");
  state._drawerPayload = null;
  state._sheetStack = [];
  state.selectedDetail = null;
  el.drawer.classList.remove("open");
  el.drawerOverlay.classList.remove("open");
  el.drawer.setAttribute("aria-hidden", "true");
  el.drawer.inert = true;
  el.drawer.removeAttribute("aria-modal");
  for (const node of document.querySelectorAll(".app-header, .page")) node.inert = false;
  el.drawerContent.innerHTML = "";
  syncSelected();
  if (wasOpen) {
    if (state._drawerTrigger?.isConnected && !state._drawerTrigger.disabled) state._drawerTrigger.focus();
    else el.detailContent.focus();
    if (history === "auto") {
      // Closing a sheet that added its own history entry steps back over it;
      // a sheet restored from a deep link only drops its URL parameters.
      if (state._sheetPushed && window.history.state?.inthub === "sheet" && window.history.back) window.history.back();
      else writeRoute("replace");
    }
  }
  state._sheetPushed = false;
  state._drawerTrigger = null;
}

function buildDetailHtml(type, payload) {
  if (type === "revision") return buildRevisionDetailHtml(payload);
  return type === "intent"
    ? buildIntentDetailHtml(payload)
    : type === "decision"
      ? buildDecisionDetailHtml(payload)
      : buildSnapDetailHtml(payload);
}

function detailUrl(type, rId) {
  if (type !== "revision") return apiUrl(`/api/v1/${DETAIL_PATHS[type]}/${encodeURIComponent(rId)}`);
  const revision = rId.split("__").slice(1).join("__");
  return apiUrl(`/api/v1/projects/${encodeURIComponent(projectIdFromRemoteId(rId))}/revisions/${encodeURIComponent(revision)}`);
}

// mode: "reset" opens a fresh stack, "push" adds a related object, "replace" retries the top.
async function openDetail(type, rId, { mode = "reset", history = "auto" } = {}) {
  if (!DETAIL_PATHS[type]) return;
  const targetProjectId = projectIdFromRemoteId(rId);
  if (targetProjectId && state.currentProjectId && targetProjectId !== state.currentProjectId
      && state.projects.some((project) => project.id === targetProjectId)) {
    closeDrawer({ history: "none" });
    await loadProject(targetProjectId, { detail: { type, remoteId: rId }, history: "push" });
    return;
  }
  const request = beginViewRequest("sheet");
  const wasOpen = sheetIsOpen();
  const entry = { type, remoteId: rId };
  state._sheetStack ||= [];
  if (mode === "push" && wasOpen) state._sheetStack.push(entry);
  else if (mode === "replace" && wasOpen && state._sheetStack.length) state._sheetStack[state._sheetStack.length - 1] = entry;
  else state._sheetStack = [entry];
  state.selectedDetail = entry;
  state._drawerPayload = null;
  renderSheetHeader();
  if (!wasOpen) openDrawer();
  syncSelected();
  const routed = writeRoute(history === "auto" ? (wasOpen ? "replace" : "push") : history, "sheet");
  if (!wasOpen) state._sheetPushed = routed === "pushed" || (routed === "none" && Boolean(window.history.state?.sheetPushed));

  const cacheKey = `${type}:${rId}`;
  const cached = state._detailCache?.get(cacheKey);
  if (cached) {
    showDetailPayload(type, cached, wasOpen);
    return;
  }
  el.drawerContent.innerHTML = viewLoadingHtml();
  el.drawerContent.scrollTop = 0;
  setViewBusy("sheet", true);
  try {
    const payload = await fetchJson(detailUrl(type, rId));
    if (!ownsViewRequest("sheet", request) || !sheetIsOpen()) return;
    state._detailCache?.set(cacheKey, payload);
    showDetailPayload(type, payload, wasOpen);
  } catch (error) {
    if (!ownsViewRequest("sheet", request)) return;
    el.drawerContent.innerHTML = detailErrorHtml(error, type, rId);
    throw error;
  } finally {
    if (ownsViewRequest("sheet", request)) setViewBusy("sheet", false);
  }
}

function showDetailPayload(type, payload, moveFocus) {
  state._drawerPayload = { type, payload };
  el.drawerContent.innerHTML = buildDetailHtml(type, payload);
  el.drawerContent.scrollTop = 0;
  renderSheetHeader(payload);
  if (moveFocus) el.drawerContent.querySelector(".detail-title")?.focus();
}

async function sheetBack() {
  if ((state._sheetStack?.length || 0) < 2) {
    closeDrawer();
    return;
  }
  state._sheetStack.pop();
  const previous = state._sheetStack.pop();
  await openDetail(previous.type, previous.remoteId, { mode: "push", history: "replace" });
}

function allDecisionsMap() {
  const map = {};
  for (const d of state.overview?.active_decisions || []) map[d.id] = d;
  for (const d of state.overview?.deprecated_decisions || []) map[d.id] = d;
  return map;
}

function activeDecisionIds() {
  const ids = new Set();
  for (const d of state.overview?.active_decisions || []) {
    ids.add(d.id);
  }
  return ids;
}

function detailMeta(parts) {
  return `<div class="detail-meta">${parts.filter(Boolean).join("")}</div>`;
}

function buildIntentDetailHtml(payload) {
  const intent = payload.intent;
  const activeIds = activeDecisionIds();

  const dMap = allDecisionsMap();
  for (const decision of payload.decisions || []) {
    dMap[decision.id] = decision;
    if (decision.status === "active") activeIds.add(decision.id);
  }
  const allIds = intent.decision_ids || [];
  const decisionLinks = [
    ...allIds.filter((dId) => activeIds.has(dId)).map((dId) => [dId, "active"]),
    ...allIds.filter((dId) => !activeIds.has(dId)).map((dId) => [dId, "deprecated"]),
  ].map(([dId, status]) => relationItem(
    "decision",
    remoteId(payload.project_id, dId),
    dId,
    dMap[dId]?.what || dId,
    truncate(dMap[dId]?.why || "", 120),
    status,
  ));
  const decisionsBody = decisionLinks.length
    ? collapsibleRelation(decisionLinks, 5)
    : `<div class="inline-empty">${esc(t("No decisions linked."))}</div>`;

  const allSnaps = [...payload.snaps].reverse();
  const latest = allSnaps[0];
  const snapLinks = allSnaps.map((s) =>
    relationItem(
      "snap",
      remoteId(payload.project_id, s.id),
      s.id,
      conciseSnapTitle(s),
      fmtDate(s.created_at),
    ),
  );
  const snapTimelineBody = snapLinks.length
    ? collapsibleRelation(snapLinks, 5)
    : `<div class="inline-empty">${esc(t("No snaps recorded."))}</div>`;
  const sourced = Object.values(dMap).filter((decision) => decision.source_intent_id === intent.id);
  const sourcedLinks = sourced.map((decision) => relationItem(
    "decision",
    decision.remote_id || remoteId(payload.project_id, decision.id),
    decision.id,
    decision.what || decision.id,
    truncate(decision.why || "", 120),
    decision.status,
  ));

  return `
    <div class="detail-header">
      ${detailMeta([statusBadge(intent.status), idChip(intent.id), identityMeta(intent), `<span>${esc(t("Created {time}", {time: fmtDate(intent.created_at)}))}</span>`])}
      <h2 class="detail-title" tabindex="-1">${esc(intent.what)}</h2>
    </div>
    ${intent.why ? detailSection(t("Why"), formatText(intent.why)) : ""}
    ${intent.reason ? detailSection(t("Reason"), formatText(intent.reason)) : ""}
    ${latest && ["active", "suspend"].includes(intent.status) ? detailSection(t("Latest checkpoint"), checkpointGrid(parseCheckpoint(latest), ["next", "blocker", "boundary", "verified"], " detail-checkpoint-grid")) : ""}
    ${intentRelationsSection(payload)}
    ${detailSection(t("Snaps"), snapTimelineBody, allSnaps.length)}
    ${detailSection(t("Linked decisions"), decisionsBody, allIds.length)}
    ${sourcedLinks.length ? detailSection(t("Decisions from this Intent"), collapsibleRelation(sourcedLinks, 5), sourcedLinks.length) : ""}
    ${rawToggle({ intent, snaps: payload.snaps, decisions: payload.decisions || [] })}`;
}

// Both directions, grouped by how they read from this Intent ("Part of", "Parts", …), each with its state.
function intentRelationsSection(payload) {
  const rows = intentRelations({ ...payload.intent, project_id: payload.project_id });
  if (!rows.length) return detailSection(t("Relations"), `<div class="inline-empty">${esc(t("No relations to other Intents."))}</div>`);
  const groups = [];
  for (const row of rows) {
    const label = relationLabel(row.type, row.direction);
    const group = groups.find((entry) => entry.label === label);
    if (group) group.rows.push(row);
    else groups.push({ label, rows: [row] });
  }
  // A part's state only repeats the part's own status, so it is shown only when its parent has ended.
  const badge = (row) => (row.type === "part_of" && !ATTENTION_STATES.has(row.state) ? "" : relationBadge(row.state, row));
  const body = groups.map((group) => `
    <div class="relation-group">
      <h4 class="relation-group-label">${esc(group.label)}</h4>
      <div class="relation-list">${group.rows.map((row) => relationItem(
        "intent",
        row.intent.remote_id || remoteId(payload.project_id, row.intent.id),
        row.intent.id,
        row.intent.what || row.intent.id,
        "",
        row.intent.status,
        badge(row),
      )).join("")}</div>
    </div>`).join("");
  const flowLink = `<button type="button" class="link-button relation-flow-link" data-flow-focus="${esc(payload.intent.id)}">${icon("flow")}${esc(t("Show in Flow"))}</button>`;
  return detailSection(t("Relations"), body + flowLink, rows.length);
}

function decisionSourceSection(payload) {
  const sourceId = payload.decision.source_intent_id;
  if (!sourceId) {
    return detailSection(t("Source"), `<div class="decision-source-none"><span class="chip">${esc(t("Project-level"))}</span><span>${esc(t("Not traced to one Intent; it applies across the project."))}</span></div>`);
  }
  const source = overviewIntentMap().get(sourceId) || (payload.intents || []).find((intent) => intent.id === sourceId) || { id: sourceId };
  return detailSection(t("Source"), `<div class="relation-list">${relationItem(
    "intent",
    source.remote_id || remoteId(payload.project_id, sourceId),
    sourceId,
    source.what || sourceId,
    truncate(source.why || "", 120),
    source.status,
  )}</div>`);
}

function buildDecisionDetailHtml(payload) {
  const decision = payload.decision;
  const linkedCount = payload.intents.length;
  const scopeSummary = linkedCount
    ? plural(linkedCount, "Applies to {count} linked Intent.", "Applies to {count} linked Intents.")
    : t("No Intent scope is recorded.");
  const intentLinks = payload.intents.map((i) =>
    relationItem(
      "intent",
      remoteId(payload.project_id, i.id),
      i.id,
      i.what || i.title || i.id,
      truncate(i.why || "", 120),
      i.status,
    ),
  );

  const intentsBody = intentLinks.length
    ? collapsibleRelation(intentLinks, 5)
    : `<div class="inline-empty">${esc(t("No linked intents."))}</div>`;

  return `
    <div class="detail-header">
      ${detailMeta([statusBadge(decision.status, "decision"), idChip(decision.id), identityMeta(decision), `<span>${esc(t("Created {time}", {time: fmtDate(decision.created_at)}))}</span>`])}
      <h2 class="detail-title" tabindex="-1">${esc(decision.what)}</h2>
      <p class="detail-context decision-detail-scope">${esc(decision.status === "active" ? t("Current cross-Intent constraint") : t("Deprecated constraint history"))} · ${esc(scopeSummary)}</p>
    </div>
    ${detailSection(t("Why"), formatText(decision.why) || `<p>${esc(t("No why provided."))}</p>`)}
    ${decision.reason ? detailSection(t("Reason"), formatText(decision.reason)) : ""}
    ${decisionSourceSection(payload)}
    ${detailSection(t("Affected Intents"), intentsBody, payload.intents.length)}
    ${rawToggle({ decision, intents: payload.intents })}`;
}

// {repo}/commit/{sha}, or the /-/ form on GitLab; only https on the hosts the CLI recognises becomes a link.
function commitUrl(repository, sha) {
  let url;
  try { url = new URL(repository); } catch { return ""; }
  if (url.protocol !== "https:" || !["github.com", "gitlab.com", "gitee.com"].includes(url.hostname) || !/^[0-9a-f]{40,64}$/.test(sha)) return "";
  return `${url.origin}${url.pathname.replace(/\/+$/, "")}${url.hostname === "gitlab.com" ? "/-" : ""}/commit/${sha}`;
}

function commitLine(snap) {
  const sha = snap.git?.commit;
  if (!sha) return "";
  const label = tHtml("Commit {sha}", { sha: `<span class="mono">${esc(sha.slice(0, 7))}</span>` });
  const url = commitUrl(state.overview?.project?.repository_url, sha);
  const commit = url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label}</a>` : label;
  return `<p class="detail-context snap-commit">${commit}${snap.git.dirty ? ` · ${esc(t("with uncommitted changes"))}` : ""}</p>`;
}

function buildSnapDetailHtml(payload) {
  const snap = payload.snap;
  const checkpoint = parseCheckpoint(snap);
  const status = timelineState(checkpoint);
  const parent = payload.intent
    ? `<button type="button" data-detail-type="intent" data-remote-id="${esc(remoteId(payload.project_id, payload.intent.id))}">${esc(payload.intent.what || payload.intent.id)}</button>`
    : esc(t("an unlinked Intent"));
  const parentLink = payload.intent
    ? `<div class="relation-list">${relationItem(
        "intent",
        remoteId(payload.project_id, payload.intent.id),
        payload.intent.id,
        payload.intent.what || payload.intent.id,
        truncate(payload.intent.why || "", 120),
        payload.intent.status,
      )}</div>`
    : `<div class="inline-empty">${esc(t("No linked intent."))}</div>`;

  return `
    <div class="detail-header detail-header-snap">
      ${detailMeta([stateBadge(status), idChip(snap.id), identityMeta(snap), `<span>${esc(fmtDate(snap.created_at))}</span>`])}
      <h2 class="detail-title detail-title-snap" tabindex="-1">${esc(conciseSnapTitle(snap, 110))}</h2>
      <p class="detail-context snap-detail-context">${esc(t("Semantic checkpoint for"))} ${parent}</p>
      ${commitLine(snap)}
    </div>
    ${detailSection(
      t("Continuation checkpoint"),
      `${checkpointGrid(checkpoint, ["verified", "boundary", "next", "blocker"], " detail-checkpoint-grid")}
      ${checkpoint.constraints ? `<p class="checkpoint-note"><strong>${esc(t("Constraints:"))}</strong> ${esc(checkpoint.constraints)}</p>` : ""}`,
    )}
    ${checkpoint.context ? detailSection(t("Context"), formatText(checkpoint.context)) : ""}
    ${detailSection(t("Parent Intent"), parentLink)}
    ${rawToggle({ snap, intent: payload.intent })}`;
}

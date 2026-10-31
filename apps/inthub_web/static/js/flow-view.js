function flowViewport(layout, width, height) {
  const target = flowTarget(layout);
  if (!target) return { left: 0, top: 0 };
  const margin = 16;
  const range = (start, size, extent, frame) => {
    const most = Math.max(0, extent - frame);
    const low = Math.min(most, Math.max(0, start + size + margin - frame));
    const high = Math.max(low, Math.min(most, start - margin));
    return Array.from({ length: 9 }, (_, index) => low + (high - low) * index / 8);
  };
  const box = target.box;
  let best = { left: 0, top: 0, score: -Infinity };
  for (const left of range(box.x1, box.x2 - box.x1, layout.width, width)) {
    for (const top of range(box.y1, box.y2 - box.y1, layout.height, height)) {
      let score = 0;
      for (const node of layout.nodes) {
        const across = Math.min(node.box.x2, left + width) - Math.max(node.box.x1, left);
        const down = Math.min(node.box.y2, top + height) - Math.max(node.box.y1, top);
        if (across > 0 && down > 0) score += across * down;
      }
      // Ties go to the position that centres the target best.
      score -= Math.abs(left + width / 2 - (box.x1 + box.x2) / 2) + Math.abs(top + height / 2 - (box.y1 + box.y2) / 2);
      if (score > best.score) best = { left, top, score };
    }
  }
  return { left: Math.round(best.left), top: Math.round(best.top) };
}

// The rows a window over [left, left + width] should keep: the target and its direct relations,
// and every card at least half inside the window.
function flowVisibleSpan(layout, left, width) {
  const target = flowTarget(layout);
  const near = new Set([target?.id]);
  for (const link of layout.relations) {
    if (link.subject === target?.id) near.add(link.target);
    if (link.target === target?.id) near.add(link.subject);
  }
  const shown = layout.nodes.filter((node) => near.has(node.id)
    || Math.min(node.box.x2, left + width) - Math.max(node.box.x1, left) >= (node.box.x2 - node.box.x1) / 2);
  if (!shown.length) return null;
  return { top: Math.min(...shown.map((node) => node.box.y1)), bottom: Math.max(...shown.map((node) => node.box.y2)) };
}

// When the graph is larger than its frame (a phone, a long history), open it at the card that matters.
// A frame that scrolls both ways (phones) also shrinks to the rows it opens on instead of empty canvas.
function revealFlowTarget(layout) {
  const canvas = el.detailContent.querySelector?.(".flow-canvas");
  if (!canvas?.clientWidth) return;
  canvas.style.removeProperty("height");
  if (canvas.scrollWidth <= canvas.clientWidth && canvas.scrollHeight <= canvas.clientHeight) return;
  let { left, top } = flowViewport(layout, canvas.clientWidth, canvas.clientHeight);
  const span = getComputedStyle(canvas).overflowY !== "hidden" ? flowVisibleSpan(layout, left, canvas.clientWidth) : null;
  if (span && span.bottom - span.top + 48 < canvas.clientHeight) {
    canvas.style.height = `${Math.max(280, Math.ceil(span.bottom - span.top + 48))}px`;
    top = Math.max(0, Math.round(span.top - 24));
  }
  canvas.scrollLeft = left;
  canvas.scrollTop = top;
}

// Only what this graph draws: a reader should not have to skip marks that appear nowhere.
function flowLegend(layout) {
  const types = new Set(layout.relations.map((link) => link.type));
  const kinds = new Set(layout.lines.map((line) => line.kind));
  const tones = new Set(layout.lines.map(flowLineTone));
  const pinned = [...layout.nodes.flatMap((node) => node.decisions), ...(layout.band?.chips || []).flatMap((chip) => chip.decision || [])];
  const sample = (className, d, extra = "") => `<svg class="flow-legend-sample" viewBox="0 0 34 16" aria-hidden="true"><g class="flow-line ${className}"><path class="flow-stroke" d="${d}"/>${extra}</g></svg>`;
  const curve = "M2 3C17 3 17 13 31 13";
  const items = [
    [sample("flow-branch flow-type-part_of tone-neutral", curve, '<circle class="flow-terminal" cx="30" cy="13" r="2.75"/>'), t("Part of")],
    [sample("flow-branch flow-type-derived_from tone-neutral", curve, '<circle class="flow-terminal" cx="30" cy="13" r="2.75"/>'), t("Derived from")],
    [sample("flow-rejoin flow-type-part_of tone-neutral", "M2 13C17 13 17 3 32 3"), t("Rejoin")],
    [sample("flow-flow flow-type-succeeds tone-neutral", "M2 8H25", `<path class="flow-arrow" d="${flowArrowHead({ x: 32, y: 8, ux: 1, uy: 0 }, 8)}"/>`), t("Succeeds")],
    [sample("flow-depends flow-type-depends_on tone-neutral", "M2 3C15 3 15 13 27 13", `<path class="flow-arrow" d="${flowArrowHead({ x: 32, y: 13, ux: 1, uy: 0 }, 6)}"/>`), t("Depends on")],
    [sample("flow-conflict flow-type-conflicts_with tone-neutral", "M2 8H32"), t("Conflicts with")],
    [sample("flow-depends tone-attention", "M2 8H32"), t("Needs attention")],
    [sample("flow-depends tone-settled", "M2 8H32"), t("Satisfied")],
    [sample("flow-depends tone-danger", "M2 8H32"), t("Broken")],
    [`<svg class="flow-legend-sample is-mark" viewBox="0 0 16 16" aria-hidden="true"><g class="flow-decision"><path class="flow-decision-shape" d="${flowDiamond(8, 8, 5)}"/></g></svg>`, t("Decision")],
    [`<svg class="flow-legend-sample is-mark" viewBox="0 0 16 16" aria-hidden="true"><g class="flow-decision is-deprecated"><path class="flow-decision-shape" d="${flowDiamond(8, 8, 5)}"/></g></svg>`, t("Deprecated")],
  ];
  const shown = [types.has("part_of"), types.has("derived_from"), kinds.has("rejoin"), types.has("succeeds"), types.has("depends_on"), types.has("conflicts_with"),
    tones.has("attention"), tones.has("settled"), tones.has("danger"), pinned.some((decision) => decision.status !== "deprecated"), pinned.some((decision) => decision.status === "deprecated")];
  return `<ul class="flow-legend" aria-label="${esc(t("Legend"))}">${items.filter((_, index) => shown[index]).map(([visual, label]) => `<li>${visual}<span>${esc(label)}</span></li>`).join("")}</ul>`;
}

function flowFocusOptions(intents) {
  const related = new Set(relationLinks(intents).flatMap((link) => [link.subject, link.target]));
  return [...intentMap(intents).values()].filter((intent) => related.has(intent.id)).sort((left, right) => byCreation(right, left));
}

function flowControls(flow, options, focused) {
  const option = (key, label, meta = "") => `<button type="button" class="timeline-filter-option${flow.focus === key ? " is-selected" : ""}" data-flow-focus="${esc(key)}" aria-pressed="${flow.focus === key}"><span>${esc(label)}</span>${meta ? `<small>${esc(meta)}</small>` : ""}</button>`;
  return `
    <div class="flow-controls">
      <button type="button" class="flow-toggle" data-flow-hide-ended aria-pressed="${Boolean(flow.hideEnded)}">${icon("hide")}<span>${esc(t("Hide ended"))}</span></button>
      <details class="timeline-filter flow-focus">
        <summary class="timeline-filter-trigger" data-tip="${esc(t("Focus on one Intent and its direct relations"))}">${icon("focus")}<span>${esc(focused ? truncate(focused.what || focused.id, 36) : t("Focus on…"))}</span>${icon("chevronDown")}</summary>
        <div class="timeline-filter-menu">${option("", t("All Intents"))}${options.map((intent) => option(intent.id, intent.what || intent.id, intent.id)).join("")}</div>
      </details>
    </div>`;
}

// Intents without relations, drawn as the same cards as the graph.
function flowCard(intent, decisions) {
  const status = ["active", "suspend", "done", "cancelled"].includes(intent.status) ? intent.status : "unknown";
  const snaps = (intent.snap_ids || []).length;
  return `
    <button type="button" class="flow-card status-${status}" data-detail-type="intent" data-remote-id="${esc(intent.remote_id || remoteId(intent.project_id, intent.id))}">
      <span class="flow-card-top">${statusBadge(intent.status)}<span class="flow-card-id">${esc(shortId(intent.id))}</span></span>
      <strong class="flow-card-title">${esc(intent.what || intent.id)}</strong>
      <span class="flow-card-meta"><span>${esc(plural(snaps, "{count} snap", "{count} snaps"))}</span>${decisions ? `<span>${esc(plural(decisions, "{count} decision", "{count} decisions"))}</span>` : ""}</span>
    </button>`;
}

// The width the graph may fill; on a narrower screen the frame scrolls only for a group wider than it.
function flowWidth() {
  const page = el.detailContent;
  if (!page.clientWidth) return undefined;
  const style = getComputedStyle(page);
  return page.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) - 2;
}

function renderFlowTab() {
  state._flow ||= { hideEnded: false, focus: "", standalone: PAGE_SIZE };
  const flow = state._flow;
  const intents = overviewIntents();
  const decisions = [...(state.overview.active_decisions || []), ...(state.overview.deprecated_decisions || [])];
  const byId = overviewIntentMap();
  if (flow.focus && !byId.has(flow.focus)) flow.focus = "";
  flow.width = flowWidth();
  const layout = flowLayout(intents, decisions, { hideEnded: flow.hideEnded, focus: flow.focus, maxWidth: flow.width });
  if (!layout.hasRelations) {
    el.detailContent.innerHTML = pageHeader({ title: t("Flow"), help: "flow" }) + `<div class="flow-empty">${emptyState({
      iconName: "flow",
      title: t("No relations between Intents yet."),
      body: t("Relations record where a goal comes from and what constrains it. Add them from the CLI; the flow appears here after the next push."),
      extra: commandSnippet([
        'itt intent create "Goal" --why "Reason" --part-of ID',
        "itt intent relate ID --depends-on OTHER",
        'itt intent cancel ID --into OTHER --reason "Duplicate"',
        'itt decision create "Rule" --why "Reason" --from ID',
      ]),
    })}</div>`;
    return;
  }
  const focused = flow.focus ? byId.get(flow.focus) : null;
  const attention = layout.relations.filter((link) => ATTENTION_STATES.has(link.state)).length;
  const header = pageHeader({
    title: t("Flow"),
    help: "flow",
    meta: [
      esc(plural(layout.relations.length, "{count} relation", "{count} relations")),
      ...(attention ? [esc(plural(attention, "{count} needs attention", "{count} need attention"))] : []),
      ...(focused ? [esc(t("Focused on {id}", {id: focused.id}))] : []),
    ],
    actions: flowControls(flow, flowFocusOptions(intents), focused),
  });
  const canvas = layout.nodes.length
    ? `<div class="flow-canvas">${renderFlowSvg(layout)}</div>`
    : `<div class="inline-empty">${esc(t("No related Intent is open. Show ended Intents to see the rest of the flow."))}</div>`;
  const sourced = new Map();
  for (const decision of decisions) if (decision.source_intent_id) sourced.set(decision.source_intent_id, (sourced.get(decision.source_intent_id) || 0) + 1);
  const cards = layout.standalone.slice(0, flow.standalone || PAGE_SIZE);
  const standalone = layout.standalone.length ? `
    <section class="section flow-standalone">
      ${sectionHeader(t("Not related to other Intents"), layout.standalone.length)}
      <div class="flow-standalone-grid">${cards.map((intent) => flowCard(intent, sourced.get(intent.id) || 0)).join("")}</div>
      ${layout.standalone.length > cards.length ? `<button type="button" class="load-more-btn" id="load-more-flow-standalone">${iconLabel("chevronDown", t("Load more ({count})", {count: layout.standalone.length - cards.length}))}</button>` : ""}
    </section>` : "";
  el.detailContent.innerHTML = `<div class="flow-page">${header}${flowLegend(layout)}${canvas}${standalone}</div>`;
  fitFlowText();
  revealFlowTarget(layout);
  // Text measured before the web font arrived is measured again once it has.
  document.fonts?.ready?.then(() => { if (state.activeTab === "flow") fitFlowText(); });
}

// Focus the Flow on one Intent (or clear it with ""). From the sheet, the view moves to that node.
function showFlowFocus(intentId, { fromSheet = false } = {}) {
  state._flow ||= { hideEnded: false, focus: "", standalone: PAGE_SIZE };
  state._flow.focus = intentId || "";
  if (state.activeTab !== "flow") switchTab("flow");
  else {
    if (sheetIsOpen()) closeDrawer();
    renderView();
  }
  const target = fromSheet && intentId
    ? el.detailContent.querySelector(".flow-node.is-focus")
    : el.detailContent.querySelector(".flow-focus .timeline-filter-trigger");
  target?.focus();
}

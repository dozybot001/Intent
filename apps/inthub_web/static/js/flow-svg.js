function flowNumber(value) {
  return Math.round(value * 10) / 10;
}

function flowMidpoint(points) {
  const lengths = points.slice(1).map((point, index) => Math.hypot(point[0] - points[index][0], point[1] - points[index][1]));
  let remaining = lengths.reduce((sum, length) => sum + length, 0) / 2;
  for (let index = 0; index < lengths.length; index++) {
    if (remaining <= lengths[index] && lengths[index]) {
      const ratio = remaining / lengths[index];
      return [points[index][0] + (points[index + 1][0] - points[index][0]) * ratio, points[index][1] + (points[index + 1][1] - points[index][1]) * ratio];
    }
    remaining -= lengths[index];
  }
  return points.at(-1);
}

// Line colour carries relation state; only dependencies turn green once satisfied.
function flowLineTone(line) {
  if (line.type === "depends_on") return relationTone(line.state);
  return ATTENTION_STATES.has(line.state) ? "attention" : "neutral";
}

function flowLineSvg(line) {
  const size = line.kind === "flow" ? 8 : 6;
  const end = flowCurveEnd(line.curve);
  const d = flowCurvePath(line.arrow ? flowTrimCurve(line.curve, size * 0.75) : line.curve);
  const state = relationStateLabel(line.state);
  const title = `${line.subject} · ${relationLabel(line.type, "out")} · ${line.target}${state ? ` · ${state}` : ""}`;
  const settled = line.state === "resolved" ? " is-settled" : "";
  let mark = "";
  if (line.kind === "conflict") {
    const [mx, my] = flowMidpoint(flowSamples(line.curve));
    mark = `<g class="flow-vs"><rect x="${flowNumber(mx - 12)}" y="${flowNumber(my - 8)}" width="24" height="16" rx="8"/><text x="${flowNumber(mx)}" y="${flowNumber(my + 3.5)}" text-anchor="middle">vs</text></g>`;
  } else if (line.kind === "branch") {
    // Where a branch meets the child: a filled dot for a part, a hollow one for a derived Intent.
    mark = `<circle class="flow-terminal" cx="${flowNumber(end.x - end.ux * 4)}" cy="${flowNumber(end.y - end.uy * 4)}" r="2.75"/>`;
  }
  return `<g class="flow-line flow-${line.kind} flow-type-${line.type} tone-${flowLineTone(line)}${settled}"><title>${esc(title)}</title><path class="flow-hit-line" d="${d}"/><path class="flow-stroke" d="${d}"/>${line.arrow ? `<path class="flow-arrow" d="${flowArrowHead(end, size)}"/>` : ""}${mark}</g>`;
}

function flowNodeLabel(node, layout) {
  const intent = node.intent;
  const parts = [`${intent.id}: ${intent.what || ""}`, intentStatusLabel(intent.status), plural((intent.snap_ids || []).length, "{count} snap", "{count} snaps")];
  if (node.decisions.length) parts.push(plural(node.decisions.length, "{count} decision", "{count} decisions"));
  // Spoken in the order of the detail sheet: where it comes from first, then by relation type.
  const rows = layout.relations
    .filter((link) => link.subject === node.id || link.target === node.id)
    .map((link) => ({ link, outgoing: link.subject === node.id }))
    .sort((left, right) => right.outgoing - left.outgoing || RELATION_TYPES.indexOf(left.link.type) - RELATION_TYPES.indexOf(right.link.type)
      || String(left.outgoing ? left.link.target : left.link.subject).localeCompare(String(right.outgoing ? right.link.target : right.link.subject)));
  for (const { link, outgoing } of rows) {
    const state = relationStateLabel(link.state, { type: link.type, direction: outgoing ? "out" : "in" });
    parts.push(`${relationLabel(link.type, outgoing ? "out" : "in")} ${outgoing ? link.target : link.subject}${state ? ` (${state})` : ""}`);
  }
  return parts.join(". ");
}

// A card: status pill and id, a title of up to two lines, then its Snaps and Decisions.
function flowNodeSvg(node, layout) {
  const g = layout.geometry;
  const intent = node.intent;
  const status = ["active", "suspend", "done", "cancelled"].includes(intent.status) ? intent.status : "unknown";
  const label = intentStatusLabel(intent.status);
  const title = flowLines(intent.what || intent.id, g.nodeW - 28, 13, 2);
  const meta = [plural((intent.snap_ids || []).length, "{count} snap", "{count} snaps")];
  if (node.decisions.length) meta.push(plural(node.decisions.length, "{count} decision", "{count} decisions"));
  return `<g class="flow-node status-${status}${layout.focus === node.id ? " is-focus" : ""}" role="button" tabindex="0" data-detail-type="intent" data-remote-id="${esc(intent.remote_id || remoteId(intent.project_id, intent.id))}" aria-label="${esc(flowNodeLabel(node, layout))}" transform="translate(${flowNumber(node.x)} ${flowNumber(node.y)})">
    <title>${esc(intent.what || intent.id)}</title>
    <g class="flow-node-body">
      <rect class="flow-node-ring" x="-4" y="-4" width="${g.nodeW + 8}" height="${g.nodeH + 8}" rx="15"/>
      <rect class="flow-node-box" width="${g.nodeW}" height="${g.nodeH}" rx="12"/>
      <g class="flow-pill" data-fit="25"><rect class="flow-pill-box" x="12" y="12" width="${flowNumber(25 + flowTextWidth(label, 11, FLOW_REGULAR))}" height="20" rx="10" data-fit-box/><circle class="flow-node-dot" cx="21" cy="22" r="3"/><text class="flow-node-status" x="29" y="25.5" data-fit-text>${esc(label)}</text></g>
      <text class="flow-node-id" x="${g.nodeW - 12}" y="25.5" text-anchor="end">${esc(intent.id)}</text>
      ${title.map((line, index) => `<text class="flow-node-title" x="14" y="${50 + index * 17}">${esc(line)}</text>`).join("")}
      <text class="flow-node-meta" x="14" y="${g.nodeH - 12}">${esc(meta.join(" · "))}</text>
    </g>
  </g>`;
}

function flowDecisionLabel(decision, projectLevel) {
  return `${t("Decision")} ${decision.id}: ${decision.what || ""} (${decisionStatusLabel(decision.status)}${projectLevel ? ` · ${t("Project-level")}` : ""})`;
}

function flowDiamond(x, y, size) {
  const n = flowNumber;
  return `M${n(x)} ${n(y - size)} L${n(x + size)} ${n(y)} L${n(x)} ${n(y + size)} L${n(x - size)} ${n(y)} Z`;
}

// Decisions taken from an Intent hang under its card: a dotted stem, then a diamond and a line of text each.
function flowPinsSvg(node, layout) {
  if (!node.decisions.length) return "";
  const g = layout.geometry;
  const x = node.x + 18;
  const top = node.y + g.nodeH;
  const listed = node.decisions.length > FLOW_PINS ? node.decisions.slice(0, FLOW_PINS) : node.decisions;
  const more = node.decisions.length - listed.length;
  const rowY = (index) => top + g.pinTop + index * g.pinRow;
  const pins = listed.map((decision, index) => {
    const y = rowY(index);
    const text = flowLines(decision.what || decision.id, g.nodeW - 40, 11.5, 1, FLOW_REGULAR)[0] || "";
    return `<g class="flow-decision flow-pin${decision.status === "deprecated" ? " is-deprecated" : ""}" role="button" tabindex="0" data-detail-type="decision" data-remote-id="${esc(decision.remote_id || remoteId(decision.project_id, decision.id))}" aria-label="${esc(flowDecisionLabel(decision, false))}" data-fit="0" data-fit-max="${g.nodeW - 40}">
      <title>${esc(`${decision.id} · ${decision.what || ""}`)}</title>
      <rect class="flow-hit" x="${flowNumber(x - 9)}" y="${flowNumber(y - 9)}" width="${flowNumber(g.nodeW - 18)}" height="18" rx="6"/>
      <path class="flow-decision-shape" d="${flowDiamond(x, y, 4.5)}"/>
      <text class="flow-pin-text" x="${flowNumber(x + 11)}" y="${flowNumber(y + 4)}" data-fit-text data-full="${esc(decision.what || decision.id)}">${esc(text)}</text>
    </g>`;
  }).join("");
  return `<path class="flow-pin-stem" aria-hidden="true" d="M${flowNumber(x)} ${flowNumber(top + 3)} V${flowNumber(rowY(listed.length - 1) - 6)}"/>${pins}`
    + (more ? `<text class="flow-pin-more" x="${flowNumber(x + 11)}" y="${flowNumber(rowY(listed.length) + 4)}">${esc(t("+{count} more", {count: more}))}</text>` : "");
}

// A Project-level Decision: a chip at the column of its time.
function flowChipSvg(chip) {
  const { x, y } = chip;
  if (!chip.decision) {
    return `<g class="flow-chip is-more" aria-hidden="true"><rect class="flow-chip-box" x="${x}" y="${y}" width="44" height="22" rx="11"/><text class="flow-chip-text" x="${x + 22}" y="${y + 15}" text-anchor="middle">+${chip.more}</text></g>`;
  }
  const decision = chip.decision;
  const text = flowLines(decision.what || decision.id, chip.width - 38, 12, 1, FLOW_REGULAR)[0] || "";
  return `<g class="flow-decision flow-chip${decision.status === "deprecated" ? " is-deprecated" : ""}" role="button" tabindex="0" data-detail-type="decision" data-remote-id="${esc(decision.remote_id || remoteId(decision.project_id, decision.id))}" aria-label="${esc(flowDecisionLabel(decision, true))}" data-fit="36" data-fit-max="${chip.width}">
    <title>${esc(`${decision.id} · ${decision.what || ""}`)}</title>
    <rect class="flow-chip-box" x="${x}" y="${y}" width="${flowNumber(Math.min(chip.width, 36 + flowTextWidth(text, 12, FLOW_REGULAR)))}" height="22" rx="11" data-fit-box/>
    <path class="flow-decision-shape" d="${flowDiamond(x + 13, y + 11, 4.5)}"/>
    <text class="flow-chip-text" x="${x + 24}" y="${y + 15}" data-fit-text data-full="${esc(decision.what || decision.id)}">${esc(text)}</text>
  </g>`;
}

function flowAxisLabel(time) {
  const date = new Date(time);
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return new Intl.DateTimeFormat(window.IntHubI18n.language, sameYear ? { month: "short", day: "numeric" } : { year: "numeric", month: "short", day: "numeric" }).format(date);
}

function renderFlowSvg(layout) {
  if (!layout.nodes.length) return "";
  const g = layout.geometry;
  const n = flowNumber;
  const defs = `<defs>
    <filter id="flow-card-shadow" x="-10%" y="-15%" width="120%" height="150%"><feDropShadow class="flow-shadow" dx="0" dy="1" stdDeviation="1.4"/></filter>
    <filter id="flow-card-lift" x="-15%" y="-20%" width="130%" height="170%"><feDropShadow class="flow-shadow-lift" dx="0" dy="5" stdDeviation="6"/></filter>
  </defs>`;
  const axis = layout.axis.length
    ? `<g class="flow-axis" aria-hidden="true"><path class="flow-axis-rule" d="M${g.padX} ${n(g.padTop + g.axisH - 6)} H${n(layout.width - g.padX)}"/>${layout.axis.map((tick) => `<path class="flow-axis-tick" d="M${n(tick.x)} ${n(tick.y + g.axisH - 10)} V${n(tick.y + g.axisH - 2)}"/><text class="flow-axis-label" x="${n(tick.x)}" y="${n(tick.y + 11)}">${esc(flowAxisLabel(tick.time))}</text>`).join("")}</g>`
    : "";
  const band = layout.band
    ? `<g class="flow-band" aria-hidden="true"><rect class="flow-band-box" x="10" y="${n(layout.band.y)}" width="${layout.width - 20}" height="${n(layout.band.height + 6)}" rx="12"/><text class="flow-band-label" x="${g.padX}" y="${n(layout.band.y + 16)}">${esc(t("Project"))}</text></g>${layout.band.chips.map(flowChipSvg).join("")}`
    : "";
  const laneLines = layout.laneLines.map((line) => `<path class="flow-lane-line" d="M${n(line.x1)} ${n(line.y)} H${n(line.x2)}"/>`).join("");
  // Reading order: the project band, then each card followed by its own Decisions.
  const nodes = layout.nodes.map((node) => flowNodeSvg(node, layout) + flowPinsSvg(node, layout)).join("");
  return `<svg class="flow-svg" width="${layout.width}" height="${layout.height}" viewBox="0 0 ${layout.width} ${layout.height}" role="group" aria-label="${esc(t("Flow between Intents"))}">
    ${defs}
    ${axis}
    ${band}
    <g class="flow-lines" aria-hidden="true">${laneLines}${layout.lines.map(flowLineSvg).join("")}</g>
    ${nodes}
  </svg>`;
}

// Cut a label to the longest start that fits, measured on the drawn text.
function fitFlowLabel(text, maxWidth) {
  const full = text.getAttribute("data-full");
  if (full === null) return;
  text.textContent = full;
  if (text.getComputedTextLength() <= maxWidth) return;
  let low = 0;
  let high = full.length;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    text.textContent = `${full.slice(0, middle).trimEnd()}…`;
    if (text.getComputedTextLength() <= maxWidth) low = middle;
    else high = middle - 1;
  }
  text.textContent = `${full.slice(0, low).trimEnd()}…`;
}

// SVG text cannot size its own box. Once drawn, labels are cut to fit exactly and pills and chips
// take the width of their text; the estimate drawn first stays wherever nothing can be measured.
function fitFlowText() {
  for (const group of el.detailContent.querySelectorAll?.(".flow-svg [data-fit]") || []) {
    const text = group.querySelector("[data-fit-text]");
    if (typeof text?.getComputedTextLength !== "function" || !text.getComputedTextLength()) continue;
    const pad = Number(group.dataset.fit) || 0;
    const max = Number(group.dataset.fitMax) || Infinity;
    fitFlowLabel(text, max - pad);
    group.querySelector("[data-fit-box]")?.setAttribute("width", String(flowNumber(Math.min(text.getComputedTextLength() + pad, max))));
  }
}

// Where a frame smaller than the graph should start: the target card fully in view, and among those
// positions the one showing the most card area, so the frame does not open on empty canvas.

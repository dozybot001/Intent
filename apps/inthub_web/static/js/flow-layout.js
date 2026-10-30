/* Flow: Intents as cards, relations as curves */

// Card size, gaps and padding of the Flow canvas. A row grows where a card carries Decision pins.
const FLOW_GEOMETRY = {
  nodeW: 200, nodeH: 100, gapX: 72, gapY: 32, padX: 28, padTop: 12, padBottom: 28,
  axisH: 26, bandLabel: 24, bandRow: 28, pinTop: 18, pinRow: 18, pinBottom: 8,
};
const FLOW_PINS = 2;
const FLOW_BAND_ROWS = 3;
// Where vertical runs may sit inside a gap, as a share of its width; parts fan out nearest first.
const FLOW_TRACKS = [0.5, 0.3, 0.7, 0.15, 0.85];
const FLOW_FAN = [0.7, 0.5, 0.3, 0.15, 0.85];
// Heights (from a card's middle) where lines may meet its side, in each kind's order of preference.
const FLOW_PORTS = {
  flow: [0, -12, 12, -24, 24, -36, 36],
  branch: [12, 24, 36, 0, -12, -24, -36],
  depends: [12, 24, 36, 0, -12, -24, -36],
  conflict: [-12, -24, -36, 0, 12, 24, 36],
};
// How far a bend may reach along a horizontal leg (across a gap) and a vertical one, and how full it is.
const FLOW_BEND = { across: 36, along: 84, fullness: 0.62 };
// Regular-weight labels run narrower than the semibold titles the width estimate is tuned for.
const FLOW_REGULAR = 0.9;
const FLOW_LINE_ORDER = ["rejoin", "branch", "flow", "depends", "conflict"];

function flowTime(object) {
  const time = Date.parse(object?.created_at || "");
  return Number.isFinite(time) ? time : 0;
}

function byCreation(left, right) {
  return flowTime(left) - flowTime(right) || String(left.id).localeCompare(String(right.id));
}

function flowDay(time) {
  const date = new Date(time);
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
}

// Lay out the Flow graph: logical columns and lanes, pixel boxes and routed lines. Pure, no DOM.
// - Columns follow creation time and never go back; a parent or predecessor also pushes the
//   later Intent at least one column right.
// - Lanes are rows. A successor continues its predecessor's lane; parts and derived Intents open
//   lanes below their parent. A row is as tall as its tallest card with Decision pins.
// - Routes run only through the gaps between columns and rows, so they never cross a card;
//   flowCurve() then turns each route into curves that stay in the same free space.
function flowLayout(intents, decisions = [], { hideEnded = false, focus = "", geometry = {} } = {}) {
  const g = { ...FLOW_GEOMETRY, ...geometry };
  const byId = intentMap(intents);
  const links = relationLinks(byId);
  const focusId = focus && byId.has(focus) ? focus : "";
  let visible = new Set(byId.keys());
  if (focusId) {
    visible = new Set([focusId]);
    for (const link of links) {
      if (link.subject === focusId) visible.add(link.target);
      if (link.target === focusId) visible.add(link.subject);
    }
  }
  if (hideEnded) for (const id of [...visible]) if (id !== focusId && ENDED_STATUSES.has(byId.get(id).status)) visible.delete(id);
  const relations = links.filter((link) => visible.has(link.subject) && visible.has(link.target));
  // Standalone means no relation at all; an Intent whose partners are hidden still belongs to the flow.
  const related = new Set(links.flatMap((link) => [link.subject, link.target]));
  const shown = [...visible].map((id) => byId.get(id)).sort(byCreation);
  const placed = focusId ? shown : shown.filter((intent) => related.has(intent.id));
  const standalone = focusId ? [] : shown.filter((intent) => !related.has(intent.id));
  const rank = new Map(placed.map((intent, index) => [intent.id, index]));

  const parentOf = new Map();
  const predecessors = new Map();
  for (const link of relations) {
    if (PARENT_RELATIONS.has(link.type) && !parentOf.has(link.subject)) parentOf.set(link.subject, link.target);
    if (link.type === "succeeds") predecessors.set(link.subject, [...(predecessors.get(link.subject) || []), link.target]);
  }
  for (const list of predecessors.values()) list.sort((left, right) => rank.get(left) - rank.get(right));
  const before = (id) => [parentOf.get(id), ...(predecessors.get(id) || [])].filter((other) => rank.has(other));

  // Creation order, except that a parent or predecessor always comes first. A cycle across
  // relation families (allowed by the rules) falls back to creation order.
  const order = [];
  const done = new Set();
  while (order.length < placed.length) {
    const next = placed.find((intent) => !done.has(intent.id) && before(intent.id).every((id) => done.has(id)))
      || placed.find((intent) => !done.has(intent.id));
    done.add(next.id);
    order.push(next);
  }

  const lanes = [];
  const laneOf = new Map();
  const placement = new Map();
  for (const intent of order) {
    const id = intent.id;
    const parent = laneOf.has(parentOf.get(id)) ? parentOf.get(id) : null;
    const preds = (predecessors.get(id) || []).filter((pred) => laneOf.has(pred));
    const free = preds.filter((pred) => lanes[laneOf.get(pred)].nodes.at(-1) === pred);
    // Carry on a predecessor's lane unless that would pull a part away from its own parent.
    const carry = free.find((pred) => !parent || parentOf.get(pred) === parent || lanes[laneOf.get(pred)].anchor === parent);
    if (carry) {
      const lane = lanes[laneOf.get(carry)];
      lane.nodes.push(id);
      laneOf.set(id, lane.index);
      placement.set(id, { kind: "continue", anchor: carry });
      continue;
    }
    const kind = parent ? "child" : preds.length ? "branch" : "root";
    const anchor = parent || preds[0] || null;
    lanes.push({ index: lanes.length, nodes: [id], kind, anchor });
    laneOf.set(id, lanes.length - 1);
    placement.set(id, { kind, anchor });
  }

  const colOf = new Map();
  let ratchet = 0;
  for (const intent of order) {
    const lane = lanes[laneOf.get(intent.id)];
    const index = lane.nodes.indexOf(intent.id);
    let col = ratchet;
    if (index > 0) col = Math.max(col, colOf.get(lane.nodes[index - 1]) + 1);
    for (const other of before(intent.id)) if (colOf.has(other)) col = Math.max(col, colOf.get(other) + 1);
    colOf.set(intent.id, col);
    ratchet = col;
  }

  const childLanes = new Map(lanes.map((lane) => [lane.index, []]));
  for (const lane of lanes) if (lane.kind !== "root") childLanes.get(laneOf.get(lane.anchor)).push(lane);
  const headOf = (lane) => lane.nodes[0];
  const rows = [];
  const visit = (lane) => {
    lane.row = rows.length;
    rows.push(lane);
    childLanes.get(lane.index)
      .sort((left, right) => colOf.get(right.anchor) - colOf.get(left.anchor)
        || colOf.get(headOf(left)) - colOf.get(headOf(right)) || rank.get(headOf(left)) - rank.get(headOf(right)))
      .forEach(visit);
  };
  lanes.filter((lane) => lane.kind === "root").sort((left, right) => rank.get(headOf(left)) - rank.get(headOf(right))).forEach(visit);

  // Decisions with a placed source hang as pins under its card; the others sit in the Project band.
  const knownDecisions = (decisions || []).filter((decision) => decision?.id).sort(byCreation);
  const hasSource = (decision) => Boolean(decision.source_intent_id) && byId.has(decision.source_intent_id);
  const pinned = new Map();
  for (const decision of knownDecisions) {
    if (hasSource(decision) && rank.has(decision.source_intent_id)) {
      pinned.set(decision.source_intent_id, [...(pinned.get(decision.source_intent_id) || []), decision]);
    }
  }
  const pinRows = (id) => {
    const count = (pinned.get(id) || []).length;
    return Math.min(count, FLOW_PINS) + (count > FLOW_PINS ? 1 : 0);
  };
  const pinSpace = (id) => (pinRows(id) ? g.pinTop + (pinRows(id) - 1) * g.pinRow + g.pinBottom : 0);

  const columnAt = (time) => order.reduce((col, intent) => (flowTime(intent) <= time ? Math.max(col, colOf.get(intent.id)) : col), 0);
  const bandColumns = new Map();
  for (const decision of focusId || !placed.length ? [] : knownDecisions.filter((entry) => !hasSource(entry))) {
    const col = columnAt(flowTime(decision));
    bandColumns.set(col, [...(bandColumns.get(col) || []), decision]);
  }
  const chips = [];
  for (const [col, list] of bandColumns) {
    const listed = list.length > FLOW_BAND_ROWS ? list.slice(0, FLOW_BAND_ROWS - 1) : list;
    listed.forEach((decision, row) => chips.push({ decision, col, row }));
    if (list.length > listed.length) chips.push({ decision: null, col, row: listed.length, more: list.length - listed.length });
  }
  const bandRows = chips.reduce((most, chip) => Math.max(most, chip.row + 1), 0);

  // From the top: the time axis, the Project band, then the lanes.
  const colX = (col) => g.padX + col * (g.nodeW + g.gapX);
  const axisY = g.padTop;
  const bandY = axisY + g.axisH;
  const bandHeight = bandRows ? g.bandLabel + bandRows * g.bandRow : 0;
  const top = bandY + bandHeight + (bandRows ? g.gapY : g.gapY / 2);
  const extra = rows.map((lane) => Math.max(0, ...lane.nodes.map(pinSpace)));
  const rowTop = [];
  let next = top;
  rows.forEach((lane, row) => {
    rowTop[row] = next;
    next += g.nodeH + extra[row] + g.gapY;
  });
  const rowBottom = (row) => rowTop[row] + g.nodeH + extra[row];

  // A quiet time axis: the creation date of the first Intent to reach each column. An Intent moved right
  // by its predecessor counts from that predecessor's date, so the axis never runs back; one label a day.
  const reached = new Map();
  let clock = 0;
  for (const intent of order) {
    clock = Math.max(clock, flowTime(intent));
    if (!reached.has(colOf.get(intent.id))) reached.set(colOf.get(intent.id), clock);
  }
  const axis = [];
  for (const col of [...reached.keys()].sort((left, right) => left - right)) {
    const time = reached.get(col);
    if (time && axis.at(-1)?.day !== flowDay(time)) axis.push({ col, x: colX(col), y: axisY, time, day: flowDay(time) });
  }

  const nodes = order.map((intent) => {
    const row = lanes[laneOf.get(intent.id)].row;
    const x = colX(colOf.get(intent.id));
    const y = rowTop[row];
    const { kind, anchor } = placement.get(intent.id);
    return {
      id: intent.id, intent, col: colOf.get(intent.id), lane: row, x, y, cx: x + g.nodeW / 2, cy: y + g.nodeH / 2,
      placement: kind, anchor, decisions: pinned.get(intent.id) || [],
      box: { x1: x, y1: y, x2: x + g.nodeW, y2: y + g.nodeH + pinSpace(intent.id) },
    };
  });
  const nodeOf = new Map(nodes.map((node) => [node.id, node]));
  const rowNodes = new Map();
  for (const node of nodes) rowNodes.set(node.lane, [...(rowNodes.get(node.lane) || []), node]);
  const laneClear = (row, from, to) => !(rowNodes.get(row) || []).some((node) => node.col > Math.min(from, to) && node.col < Math.max(from, to));
  const maxCol = nodes.reduce((most, node) => Math.max(most, node.col), 0);

  // Vertical runs share the gaps between columns (gap k lies just left of column k);
  // each run takes its own track so two lines never lie on top of each other.
  const usedTracks = new Map();
  const track = (gap, y1, y2, prefer, allowed = FLOW_TRACKS) => {
    const lo = Math.min(y1, y2) - 10;
    const hi = Math.max(y1, y2) + 10;
    const used = usedTracks.get(gap) || [];
    const share = [...allowed].sort((a, b) => Math.abs(a - prefer) - Math.abs(b - prefer))
      .find((candidate) => !used.some((entry) => entry.share === candidate && entry.lo < hi && entry.hi > lo)) ?? prefer;
    used.push({ share, lo, hi });
    usedTracks.set(gap, used);
    return Math.max(4, colX(gap) - g.gapX + g.gapX * share);
  };
  // Lines meeting the same side of a card do so at their own height.
  const usedPorts = new Map();
  const portsOf = (node, side) => {
    const key = `${node.id}:${side}`;
    if (!usedPorts.has(key)) usedPorts.set(key, new Set());
    return usedPorts.get(key);
  };
  const reserve = (node, side) => portsOf(node, side).add(0);
  const port = (node, side, kind) => {
    const used = portsOf(node, side);
    const slot = FLOW_PORTS[kind].find((offset) => !used.has(offset)) ?? FLOW_PORTS[kind][0];
    used.add(slot);
    return node.cy + slot;
  };
  // Along whichever lane is clear, through the gap beside the other end; around on a gap row otherwise.
  const connect = (from, to, kind, prefer) => {
    if (to.col === from.col) {
      const y1 = port(from, "right", kind);
      const y2 = port(to, "right", kind);
      const gx = track(from.col + 1, y1, y2, prefer);
      return [[from.x + g.nodeW, y1], [gx, y1], [gx, y2], [to.x + g.nodeW, y2]];
    }
    const forward = to.col > from.col;
    const exitX = forward ? from.x + g.nodeW : from.x;
    const enterX = forward ? to.x : to.x + g.nodeW;
    const y1 = port(from, forward ? "right" : "left", kind);
    const y2 = port(to, forward ? "left" : "right", kind);
    const besideTarget = forward ? to.col : to.col + 1;
    const besideSource = forward ? from.col + 1 : from.col;
    if (laneClear(from.lane, from.col, to.col)) {
      if (from.lane === to.lane && y1 === y2) return [[exitX, y1], [enterX, y2]];
      const gx = track(besideTarget, y1, y2, prefer);
      return [[exitX, y1], [gx, y1], [gx, y2], [enterX, y2]];
    }
    if (laneClear(to.lane, from.col, to.col)) {
      const gx = track(besideSource, y1, y2, prefer);
      return [[exitX, y1], [gx, y1], [gx, y2], [enterX, y2]];
    }
    const rowLine = from.cy <= to.cy ? rowTop[to.lane] - g.gapY / 2 : rowBottom(to.lane) + g.gapY / 2;
    const sx = track(besideSource, y1, rowLine, prefer);
    const tx = track(besideTarget, rowLine, y2, prefer);
    return [[exitX, y1], [sx, y1], [sx, rowLine], [tx, rowLine], [tx, y2], [enterX, y2]];
  };

  const lines = [];
  const laneEnd = new Map(lanes.map((lane) => [lane.row, nodeOf.get(lane.nodes.at(-1)).x + g.nodeW]));
  const ends = (link) => [nodeOf.get(link.target), nodeOf.get(link.subject)];
  const about = (link) => ({ type: link.type, subject: link.subject, target: link.target, state: link.state });
  const carried = (from, to) => to.lane === from.lane && lanes[laneOf.get(to.id)].nodes[lanes[laneOf.get(to.id)].nodes.indexOf(to.id) - 1] === from.id;
  const forked = (from, to) => to.placement === "branch" && to.anchor === from.id;
  const tree = (from, to) => to.placement === "child" && to.anchor === from.id;

  // A lane's own successions keep the middle of both sides.
  for (const link of relations) {
    const [from, to] = ends(link);
    if (link.type !== "succeeds" || !carried(from, to)) continue;
    reserve(from, "right");
    reserve(to, "left");
    lines.push({ ...about(link), kind: "flow", arrow: true, points: [[from.x + g.nodeW, from.cy], [to.x, to.cy]] });
  }
  // Each part or derived Intent gets its own strand from its parent's side, nearest child highest and
  // furthest from the parent, so the strands nest instead of crossing.
  const children = new Map();
  for (const link of relations) {
    const [from, to] = ends(link);
    if (PARENT_RELATIONS.has(link.type) && tree(from, to)) children.set(from.id, [...(children.get(from.id) || []), { link, to }]);
  }
  for (const [parentId, list] of children) {
    const from = nodeOf.get(parentId);
    list.sort((left, right) => left.to.lane - right.to.lane).forEach(({ link, to }, index) => {
      reserve(to, "left");
      const y1 = port(from, "right", "branch");
      const gx = track(from.col + 1, y1, to.cy, FLOW_FAN[index] ?? 0.5);
      lines.push({ ...about(link), kind: "branch", points: [[from.x + g.nodeW, y1], [gx, y1], [gx, to.cy], [to.x, to.cy]] });
    });
  }
  for (const link of relations) {
    const [from, to] = ends(link);
    // A part that has ended (done or dropped) rejoins its parent's lane.
    if (link.type === "part_of" && ENDED_STATUSES.has(to.intent.status) && to.lane !== from.lane) {
      reserve(to, "right");
      // It turns back along the parent's lane, so it keeps clear of the column edge.
      const gx = track(to.col + 1, to.cy, from.cy, 0.3, FLOW_TRACKS.filter((share) => share >= 0.3));
      const endX = Math.max(to.x + g.nodeW + 2, gx - 30);
      lines.push({ ...about(link), kind: "rejoin", points: [[to.x + g.nodeW, to.cy], [gx, to.cy], [gx, from.cy], [endX, from.cy]] });
      laneEnd.set(from.lane, Math.max(laneEnd.get(from.lane), gx));
    }
    if (link.type === "succeeds" && forked(from, to)) {
      reserve(from, "right");
      reserve(to, "left");
      const gx = track(from.col + 1, from.cy, to.cy, 0.5);
      lines.push({ ...about(link), kind: "flow", arrow: true, points: [[from.x + g.nodeW, from.cy], [gx, from.cy], [gx, to.cy], [to.x, to.cy]] });
    }
  }
  for (const type of [...PARENT_RELATIONS, "succeeds", "depends_on", "conflicts_with"]) {
    for (const link of relations.filter((entry) => entry.type === type)) {
      const [from, to] = ends(link);
      if (PARENT_RELATIONS.has(type) && !tree(from, to)) {
        lines.push({ ...about(link), kind: "branch", points: connect(from, to, "branch", 0.5) });
      } else if (type === "succeeds" && !carried(from, to) && !forked(from, to)) {
        lines.push({ ...about(link), kind: "flow", arrow: true, points: connect(from, to, "flow", 0.5) });
      } else if (type === "depends_on") {
        lines.push({ ...about(link), kind: "depends", arrow: true, points: connect(from, to, "depends", 0.3) });
      } else if (type === "conflicts_with") {
        lines.push({ ...about(link), kind: "conflict", points: connect(from, to, "conflict", 0.7) });
      }
    }
  }
  lines.sort((left, right) => FLOW_LINE_ORDER.indexOf(left.kind) - FLOW_LINE_ORDER.indexOf(right.kind));
  const obstacles = nodes.map((node) => node.box);
  for (const line of lines) line.curve = flowCurve(line.points, obstacles);
  // A parent's lane only runs on as far as its ended parts come back to join it.
  const laneLines = lanes.map((lane) => {
    const last = nodeOf.get(lane.nodes.at(-1));
    const x2 = laneEnd.get(lane.row);
    return x2 > last.x + g.nodeW + 1 ? { row: lane.row, x1: last.x + g.nodeW, x2, y: last.cy } : null;
  }).filter(Boolean);

  const reach = Math.max(colX(maxCol) + g.nodeW + g.padX, ...lines.flatMap((line) => line.points.map((point) => point[0] + 16)), ...laneLines.map((line) => line.x2 + 16));
  return {
    geometry: g, hasRelations: links.length > 0, focus: focusId, relations, standalone,
    nodes: [...nodes].sort((left, right) => left.lane - right.lane || left.col - right.col),
    lines, laneLines, axis,
    band: bandRows ? {
      y: bandY, height: bandHeight,
      // A chip may run on over the next column when no chip of its row starts there.
      chips: chips.map((chip) => {
        const next = chips.filter((other) => other.row === chip.row && other.col > chip.col).reduce((nearest, other) => Math.min(nearest, other.col), chip.col + 2);
        const span = Math.min(next, chip.col + 2) - chip.col;
        const width = Math.min(span * g.nodeW + (span - 1) * g.gapX, colX(maxCol) + g.nodeW - colX(chip.col));
        return { ...chip, x: colX(chip.col), y: bandY + g.bandLabel + chip.row * g.bandRow, width };
      }),
    } : null,
    width: nodes.length ? Math.ceil(reach) : 0,
    height: nodes.length ? Math.ceil(rowBottom(rows.length - 1) + g.padBottom) : 0,
    columns: nodes.length ? maxCol + 1 : 0, lanes: rows.length,
  };
}

// The card to bring into view first: the focused Intent, else the most recent open one.

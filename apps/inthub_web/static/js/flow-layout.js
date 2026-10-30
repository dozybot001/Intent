/* Flow: Intents as cards, relations as curves */

// Card size, gaps and padding of the Flow canvas. A row grows where a card carries Decision pins.
const FLOW_GEOMETRY = {
  nodeW: 200, nodeH: 100, gapX: 64, gapY: 20, groupGap: 40, padX: 24, padTop: 24, padBottom: 24,
  bandLabel: 24, bandRow: 28, pinTop: 18, pinRow: 18, pinBottom: 8,
};
const FLOW_WIDTH = 1340;
const FLOW_PINS = 2;
const FLOW_BAND_ROWS = 3;
const FLOW_CHIP_WIDTH = 360;

function flowTime(object) {
  const time = Date.parse(object?.created_at || "");
  return Number.isFinite(time) ? time : 0;
}

function byCreation(left, right) {
  return flowTime(left) - flowTime(right) || String(left.id).localeCompare(String(right.id));
}

// The forest behind the page. Each Intent hangs from one place: it carries on a predecessor's lane,
// or it is a kid of its parent (or of the predecessor it forks from), or it leans on what it depends
// on or conflicts with, after the real kids; only an Intent with none of these is a root. Parents and
// predecessors come first, then dependencies where that is possible; a cycle across relation families
// (allowed by the rules) falls back to creation order, so an Intent only ever hangs from one already
// placed and nothing is lost.
function flowTree(placed, relations) {
  const rank = new Map(placed.map((intent, index) => [intent.id, index]));
  const parentOf = new Map();
  const predecessors = new Map();
  const dependencies = new Map();
  const rivals = new Map();
  const note = (map, id, other) => map.set(id, [...(map.get(id) || []), other]);
  for (const link of relations) {
    if (PARENT_RELATIONS.has(link.type) && !parentOf.has(link.subject)) parentOf.set(link.subject, link.target);
    if (link.type === "succeeds") note(predecessors, link.subject, link.target);
    if (link.type === "depends_on") note(dependencies, link.subject, link.target);
    if (link.type === "conflicts_with") {
      note(rivals, link.subject, link.target);
      note(rivals, link.target, link.subject);
    }
  }
  for (const list of predecessors.values()) list.sort((left, right) => rank.get(left) - rank.get(right));
  const before = (id) => [parentOf.get(id), ...(predecessors.get(id) || [])];
  const waiting = (test) => placed.find((intent) => !seen.has(intent.id) && test(intent.id));
  const settled = (list) => list.every((other) => seen.has(other) || !rank.has(other));
  const seen = new Set();
  const laneNext = new Map();
  const kids = new Map();
  const roots = [];
  const leaning = new Set();
  while (seen.size < placed.length) {
    const { id } = waiting((other) => settled(before(other)) && settled(dependencies.get(other) || []))
      || waiting((other) => settled(before(other))) || waiting(() => true);
    const parent = seen.has(parentOf.get(id)) ? parentOf.get(id) : null;
    const preds = (predecessors.get(id) || []).filter((pred) => seen.has(pred));
    // Carry on a predecessor's lane unless that would pull a part away from its own parent.
    const carry = preds.find((pred) => !laneNext.has(pred) && (!parent || parentOf.get(pred) === parent));
    const leanOn = [...(dependencies.get(id) || []), ...(rivals.get(id) || [])].find((other) => seen.has(other));
    const anchor = parent || preds[0] || leanOn;
    if (!parent && !preds[0] && leanOn) leaning.add(id);
    if (carry) laneNext.set(carry, id);
    else if (anchor) note(kids, anchor, id);
    else roots.push(id);
    seen.add(id);
  }
  for (const [anchor, list] of kids) kids.set(anchor, [...list.filter((id) => !leaning.has(id)), ...list.filter((id) => leaning.has(id))]);
  return { laneNext, kids, roots, leaning };
}

// Intents connected by any relation form a group. Groups never share lines, so they can sit side by side.
function flowGroups(roots, relations) {
  const links = new Map();
  const find = (id) => {
    let root = id;
    while (links.has(root)) root = links.get(root);
    return root;
  };
  for (const link of relations) {
    const [subject, target] = [find(link.subject), find(link.target)];
    if (subject !== target) links.set(subject, target);
  }
  const groups = new Map();
  for (const id of roots) groups.set(find(id), [...(groups.get(find(id)) || []), id]);
  return [...groups.values()];
}

// Lay out the Flow graph: cards, then routed lines. Pure, no DOM.
// - Within a group, a kid sits one column right of its parent, the first on the parent's own row and
//   the others below it; a successor continues its predecessor's row. Rows hold nothing else, so a
//   tree needs no long lines.
// - Groups with open work come first, newest first, packed left to right and then down, so a project
//   fills the page instead of running down one staircase.
function flowLayout(intents, decisions = [], { hideEnded = false, focus = "", maxWidth = FLOW_WIDTH, geometry = {} } = {}) {
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
  const standalone = focusId ? [] : shown.filter((intent) => !related.has(intent.id)).reverse();

  const tree = flowTree(placed, relations);
  const kidsOf = (id) => tree.kids.get(id) || [];
  const memo = (compute) => {
    const known = new Map();
    return (id) => {
      if (!known.has(id)) known.set(id, compute(id));
      return known.get(id);
    };
  };
  const kidColumns = (id) => Math.max(0, ...kidsOf(id).map((kid) => columnsOf(kid)));
  const columnsOf = memo((id) => 1 + kidColumns(id) + (tree.laneNext.has(id) ? columnsOf(tree.laneNext.get(id)) : 0));
  const rowsUnder = (id) => kidsOf(id).reduce((rows, kid) => rows + rowsOf(kid), 0);
  const rowsOf = memo((id) => {
    const next = tree.laneNext.get(id);
    return next ? Math.max(1 + rowsUnder(id), rowsOf(next)) : Math.max(1, rowsUnder(id));
  });

  // Decisions with a placed source hang as pins under its card; the others sit in the Project band.
  const known = (decisions || []).filter((decision) => decision?.id).sort(byCreation);
  const hasSource = (decision) => Boolean(decision.source_intent_id) && byId.has(decision.source_intent_id);
  const pinned = new Map();
  const placedIds = new Set(placed.map((intent) => intent.id));
  for (const decision of known) {
    if (hasSource(decision) && placedIds.has(decision.source_intent_id)) {
      pinned.set(decision.source_intent_id, [...(pinned.get(decision.source_intent_id) || []), decision]);
    }
  }
  const pinRows = (id) => {
    const count = (pinned.get(id) || []).length;
    return Math.min(count, FLOW_PINS) + (count > FLOW_PINS ? 1 : 0);
  };
  const pinSpace = (id) => (pinRows(id) ? g.pinTop + (pinRows(id) - 1) * g.pinRow + g.pinBottom : 0);

  // Each group: logical cells first, then row heights.
  const groups = flowGroups(tree.roots, relations).map((roots) => {
    const cells = [];
    const place = (id, col, row) => {
      cells.push({ id, col, row });
      const next = tree.laneNext.get(id);
      let below = next ? row + 1 : row;
      for (const kid of kidsOf(id)) {
        place(kid, col + 1, below);
        below += rowsOf(kid);
      }
      if (next) place(next, col + 1 + kidColumns(id), row);
    };
    let row = 0;
    for (const root of roots) {
      place(root, 0, row);
      row += rowsOf(root);
    }
    const heights = Array.from({ length: row }, () => g.nodeH);
    for (const cell of cells) heights[cell.row] = Math.max(heights[cell.row], g.nodeH + pinSpace(cell.id));
    const rowTop = [];
    heights.reduce((top, height, index) => {
      rowTop[index] = top;
      return top + height + g.gapY;
    }, 0);
    const times = cells.map((cell) => flowTime(byId.get(cell.id)));
    return {
      cells, rowTop, height: rowTop.at(-1) + heights.at(-1),
      columns: Math.max(...roots.map((root) => columnsOf(root))),
      open: cells.some((cell) => !ENDED_STATUSES.has(byId.get(cell.id).status)),
      latest: Math.max(...times),
    };
  }).sort((left, right) => right.open - left.open || right.latest - left.latest);

  const unit = g.nodeW + g.gapX;
  const colX = (col) => g.padX + col * unit;
  const grid = Math.max(1, Math.floor((maxWidth - 2 * g.padX + g.gapX) / unit));

  // The Project band runs across the top: chips in reading order, wrapped to the width.
  const chips = [];
  let more = 0;
  const bandWidth = grid * unit - g.gapX;
  let chipX = 0;
  let chipRow = 0;
  const projectWide = focusId || !placed.length ? [] : known.filter((entry) => !hasSource(entry));
  for (const [index, decision] of projectWide.entries()) {
    const width = Math.min(FLOW_CHIP_WIDTH, bandWidth, 38 + flowTextWidth(decision.what || decision.id, 12, FLOW_REGULAR));
    const lastRow = chipRow === FLOW_BAND_ROWS - 1;
    // The last row keeps room for the "+N" chip.
    if (chipX && chipX + width > bandWidth - (lastRow ? 52 : 0)) {
      if (lastRow) {
        more = projectWide.length - index;
        break;
      }
      chipX = 0;
      chipRow += 1;
    }
    chips.push({ decision, row: chipRow, x: colX(0) + chipX, width });
    chipX += width + 8;
  }
  if (more) chips.push({ decision: null, more, row: FLOW_BAND_ROWS - 1, x: colX(0) + chipX, width: 44 });
  const bandY = g.padTop;
  const bandHeight = chips.length ? g.bandLabel + (chips.at(-1).row + 1) * g.bandRow : 0;
  const top = bandY + bandHeight + (chips.length ? g.groupGap : 0);

  // Fill from the top: each group takes the lowest place its width fits, leftmost on a tie.
  const bottoms = Array.from({ length: grid }, () => top);
  const nodes = [];
  for (const [index, group] of groups.entries()) {
    const span = group.columns;
    let start = 0;
    let y = Infinity;
    for (let col = 0; col <= Math.max(0, grid - span); col++) {
      const lowest = Math.max(...bottoms.slice(col, col + span));
      if (lowest < y) {
        y = lowest;
        start = col;
      }
    }
    for (let col = start; col < start + span; col++) bottoms[col] = y + group.height + g.groupGap;
    for (const { id, col, row } of group.cells) {
      const x = colX(start + col);
      const top = y + group.rowTop[row];
      nodes.push({
        id, intent: byId.get(id), col: start + col, lane: `${index}:${row}`, x, y: top, cx: x + g.nodeW / 2, cy: top + g.nodeH / 2,
        decisions: pinned.get(id) || [],
        box: { x1: x, y1: top, x2: x + g.nodeW, y2: top + g.nodeH + pinSpace(id) },
      });
    }
  }
  const { lines, joins } = flowRoutes({ g, tree, relations, nodes, colX, columnsOf });
  const maxCol = nodes.reduce((most, node) => Math.max(most, node.col), 0);
  const reach = Math.max(colX(maxCol) + g.nodeW + g.padX, ...lines.flatMap((line) => line.points.map((point) => point[0] + 16)));
  return {
    geometry: g, hasRelations: links.length > 0, focus: focusId, relations, standalone,
    nodes, lines, joins,
    band: chips.length ? {
      y: bandY, height: bandHeight,
      chips: chips.map((chip) => ({ ...chip, y: bandY + g.bandLabel + chip.row * g.bandRow })),
    } : null,
    width: nodes.length ? Math.ceil(Math.max(reach, chips.length ? colX(0) + bandWidth + g.padX : 0)) : 0,
    height: nodes.length ? Math.ceil(Math.max(...bottoms) - g.groupGap + g.padBottom) : 0,
    columns: nodes.length ? maxCol + 1 : 0, groups: groups.length,
  };
}

// The card to bring into view first: the focused Intent, else the most recent open one.

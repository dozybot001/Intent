/* Flow: where the lines run */

// Where vertical runs may sit inside a gap, as a share of its width. The middle belongs to trunks.
const FLOW_TRACKS = [0.3, 0.7, 0.15, 0.85, 0.5];
// Heights (from a card's middle) where lines may meet its side, in each kind's order of preference.
const FLOW_PORTS = {
  flow: [0, -12, 12, -24, 24, -36, 36],
  branch: [12, 24, 36, 0, -12, -24, -36],
  depends: [12, 24, 36, 0, -12, -24, -36],
  conflict: [-12, -24, -36, 0, 12, 24, 36],
};
// How far a bend may reach along a horizontal leg (across a gap) and a vertical one, and how full it is.
const FLOW_BEND = { across: 36, along: 84, fullness: 0.62 };
// Trunks turn in the same small radius, so lines sharing one lie exactly on top of each other.
const FLOW_ELBOW = { across: 14, along: 14, fullness: 0.62 };
// Regular-weight labels run narrower than the semibold titles the width estimate is tuned for.
const FLOW_REGULAR = 0.9;
const FLOW_LINE_ORDER = ["rejoin", "branch", "flow", "depends", "conflict"];
const FLOW_LINE_STYLES = {
  succeeds: { kind: "flow", arrow: true },
  depends_on: { kind: "depends", arrow: true },
  conflicts_with: { kind: "conflict" },
};

// A parent reaches its kids through one trunk in the gap beside it, and its ended parts come back
// through one spine to a single point on its row: a fork and a join, whatever the number of kids.
// Anything else (dependencies, conflicts, a second predecessor) runs through the gaps on its own track.
function flowRoutes({ g, tree, relations, nodes, colX, columnsOf }) {
  const nodeOf = new Map(nodes.map((node) => [node.id, node]));
  const rows = new Map();
  for (const node of nodes) rows.set(node.lane, [...(rows.get(node.lane) || []), node]);
  const laneClear = (lane, from, to) => !rows.get(lane).some((node) => node.col > Math.min(from, to) && node.col < Math.max(from, to));
  const laneTop = (lane) => Math.min(...rows.get(lane).map((node) => node.box.y1));
  const laneBottom = (lane) => Math.max(...rows.get(lane).map((node) => node.box.y2));

  // Vertical runs share the gaps between columns (gap k lies just left of column k);
  // each run takes its own track so two lines never lie on top of each other.
  const usedTracks = new Map();
  const occupy = (gap, share, y1, y2) => {
    const used = usedTracks.get(gap) || [];
    used.push({ share, lo: Math.min(y1, y2) - 10, hi: Math.max(y1, y2) + 10 });
    usedTracks.set(gap, used);
  };
  const track = (gap, y1, y2, prefer) => {
    const lo = Math.min(y1, y2) - 10;
    const hi = Math.max(y1, y2) + 10;
    const used = usedTracks.get(gap) || [];
    const share = [...FLOW_TRACKS].sort((a, b) => Math.abs(a - prefer) - Math.abs(b - prefer))
      .find((candidate) => !used.some((entry) => entry.share === candidate && entry.lo < hi && entry.hi > lo)) ?? prefer;
    occupy(gap, share, y1, y2);
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
    const rowLine = from.cy <= to.cy ? laneTop(to.lane) - g.gapY / 2 : laneBottom(to.lane) + g.gapY / 2;
    const sx = track(besideSource, y1, rowLine, prefer);
    const tx = track(besideTarget, rowLine, y2, prefer);
    return [[exitX, y1], [sx, y1], [sx, rowLine], [tx, rowLine], [tx, y2], [enterX, y2]];
  };

  const about = (link) => ({ type: link.type, subject: link.subject, target: link.target, state: link.state });
  const styleOf = (link) => FLOW_LINE_STYLES[link.type] || { kind: "branch" };
  // What hangs one card from another: a parent or predecessor before a dependency, and a conflict either way round.
  const tieOf = (id, anchor) => {
    const ties = relations.filter((link) => (link.subject === id && link.target === anchor)
      || (link.type === "conflicts_with" && link.subject === anchor && link.target === id));
    return ties.find((link) => !["depends_on", "conflicts_with"].includes(link.type)) || ties[0];
  };
  const kidsOf = (id) => tree.kids.get(id) || [];
  const lines = [];
  const handled = new Set();
  const add = (link, line) => {
    handled.add(link);
    lines.push({ ...about(link), ...line });
  };

  // The spine and join point of each parent with ended parts, right of its widest kid.
  const joinX = new Map();
  for (const [parent, kids] of tree.kids) {
    const ended = kids.filter((kid) => tieOf(kid, parent)?.type === "part_of" && ENDED_STATUSES.has(nodeOf.get(kid).intent.status));
    // One line into a point that leads nowhere says nothing: a join needs two, or a row to carry on.
    if (ended.length > 1 || (ended.length && tree.laneNext.has(parent))) {
      joinX.set(parent, colX(nodeOf.get(parent).col + 1 + Math.max(...kids.map(columnsOf))) - g.gapX / 2);
    }
  }
  // Where a row's own drawing ends: its join point, or its last card.
  const rowEnd = (id) => {
    let last = id;
    while (tree.laneNext.has(last)) last = tree.laneNext.get(last);
    if (joinX.has(last)) return joinX.get(last);
    return kidsOf(last).length ? rowEnd(kidsOf(last)[0]) : nodeOf.get(last).x + g.nodeW;
  };

  for (const [from, to] of tree.laneNext) {
    const [source, target] = [nodeOf.get(from), nodeOf.get(to)];
    reserve(source, "right");
    reserve(target, "left");
    add(tieOf(to, from), { kind: "flow", arrow: true, points: [[source.x + g.nodeW, source.cy], [target.x, target.cy]] });
  }
  const joins = [];
  for (const [parent, kids] of tree.kids) {
    const from = nodeOf.get(parent);
    const x0 = from.x + g.nodeW;
    const spine = x0 + g.gapX / 2;
    reserve(from, "right");
    occupy(from.col + 1, 0.5, from.cy, Math.max(...kids.map((kid) => nodeOf.get(kid).cy)));
    for (const [index, kid] of kids.entries()) {
      const to = nodeOf.get(kid);
      const link = tieOf(kid, parent);
      const above = index ? nodeOf.get(kids[index - 1]).cy : from.cy;
      // A leaning kid draws only its own stretch of the trunk, so its colour never runs over the others'.
      const stem = tree.leaning.has(kid) ? [[spine, above]] : [[x0, from.cy], [spine, from.cy]];
      const points = to.cy === from.cy ? [[x0, from.cy], [to.x, to.cy]] : [...stem, [spine, to.cy], [to.x, to.cy]];
      reserve(to, "left");
      add(link, { ...styleOf(link), points, bend: FLOW_ELBOW, mark: [spine, (above + to.cy) / 2] });
    }
    if (!joinX.has(parent)) continue;
    const x = joinX.get(parent);
    joins.push({ x, y: from.cy });
    for (const kid of kids) {
      const to = nodeOf.get(kid);
      const link = tieOf(kid, parent);
      if (link.type !== "part_of" || !ENDED_STATUSES.has(to.intent.status)) continue;
      const start = rowEnd(kid);
      // A kid whose own join falls on this point has nothing left to draw.
      if (to.cy === from.cy && start >= x) continue;
      lines.push({ ...about(link), kind: "rejoin", bend: FLOW_ELBOW,
        points: to.cy === from.cy ? [[start, to.cy], [x, to.cy]] : [[start, to.cy], [x, to.cy], [x, from.cy]] });
    }
    occupy(from.col + 1 + Math.max(...kids.map(columnsOf)), 0.5, from.cy, Math.max(...kids.map((kid) => nodeOf.get(kid).cy)));
  }
  for (const type of [...PARENT_RELATIONS, "succeeds", "depends_on", "conflicts_with"]) {
    for (const link of relations.filter((entry) => entry.type === type && !handled.has(entry))) {
      const [from, to] = [nodeOf.get(link.target), nodeOf.get(link.subject)];
      const style = styleOf(link);
      add(link, { ...style, points: connect(from, to, style.kind, style.kind === "conflict" ? 0.7 : 0.3) });
    }
  }
  lines.sort((left, right) => FLOW_LINE_ORDER.indexOf(left.kind) - FLOW_LINE_ORDER.indexOf(right.kind));
  const obstacles = nodes.map((node) => node.box);
  for (const line of lines) line.curve = flowCurve(line.points, obstacles, line.bend);
  return { lines, joins };
}

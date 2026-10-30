const {assert, context, fs, path, root, vm} = require('./harness.cjs');

async function flowAndPagingCases() {
  await vm.runInContext(`(async () => {
    const flush = async () => { for (let index = 0; index < 12; index++) await Promise.resolve(); };
    let focusedOn001;
    window.IntHubI18n.setLanguage('zh-CN');

    // Derived relation states, subject (rows) against target (columns): active, suspend, done, cancelled.
    const statuses = ['active', 'suspend', 'done', 'cancelled'];
    const open = ['in_progress', 'in_progress', 'orphaned', 'orphaned'];
    const expected = {
      part_of: [open, open, Array(4).fill('done'), Array(4).fill('dropped')],
      derived_from: Array(4).fill(Array(4).fill(null)),
      succeeds: Array(4).fill(['pending', 'pending', 'handed_over', 'handed_over']),
      depends_on: Array(4).fill(['blocked', 'blocked', 'satisfied', 'broken']),
      conflicts_with: [['unresolved', 'unresolved', 'resolved', 'resolved'], ['unresolved', 'unresolved', 'resolved', 'resolved'], Array(4).fill('resolved'), Array(4).fill('resolved')],
    };
    for (const [kind, table] of Object.entries(expected)) {
      statuses.forEach((subject, row) => statuses.forEach((target, column) => {
        assert.equal(relationState(kind, {status: subject}, {status: target}), table[row][column], kind + ' ' + subject + ' → ' + target);
      }));
    }
    for (const [kind, subject, target, want] of relationParity) {
      assert.equal(relationState(kind, {status: subject}, {status: target}), want, 'parity ' + kind + ' ' + subject + ' → ' + target);
    }
    assert.deepEqual([...ATTENTION_STATES].sort(), ['blocked', 'broken', 'orphaned', 'pending', 'unresolved']);

    const at = minute => new Date(Date.UTC(2026, 9, 30, 8, minute)).toISOString();
    const rel = (type, intent, extra = {}) => ({type, intent, created_at: at(50), ...extra});
    const flowIntents = [
      {id:'intent-001', what:'Checkout revamp', status:'active', created_at: at(1), snap_ids:['snap-001', 'snap-002']},
      {id:'intent-002', what:'Apple Pay', status:'done', created_at: at(2), relations:[rel('part_of', 'intent-001')]},
      {id:'intent-003', what:'Google Pay', status:'active', created_at: at(3), relations:[rel('part_of', 'intent-001')]},
      {id:'intent-004', what:'PaymentIntents migration', status:'active', created_at: at(4), relations:[rel('derived_from', 'intent-001')]},
      {id:'intent-005', what:'Receipts v1', status:'cancelled', created_at: at(5)},
      {id:'intent-006', what:'Receipts v2', status:'active', created_at: at(6), relations:[rel('succeeds', 'intent-005')]},
      {id:'intent-007', what:'Launch to 10%', status:'active', created_at: at(7), relations:[rel('depends_on', 'intent-003'), rel('conflicts_with', 'intent-004', {removed_at: at(51)})]},
      {id:'intent-008', what:'Server <totals>', status:'suspend', created_at: at(8), relations:[rel('conflicts_with', 'intent-006')]},
      {id:'intent-009', what:'Unrelated cleanup', status:'done', created_at: at(9)},
    ].map(intent => ({snap_ids: [], decision_ids: [], ...intent, project_id: 'p', remote_id: 'p__' + intent.id}));
    const flowDecisions = [
      {id:'decision-001', what:'Project rule', status:'active', created_at: at(2), project_id:'p', remote_id:'p__decision-001'},
      {id:'decision-002', what:'Old payment rule', status:'deprecated', created_at: at(3), source_intent_id:'intent-001', project_id:'p', remote_id:'p__decision-002'},
      {id:'decision-003', what:'Lost source', status:'active', created_at: at(4), source_intent_id:'intent-404', project_id:'p', remote_id:'p__decision-003'},
    ];

    // Both directions, outgoing first; withdrawn relations are ignored.
    const view = relationView(flowIntents, 'intent-007');
    assert.deepEqual(view.map(row => [row.type, row.direction, row.intent.id, row.state]), [['depends_on', 'out', 'intent-003', 'blocked']]);
    assert.deepEqual(relationView(flowIntents, 'intent-001').map(row => row.type + ':' + row.direction + ':' + row.intent.id),
      ['part_of:in:intent-002', 'part_of:in:intent-003', 'derived_from:in:intent-004']);
    assert.equal(relationLabel('part_of', 'out'), '属于');
    assert.equal(relationLabel('part_of', 'in'), '组成部分');
    assert.equal(relationLabel('succeeds', 'in'), '被继承');
    assert.equal(relationLabel('depends_on', 'in'), '被依赖');
    assert.ok(relationBadge('broken').includes('rel-danger') && relationBadge('broken').includes('依赖已失效'));
    assert.ok(relationBadge('blocked').includes('<span class="status-dot" aria-hidden="true"></span>被阻塞</span>'));

    const layout = flowLayout(flowIntents, flowDecisions);
    const place = id => layout.nodes.find(node => node.id === id);
    const {nodeW, gapX} = layout.geometry;
    assert.deepEqual(layout.standalone.map(intent => intent.id), ['intent-009']);
    assert.equal(layout.hasRelations, true);
    // A parent's first kid sits on its row, the others below it, all one column right; a successor continues its row.
    assert.equal(place('intent-002').y, place('intent-001').y);
    for (const part of ['intent-002', 'intent-003', 'intent-004']) assert.equal(place(part).col, place('intent-001').col + 1);
    assert.ok(place('intent-002').y < place('intent-003').y && place('intent-003').y < place('intent-004').y);
    assert.equal(place('intent-006').y, place('intent-005').y);
    assert.equal(place('intent-006').col, place('intent-005').col + 1);
    const kinds = layout.lines.map(line => line.kind + ':' + line.subject + ':' + (line.state || ''));
    assert.deepEqual(kinds.sort(), [
      'branch:intent-002:done', 'branch:intent-003:in_progress', 'branch:intent-004:', 'conflict:intent-008:unresolved',
      'depends:intent-007:blocked', 'flow:intent-006:handed_over',
    ]);
    // What depends on or conflicts with another card sits right of it, so its line runs forward.
    assert.equal(place('intent-007').y, place('intent-003').y);
    assert.equal(place('intent-007').col, place('intent-003').col + 1);
    assert.equal(place('intent-008').y, place('intent-006').y);
    assert.equal(place('intent-008').col, place('intent-006').col + 1);
    assert.equal(layout.lines.find(line => line.kind === 'depends').points.length, 2);
    const succession = layout.lines.find(line => line.kind === 'flow');
    assert.deepEqual(succession.points, [[place('intent-005').x + nodeW, place('intent-005').cy], [place('intent-006').x, place('intent-006').cy]]);
    // Kids share one trunk in the gap beside their parent; the kid on the parent's row is a straight line.
    const parentRight = place('intent-001').x + nodeW;
    const strands = ['intent-002', 'intent-003', 'intent-004'].map(id => layout.lines.find(line => line.kind === 'branch' && line.subject === id));
    for (const strand of strands) {
      assert.deepEqual(strand.points[0], [parentRight, place('intent-001').cy]);
      assert.deepEqual(strand.points.at(-1), [place(strand.subject).x, place(strand.subject).cy]);
    }
    assert.equal(strands[0].points.length, 2);
    assert.deepEqual(strands.slice(1).map(strand => strand.points[1]), [[parentRight + gapX / 2, place('intent-001').cy], [parentRight + gapX / 2, place('intent-001').cy]]);
    assert.deepEqual(strands[1].curve.segments[0], strands[2].curve.segments[0], 'the first bend lies on the shared trunk');
    // A lone ended part has nothing to join; two come back to one point on the parent's row, right of the widest kid.
    assert.deepEqual(layout.joins, []);
    const joined = flowLayout([
      {id:'intent-041', status:'active', created_at: at(1)},
      {id:'intent-042', status:'done', created_at: at(2), relations:[rel('part_of', 'intent-041')]},
      {id:'intent-043', status:'done', created_at: at(3), relations:[rel('part_of', 'intent-041')]},
      {id:'intent-044', status:'active', created_at: at(4), relations:[rel('conflicts_with', 'intent-041')]},
    ]);
    const atJoin = id => joined.nodes.find(node => node.id === id);
    const rejoin = joined.lines.find(line => line.kind === 'rejoin');
    assert.deepEqual(joined.joins, [{x: rejoin.points.at(-1)[0], y: atJoin('intent-041').cy}]);
    assert.ok(joined.joins[0].x > atJoin('intent-042').box.x2);
    // A leaning kid comes after the parts and starts from the trunk's foot, its mark on that stretch.
    const rival = joined.lines.find(line => line.kind === 'conflict');
    const trunk = atJoin('intent-041').x + nodeW + gapX / 2;
    assert.ok(atJoin('intent-044').y > atJoin('intent-043').y);
    assert.deepEqual(rival.points[0], [trunk, atJoin('intent-043').cy]);
    assert.deepEqual(rival.mark, [trunk, (atJoin('intent-043').cy + atJoin('intent-044').cy) / 2]);
    // Groups with open work come first, and each takes the lowest place its width fits.
    const newest = flowLayout([
      {id:'intent-051', status:'done', created_at: at(1)},
      {id:'intent-052', status:'done', created_at: at(2), relations:[rel('derived_from', 'intent-051')]},
      {id:'intent-053', status:'active', created_at: at(3)},
      {id:'intent-054', status:'done', created_at: at(4), relations:[rel('derived_from', 'intent-053')]},
      {id:'intent-055', status:'done', created_at: at(5)},
      {id:'intent-056', status:'done', created_at: at(6), relations:[rel('derived_from', 'intent-055')]},
    ], [], {maxWidth: 1200});
    const at0 = id => newest.nodes.find(node => node.id === id);
    assert.ok(at0('intent-053').y === at0('intent-055').y && at0('intent-053').x < at0('intent-055').x, 'two groups side by side');
    assert.ok(at0('intent-051').y > at0('intent-053').y, 'the third wraps');
    const narrow = flowLayout(flowIntents, flowDecisions, {maxWidth: 340});
    assert.equal(narrow.nodes.reduce((left, node) => Math.min(left, node.x), Infinity), narrow.geometry.padX);
    // Lines meeting one side of a node never share a height.
    const sides = new Map();
    for (const line of layout.lines.filter(line => !['branch', 'rejoin'].includes(line.kind))) {
      const [x, y] = line.points.at(-1);
      const key = Math.round(x) + ':' + Math.round(y);
      assert.ok(!sides.has(key), 'two lines end at ' + key);
      sides.set(key, line);
    }
    // Decisions: the sourceless one and the one whose source is gone are chips in the Project band;
    // a sourced one hangs as a pin under its card, whose row grows for it.
    assert.deepEqual(layout.band.chips.map(chip => [chip.decision.id, chip.row]), [['decision-001', 0], ['decision-003', 0]]);
    for (const chip of layout.band.chips) assert.ok(chip.y + 22 < Math.min(...layout.nodes.map(node => node.y)));
    assert.deepEqual(place('intent-001').decisions.map(decision => decision.id), ['decision-002']);
    assert.ok(place('intent-001').box.y2 > place('intent-001').y + layout.geometry.nodeH);
    assert.ok(place('intent-003').y >= place('intent-001').box.y2 + layout.geometry.gapY);
    // A long list of chips ends in a count instead of pushing the graph down.
    const crowded = flowLayout(flowIntents, Array.from({length: 40}, (_, index) => ({id: 'decision-' + index, what: 'A rule that takes a fair amount of room', status: 'active'})), {maxWidth: 1000});
    assert.equal(crowded.band.chips.at(-1).decision, null);
    assert.ok(crowded.band.chips.at(-1).more > 0 && crowded.band.chips.every(chip => chip.row < 3));
    assert.ok(crowded.band.chips.at(-1).x >= crowded.band.chips.at(-2).x + crowded.band.chips.at(-2).width, 'the count follows the last chip');
    assert.ok(flowLegend(crowded).includes('flow-legend'));
    assert.equal(flowTarget(layout).id, 'intent-008');
    const days = flowLayout([
      {id:'intent-041', status:'active', created_at:'2026-10-01T10:00:00Z'},
      {id:'intent-042', status:'active', created_at:'2026-10-01T10:02:00Z', relations:[rel('part_of', 'intent-041')]},
      {id:'intent-043', status:'active', created_at:'2026-10-03T10:00:00Z', relations:[rel('succeeds', 'intent-042')]},
      {id:'intent-044', status:'done', created_at:'2026-10-03T10:02:00Z', relations:[rel('succeeds', 'intent-043')]},
    ]);
    assert.equal(flowTarget(days).id, 'intent-043');
    // A frame smaller than the graph opens with the target fully in view, over as much card area as it can.
    const opening = flowViewport(layout, 360, 600);
    const latest = place('intent-008');
    assert.ok(opening.left <= latest.box.x1 && opening.left + 360 >= latest.box.x2 && opening.top <= latest.box.y1 && opening.top + 600 >= latest.box.y2);
    assert.ok(opening.left >= 0 && opening.top >= 0 && opening.left <= layout.width - 360 && opening.top <= layout.height - 600);
    assert.deepEqual(flowViewport(days, 4000, 4000), {left: 0, top: 0});
    // On a phone the frame hugs the rows of the cards it opens on, keeping the target's direct relations.
    const partsView = flowLayout(flowIntents, flowDecisions, {focus: 'intent-001'});
    const focusSpan = flowVisibleSpan(partsView, 0, 360);
    for (const id of ['intent-002', 'intent-003', 'intent-004']) assert.ok(focusSpan.bottom >= partsView.nodes.find(node => node.id === id).box.y2);
    const span = flowVisibleSpan(layout, opening.left, 360);
    assert.ok(span.top <= latest.box.y1 && span.bottom >= latest.box.y2);
    for (const node of layout.nodes) {
      const across = Math.min(node.box.x2, opening.left + 360) - Math.max(node.box.x1, opening.left);
      if (across >= layout.geometry.nodeW / 2) assert.ok(node.box.y1 >= span.top && node.box.y2 <= span.bottom);
    }
    // A longer route keeps its waypoints; each bend becomes a cubic whose tangents follow the legs.
    const blocked = [{x1: 100, y1: 40, x2: 300, y2: 260}];
    const bendy = flowCurve([[0, 0], [40, 0], [40, 300], [400, 300]], blocked);
    assert.deepEqual(bendy.segments.map(segment => (segment.c1 ? 'C' : 'L')), ['L', 'C', 'L', 'C', 'L']);
    assert.deepEqual([bendy.segments[1].c1[1], bendy.segments[1].c2[0], bendy.segments[3].c1[0], bendy.segments[3].c2[1]], [0, 40, 40, 300]);
    assert.deepEqual(bendy.segments[1].to, [40, 84]);
    // A bend shrinks rather than clip a card standing in its way.
    const squeezed = [...blocked, {x1: 44, y1: 200, x2: 120, y2: 280}];
    for (const [x, y] of flowSamples(flowCurve([[0, 0], [40, 0], [40, 300], [400, 300]], squeezed))) {
      for (const box of squeezed) assert.ok(!(x > box.x1 + 0.5 && x < box.x2 - 0.5 && y > box.y1 + 0.5 && y < box.y2 - 0.5));
    }
    assert.deepEqual(flowCurveEnd(flowCurve([[0, 0], [72, 0], [72, 80], [144, 80]])), {x: 144, y: 80, ux: 1, uy: 0, length: 72});

    // Hidden partners do not make an Intent standalone: intent-006 keeps its place in the flow.
    const hidden = flowLayout(flowIntents, flowDecisions, {hideEnded: true});
    assert.deepEqual(hidden.nodes.map(node => node.id).sort(), ['intent-001', 'intent-003', 'intent-004', 'intent-006', 'intent-007', 'intent-008']);
    assert.deepEqual(hidden.standalone, []);
    assert.ok(!hidden.relations.some(link => link.subject === 'intent-002' || link.target === 'intent-005'));
    const node001 = renderFlowSvg(focusedOn001 = flowLayout(flowIntents, flowDecisions, {focus: 'intent-001'}));
    assert.ok(node001.includes('aria-label="intent-001: Checkout revamp. 进行中. 2 个 Snap. 1 条决策. 组成部分 intent-002 (已完成). 组成部分 intent-003 (进行中). 衍生出 intent-004"'));
    const focused = flowLayout(flowIntents, flowDecisions, {focus: 'intent-003'});
    assert.deepEqual(focused.nodes.map(node => node.id).sort(), ['intent-001', 'intent-003', 'intent-007']);
    assert.equal(focused.band, null);
    assert.equal(focused.focus, 'intent-003');
    assert.equal(flowTarget(focused).id, 'intent-003');

    // Convergence and branching of succession: two Intents merge into one, which then splits.
    const merge = flowLayout([
      {id:'intent-011', status:'cancelled', created_at: at(11)},
      {id:'intent-012', status:'cancelled', created_at: at(12)},
      {id:'intent-013', status:'active', created_at: at(13), relations:[rel('succeeds', 'intent-011'), rel('succeeds', 'intent-012')]},
      {id:'intent-014', status:'active', created_at: at(14), relations:[rel('succeeds', 'intent-013')]},
      {id:'intent-015', status:'active', created_at: at(15), relations:[rel('succeeds', 'intent-013')]},
    ]);
    const merged = id => merge.nodes.find(node => node.id === id);
    assert.deepEqual(['intent-011', 'intent-013', 'intent-014'].map(id => merged(id).y), Array(3).fill(merged('intent-011').y));
    assert.ok(merged('intent-015').y > merged('intent-014').y && merged('intent-015').x > merged('intent-013').x);
    assert.ok(merged('intent-012').y > merged('intent-011').y);
    const intoMerge = merge.lines.find(line => line.target === 'intent-012');
    assert.equal(intoMerge.points.at(-1)[0], merge.nodes.find(node => node.id === 'intent-013').x);
    assert.equal(merge.lines.filter(line => line.kind === 'flow').length, 4);
    // A cycle across relation families still places every Intent.
    const cycle = flowLayout([
      {id:'intent-021', status:'active', created_at: at(21), relations:[rel('succeeds', 'intent-022')]},
      {id:'intent-022', status:'active', created_at: at(22), relations:[rel('part_of', 'intent-021')]},
    ]);
    assert.equal(cycle.nodes.length, 2);
    assert.deepEqual(flowLayout([{id:'intent-031', status:'active'}]).nodes, []);

    // Property check over seeded random histories that respect the relation rules: every Intent placed once,
    // no two cards overlap, parents and predecessors sit to the left, and no route or rendered curve
    // (sampled 12 times per cubic) enters a card or its pins.
    let seed = 7;
    const random = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
    const relationKinds = ['part_of', 'derived_from', 'succeeds', 'depends_on', 'conflicts_with'];
    const familyOf = kind => (kind === 'part_of' || kind === 'derived_from') ? 'parent' : kind;
    const inside = (box, x, y) => x > box.x1 + 0.5 && x < box.x2 - 0.5 && y > box.y1 + 0.5 && y < box.y2 - 0.5;
    const crosses = (box, [x1, y1], [x2, y2]) => {
      if (y1 === y2) return y1 > box.y1 + 0.5 && y1 < box.y2 - 0.5 && Math.max(x1, x2) > box.x1 + 0.5 && Math.min(x1, x2) < box.x2 - 0.5;
      if (x1 === x2) return x1 > box.x1 + 0.5 && x1 < box.x2 - 0.5 && Math.max(y1, y2) > box.y1 + 0.5 && Math.min(y1, y2) < box.y2 - 0.5;
      return true;
    };
    for (let round = 0; round < 120; round++) {
      const count = 4 + Math.floor(random() * 22);
      const graph = Array.from({length: count}, (_, index) => ({
        id: 'intent-' + String(index + 1).padStart(3, '0'),
        status: ['active', 'active', 'suspend', 'done', 'cancelled'][Math.floor(random() * 5)],
        created_at: at(Math.floor(index * 2 + random() * 2)), relations: [],
      }));
      const graphDecisions = graph.flatMap((intent, index) => Array.from({length: random() < 0.6 ? 0 : 1 + Math.floor(random() * 3)}, (_, number) => ({
        id: 'decision-' + index + '-' + number, status: random() < 0.3 ? 'deprecated' : 'active', created_at: intent.created_at,
        ...(random() < 0.8 ? {source_intent_id: intent.id} : {}),
      })));
      const edges = {parent: new Map(), succeeds: new Map(), depends_on: new Map()};
      const order = new Map();  // parent and succeeds together must stay acyclic for the column rule
      const reaches = (map, from, goal) => { const stack = [from], seen = new Set(); while (stack.length) { const id = stack.pop(); if (id === goal) return true; if (!seen.has(id)) { seen.add(id); stack.push(...(map.get(id) || [])); } } return false; };
      const add = (map, from, to) => map.set(from, [...(map.get(from) || []), to]);
      const pairs = new Set();
      for (let attempt = 0; attempt < count * 2; attempt++) {
        const subject = graph[Math.floor(random() * count)];
        const target = graph[Math.floor(random() * count)];
        const kind = relationKinds[Math.floor(random() * relationKinds.length)];
        const pair = [subject.id, target.id].sort().join();
        if (subject === target || pairs.has(pair)) continue;
        const family = familyOf(kind);
        if (family === 'parent' && subject.relations.some(entry => familyOf(entry.type) === 'parent')) continue;
        if (edges[family] && reaches(edges[family], target.id, subject.id)) continue;
        if ((family === 'parent' || family === 'succeeds') && reaches(order, target.id, subject.id)) continue;
        pairs.add(pair);
        subject.relations.push(rel(kind, target.id));
        if (edges[family]) add(edges[family], subject.id, target.id);
        if (family === 'parent' || family === 'succeeds') add(order, subject.id, target.id);
      }
      for (const options of [{}, {hideEnded: true}, {focus: graph[0].id}]) {
        const result = flowLayout(graph, graphDecisions, options);
        renderFlowSvg(result);
        const ids = [...result.nodes.map(node => node.id), ...result.standalone.map(intent => intent.id)];
        assert.equal(new Set(ids).size, ids.length, 'placed once');
        if (!options.hideEnded && !options.focus) assert.equal(ids.length, count, 'every Intent shown');
        for (const one of result.nodes) for (const other of result.nodes) {
          if (one !== other) assert.ok(one.box.x2 <= other.box.x1 || other.box.x2 <= one.box.x1 || one.box.y2 <= other.box.y1 || other.box.y2 <= one.box.y1, one.id + ' overlaps ' + other.id + ', round ' + round);
        }
        const cellOf = new Map(result.nodes.map(node => [node.id, node]));
        for (const link of result.relations) {
          if (link.type === 'part_of' || link.type === 'derived_from') {
            assert.ok(cellOf.get(link.subject).col > cellOf.get(link.target).col, link.subject + ' ' + link.type + ' ' + link.target + ' sits right, round ' + round);
          }
        }
        for (const line of result.lines) {
          const label = line.kind + ' ' + line.subject + '→' + line.target;
          for (let index = 1; index < line.points.length; index++) {
            for (const node of result.nodes) assert.ok(!crosses(node.box, line.points[index - 1], line.points[index]), label + ' route crosses ' + node.id + ', round ' + round);
          }
          for (const [x, y] of flowSamples(line.curve, 12)) {
            for (const node of result.nodes) assert.ok(!inside(node.box, x, y), label + ' curve clips ' + node.id + ', round ' + round);
          }
        }
      }
    }

    const lines = flowLines('Make checkout payments go through PaymentIntents only, everywhere, always', 164, 13, 2);
    assert.equal(lines.length, 2);
    assert.ok(lines[1].endsWith('…'));
    for (const line of lines) assert.ok(flowTextWidth(line, 13) <= 164);
    assert.deepEqual(flowLines('接入 Apple Pay', 164, 13, 2), ['接入 Apple Pay']);
    // Closing punctuation never starts a line.
    assert.deepEqual(flowLines('记录每次修改的作者和推送者，并在 IntHub 展示历史', 172, 13, 2), ['记录每次修改的作者和推送者，', '并在 IntHub 展示历史']);
    assert.ok(flowLines('超长的中文目标标题需要在两行之内被截断并且加上省略号才能放进节点里面去', 164, 13, 2)[1].endsWith('…'));

    const svg = renderFlowSvg(layout);
    assert.ok(!/\\sstyle=/.test(svg), 'no inline style attributes under the CSP');
    assert.equal((svg.match(/class="flow-node /g) || []).length, 8);
    assert.ok(svg.includes('role="button" tabindex="0" data-detail-type="intent" data-remote-id="p__intent-003"'));
    assert.ok(svg.includes('aria-label="intent-007: Launch to 10%. 进行中. 0 个 Snap. 依赖 intent-003 (被阻塞)"'));
    assert.ok(svg.includes('Server &lt;totals&gt;') && !svg.includes('Server <totals>'));
    assert.ok(svg.includes('>vs</text>'));
    assert.ok(svg.includes('class="flow-decision flow-pin is-deprecated" role="button" tabindex="0" data-detail-type="decision" data-remote-id="p__decision-002"'));
    assert.ok(svg.includes('class="flow-pin-stem"'));
    assert.ok(svg.includes('>项目</text>'));
    assert.ok(svg.includes('class="flow-decision flow-chip" role="button" tabindex="0" data-detail-type="decision" data-remote-id="p__decision-001"'));
    assert.ok(svg.includes('>Project rule</text>'));
    assert.ok(svg.includes('class="flow-line flow-depends flow-type-depends_on tone-attention"'));
    assert.ok(svg.indexOf('data-remote-id="p__decision-001"') < svg.indexOf('data-remote-id="p__intent-001"'));
    // Curves rather than corners, a status pill sized after drawing, no accent bar, a join on the parent's row.
    assert.ok(/class="flow-stroke" d="M[^"]*C/.test(svg));
    assert.ok(svg.includes('<g class="flow-pill" data-fit="25">'));
    assert.ok(!svg.includes('accent') && !svg.includes('flow-card-clip'));
    assert.ok(renderFlowSvg(joined).includes('<circle class="flow-join"'));
    assert.ok(svg.includes('<circle class="flow-terminal"'));

    state.currentProjectId = 'p';
    state.activeTab = 'flow';
    state._flow = null;
    state.overview = {project:{id:'p', name:'p'}, history:{project_id:'p', revision:'a'.repeat(64), last_synced_at: at(30)},
      active_intents: [{id:'intent-041', project_id:'p', remote_id:'p__intent-041', status:'active', what:'Lonely', created_at: at(1)}],
      other_intents: [], active_decisions: [], deprecated_decisions: [], recent_snaps: [], total_snaps: 0};
    renderFlowTab();
    assert.ok(el.detailContent.innerHTML.includes('flow-empty'));
    assert.ok(el.detailContent.innerHTML.includes('itt intent relate ID --depends-on OTHER'));
    assert.ok(el.detailContent.innerHTML.includes('itt decision create &quot;Rule&quot; --why &quot;Reason&quot; --from ID'));
    assert.ok(el.detailContent.innerHTML.includes('意图之间还没有关系。'));
    state.overview = {...state.overview, active_intents: flowIntents.filter(intent => intent.status === 'active'),
      other_intents: flowIntents.filter(intent => intent.status !== 'active'),
      active_decisions: flowDecisions.filter(decision => decision.status === 'active'), deprecated_decisions: flowDecisions.filter(decision => decision.status === 'deprecated')};
    renderFlowTab();
    let page = el.detailContent.innerHTML;
    assert.ok(page.includes('class="flow-canvas"') && page.includes('class="flow-legend"'));
    assert.ok(page.includes('data-flow-hide-ended aria-pressed="false"'));
    assert.ok(page.includes('data-flow-focus="intent-003"'));
    assert.ok(page.includes('6 条关系') && page.includes('2 条需要处理'));
    assert.ok(page.includes('class="flow-card status-done" data-detail-type="intent" data-remote-id="p__intent-009"'));
    assert.ok(page.includes('data-help="flow"'));
    state._flow.hideEnded = true;
    renderFlowTab();
    assert.ok(el.detailContent.innerHTML.includes('data-flow-hide-ended aria-pressed="true"'));
    assert.ok(!el.detailContent.innerHTML.includes('p__intent-009'));
    state._flow = {hideEnded: false, focus: 'intent-003', standalone: 30};
    renderFlowTab();
    page = el.detailContent.innerHTML;
    assert.ok(page.includes('聚焦于 intent-003'));
    assert.ok(page.includes('class="flow-node status-active is-focus"'));
    assert.ok(!page.includes('flow-standalone'));
    window.IntHubI18n.setLanguage('en');
    renderFlowTab();
    assert.ok(el.detailContent.innerHTML.includes('Focused on intent-003'));
    assert.ok(el.detailContent.innerHTML.includes('Depends on'));
    window.IntHubI18n.setLanguage('zh-CN');
    state._flow = null;

    // Brief: the parent line and attention badges, each paired with text, also in the copied Markdown.
    state.handoff = {
      intents: [flowIntents[2], flowIntents[6]].map(intent => ({...intent, latest_snap: {id:'snap-100', what:'Verified: ok. Boundary: web. Next: ship. Blocker: none.', created_at: at(20)}})),
      suspended_intents: [{...flowIntents[7], latest_snap: null}],
      active_decisions: [],
    };
    renderProjectSummary();
    const brief = el.detailContent.innerHTML;
    assert.ok(brief.includes('class="brief-relations"'));
    assert.ok(brief.includes('<span class="brief-relation-label">属于</span>'));
    assert.ok(brief.includes('data-detail-type="intent" data-remote-id="p__intent-001">Checkout revamp</button>'));
    assert.ok(brief.includes('被阻塞</span>\\n      <span class="brief-relation-label">依赖</span>'));
    // The prerequisite's side says it is blocking someone, not that it is blocked itself.
    assert.ok(brief.includes('阻塞中</span>\\n      <span class="brief-relation-label">被依赖</span>'));
    assert.ok(brief.includes('对立未解决') && brief.includes('对立 intent-006'));
    assert.ok(brief.includes('health-pill is-warning'));
    assert.equal(continuationHealth(state.handoff.intents).label, '1 个目标被阻塞');
    const markdown = briefMarkdown();
    assert.ok(markdown.includes('- **属于:** Checkout revamp (intent-001)'));
    assert.ok(markdown.includes('- **依赖:** Google Pay (intent-003) · 被阻塞'));
    assert.ok(markdown.includes('- Server <totals> (intent-008); 对立 Receipts v2 (intent-006) · 对立未解决'));

    // Intent sheet: both directions with readable labels and states; Decision sheet: its source.
    const intentSheet = buildIntentDetailHtml({project_id:'p', intent: flowIntents[0], snaps: [], decisions: []});
    assert.ok(intentSheet.includes('<h4 class="relation-group-label">组成部分</h4>'));
    assert.ok(intentSheet.includes('<h4 class="relation-group-label">衍生出</h4>'));
    assert.ok(intentSheet.includes('data-detail-type="intent" data-remote-id="p__intent-002"'));
    // Parts carry their own status already; their relation state only shows when it needs attention.
    assert.ok(!intentSheet.includes('rel-state'));
    const successorSheet = buildIntentDetailHtml({project_id:'p', intent: flowIntents[5], snaps: [], decisions: []});
    assert.ok(successorSheet.includes('<h4 class="relation-group-label">继承自</h4>'));
    assert.ok(successorSheet.includes('rel-state rel-settled') && successorSheet.includes('已交接'));
    const blockedSheet = buildIntentDetailHtml({project_id:'p', intent: flowIntents[6], snaps: [], decisions: []});
    assert.ok(blockedSheet.includes('rel-state rel-attention') && blockedSheet.includes('被阻塞'));
    assert.ok(intentSheet.includes('data-flow-focus="intent-001"'));
    assert.ok(intentSheet.includes('源自此意图的决策') && intentSheet.includes('data-remote-id="p__decision-002"'));
    const partSheet = buildIntentDetailHtml({project_id:'p', intent: flowIntents[2], snaps: [], decisions: []});
    assert.ok(partSheet.indexOf('>属于</h4>') < partSheet.indexOf('>被依赖</h4>'));
    assert.ok(buildIntentDetailHtml({project_id:'p', intent: flowIntents[8], snaps: [], decisions: []}).includes('与其他意图没有关系。'));
    const sourced = buildDecisionDetailHtml({project_id:'p', decision: flowDecisions[1], intents: []});
    assert.ok(sourced.includes('来源') && sourced.includes('data-detail-type="intent" data-remote-id="p__intent-001"'));
    const projectLevel = buildDecisionDetailHtml({project_id:'p', decision: flowDecisions[0], intents: []});
    assert.ok(projectLevel.includes('<span class="chip">项目级</span>'));

    // Timeline pages come from /snaps; Load more asks for the next offset; the filter goes to the server.
    const savedFetch = fetchJson;
    const requested = [];
    const responses = new Map();
    fetchJson = url => { requested.push(url); return responses.get(url) || Promise.reject(new Error('unexpected ' + url)); };
    const snapPage = (offset, count, total, more, intentId = 'intent-001') => ({project_id:'p', total, offset, limit:50, has_more: more,
      snaps: Array.from({length: count}, (_, index) => {
        const id = 'snap-' + String(500 - offset - index).padStart(3, '0');
        return {id, project_id:'p', remote_id:'p__' + id, intent_id: intentId, what:'Checkpoint ' + (offset + index), created_at: at(40)};
      })});
    state.activeTab = 'snaps';
    state._timeline = null;
    state.overview = {...state.overview, total_snaps: 75, active_intents: [{...flowIntents[0], snap_ids: Array(60).fill('snap-001'), latest_snap_id: 'snap-500'}, {...flowIntents[2], snap_ids: ['snap-101'], latest_snap_id: 'snap-101'}], other_intents: []};
    const first = '/api/v1/projects/p/snaps?offset=0&limit=50';
    responses.set(first, Promise.resolve(snapPage(0, 50, 75, true)));
    renderSnapsTab();
    assert.equal(requested.at(-1), first);
    assert.ok(el.detailContent.innerHTML.includes('view-loading'));
    await flush();
    assert.equal(state._timeline.snaps.length, 50);
    assert.ok(el.detailContent.innerHTML.includes('data-remote-id="p__snap-500"'));
    assert.ok(el.detailContent.innerHTML.includes('id="load-more-snaps"><svg') && el.detailContent.innerHTML.includes('<span class="button-label">加载更多（25）</span></button>'));
    assert.ok(el.detailContent.innerHTML.includes('75 个检查点'));
    responses.set('/api/v1/projects/p/snaps?offset=50&limit=50', Promise.resolve(snapPage(50, 25, 75, false)));
    await loadTimelinePage();
    assert.equal(requested.at(-1), '/api/v1/projects/p/snaps?offset=50&limit=50');
    assert.equal(state._timeline.snaps.length, 75);
    assert.ok(!el.detailContent.innerHTML.includes('load-more-snaps'));
    assert.ok(state._snapCache.has('p__snap-451'));
    // A slow page for an older filter cannot replace the newer one.
    let releaseSlow;
    responses.set(first + '&intent_id=intent-003', new Promise(resolve => { releaseSlow = resolve; }));
    resetTimeline('intent-003');
    renderSnapsTab();
    assert.equal(requested.at(-1), first + '&intent_id=intent-003');
    assert.ok(el.detailContent.innerHTML.includes('Google Pay'));
    responses.set(first, Promise.resolve(snapPage(0, 3, 3, false)));
    resetTimeline('');
    renderSnapsTab();
    await flush();
    releaseSlow(snapPage(0, 1, 1, false, 'intent-003'));
    await flush();
    assert.equal(state._timeline.intentId, '');
    assert.equal(state._timeline.snaps.length, 3);
    responses.set(first, Promise.reject(new Error('offline')));
    resetTimeline('');
    renderSnapsTab();
    await flush();
    assert.ok(el.detailContent.innerHTML.includes('data-retry-timeline'));

    // A latest Snap outside the overview window is fetched once and its label refreshed in place.
    state.activeTab = 'intents';
    state._snapCache = new Map();
    state._snapFailed = new Set();
    state._detailCache = new Map();
    state.overview = {...state.overview, recent_snaps: [], active_intents: [{...flowIntents[0], snap_ids:['snap-007'], latest_snap_id:'snap-007'}], other_intents: []};
    const label = document.getElementById('latest-snap-label');
    label.dataset.latestSnap = 'p__snap-007';
    const savedQuery = el.detailContent.querySelectorAll;
    el.detailContent.querySelectorAll = selector => selector === '[data-latest-snap]' ? [label] : [];
    responses.set('/api/v1/snaps/p__snap-007', Promise.resolve({remote_id:'p__snap-007', project_id:'p', id:'snap-007', snap:{id:'snap-007', intent_id:'intent-001', what:'old', created_at: new Date().toISOString()}, intent:{}}));
    renderIntentsTab();
    assert.ok(el.detailContent.innerHTML.includes('data-latest-snap="p__snap-007">检查点 snap-007</span>'));
    await flush();
    assert.equal(requested.filter(url => url === '/api/v1/snaps/p__snap-007').length, 1);
    assert.equal(label.textContent, '刚刚更新');
    assert.ok(state._detailCache.has('snap:p__snap-007'));
    renderIntentsTab();
    await flush();
    assert.equal(requested.filter(url => url === '/api/v1/snaps/p__snap-007').length, 1);
    assert.ok(el.detailContent.innerHTML.includes('data-latest-snap="p__snap-007">刚刚更新</span>'));
    el.detailContent.querySelectorAll = savedQuery;
    fetchJson = savedFetch;

    // Search: at most 50 matches, and the reader is told when there are more.
    const fifty = Array.from({length: 50}, (_, index) => ({object_type:'intent', remote_id:'p__intent-' + index, id:'intent-' + index, status:'active', what:'Pay ' + index, why:''}));
    assert.deepEqual(searchSummary({matches: fifty, total: 132, truncated: true}), {text: '显示前 50 条，共 132 条，请细化搜索', visible: true});
    assert.deepEqual(searchSummary({matches: fifty.slice(0, 2), total: 2, truncated: false}), {text: '2 个结果', visible: false});
    el.searchDialog.open = true;
    renderSearchResults({matches: fifty, total: 132, truncated: true, query: 'pay'});
    assert.equal(el.searchStatus.innerHTML, '显示前 50 条，共 132 条，请细化搜索');
    assert.equal(el.searchStatus.classList.contains('visually-hidden'), false);
    assert.equal(el.searchStatus.classList.contains('is-note'), true);
    window.IntHubI18n.setLanguage('en');
    assert.equal(searchSummary({matches: fifty, total: 132, truncated: true}).text, 'Showing 50 of 132 — refine the search');
    renderSearchResults({matches: fifty.slice(0, 3), total: 3, truncated: false, query: 'pay'});
    assert.equal(el.searchStatus.classList.contains('visually-hidden'), true);
    assert.equal(el.searchStatus.classList.contains('is-note'), false);
    window.IntHubI18n.setLanguage('zh-CN');
    el.searchDialog.open = false;
  })()`, context);
  console.log('Relation state parity, Flow layout and rendering, brief and sheet relations, paged timeline, Snap fallback and truncated search tests passed.');
}

module.exports = flowAndPagingCases;

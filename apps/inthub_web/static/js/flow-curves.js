function flowTarget(layout) {
  if (!layout.nodes.length) return null;
  if (layout.focus) return layout.nodes.find((node) => node.id === layout.focus) || null;
  const open = layout.nodes.filter((node) => !ENDED_STATUSES.has(node.intent.status));
  return [...(open.length ? open : layout.nodes)].sort((left, right) => byCreation(right.intent, left.intent))[0];
}

// Drop repeated points and merge straight runs, so every remaining point is a real bend.
function flowSimplify(points) {
  const list = [];
  for (const point of points) {
    const last = list.at(-1);
    if (last && last[0] === point[0] && last[1] === point[1]) continue;
    const before = list.at(-2);
    if (before && ((before[0] === last[0] && last[0] === point[0] && Math.sign(last[1] - before[1]) === Math.sign(point[1] - last[1]))
        || (before[1] === last[1] && last[1] === point[1] && Math.sign(last[0] - before[0]) === Math.sign(point[0] - last[0])))) {
      list.pop();
    }
    list.push(point);
  }
  return list;
}

// Turn an orthogonal route into tangent-continuous curves. A single step across a gap
// (horizontal, vertical, horizontal) becomes one S with horizontal tangents and control points
// half way across, when its box is clear. Otherwise each bend becomes a cubic reaching up to
// FLOW_BEND.across along a horizontal leg and FLOW_BEND.along along a vertical one, never more than
// half a shared leg; it shrinks until its control box, which holds the whole curve, clears every card.
function flowCurve(points, obstacles = []) {
  const list = flowSimplify(points);
  const start = list[0] || [0, 0];
  if (list.length < 2) return { start, segments: [] };
  const clear = (x1, y1, x2, y2) => !obstacles.some((box) => Math.min(x1, x2) < box.x2 - 0.5 && Math.max(x1, x2) > box.x1 + 0.5
    && Math.min(y1, y2) < box.y2 - 0.5 && Math.max(y1, y2) > box.y1 + 0.5);
  const [p0, p1, p2, p3] = list;
  if (list.length === 4 && p0[1] === p1[1] && p1[0] === p2[0] && p2[1] === p3[1]
      && Math.sign(p1[0] - p0[0]) === Math.sign(p3[0] - p2[0]) && clear(p0[0], p0[1], p3[0], p3[1])) {
    const half = (p3[0] - p0[0]) / 2;
    return { start, segments: [{ c1: [p0[0] + half, p0[1]], c2: [p3[0] - half, p3[1]], to: p3 }] };
  }
  const segments = [];
  let at = start;
  for (let index = 1; index < list.length - 1; index++) {
    const [px, py] = list[index - 1];
    const [x, y] = list[index];
    const [nx, ny] = list[index + 1];
    const inLength = Math.hypot(x - px, y - py);
    const outLength = Math.hypot(nx - x, ny - y);
    const uIn = [(x - px) / inLength, (y - py) / inLength];
    const uOut = [(nx - x) / outLength, (ny - y) / outLength];
    // The legs at either end keep a short straight piece where they meet a card.
    const reach = (length, unit, shared) => Math.max(0, Math.min(unit[1] ? FLOW_BEND.along : FLOW_BEND.across, shared ? length / 2 : length - 8));
    let rIn = reach(inLength, uIn, index > 1);
    let rOut = reach(outLength, uOut, index < list.length - 2);
    const box = () => {
      const ax = x - uIn[0] * rIn;
      const ay = y - uIn[1] * rIn;
      const bx = x + uOut[0] * rOut;
      const by = y + uOut[1] * rOut;
      return [Math.min(ax, bx, x), Math.min(ay, by, y), Math.max(ax, bx, x), Math.max(ay, by, y)];
    };
    for (let attempt = 0; attempt < 12 && !clear(...box()); attempt++) {
      rIn *= 0.7;
      rOut *= 0.7;
    }
    if (rIn < 1 || rOut < 1 || !clear(...box())) {
      segments.push({ to: [x, y] });
      at = [x, y];
      continue;
    }
    const a = [x - uIn[0] * rIn, y - uIn[1] * rIn];
    const b = [x + uOut[0] * rOut, y + uOut[1] * rOut];
    if (Math.hypot(a[0] - at[0], a[1] - at[1]) > 0.01) segments.push({ to: a });
    const k = FLOW_BEND.fullness;
    segments.push({ c1: [a[0] + uIn[0] * rIn * k, a[1] + uIn[1] * rIn * k], c2: [b[0] - uOut[0] * rOut * k, b[1] - uOut[1] * rOut * k], to: b });
    at = b;
  }
  const last = list.at(-1);
  if (Math.hypot(last[0] - at[0], last[1] - at[1]) > 0.01) segments.push({ to: last });
  return { start, segments };
}

function flowCubicPoint(from, c1, c2, to, t) {
  const s = 1 - t;
  return [0, 1].map((axis) => s * s * s * from[axis] + 3 * s * s * t * c1[axis] + 3 * s * t * t * c2[axis] + t * t * t * to[axis]);
}

// Points along a rendered curve: each cubic sampled `steps` times, each straight piece at its ends.
function flowSamples(curve, steps = 12) {
  const points = [curve.start];
  let from = curve.start;
  for (const segment of curve.segments) {
    if (segment.c1) for (let index = 1; index <= steps; index++) points.push(flowCubicPoint(from, segment.c1, segment.c2, segment.to, index / steps));
    else points.push(segment.to);
    from = segment.to;
  }
  return points;
}

function flowCurveEnd(curve) {
  const last = curve.segments.at(-1);
  const [x, y] = last.to;
  const from = last.c2 || curve.segments.at(-2)?.to || curve.start;
  const length = Math.hypot(x - from[0], y - from[1]);
  return { x, y, ux: length ? (x - from[0]) / length : 1, uy: length ? (y - from[1]) / length : 0, length };
}

// Stop the stroke short of an arrow tip so it never pokes through; a final cubic keeps its tangent.
function flowTrimCurve(curve, by) {
  const end = flowCurveEnd(curve);
  const last = curve.segments.at(-1);
  if (!last.c2 && end.length <= by) return curve;
  const trimmed = { ...last, to: [end.x - end.ux * by, end.y - end.uy * by] };
  if (last.c2) trimmed.c2 = [last.c2[0] - end.ux * by, last.c2[1] - end.uy * by];
  return { start: curve.start, segments: [...curve.segments.slice(0, -1), trimmed] };
}

function flowCurvePath(curve) {
  const n = flowNumber;
  return [`M${n(curve.start[0])} ${n(curve.start[1])}`, ...curve.segments.map((segment) => (segment.c1
    ? `C${n(segment.c1[0])} ${n(segment.c1[1])} ${n(segment.c2[0])} ${n(segment.c2[1])} ${n(segment.to[0])} ${n(segment.to[1])}`
    : `L${n(segment.to[0])} ${n(segment.to[1])}`))].join(" ");
}

// A small arrowhead along the end tangent.
function flowArrowHead(end, size) {
  const n = flowNumber;
  const bx = end.x - end.ux * size;
  const by = end.y - end.uy * size;
  const half = size * 0.5;
  return `M${n(end.x)} ${n(end.y)} L${n(bx - end.uy * half)} ${n(by + end.ux * half)} L${n(bx + end.uy * half)} ${n(by - end.ux * half)} Z`;
}

const FLOW_WIDE = /[\u1100-\u115f\u2e80-\ua4cf\uac00-\ud7a3\uf900-\ufaff\ufe30-\ufe4f\uff00-\uff60\uffe0-\uffe6]/;

// SVG text does not wrap, so titles are fitted by an estimate that errs on the narrow side
// (semibold by default; `scale` below 1 for regular text).
function flowTextWidth(text, size, scale = 1) {
  let units = 0;
  for (const char of String(text)) {
    units += FLOW_WIDE.test(char) ? 1 : char === " " ? 0.3 : /[ijlrtf.,:;'|!()[\]]/.test(char) ? 0.36 : /[A-Z0-9mwMW@#%&]/.test(char) ? 0.72 : 0.6;
  }
  return units * size * scale;
}

function flowTokens(text) {
  const tokens = [];
  let word = "";
  for (const char of String(text || "").replace(/\s+/g, " ").trim()) {
    if (char === " " || FLOW_WIDE.test(char)) {
      if (word) tokens.push(word);
      word = "";
      tokens.push(char);
    } else {
      word += char;
    }
  }
  if (word) tokens.push(word);
  return tokens;
}

function flowLines(text, maxWidth, size = 13, maxLines = 2, scale = 1) {
  const fits = (value) => flowTextWidth(value, size, scale) <= maxWidth;
  const tokens = flowTokens(text);
  const lines = [];
  let line = "";
  let overflow = false;
  const close = () => {
    lines.push(line.trimEnd());
    line = "";
    return lines.length >= maxLines;
  };
  for (let index = 0; index < tokens.length && !overflow; index++) {
    const token = tokens[index];
    if (fits(line + token)) {
      line += token;
    } else if (token === " ") {
      if (close()) overflow = index < tokens.length - 1;
    } else {
      if (line.trim() && close()) {
        overflow = true;
        break;
      }
      line = "";
      // A word wider than the whole line breaks between characters.
      for (const char of token) {
        if (line && !fits(line + char) && close()) {
          overflow = true;
          break;
        }
        line += char;
      }
    }
  }
  if (!overflow && line.trim()) {
    if (lines.length < maxLines) lines.push(line.trimEnd());
    else overflow = true;
  }
  if (overflow && lines.length) {
    let last = lines.at(-1);
    while (last && !fits(`${last}…`)) last = [...last].slice(0, -1).join("");
    lines[lines.length - 1] = `${last.trimEnd()}…`;
  }
  return lines;
}

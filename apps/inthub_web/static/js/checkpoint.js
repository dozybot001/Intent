/* ---- Checkpoint contract ---- */

function checkpointKey(label) {
  const normalized = String(label || "").trim().toLowerCase();
  if (/verified|已验证|验证结果|当前状态/.test(normalized)) return "verified";
  if (/boundary|边界/.test(normalized)) return "boundary";
  if (/^next|下一步/.test(normalized)) return "next";
  if (/blocker|阻塞/.test(normalized)) return "blocker";
  if (/constraint|约束|必须遵守/.test(normalized)) return "constraints";
  return null;
}

function extractCheckpointParts(value) {
  const source = String(value || "")
    .trim()
    .replace(/^(?:checkpoint|检查点)\s*[:：]\s*/i, "");
  const fields = {};
  const marker = /(?:^|[\n\r.。；;])\s*(Verified(?: state)?|Boundary|Current(?: work)? boundary|Next(?: step)?|Blockers?|Constraints?|已验证(?:到)?(?:的?状态)?|验证结果|当前状态|当前(?:真正的)?工作边界|当前边界|工作边界|边界|下一步|阻塞(?:项)?|必须遵守(?:的约束)?|约束)\s*[:：]\s*/giu;
  const matches = [];
  let match;
  while ((match = marker.exec(source)) !== null) {
    matches.push({
      key: checkpointKey(match[1]),
      markerStart: match.index,
      valueStart: marker.lastIndex,
    });
  }

  for (let index = 0; index < matches.length; index += 1) {
    const current = matches[index];
    const end = matches[index + 1]?.markerStart ?? source.length;
    const value = source
      .slice(current.valueStart, end)
      .replace(/^[\s.。；;]+|[\s.。；;]+$/g, "")
      .trim();
    if (current.key && value && !fields[current.key]) fields[current.key] = value;
  }

  const context = matches.length
    ? source.slice(0, matches[0].markerStart).replace(/[\s.。；;]+$/g, "").trim()
    : source;
  return { fields, context, structured: matches.length > 0 };
}

const CHECKPOINT_KEYS = ["verified", "boundary", "next", "blocker", "constraints"];

function recordedCheckpointFields(checkpoint) {
  if (!checkpoint || typeof checkpoint !== "object" || Array.isArray(checkpoint)) return null;
  const fields = {};
  for (const key of CHECKPOINT_KEYS) {
    const value = typeof checkpoint[key] === "string" ? checkpoint[key].trim() : "";
    if (value) fields[key] = value;
  }
  return Object.keys(fields).length ? fields : null;
}

// A recorded snap.checkpoint is the explicit contract: absent cells stay missing
// instead of being guessed from prose. Legacy Snaps fall back to text labels.
function snapCheckpointParts(snap) {
  const recorded = recordedCheckpointFields(snap?.checkpoint);
  if (recorded) return { fields: recorded, context: String(snap?.why || "").trim(), recorded: true };
  const what = extractCheckpointParts(snap?.what);
  const why = extractCheckpointParts(snap?.why);
  const context = [what.structured ? what.context : "", why.context]
    .filter(Boolean)
    .filter((value, index, values) => values.indexOf(value) === index)
    .join(" · ");
  return { fields: { ...why.fields, ...what.fields }, context, recorded: false };
}

function parseCheckpoint(snap) {
  const { fields, context } = snapCheckpointParts(snap);
  return {
    verified: fields.verified || snap?.what || "",
    boundary: fields.boundary || "",
    next: fields.next || "",
    blocker: fields.blocker || "",
    constraints: fields.constraints || "",
    context,
  };
}

function conciseSnapTitle(snap, maxLength = 86) {
  const { fields, recorded } = snapCheckpointParts(snap);
  // With a recorded checkpoint WHAT stays a clean milestone; legacy WHAT may hold the whole checkpoint.
  const source = String((recorded ? snap?.what || fields.verified : fields.verified || snap?.what) || "")
    .replace(/\s+/g, " ")
    .replace(/^(?:verified(?: state)?|已验证(?:到)?(?:的?状态)?|验证结果|当前状态)\s*[:：]\s*/i, "")
    .trim();
  if (!source) return t("{id} checkpoint", {id: snap?.id || "Snap"});

  const stop = source.search(/[。！？!?；;\n]/);
  const clause = stop >= 16 && stop <= maxLength + 18
    ? source.slice(0, stop + 1)
    : source;
  return truncate(clause, maxLength);
}

function isClearBlocker(value) {
  return /^(none|n\/a|not blocked|no blocker|无|没有|无阻塞|暂无)[.!。！]?$/.test(
    String(value || "").trim().toLowerCase(),
  );
}

function timelineState(checkpoint) {
  if (checkpoint.blocker && !isClearBlocker(checkpoint.blocker)) {
    return { key: "blocked", className: " is-blocked", label: t("Blocked") };
  }
  if (!checkpoint.next) {
    return { key: "incomplete", className: " is-incomplete", label: t("Next missing") };
  }
  if (checkpoint.blocker && isClearBlocker(checkpoint.blocker)) {
    return { key: "ready", className: " is-ready", label: t("Unblocked") };
  }
  return { key: "checkpoint", className: "", label: t("Checkpoint") };
}

function continuationHealth(intents) {
  if (!intents.length) return { ready: false, label: t("No active objective") };
  const checkpoints = intents.map(intent => snapCheckpointParts(intent.latest_snap).fields);
  const incomplete = checkpoints.filter(checkpoint => !checkpoint.verified || !checkpoint.boundary || !checkpoint.next || !checkpoint.blocker).length;
  if (incomplete) return { ready: false, label: plural(incomplete, "{count} incomplete checkpoint", "{count} incomplete checkpoints") };
  const blocked = checkpoints.filter((checkpoint, index) => !isClearBlocker(checkpoint.blocker) || dependencyBlocked(intents[index])).length;
  if (blocked) return { ready: false, label: plural(blocked, "{count} blocked objective", "{count} blocked objectives") };
  return { ready: true, label: t("Ready to continue") };
}

function checkpointCell(key, label, value) {
  const missing = !value;
  const clearBlocker = key === "blocker" && isClearBlocker(value);
  const blocked = key === "blocker" && !missing && !clearBlocker;
  const iconName = key === "blocker" ? (clearBlocker ? "clear" : "blocker") : key;
  return `
    <section class="checkpoint checkpoint-${esc(key)}${missing ? " is-missing" : ""}${clearBlocker ? " is-clear" : ""}${blocked ? " is-blocked" : ""}">
      <h4 class="checkpoint-label">${icon(iconName)}${esc(label)}</h4>
      <p class="checkpoint-value">${esc(missing ? t("Not explicitly recorded in the latest Snap.") : value)}</p>
    </section>`;
}

function checkpointGrid(checkpoint, order = ["next", "blocker", "boundary", "verified"], className = "") {
  const labels = { verified: t("Verified"), boundary: t("Boundary"), next: t("Next"), blocker: t("Blocker") };
  return `<div class="checkpoint-grid${className}">${order.map((key) => checkpointCell(key, labels[key], checkpoint[key])).join("")}</div>`;
}

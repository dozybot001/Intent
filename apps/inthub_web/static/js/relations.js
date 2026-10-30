/* ---- Relations between Intents ----
   Mirrors src/intent_cli/relations.py. Relations live on the Intent that declares
   them (the subject B) and point at a target A. Their states are never stored:
   they follow from the statuses of the two Intents. */

const RELATION_TYPES = ["part_of", "derived_from", "succeeds", "depends_on", "conflicts_with"];
const PARENT_RELATIONS = new Set(["part_of", "derived_from"]);
const ENDED_STATUSES = new Set(["done", "cancelled"]);
const ATTENTION_STATES = new Set(["orphaned", "pending", "blocked", "broken", "unresolved"]);

function activeRelationEntries(intent) {
  const entries = Array.isArray(intent?.relations) ? intent.relations : [];
  return entries.filter((entry) => entry && typeof entry === "object" && !("removed_at" in entry)
    && RELATION_TYPES.includes(entry.type) && typeof entry.intent === "string");
}

function relationState(kind, subject, target) {
  const subjectStatus = subject?.status;
  const targetStatus = target?.status;
  if (kind === "part_of") {
    if (subjectStatus === "done") return "done";
    if (subjectStatus === "cancelled") return "dropped";
    return ENDED_STATUSES.has(targetStatus) ? "orphaned" : "in_progress";
  }
  if (kind === "succeeds") return ENDED_STATUSES.has(targetStatus) ? "handed_over" : "pending";
  if (kind === "depends_on") return targetStatus === "done" ? "satisfied" : targetStatus === "cancelled" ? "broken" : "blocked";
  if (kind === "conflicts_with") return ENDED_STATUSES.has(subjectStatus) || ENDED_STATUSES.has(targetStatus) ? "resolved" : "unresolved";
  return null;
}

function intentMap(intents) {
  if (intents instanceof Map) return intents;
  const map = new Map();
  for (const intent of intents || []) if (intent?.id && !map.has(intent.id)) map.set(intent.id, intent);
  return map;
}

// Every active relation whose two Intents exist, with its derived state.
function relationLinks(intents) {
  const byId = intentMap(intents);
  const links = [];
  for (const [id, subject] of byId) {
    for (const entry of activeRelationEntries(subject)) {
      const target = byId.get(entry.intent);
      if (!target || entry.intent === id) continue;
      links.push({ type: entry.type, subject: id, target: entry.intent, state: relationState(entry.type, subject, target) });
    }
  }
  return links;
}

// Relations touching one Intent, both directions: outgoing first (where it comes from), then by type.
function relationView(intents, intentId) {
  const byId = intentMap(intents);
  const rows = [];
  for (const link of relationLinks(byId)) {
    if (link.subject !== intentId && link.target !== intentId) continue;
    const outgoing = link.subject === intentId;
    rows.push({ type: link.type, direction: outgoing ? "out" : "in", intent: byId.get(outgoing ? link.target : link.subject), state: link.state });
  }
  return rows.sort((left, right) => (left.direction !== "out") - (right.direction !== "out")
    || RELATION_TYPES.indexOf(left.type) - RELATION_TYPES.indexOf(right.type)
    || String(left.intent.id).localeCompare(String(right.intent.id)));
}

function relationLabel(type, direction) {
  const labels = {
    part_of: [t("Part of"), t("Parts")],
    derived_from: [t("Derived from"), t("Spawned")],
    succeeds: [t("Succeeds"), t("Succeeded by")],
    depends_on: [t("Depends on"), t("Needed by")],
    conflicts_with: [t("Conflicts with"), t("Conflicts with")],
  }[type];
  return labels ? labels[direction === "out" ? 0 : 1] : String(type || "");
}

// Read from one side: the prerequisite of an unmet dependency is "blocking", the dependent "blocked".
function relationStateLabel(key, row = null) {
  if (key === "blocked" && row?.type === "depends_on" && row.direction === "in") return t("Blocking");
  return {
    in_progress: t("In progress"), done: t("Completed"), dropped: t("Dropped"), orphaned: t("Parent ended"),
    pending: t("Handover pending"), handed_over: t("Handed over"),
    blocked: t("Blocked"), satisfied: t("Satisfied"), broken: t("Broken dependency"),
    unresolved: t("Unresolved conflict"), resolved: t("Resolved"),
  }[key] || "";
}

function relationTone(key) {
  if (key === "broken") return "danger";
  if (ATTENTION_STATES.has(key)) return "attention";
  if (["satisfied", "handed_over", "resolved", "done"].includes(key)) return "settled";
  return "neutral";
}

// A relation state is never shown by colour alone: the pill always carries its label.
function relationBadge(key, row = null) {
  if (!key) return "";
  return `<span class="status-pill rel-state rel-${relationTone(key)}"><span class="status-dot" aria-hidden="true"></span>${esc(relationStateLabel(key, row))}</span>`;
}

const intentMaps = new WeakMap();

function overviewIntentMap() {
  const overview = state.overview;
  if (!overview) return new Map();
  if (!intentMaps.has(overview)) intentMaps.set(overview, intentMap(overviewIntents()));
  return intentMaps.get(overview);
}

// Relations of one Intent against the whole project; a fresher copy of the Intent (handoff, detail) wins.
function intentRelations(intent) {
  if (!intent?.id) return [];
  const byId = new Map(overviewIntentMap());
  byId.set(intent.id, { ...(byId.get(intent.id) || {}), ...intent });
  return relationView(byId, intent.id);
}

function relationContext(intent) {
  const rows = intentRelations(intent);
  const parent = rows.find((row) => row.direction === "out" && PARENT_RELATIONS.has(row.type)) || null;
  return { rows, parent, attention: rows.filter((row) => row !== parent && ATTENTION_STATES.has(row.state)) };
}

// An open Intent cannot proceed while a dependency is unmet or was cancelled.
function dependencyBlocked(intent) {
  return intentRelations(intent).some((row) => row.type === "depends_on" && row.direction === "out" && ["blocked", "broken"].includes(row.state));
}

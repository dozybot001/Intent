"""Relations between Intents: where a goal comes from and what constrains it.

Relations are stored on the Intent that declares them, in its optional
``relations`` list. Entries are append-only; withdrawing one only adds
``removed_at``. Their states are never stored: they follow from the statuses
of the two Intents. See docs/EN/intent-flow.md.
"""

RELATION_TYPES = ("part_of", "derived_from", "succeeds", "depends_on", "conflicts_with")
PARENT_TYPES = frozenset({"part_of", "derived_from"})
# Each family must stay acyclic; conflicts_with is symmetric and exempt.
ACYCLIC_FAMILIES = (PARENT_TYPES, frozenset({"succeeds"}), frozenset({"depends_on"}))
ENDED = frozenset({"done", "cancelled"})
# Relation states that ask someone to act, as seen from either Intent.
ATTENTION_STATES = frozenset({"orphaned", "pending", "blocked", "broken", "unresolved"})


def words(kind):
    return kind.replace("_", " ")


def active_entries(intent):
    return [entry for entry in intent.get("relations") or [] if "removed_at" not in entry]


def active_relations(intents):
    """Yield (subject_id, type, target_id) for every relation that is not withdrawn."""
    for subject_id, intent in intents.items():
        for entry in active_entries(intent):
            yield subject_id, entry["type"], entry["intent"]


def state(kind, subject, target):
    """Derive a relation's state from the two statuses; None when it has none."""
    subject_status, target_status = subject.get("status"), target.get("status")
    if kind == "part_of":
        if subject_status == "done":
            return "done"
        if subject_status == "cancelled":
            return "dropped"
        return "orphaned" if target_status in ENDED else "in_progress"
    if kind == "succeeds":
        return "handed_over" if target_status in ENDED else "pending"
    if kind == "depends_on":
        return {"done": "satisfied", "cancelled": "broken"}.get(target_status, "blocked")
    if kind == "conflicts_with":
        return "resolved" if {subject_status, target_status} & ENDED else "unresolved"
    return None


def view(intents, intent_id):
    """Active relations touching one Intent, in both directions, with their states."""
    rows = []
    for subject_id, kind, target_id in active_relations(intents):
        if intent_id not in (subject_id, target_id):
            continue
        subject, target = intents.get(subject_id), intents.get(target_id)
        if subject is None or target is None:
            continue
        outgoing = subject_id == intent_id
        other = target if outgoing else subject
        rows.append({
            "type": kind,
            "direction": "out" if outgoing else "in",
            "intent": {"id": other["id"], "what": other.get("what"), "status": other.get("status")},
            "state": state(kind, subject, target),
        })
    # Outgoing first (where this goal comes from), each side in type order.
    rows.sort(key=lambda row: (row["direction"] != "out", RELATION_TYPES.index(row["type"])))
    return rows


def _reaches(edges, start, goal):
    stack, seen = [start], set()
    while stack:
        node = stack.pop()
        if node == goal:
            return True
        if node not in seen:
            seen.add(node)
            stack.extend(edges.get(node, ()))
    return False


def _edges(intents, family):
    edges = {}
    for subject_id, kind, target_id in active_relations(intents):
        if kind in family:
            edges.setdefault(subject_id, []).append(target_id)
    return edges


def violation(intents, subject_id, kind, target_id):
    """Return (code, message) if adding this relation would break a rule, else None."""
    if kind not in RELATION_TYPES:
        return "INVALID_INPUT", f"Unknown relation type {kind!r}."
    if subject_id == target_id:
        return "INVALID_RELATION", "An intent cannot relate to itself."
    if target_id not in intents:
        return "OBJECT_NOT_FOUND", f"Intent {target_id} not found."
    pair = {subject_id, target_id}
    for existing_subject, existing_kind, existing_target in active_relations(intents):
        if {existing_subject, existing_target} == pair:
            return "INVALID_RELATION", (
                f"{subject_id} and {target_id} are already related ({existing_subject} {words(existing_kind)} "
                f"{existing_target}); withdraw it first with: itt intent unrelate {subject_id} {target_id}")
    if kind in PARENT_TYPES:
        if any(entry["type"] in PARENT_TYPES for entry in active_entries(intents.get(subject_id, {}))):
            return "INVALID_RELATION", f"{subject_id} already has a parent intent."
        if kind == "part_of" and intents[target_id].get("status") in ENDED:
            return "INVALID_RELATION", f"{target_id} has ended and cannot gain new parts."
    family = next((family for family in ACYCLIC_FAMILIES if kind in family), None)
    if family and _reaches(_edges(intents, family), target_id, subject_id):
        return "INVALID_RELATION", f"{subject_id} {words(kind)} {target_id} would create a cycle."
    return None


def graph_issues(intents):
    """Rule violations in a stored graph, as (intent_id, message) pairs."""
    issues, pairs, parents = [], {}, {}
    for subject_id, kind, target_id in active_relations(intents):
        if target_id not in intents:
            continue  # reported as a missing reference by the caller
        if subject_id == target_id:
            issues.append((subject_id, "Relates to itself."))
            continue
        key = frozenset((subject_id, target_id))
        if key in pairs:
            issues.append((subject_id, f"Has more than one active relation with {target_id}."))
        pairs[key] = kind
        if kind in PARENT_TYPES:
            if subject_id in parents:
                issues.append((subject_id, "Has more than one parent intent."))
            parents[subject_id] = target_id
    for family in ACYCLIC_FAMILIES:
        edges = _edges(intents, family)
        for subject_id, targets in edges.items():
            if any(target != subject_id and _reaches(edges, target, subject_id) for target in targets):
                issues.append((subject_id, f"Is in a cycle of {' / '.join(words(kind) for kind in sorted(family))} relations."))
    return issues

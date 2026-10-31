"""What one side of a sync lacks: revisions past what it holds, with their new trees and object versions."""

from intent_cli.repo import TREE_DEPTH


def reachable(tips, read_revision, stop=()):
    """{digest: revision} reachable from tips, going no further than stop."""
    revisions, pending = {}, list(tips)
    while pending:
        digest = pending.pop()
        if digest not in revisions and digest not in stop:
            revisions[digest] = read_revision(digest)
            pending.extend(revisions[digest]["parents"])
    return revisions


def _walk_tree(tree, read_node, known, found, depth=0):
    # A node is checked for the level it sits at, so the same digest counts once per level.
    if (tree, depth) in known:
        return
    known.add((tree, depth))
    found.append(("tree", tree))
    for child in read_node(tree, depth).values():
        if depth < TREE_DEPTH:
            _walk_tree(child, read_node, known, found, depth + 1)
        elif child not in known:
            known.add(child)
            found.append(("object", child))


def plan(want, have, read_revision, read_node):
    """[(kind, digest)] reachable from want and not from have, each once.

    The other side holds the trees just behind the new revisions, so only the paths
    that changed since then are listed. It may be sent a node it already has elsewhere.
    """
    held = reachable(have, read_revision)
    new = reachable(want, read_revision, stop=held)
    known = set()
    for revision in new.values():
        for parent in revision["parents"]:
            if parent in held:
                _walk_tree(held[parent]["tree"], read_node, known, [])
    found = [("revision", digest) for digest in new]
    for revision in new.values():
        _walk_tree(revision["tree"], read_node, known, found)
    return list(dict.fromkeys(found))

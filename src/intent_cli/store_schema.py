"""The shape of stored objects: IDs, required fields and how each one is validated."""

import re
from intent_cli import relations as relation_rules
from intent_cli.identity import COMMIT
from intent_cli.store_errors import InvalidObjectIdError, StoredObjectIntegrityError, StoredObjectSchemaError


INTENT_DIR = ".intent"


SUBDIRS = {"intent": "intents", "snap": "snaps", "decision": "decisions"}


VALID_STATUSES = {
    "intent": {"active", "suspend", "done", "cancelled"},
    "decision": {"active", "deprecated"},
}


OBJECT_ID_PATTERNS = {
    object_type: re.compile(rf"{object_type}-[0-9]+", re.ASCII)
    for object_type in SUBDIRS
}


def validate_object_id(object_type, obj_id):
    """Validate and return a type-specific, path-safe local object ID."""
    pattern = OBJECT_ID_PATTERNS.get(object_type)
    if (
        pattern is None
        or not isinstance(obj_id, str)
        or pattern.fullmatch(obj_id) is None
    ):
        raise InvalidObjectIdError(object_type, obj_id)
    return obj_id


def _validate_stored_object_id(obj, path, expected_id):
    """Verify that object data agrees with its storage filename."""
    if not isinstance(obj, dict):
        raise StoredObjectSchemaError(path, "top-level JSON must be an object")
    if "id" not in obj:
        raise StoredObjectSchemaError(
            path, "missing required field 'id'", field="id",
        )
    if not isinstance(obj["id"], str):
        raise StoredObjectSchemaError(
            path,
            f"field 'id' must be a string, got {type(obj['id']).__name__}",
            field="id",
        )
    if obj["id"] != expected_id:
        raise StoredObjectIntegrityError(
            path,
            f"field 'id' is {obj['id']!r}, expected {expected_id!r}",
        )
    return obj


REQUIRED_STRING_FIELDS = {
    "intent": ("id", "object", "created_at", "what", "why", "origin", "status"),
    "snap": ("id", "object", "created_at", "what", "why", "origin", "intent_id"),
    "decision": (
        "id", "object", "created_at", "what", "why", "origin", "status",
    ),
}


RELATION_FIELDS = {
    "intent": {"snap_ids": "snap", "decision_ids": "decision"},
    "snap": {},
    "decision": {"intent_ids": "intent"},
}


# Optional structured continuation checkpoint on a Snap. Keys are exact and
# lowercase so every reader shows the same cells; an absent key means the
# author did not record that cell.
CHECKPOINT_FIELDS = ("verified", "boundary", "next", "blocker", "constraints")


CHECKPOINT_FIELD_MAX_CHARS = 2000


def _validate_checkpoint(checkpoint, path):
    """Validate the optional Snap checkpoint display contract."""
    if not isinstance(checkpoint, dict) or not checkpoint:
        raise StoredObjectSchemaError(
            path,
            "field 'checkpoint' must be a non-empty object",
            field="checkpoint",
        )
    for key, value in checkpoint.items():
        if key not in CHECKPOINT_FIELDS:
            raise StoredObjectSchemaError(
                path,
                f"field 'checkpoint' has unsupported key {key!r}; "
                f"allowed keys: {', '.join(CHECKPOINT_FIELDS)}",
                field="checkpoint",
            )
        if not isinstance(value, str) or not value.strip():
            raise StoredObjectSchemaError(
                path,
                f"field 'checkpoint.{key}' must be a non-blank string",
                field=f"checkpoint.{key}",
            )
        if len(value) > CHECKPOINT_FIELD_MAX_CHARS:
            raise StoredObjectSchemaError(
                path,
                f"field 'checkpoint.{key}' exceeds "
                f"{CHECKPOINT_FIELD_MAX_CHARS} characters",
                field=f"checkpoint.{key}",
            )


def _validate_author(author, path):
    """Validate the optional author, recorded like a Git identity (see identity.py)."""
    if (not isinstance(author, dict) or not author
            or not all(isinstance(author.get(key, ""), str) for key in ("name", "email"))):
        raise StoredObjectSchemaError(path, "field 'author' must be an object with string name and email", field="author")


def _validate_git(git, path):
    """Validate the optional commit a Snap was recorded on."""
    if (not isinstance(git, dict) or not isinstance(git.get("commit"), str) or not COMMIT.fullmatch(git["commit"])
            or not isinstance(git.get("dirty", False), bool)):
        raise StoredObjectSchemaError(path, "field 'git' must hold a commit hash and an optional dirty flag", field="git")


def _validate_relations(entries, path):
    """Validate the optional Intent relations list (see relations.py)."""
    if not isinstance(entries, list):
        raise StoredObjectSchemaError(path, "field 'relations' must be a list", field="relations")
    for index, entry in enumerate(entries):
        field = f"relations[{index}]"
        if not isinstance(entry, dict) or not all(isinstance(entry.get(key), str) for key in ("type", "intent", "created_at")):
            raise StoredObjectSchemaError(
                path, f"field '{field}' needs string type, intent and created_at", field=field,
            )
        if entry["type"] not in relation_rules.RELATION_TYPES:
            raise StoredObjectSchemaError(
                path, f"field '{field}.type' has unknown relation type {entry['type']!r}", field=f"{field}.type",
            )
        try:
            validate_object_id("intent", entry["intent"])
        except InvalidObjectIdError as exc:
            raise StoredObjectSchemaError(
                path, f"field '{field}.intent' is not a valid intent ID", field=f"{field}.intent",
            ) from exc
        if "removed_at" in entry and not isinstance(entry["removed_at"], str):
            raise StoredObjectSchemaError(
                path, f"field '{field}.removed_at' must be a string", field=f"{field}.removed_at",
            )


def _validate_object_schema(
    obj,
    path,
    object_type,
    expected_id,
    *,
    require_object_type=False,
):
    """Validate required object fields and relationship field types."""
    _validate_stored_object_id(obj, path, expected_id)

    for field in REQUIRED_STRING_FIELDS[object_type]:
        if field not in obj:
            raise StoredObjectSchemaError(
                path, f"missing required field {field!r}", field=field,
            )
        if not isinstance(obj[field], str):
            raise StoredObjectSchemaError(
                path,
                f"field {field!r} must be a string, got {type(obj[field]).__name__}",
                field=field,
            )

    if require_object_type and obj["object"] != object_type:
        raise StoredObjectSchemaError(
            path,
            f"field 'object' must be {object_type!r}, got {obj['object']!r}",
            field="object",
        )

    if "reason" in obj and not isinstance(obj["reason"], str):
        raise StoredObjectSchemaError(
            path,
            f"field 'reason' must be a string, got {type(obj['reason']).__name__}",
            field="reason",
        )

    for field, target_type in RELATION_FIELDS[object_type].items():
        if field not in obj:
            raise StoredObjectSchemaError(
                path, f"missing required field {field!r}", field=field,
            )
        values = obj[field]
        if not isinstance(values, list):
            raise StoredObjectSchemaError(
                path,
                f"field {field!r} must be a list of {target_type} IDs",
                field=field,
            )
        for index, value in enumerate(values):
            try:
                validate_object_id(target_type, value)
            except InvalidObjectIdError as exc:
                raise StoredObjectSchemaError(
                    path,
                    f"field {field!r} item {index} is not a valid {target_type} ID",
                    field=field,
                ) from exc

    if object_type == "snap":
        try:
            validate_object_id("intent", obj["intent_id"])
        except InvalidObjectIdError as exc:
            raise StoredObjectSchemaError(
                path,
                "field 'intent_id' is not a valid intent ID",
                field="intent_id",
            ) from exc
        if "checkpoint" in obj:
            _validate_checkpoint(obj["checkpoint"], path)
        if "git" in obj:
            _validate_git(obj["git"], path)

    if "author" in obj:
        _validate_author(obj["author"], path)

    if object_type == "intent" and "relations" in obj:
        _validate_relations(obj["relations"], path)

    if object_type == "decision" and "source_intent_id" in obj:
        try:
            validate_object_id("intent", obj["source_intent_id"])
        except InvalidObjectIdError as exc:
            raise StoredObjectSchemaError(
                path,
                "field 'source_intent_id' is not a valid intent ID",
                field="source_intent_id",
            ) from exc

    return obj

from __future__ import annotations

SCHEMA_VERSION = "0.2"

EXIT_SUCCESS = 0
EXIT_GENERAL_FAILURE = 1
EXIT_INVALID_INPUT = 2
EXIT_STATE_CONFLICT = 3
EXIT_OBJECT_NOT_FOUND = 4

DIR_NAMES = {
    "intent": "intents",
    "snap": "snaps",
}

ID_PREFIXES = {
    "intent": "intent",
    "snap": "snap",
}

SCHEMA_VERSION = "0.1"

EXIT_SUCCESS = 0
EXIT_GENERAL_FAILURE = 1
EXIT_INVALID_INPUT = 2
EXIT_STATE_CONFLICT = 3
EXIT_OBJECT_NOT_FOUND = 4

DIR_NAMES = {
    "intent": "intents",
    "checkpoint": "checkpoints",
    "adoption": "adoptions",
    "run": "runs",
    "decision": "decisions",
}

ID_PREFIXES = {
    "intent": "intent",
    "checkpoint": "cp",
    "adoption": "adopt",
    "run": "run",
    "decision": "decision",
}

OBJECT_LABELS = {
    "intent": "Intent",
    "checkpoint": "Checkpoint",
    "adoption": "Adoption",
    "run": "Run",
    "decision": "Decision",
}

OBJECT_PLURALS = {
    "intent": "Intents",
    "checkpoint": "Checkpoints",
    "adoption": "Adoptions",
    "run": "Runs",
    "decision": "Decisions",
}

OBJECT_SELECTORS = {
    "intent": {"@active"},
    "checkpoint": {"@current"},
    "adoption": {"@latest"},
    "run": {"@active"},
    "decision": {"@latest"},
}

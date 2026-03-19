"""Compatibility exports for the split IntHub API storage modules."""

from apps.inthub_api.common import (
    APIError,
    make_remote_object_id,
    split_remote_object_id,
)
from apps.inthub_api.db import connect, init_db
from apps.inthub_api.ingest import link_project, store_sync_batch
from apps.inthub_api.queries import (
    get_decision_detail,
    get_intent_detail,
    project_handoff,
    project_overview,
    search_project,
)

__all__ = [
    "APIError",
    "connect",
    "get_decision_detail",
    "get_intent_detail",
    "init_db",
    "link_project",
    "make_remote_object_id",
    "project_handoff",
    "project_overview",
    "search_project",
    "split_remote_object_id",
    "store_sync_batch",
]

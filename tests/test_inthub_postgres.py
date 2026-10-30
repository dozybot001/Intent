import os
import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from apps.inthub_api.auth import (
    account_for_access_token,
    account_for_session,
    create_account_access_token,
    create_web_session,
    upsert_github_account,
)
from apps.inthub_api.common import APIError
from apps.inthub_api.db import connect
from apps.inthub_api.history import link_history, push_history, read_history
from intent_cli.hub.versions import revision_id
from apps.inthub_api.projects import delete_project, export_project, rename_project
from apps.inthub_api.queries import list_projects, project_overview
from apps.inthub_api.tenon import (
    account_for_identity, account_for_session as tenon_account_for_session,
    bind_existing_account, consume_attempt, create_attempt, create_session,
)
import time
from uuid import uuid4
from apps.inthub_api.product_deletion import delete_product_account
from apps.inthub_api.tenon import ISSUER


POSTGRES_URL = os.getenv("INTHUB_TEST_POSTGRES_URL")


@pytest.mark.skipif(not POSTGRES_URL, reason="INTHUB_TEST_POSTGRES_URL is not configured")
def test_postgresql_product_deletion_receipt_and_subject_lock():
    subject = "deletion-" + os.urandom(6).hex()
    info = {"sub": subject, "name": "Integration", "platform_role": "user", "expires_at": time.time() + 60}
    account = account_for_identity(POSTGRES_URL, info)
    session = create_session(POSTGRES_URL, account["id"], info)
    pat = create_account_access_token(POSTGRES_URL, account["id"])
    project = link_history(POSTGRES_URL, subject, account["id"])
    proof = {"issuer": ISSUER, "sub": subject, "productId": "inthub", "operationId": str(uuid4())}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: delete_product_account(POSTGRES_URL, proof), range(2)))
    assert results[0] == results[1] == {"operationId": proof["operationId"], "status": "completed", "deleted": True}
    assert tenon_account_for_session(POSTGRES_URL, session["token"]) is None
    assert account_for_access_token(POSTGRES_URL, pat["token"]) is None
    with connect(POSTGRES_URL) as conn:
        assert conn.execute("SELECT id FROM projects WHERE id = ?", (project["project_id"],)).fetchone() is None
        assert conn.execute("SELECT count(*) AS n FROM product_deletion_receipts WHERE operation_id = ?", (proof["operationId"],)).fetchone()["n"] == 1
    attempt = create_attempt(POSTGRES_URL)
    started = consume_attempt(POSTGRES_URL, attempt["state"])["started_at"]
    replacement = account_for_identity(POSTGRES_URL, info, request_started_at=started)
    assert replacement["id"] != account["id"]
    assert delete_product_account(POSTGRES_URL, {**proof, "completed": True}) == results[0]
    assert account_for_identity(POSTGRES_URL, info, request_started_at=started)["id"] == replacement["id"]


@pytest.mark.skipif(not POSTGRES_URL, reason="INTHUB_TEST_POSTGRES_URL is not configured")
def test_postgresql_shared_history_serializes_concurrent_pushes():
    name = "shared-" + os.urandom(6).hex()
    account = upsert_github_account(POSTGRES_URL, {"id": name, "login": name})
    with ThreadPoolExecutor(max_workers=2) as pool:
        links = list(pool.map(lambda _: link_history(POSTGRES_URL, name, account["id"]), range(2)))
    assert links[0] == links[1]
    pid = links[0]["project_id"]
    snapshot = {"intents": [{"id": "intent-001", "object": "intent", "status": "active",
                            "created_at": "2026-10-04T00:00:00+00:00", "origin": "test",
                            "what": "shared", "why": "concurrency", "snap_ids": [], "decision_ids": []}],
                "snaps": [], "decisions": []}
    first = {"project_name": name, "project_id": pid, "parent": None,
             "revision": revision_id(None, snapshot), "snapshot": snapshot}
    assert push_history(POSTGRES_URL, first, account["id"])["changed"]
    assert push_history(POSTGRES_URL, first, account["id"])["changed"] is False
    barrier = threading.Barrier(2)

    def push(label):
        following = copy.deepcopy(snapshot)
        following["snaps"].append({"id": "snap-001", "object": "snap", "what": label,
                                    "created_at": "2026-10-04T00:00:01+00:00", "origin": "test",
                                    "why": "", "intent_id": "intent-001"})
        following["intents"][0]["snap_ids"].append("snap-001")
        payload = {**first, "snapshot": following, "parent": first["revision"],
                   "revision": revision_id(first["revision"], following)}
        barrier.wait()
        try:
            return push_history(POSTGRES_URL, payload, account["id"])
        except APIError as exc:
            return {"error": exc.code}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(push, ["first", "second"]))
    assert sum(result.get("changed") is True for result in results) == 1
    assert sum(result.get("error") == "NON_FAST_FORWARD" for result in results) == 1
    with connect(POSTGRES_URL) as conn:
        assert conn.execute("SELECT count(*) AS count FROM semantic_versions WHERE project_id = ?", (pid,)).fetchone()["count"] == 2
    overview = project_overview(POSTGRES_URL, pid, account_id=account["id"])
    assert overview["history"]["revision"] == read_history(POSTGRES_URL, name, account["id"])["revision"]
    assert "workspaces" not in overview


@pytest.mark.skipif(not POSTGRES_URL, reason="INTHUB_TEST_POSTGRES_URL is not configured")
def test_postgresql_project_rename_export_and_delete():
    name = "managed-" + os.urandom(6).hex()
    account = upsert_github_account(POSTGRES_URL, {"id": name, "login": name})
    pid = link_history(POSTGRES_URL, name, account["id"])["project_id"]
    taken = link_history(POSTGRES_URL, name + "-taken", account["id"])["project_id"]
    snapshot = {"intents": [], "snaps": [], "decisions": []}
    renamed = name + "-renamed"
    with pytest.raises(APIError) as exc:
        rename_project(POSTGRES_URL, pid, name + "-taken", account["id"])
    assert exc.value.code == "NAME_TAKEN"
    assert rename_project(POSTGRES_URL, pid, renamed, account["id"])["project"]["name"] == renamed
    # A push that names the old project but carries its ID lands on the renamed one.
    pushed = push_history(POSTGRES_URL, {"project_name": name, "project_id": pid, "parent": None,
                                         "revision": revision_id(None, snapshot), "snapshot": snapshot}, account["id"])
    assert pushed["project_name"] == renamed
    assert read_history(POSTGRES_URL, name, account["id"], project_id=pid)["project_name"] == renamed
    assert [row["revision"] for row in export_project(POSTGRES_URL, pid, account["id"])["revisions"]] == [pushed["revision"]]
    assert delete_project(POSTGRES_URL, pid, renamed, account["id"]) == {"deleted": True, "id": pid}
    assert [project["id"] for project in list_projects(POSTGRES_URL, account_id=account["id"])["projects"]] == [taken]


@pytest.mark.skipif(not POSTGRES_URL, reason="INTHUB_TEST_POSTGRES_URL is not configured")
def test_postgresql_tenon_mapping_attempt_and_session():
    suffix = os.urandom(6).hex()
    account = upsert_github_account(POSTGRES_URL, {"id": "legacy-" + suffix, "login": suffix})
    subject = "tenon-" + suffix
    bind_existing_account(POSTGRES_URL, account["id"], subject)
    info = {"sub": subject, "name": "Integration", "platform_role": "admin", "expires_at": time.time() + 60}
    assert account_for_identity(POSTGRES_URL, info)["id"] == account["id"]
    attempt = create_attempt(POSTGRES_URL)
    assert consume_attempt(POSTGRES_URL, attempt["state"])["nonce"] == attempt["nonce"]
    session = create_session(POSTGRES_URL, account["id"], info)
    assert tenon_account_for_session(POSTGRES_URL, session["token"])["role"] == "admin"


@pytest.mark.skipif(not POSTGRES_URL, reason="INTHUB_TEST_POSTGRES_URL is not configured")
def test_postgresql_account_and_session_round_trip():
    suffix = os.urandom(6).hex()
    account = upsert_github_account(
        POSTGRES_URL,
        {
            "id": f"integration-{suffix}",
            "login": f"integration-{suffix}",
            "name": "Integration Account",
        },
    )
    session = create_web_session(POSTGRES_URL, account["id"], ttl_seconds=60)

    recovered = account_for_session(POSTGRES_URL, session["token"])
    assert recovered["id"] == account["id"]
    assert recovered["login"] == f"integration-{suffix}"

    access_token = create_account_access_token(
        POSTGRES_URL,
        account["id"],
        ttl_seconds=60,
    )
    recovered_for_cli = account_for_access_token(POSTGRES_URL, access_token["token"])
    assert recovered_for_cli["id"] == account["id"]

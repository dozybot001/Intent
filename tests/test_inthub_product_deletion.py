import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer

import httpx
import pytest

from apps.inthub_api.auth import account_for_access_token, create_account_access_token
from apps.inthub_api.common import APIError
from apps.inthub_api.db import connect
from apps.inthub_api.history import link_history
from apps.inthub_api.product_deletion import ProductDeletionClient, delete_product_account, subject_for_account
from apps.inthub_api.server import make_handler
from apps.inthub_api.tenon import ISSUER, account_for_identity, account_for_session, create_session


def identity(subject):
    return {"sub": subject, "name": "Synthetic user", "platform_role": "user", "expires_at": time.time() + 60}


def proof(subject="person-1", operation="f8132b30-0471-4a4b-95d7-a9f2fe6f4df7"):
    return {"issuer": ISSUER, "sub": subject, "productId": "inthub", "operationId": operation}


def populate(target, subject="person-1"):
    value = identity(subject)
    account = account_for_identity(target, value)
    session = create_session(target, account["id"], value)
    pat = create_account_access_token(target, account["id"])
    project = link_history(target, "Synthetic project", account["id"])
    pid = project["project_id"]
    with connect(target) as conn:
        conn.execute("INSERT INTO workspaces VALUES ('ws-' || ?, ?, 'intent', 'repo', 'now')", (subject, pid))
        conn.execute("INSERT INTO sync_batches(id,project_id,workspace_id,generated_at,accepted_at,payload_json) VALUES (?, ?, ?, 'now','now','{}')", ("batch-" + subject, pid, "ws-" + subject))
        conn.execute("INSERT INTO semantic_versions VALUES (?, 'revision', NULL, '{}', 'now')", (pid,))
        conn.execute("INSERT INTO public_profiles VALUES (?, ?, 'Title', 'Description', 'now', 'now')", ("profile-" + subject, account["id"]))
        conn.execute("INSERT INTO public_profile_projects VALUES (?, ?, 1, 'now')", ("profile-" + subject, pid))
    return account, session, pat, pid


def test_product_deletion_removes_owned_cloud_history_credentials_and_preserves_other_accounts(tmp_path):
    target = str(tmp_path / "fixture.sqlite")
    account, session, pat, pid = populate(target)
    other, other_session, other_pat, other_pid = populate(target, "person-2")
    result = delete_product_account(target, proof())
    assert result == {"operationId": proof()["operationId"], "status": "completed", "deleted": True}
    assert account_for_session(target, session["token"]) is None
    assert account_for_access_token(target, pat["token"]) is None
    assert account_for_session(target, other_session["token"])["id"] == other["id"]
    assert account_for_access_token(target, other_pat["token"])["id"] == other["id"]
    with connect(target) as conn:
        assert conn.execute("SELECT id FROM accounts WHERE id = ?", (account["id"],)).fetchone() is None
        assert [row["id"] for row in conn.execute("SELECT id FROM projects").fetchall()] == [other_pid]
        for table in ("semantic_heads", "semantic_versions", "sync_batches", "workspaces", "public_profile_projects"):
            assert conn.execute(f"SELECT count(*) AS n FROM {table} WHERE project_id = ?", (pid,)).fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM product_deletion_receipts").fetchone()["n"] == 1
    # A repeated authorized operation cannot delete a re-registered account.
    replacement = account_for_identity(target, identity("person-1"), request_started_at=(datetime.now(timezone.utc) + timedelta(milliseconds=1)).isoformat())
    assert replacement["id"] != account["id"]
    assert delete_product_account(target, proof()) == result
    assert subject_for_account(target, replacement["id"]) == "person-1"


def test_absent_identity_and_receipt_are_idempotent_but_subject_cannot_change(tmp_path):
    target = str(tmp_path / "fixture.sqlite")
    assert delete_product_account(target, proof())["deleted"]
    assert delete_product_account(target, proof())["deleted"]
    with pytest.raises(APIError, match="does not match"):
        delete_product_account(target, proof("person-2"))


def test_late_oidc_callback_cannot_recreate_deleted_identity_and_completed_proof_cannot_delete_new_identity(tmp_path):
    target = str(tmp_path / "fixture.sqlite")
    old_started = datetime.now(timezone.utc).isoformat()
    account, _, _, _ = populate(target)
    delete_product_account(target, proof())
    with pytest.raises(APIError, match="new Tenon sign-in"):
        account_for_identity(target, identity("person-1"), request_started_at=old_started)
    replacement = account_for_identity(target, identity("person-1"), request_started_at=(datetime.now(timezone.utc) + timedelta(milliseconds=1)).isoformat())
    assert replacement["id"] != account["id"]
    assert delete_product_account(target, {**proof(), "completed": True})["deleted"]
    with pytest.raises(APIError, match="receipt is unavailable"):
        delete_product_account(target, {**proof(operation="cdd09571-5c42-4c3a-800a-8c26b148aa1c"), "completed": True})
    assert subject_for_account(target, replacement["id"]) == "person-1"


def test_receipt_failure_rolls_back_data_and_session_removal(tmp_path):
    target = str(tmp_path / "fixture.sqlite")
    account, session, pat, pid = populate(target)
    with connect(target) as conn:
        conn.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON product_deletion_receipts BEGIN SELECT RAISE(ABORT, 'fixture failure'); END")
    with pytest.raises(Exception, match="fixture failure"):
        delete_product_account(target, proof())
    assert account_for_session(target, session["token"])["id"] == account["id"]
    assert account_for_access_token(target, pat["token"])["id"] == account["id"]
    with connect(target) as conn:
        assert conn.execute("SELECT id FROM projects WHERE id = ?", (pid,)).fetchone()
        assert conn.execute("SELECT count(*) AS n FROM product_deletion_receipts").fetchone()["n"] == 0


@pytest.mark.parametrize("change", [{"issuer": "https://fake.example"}, {"productId": "wesaid"}, {"operationId": "different"}])
def test_wrong_central_proof_never_deletes(tmp_path, change):
    target = str(tmp_path / "fixture.sqlite")
    account, session, _, _ = populate(target)
    client = ProductDeletionClient("fixture-client", "fixture-secret", request=lambda *args, **kwargs: httpx.Response(200, json={**proof(), **change}))
    with pytest.raises(APIError):
        client.execute(target, {"operationId": proof()["operationId"], "grant": "x" * 43})
    assert account_for_session(target, session["token"])["id"] == account["id"]


def test_expired_central_grant_cannot_delete_and_finish_outage_cannot_undo_committed_receipt(tmp_path):
    target = str(tmp_path / "fixture.sqlite")
    account, session, _, _ = populate(target)
    calls = []
    def expired(url, **kwargs):
        calls.append(url)
        return httpx.Response(410, json={"error": "expired"})
    client = ProductDeletionClient("fixture-client", "fixture-secret", request=expired)
    with pytest.raises(APIError):
        client.execute(target, {"operationId": proof()["operationId"], "grant": "x" * 43})
    assert account_for_session(target, session["token"])["id"] == account["id"]
    def committed(url, **kwargs):
        assert kwargs["headers"]["Authorization"].startswith("Basic ")
        assert kwargs["follow_redirects"] is False
        return httpx.Response(503 if url.endswith("finish") else 200, json=proof())
    client.request = committed
    assert client.execute(target, {"operationId": proof()["operationId"], "grant": "x" * 43})["deleted"] is True
    assert account_for_session(target, session["token"]) is None


def test_rejects_nonstandard_input_and_nonunique_start_request(tmp_path):
    target = str(tmp_path / "fixture.sqlite")
    calls = []
    def request(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json=proof())
    client = ProductDeletionClient("fixture-client", "fixture-secret", request=request)
    for value in ({"operationId": proof()["operationId"], "grant": "x" * 43, "sub": "other"},
                  {"operationId": "legacy-operation", "grant": "x" * 43},
                  {"operationId": proof()["operationId"], "grant": "short"},
                  {"operationId": proof()["operationId"], "grant": "!" * 43}):
        with pytest.raises(APIError):
            client.execute(target, value)
    assert calls == []
    base = "https://account.tenon.asia/account/delete/?request=" + "x" * 43
    for url in (base + "&request=" + "x" * 43, base + "&extra=yes", base.replace("x" * 43, "short")):
        client.request = lambda *args, **kwargs: httpx.Response(200, json={"url": url, "expiresAt": time.time() * 1000 + 300000})
        with pytest.raises(APIError):
            client.start("person-1")


def test_http_start_requires_local_session_same_origin_and_execute_requires_central_claim(tmp_path):
    target = str(tmp_path / "fixture.sqlite")
    _, session, _, _ = populate(target)
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs["json"]))
        if url.endswith("start"):
            return httpx.Response(200, json={"url": "https://account.tenon.asia/account/delete/?request=fffffffffffffffffffffffffffffffffffffffffff", "expiresAt": time.time() * 1000 + 300000})
        return httpx.Response(200, json=proof())
    client = ProductDeletionClient("fixture-client", "fixture-secret", request=request)
    handler = make_handler(target, tenon_client_id="fixture-client", tenon_client_secret="fixture-secret",
                           oauth_client=object(), public_api_base_url="https://inthub.tenon.asia", deletion_client=client)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    start = "/api/auth/tenon/delete/start"
    headers = {"Origin": "https://inthub.tenon.asia", "Cookie": "inthub_session=" + session["token"]}
    try:
        assert httpx.post(base + start, json={}, headers={"Origin": "https://evil.example"}).status_code == 403
        assert httpx.post(base + start, json={}, headers={"Origin": headers["Origin"]}).status_code == 401
        assert httpx.post(base + start, json={"sub": "other"}, headers=headers).status_code == 400
        assert httpx.post(base + start, json={}, headers=headers).status_code == 200
        assert calls[-1][1] == {"sub": "person-1"}
        execute = "/api/auth/tenon/delete/execute"
        assert httpx.get(base + execute, headers=headers).status_code in (401, 404)
        assert httpx.post(base + execute, json={"operationId": proof()["operationId"], "grant": "x" * 43}, headers=headers).status_code == 403
        response = httpx.post(base + execute, json={"operationId": proof()["operationId"], "grant": "x" * 43})
        assert response.status_code == 200 and response.json()["deleted"]
        assert account_for_session(target, session["token"]) is None
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

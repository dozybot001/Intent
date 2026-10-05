"""Product-bound Tenon deletion proofs and atomic IntHub data removal."""

import base64
import re
import time
from urllib.parse import parse_qsl, quote, urlsplit

import httpx

from apps.inthub_api.common import APIError, now_utc
from apps.inthub_api.db import connect
from apps.inthub_api.tenon import ISSUER, _identity_lock

PRODUCT_ID = "inthub"
OPERATION_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


def validate_operation(operation_id, grant):
    if (not isinstance(operation_id, str) or not OPERATION_PATTERN.fullmatch(operation_id)
            or not isinstance(grant, str) or not TOKEN_PATTERN.fullmatch(grant)):
        raise APIError("INVALID_DELETION_REQUEST", "Invalid deletion request.", 400)


def validate_proof(proof, operation_id):
    if (not isinstance(operation_id, str) or not OPERATION_PATTERN.fullmatch(operation_id)
            or not isinstance(proof, dict) or proof.get("issuer") != ISSUER
            or set(proof) - {"issuer", "sub", "productId", "operationId", "completed"}
            or ("completed" in proof and not isinstance(proof["completed"], bool))
            or proof.get("productId") != PRODUCT_ID or proof.get("operationId") != operation_id
            or not isinstance(proof.get("sub"), str) or not 1 <= len(proof["sub"]) <= 255):
        raise APIError("DELETION_PROOF_INVALID", "The product deletion authorization is invalid.", 401)
    return proof


def subject_for_account(db_target, account_id):
    with connect(db_target) as conn:
        row = conn.execute(
            "SELECT subject FROM account_identities WHERE issuer = ? AND account_id = ?",
            (ISSUER, account_id),
        ).fetchone()
    if row is None:
        raise APIError("AUTHENTICATION_REQUIRED", "Sign in with Tenon.", 401)
    return row["subject"]


def delete_product_account(db_target, proof):
    """The caller must first obtain this proof from Tenon's authenticated claim API."""
    operation_id = proof.get("operationId") if isinstance(proof, dict) else None
    validate_proof(proof, operation_id)
    subject = proof["sub"]
    with connect(db_target) as conn:
        # This is also the login identity lock: a concurrent login either precedes
        # deletion and is removed, or follows it and creates a fresh product ID.
        _identity_lock(conn, subject)
        receipt = conn.execute(
            "SELECT issuer, subject FROM product_deletion_receipts WHERE operation_id = ?",
            (operation_id,),
        ).fetchone()
        if receipt is not None:
            if receipt["issuer"] != ISSUER or receipt["subject"] != subject:
                raise APIError("DELETION_PROOF_INVALID", "The deletion operation does not match.", 401)
            return {"operationId": operation_id, "status": "completed", "deleted": True}
        if proof.get("completed") is True:
            raise APIError("DELETION_RECEIPT_MISSING", "A completed deletion receipt is unavailable. No new account was deleted.", 503)
        mapping = conn.execute(
            "SELECT account_id FROM account_identities WHERE issuer = ? AND subject = ?",
            (ISSUER, subject),
        ).fetchone()
        if mapping is not None:
            account_id = mapping["account_id"]
            owned = "SELECT id FROM projects WHERE account_id = ?"
            # Foreign keys are deliberately not cascaded for immutable history.
            # Delete only this account's cloud copies, never another account or
            # a local CLI .intent directory.
            for table in ("public_profile_projects", "semantic_heads", "semantic_versions", "sync_batches", "workspaces"):
                conn.execute(f"DELETE FROM {table} WHERE project_id IN ({owned})", (account_id,))
            conn.execute("DELETE FROM projects WHERE account_id = ?", (account_id,))
            conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        # The receipt has no account FK; it must survive deletion/re-registration.
        conn.execute("INSERT INTO product_deletion_receipts VALUES (?, ?, ?, ?)",
                     (operation_id, ISSUER, subject, now_utc()))
    return {"operationId": operation_id, "status": "completed", "deleted": True}


class ProductDeletionClient:
    def __init__(self, client_id, client_secret, request=httpx.post):
        if not client_id or not client_secret:
            raise ValueError("Tenon product deletion requires confidential client credentials.")
        encoded = quote(client_id, safe="") + ":" + quote(client_secret, safe="")
        self.authorization = "Basic " + base64.b64encode(encoded.encode()).decode()
        self.request = request

    def call(self, action, payload):
        try:
            response = self.request(ISSUER + "/product-deletion/" + action, json=payload,
                                    headers={"Authorization": self.authorization},
                                    timeout=2 if action == "finish" else 5, follow_redirects=False)
            if response.status_code != 200:
                status = 401 if response.status_code in (400, 401, 403, 404, 409, 410) else 502
                raise APIError("DELETION_AUTHORIZATION_FAILED", "Tenon could not authorize this deletion. Try again.", status)
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("Invalid response")
            return result
        except APIError:
            raise
        except Exception:
            # Do not include response bodies, grants or private credentials in errors.
            raise APIError("DELETION_SERVICE_UNAVAILABLE", "Tenon account management is temporarily unavailable.", 502) from None

    def start(self, subject):
        result = self.call("start", {"sub": subject})
        target = urlsplit(result.get("url", ""))
        query = parse_qsl(target.query, keep_blank_values=True)
        if (target.scheme != "https" or target.netloc != "account.tenon.asia"
                or target.path != "/account/delete/" or target.username or target.password or target.fragment
                or set(result) != {"url", "expiresAt"}
                or len(query) != 1 or query[0][0] != "request" or not TOKEN_PATTERN.fullmatch(query[0][1])
                or not isinstance(result.get("expiresAt"), (int, float)) or isinstance(result["expiresAt"], bool)
                or not time.time() * 1000 < result["expiresAt"] < 2 ** 53):
            raise APIError("DELETION_PROOF_INVALID", "Tenon returned an invalid deletion destination.", 502)
        return result

    def execute(self, db_target, payload):
        if not isinstance(payload, dict) or set(payload) != {"operationId", "grant"}:
            raise APIError("INVALID_DELETION_REQUEST", "Invalid deletion request.", 400)
        operation_id, grant = payload.get("operationId"), payload.get("grant")
        validate_operation(operation_id, grant)
        proof = validate_proof(self.call("claim", {"operationId": operation_id, "grant": grant}), operation_id)
        try:
            result = delete_product_account(db_target, proof)
        except Exception:
            try:
                self.call("finish", {"operationId": operation_id, "grant": grant, "status": "failed"})
            except APIError:
                pass
            raise APIError("PRODUCT_DELETION_FAILED", "IntHub data could not be deleted. Nothing was confirmed deleted.", 503) from None
        try:
            self.call("finish", {"operationId": operation_id, "grant": grant, "status": "completed"})
        except APIError:
            # The durable transaction is the receipt; central acknowledgement
            # failure must never turn a completed deletion into a fake failure.
            pass
        return result

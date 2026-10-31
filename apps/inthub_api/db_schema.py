"""The database's tables: what each migration creates, and the columns a current schema must have."""
import hashlib

LATEST_SCHEMA_VERSION = 9
_REPOSITORY_SCHEMA_NAME = "revision-graph"
_REPOSITORY_SCHEMA_CHECKSUM = hashlib.sha256(b"0009:repo-blobs:repo-refs:version-tip").hexdigest()
_HOSTED_SCHEMA_NAME = "device-logins-limits-suspension"
_HOSTED_SCHEMA_CHECKSUM = hashlib.sha256(b"0008:device-logins:project-stored-bytes:account-project-suspension").hexdigest()
_TEAMS_SCHEMA_NAME = "teams-and-visibility"
_TEAMS_SCHEMA_CHECKSUM = hashlib.sha256(b"0007:teams:members:invites:project-team-visibility").hexdigest()
_IDENTITY_SCHEMA_NAME = "revision-identity"
_IDENTITY_SCHEMA_CHECKSUM = hashlib.sha256(b"0006:account-email:project-repository:revision-pusher-changes:verified-objects").hexdigest()
_DELETION_SCHEMA_NAME = "product-deletion-receipts"
_DELETION_SCHEMA_CHECKSUM = hashlib.sha256(b"0005:product-deletion:operation-subject-receipts:login-start").hexdigest()
_HISTORY_SCHEMA_NAME = "shared-semantic-history"
_HISTORY_SCHEMA_CHECKSUM = hashlib.sha256(b"0004:project-head:immutable-parent-revisions").hexdigest()
_INITIAL_SCHEMA_NAME = "initial-account-scoped-schema"
_INITIAL_SCHEMA_CHECKSUM = hashlib.sha256(
    b"0001:initial-account-scoped-schema:projects-account:tokens:sync-sequence"
).hexdigest()
_PUBLIC_PROFILES_SCHEMA_NAME = "public-profiles-with-explicit-project-grants"
_PUBLIC_PROFILES_SCHEMA_CHECKSUM = hashlib.sha256(
    b"0002:public-profiles:explicit-project-grants"
).hexdigest()
_TENON_SCHEMA_NAME = "tenon-identities-and-bounded-session-grants"
_TENON_SCHEMA_CHECKSUM = hashlib.sha256(
    b"0003:tenon-identities:nonce-attempts:bounded-session-grants"
).hexdigest()
_EXPECTED_SCHEMA_COLUMNS_V1 = {
    "projects": {
        "id",
        "account_id",
        "name",
        "provider",
        "repo_id",
        "owner",
        "repo_name",
        "created_at",
    },
    "workspaces": {"id", "project_id", "provider", "repo_id", "created_at"},
    "sync_batches": {
        "sequence_id",
        "id",
        "project_id",
        "workspace_id",
        "generated_at",
        "accepted_at",
        "payload_json",
    },
    "accounts": {
        "id",
        "provider",
        "provider_user_id",
        "login",
        "display_name",
        "avatar_url",
        "role",
        "created_at",
        "updated_at",
        "last_login_at",
    },
    "oauth_login_attempts": {
        "state_hash",
        "code_verifier",
        "return_to",
        "created_at",
        "expires_at",
    },
    "web_sessions": {
        "id",
        "token_hash",
        "account_id",
        "created_at",
        "expires_at",
        "last_seen_at",
    },
    "account_access_tokens": {
        "id",
        "token_hash",
        "account_id",
        "name",
        "created_at",
        "expires_at",
        "last_used_at",
        "revoked_at",
    },
}
_EXPECTED_SCHEMA_COLUMNS_V2 = {
    "public_profiles": {
        "slug",
        "account_id",
        "title",
        "description",
        "created_at",
        "updated_at",
    },
    "public_profile_projects": {
        "profile_slug",
        "project_id",
        "position",
        "published_at",
    },
}
_EXPECTED_SCHEMA_COLUMNS = {
    **_EXPECTED_SCHEMA_COLUMNS_V1,
    **_EXPECTED_SCHEMA_COLUMNS_V2,
    "account_identities": {"issuer", "subject", "account_id", "created_at"},
    "tenon_login_attempts": {
        "state_hash", "code_verifier", "nonce", "return_to", "expires_at",
    },
    "tenon_session_grants": {
        "session_id", "issuer", "subject", "platform_role", "verified_at",
    },
}
_EXPECTED_SCHEMA_COLUMNS_V3 = dict(_EXPECTED_SCHEMA_COLUMNS)
_EXPECTED_SCHEMA_COLUMNS.update({
    "semantic_heads": {"project_id", "revision"},
    "semantic_versions": {"project_id", "revision", "parent", "snapshot_json", "created_at"},
    "product_deletion_receipts": {"operation_id", "issuer", "subject", "completed_at"},
})
_EXPECTED_SCHEMA_COLUMNS["tenon_login_attempts"] = _EXPECTED_SCHEMA_COLUMNS["tenon_login_attempts"] | {"started_at"}
_IDENTITY_COLUMNS = {
    "accounts": {"email"},
    "projects": {"repository_url"},
    "semantic_versions": {"pushed_by", "pusher_json", "changes_json"},
}
for _table, _columns in _IDENTITY_COLUMNS.items():
    _EXPECTED_SCHEMA_COLUMNS[_table] = _EXPECTED_SCHEMA_COLUMNS[_table] | _columns
_EXPECTED_SCHEMA_COLUMNS["verified_objects"] = {"project_id", "object_id", "revision"}
_EXPECTED_SCHEMA_COLUMNS["semantic_versions"] = _EXPECTED_SCHEMA_COLUMNS["semantic_versions"] | {"tip"}
_EXPECTED_SCHEMA_COLUMNS["repo_blobs"] = {"project_id", "kind", "digest", "body", "is_binary"}
_EXPECTED_SCHEMA_COLUMNS["repo_refs"] = {"project_id", "name", "revision"}
_EXPECTED_SCHEMA_COLUMNS["projects"] = _EXPECTED_SCHEMA_COLUMNS["projects"] | {"team_id", "visibility", "stored_bytes", "suspended_at"}
_EXPECTED_SCHEMA_COLUMNS["accounts"] = _EXPECTED_SCHEMA_COLUMNS["accounts"] | {"suspended_at"}
_EXPECTED_SCHEMA_COLUMNS.update({
    "teams": {"id", "slug", "name", "created_by", "created_at"},
    "team_members": {"team_id", "account_id", "role", "joined_at"},
    "team_invites": {"id", "team_id", "token_hash", "role", "created_by", "created_at", "expires_at"},
    "device_logins": {"id", "device_hash", "user_hash", "name", "created_at", "expires_at", "account_id", "decided_at"},
})



def _create_sqlite_schema(conn):
    conn.raw.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            account_id TEXT,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            owner TEXT NOT NULL,
            repo_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (account_id, provider, repo_id)
        );

        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        CREATE TABLE IF NOT EXISTS sync_batches (
            sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT NOT NULL UNIQUE,
            project_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            accepted_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
        );
        """
    )

    conn.raw.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            provider_user_id TEXT NOT NULL,
            login TEXT NOT NULL,
            display_name TEXT,
            avatar_url TEXT,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL,
            UNIQUE (provider, provider_user_id)
        );

        CREATE TABLE IF NOT EXISTS oauth_login_attempts (
            state_hash TEXT PRIMARY KEY,
            code_verifier TEXT NOT NULL,
            return_to TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS web_sessions (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            account_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS account_access_tokens (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            account_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_used_at TEXT,
            revoked_at TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_web_sessions_account
            ON web_sessions(account_id);
        CREATE INDEX IF NOT EXISTS idx_web_sessions_expires
            ON web_sessions(expires_at);
        CREATE INDEX IF NOT EXISTS idx_oauth_login_attempts_expires
            ON oauth_login_attempts(expires_at);
        CREATE INDEX IF NOT EXISTS idx_account_access_tokens_account
            ON account_access_tokens(account_id);
        CREATE INDEX IF NOT EXISTS idx_account_access_tokens_expires
            ON account_access_tokens(expires_at);
        CREATE INDEX IF NOT EXISTS idx_projects_account
            ON projects(account_id);

        CREATE INDEX IF NOT EXISTS idx_workspaces_project
            ON workspaces(project_id);
        CREATE INDEX IF NOT EXISTS idx_sync_batches_project_workspace_sequence
            ON sync_batches(project_id, workspace_id, sequence_id DESC);
        CREATE INDEX IF NOT EXISTS idx_sync_batches_workspace_sequence
            ON sync_batches(workspace_id, sequence_id DESC);
        """
    )


def _create_postgresql_schema(conn):
    statements = (
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            account_id TEXT,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            owner TEXT NOT NULL,
            repo_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (account_id, provider, repo_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id),
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sync_batches (
            sequence_id BIGSERIAL PRIMARY KEY,
            id TEXT NOT NULL UNIQUE,
            project_id TEXT NOT NULL REFERENCES projects(id),
            workspace_id TEXT NOT NULL REFERENCES workspaces(id),
            generated_at TEXT NOT NULL,
            accepted_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            provider_user_id TEXT NOT NULL,
            login TEXT NOT NULL,
            display_name TEXT,
            avatar_url TEXT,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL,
            UNIQUE (provider, provider_user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS oauth_login_attempts (
            state_hash TEXT PRIMARY KEY,
            code_verifier TEXT NOT NULL,
            return_to TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS web_sessions (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS account_access_tokens (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_used_at TEXT,
            revoked_at TEXT
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_web_sessions_account
            ON web_sessions(account_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_web_sessions_expires
            ON web_sessions(expires_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_oauth_login_attempts_expires
            ON oauth_login_attempts(expires_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_account_access_tokens_account
            ON account_access_tokens(account_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_account_access_tokens_expires
            ON account_access_tokens(expires_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_projects_account
            ON projects(account_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_workspaces_project
            ON workspaces(project_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sync_batches_project_workspace_sequence
            ON sync_batches(project_id, workspace_id, sequence_id DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sync_batches_workspace_sequence
            ON sync_batches(workspace_id, sequence_id DESC)
        """,
    )
    for statement in statements:
        conn.execute(statement)


def _create_sqlite_public_profiles_schema(conn):
    # Retain schema migration 0002 for existing databases; public routes are retired.
    conn.raw.executescript(
        """
        CREATE TABLE IF NOT EXISTS public_profiles (
            slug TEXT PRIMARY KEY,
            account_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS public_profile_projects (
            profile_slug TEXT NOT NULL,
            project_id TEXT NOT NULL UNIQUE,
            position INTEGER NOT NULL,
            published_at TEXT NOT NULL,
            PRIMARY KEY (profile_slug, project_id),
            FOREIGN KEY (profile_slug) REFERENCES public_profiles(slug) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_public_profile_projects_profile_position
            ON public_profile_projects(profile_slug, position, project_id);
        """
    )


def _create_postgresql_public_profiles_schema(conn):
    statements = (
        """
        CREATE TABLE IF NOT EXISTS public_profiles (
            slug TEXT PRIMARY KEY,
            account_id TEXT NOT NULL UNIQUE REFERENCES accounts(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS public_profile_projects (
            profile_slug TEXT NOT NULL REFERENCES public_profiles(slug) ON DELETE CASCADE,
            project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            published_at TEXT NOT NULL,
            PRIMARY KEY (profile_slug, project_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_public_profile_projects_profile_position
            ON public_profile_projects(profile_slug, position, project_id)
        """,
    )
    for statement in statements:
        conn.execute(statement)


def _create_tenon_schema(conn):
    # Additive tables keep the previous image compatible during a release rollback.
    for statement in (
        """CREATE TABLE IF NOT EXISTS account_identities (
            issuer TEXT NOT NULL, subject TEXT NOT NULL,
            account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            PRIMARY KEY (issuer, subject), UNIQUE (account_id, issuer)
        )""",
        """CREATE TABLE IF NOT EXISTS tenon_login_attempts (
            state_hash TEXT PRIMARY KEY, code_verifier TEXT NOT NULL,
            nonce TEXT NOT NULL, return_to TEXT NOT NULL, expires_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS tenon_session_grants (
            session_id TEXT PRIMARY KEY REFERENCES web_sessions(id) ON DELETE CASCADE,
            issuer TEXT NOT NULL, subject TEXT NOT NULL,
            platform_role TEXT NOT NULL CHECK (platform_role IN ('admin', 'user')),
            verified_at TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS idx_tenon_attempts_expires ON tenon_login_attempts(expires_at)",
    ):
        conn.execute(statement)

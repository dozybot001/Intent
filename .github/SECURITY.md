# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 7.x     | :white_check_mark: |
| < 7.0   | :x: |

## Reporting a Vulnerability

If you discover a security vulnerability in Intent CLI or IntHub, use [GitHub's private vulnerability reporting](https://github.com/dozybot001/Intent/security/advisories/new) when that option is available. Otherwise, open a minimal [issue](https://github.com/dozybot001/Intent/issues) asking the maintainer for a private contact channel without including exploit details. Do not disclose user data, credentials, or an unpatched exploit in a public issue. Public, non-sensitive hardening suggestions may use the regular issue tracker directly.

We will acknowledge reports within 7 days and provide an update on the fix timeline.

## Scope

- **Intent CLI** (`itt`): runs locally, reads and writes `.intent/` JSON files, and communicates with IntHub via HTTP.
- **`.intent/` data**: may contain goals, implementation rationale, decisions, repository metadata, and an IntHub configuration. `itt init` adds `.intent/` to that clone's Git-local `.git/info/exclude` and reports a warning if it cannot; it does not edit the shared `.gitignore`. Users should still review the directory before sharing it or staging ignored files explicitly.
- **Hub credentials**: `itt auth login` stores an account access token through Git's configured credential helper, scoped to one IntHub endpoint; its protection is that helper's (for example the macOS Keychain, or plaintext with `credential.helper=store`). `--token` and `INTHUB_TOKEN` are never persisted and are only sent to the endpoint given on the command line, the user-level endpoint, or loopback, never to an endpoint named only by a shared `.intent/hub.json`. Remote IntHub URLs must use HTTPS. Tokens never enter `.intent/`.
- **IntHub Local**: binds to `127.0.0.1` by default and stores synchronized snapshots in an unencrypted SQLite database under `~/.inthub/inthub.db` unless configured otherwise.

## IntHub Local Trust Boundary

The bundled IntHub Local service is a single-user browser and read model for a trusted machine. It has no accounts: anything that can reach it can read and write its history. To keep other websites in your browser out, it answers only same-origin requests on loopback host names (no CORS headers, `Host` checked against 127.0.0.1/localhost to defeat DNS rebinding, JSON-only request bodies), and the server refuses to start unauthenticated on a non-loopback interface. It does not provide transport security or encryption at rest.

Do not bind IntHub Local to a LAN or public interface or publish it through a reverse proxy. For remote or multi-user use, deploy the authenticated profile instead.

The hosted service (https://inthub.tenon.asia) uses that authenticated profile: Tenon OIDC sign-in (PKCE, nonce, single-use state), host-only `Secure` `SameSite=Strict` session cookies, per-account history isolation, account access tokens that are stored as hashes and can be revoked, same-origin checks on browser writes, a strict Content-Security-Policy, and PostgreSQL bound to a private network behind TLS. Browser sessions are read-only for history; only account access tokens can push. Revoke a token from the account menu after any suspected disclosure.

# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 5.x     | :white_check_mark: |
| < 5.0   | :x: |

## Reporting a Vulnerability

If you discover a security vulnerability in Intent CLI or IntHub, use [GitHub's private vulnerability reporting](https://github.com/dozybot001/Intent/security/advisories/new) when that option is available. Otherwise, open a minimal [issue](https://github.com/dozybot001/Intent/issues) asking the maintainer for a private contact channel without including exploit details. Do not disclose user data, credentials, or an unpatched exploit in a public issue. Public, non-sensitive hardening suggestions may use the regular issue tracker directly.

We will acknowledge reports within 7 days and provide an update on the fix timeline.

## Scope

- **Intent CLI** (`itt`): runs locally, reads and writes `.intent/` JSON files, and communicates with IntHub via HTTP.
- **`.intent/` data**: may contain goals, implementation rationale, decisions, repository metadata, and an IntHub configuration. `itt init` adds `.intent/` to that clone's Git-local `.git/info/exclude` and reports a warning if it cannot; it does not edit the shared `.gitignore`. Users should still review the directory before sharing it or staging ignored files explicitly.
- **Hub credentials**: the current CLI accepts `--token` or `INTHUB_TOKEN` without persisting the credential. Older releases could write a plaintext `auth_token` to `.intent/hub.json`; inspect and remove that legacy field before committing or sharing the directory. A later `itt hub link` or `itt hub sync` also rewrites the config without the legacy token.
- **IntHub Local**: binds to `127.0.0.1` by default and stores synchronized snapshots in an unencrypted SQLite database under `~/.inthub/inthub.db` unless configured otherwise.

## IntHub Local Trust Boundary

The bundled IntHub Local service is a single-user browser and read model for a trusted machine. The current server does not enforce bearer-token authentication and sends `Access-Control-Allow-Origin: *`. It does not provide multi-user authorization, tenant isolation, transport security, or encryption at rest.

Do not bind IntHub Local to a LAN or public interface, publish it through a reverse proxy, or treat a configured client token as server-side access control. If remote or multi-user deployment is required, place an independently reviewed authentication and TLS boundary in front of it and assess the API and stored data for that environment.

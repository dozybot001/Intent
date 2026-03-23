# Security Policy

[中文](SECURITY_CN.md) | English

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 2.x     | :white_check_mark: |
| < 2.0   | :x: |

## Reporting a Vulnerability

If you discover a security vulnerability in Intent CLI or IntHub, please report it by opening a [GitHub issue](https://github.com/dozybot001/Intent/issues). If the vulnerability is sensitive, contact the maintainers directly before disclosing publicly.

We will acknowledge reports within 7 days and provide an update on the fix timeline.

## Scope

- **Intent CLI** (`itt`): runs locally, reads and writes `.intent/` JSON files, and communicates with IntHub via HTTP.
- **IntHub Local**: binds to `127.0.0.1` by default. It is not designed for public-facing deployment.
- **`.intent/` data**: stored locally and excluded from Git by default (`.gitignore`). It may contain project context, so treat it like other local workspace metadata.

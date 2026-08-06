"""Run the explicit IntHub database migration gate.

Production invokes this module from the exact candidate image after a verified
backup and before the candidate application starts. Output is deliberately
JSON and never includes the database URL.
"""

import argparse
import json
import os

from .db import LATEST_SCHEMA_VERSION, migrate_target


def _parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.environ.get("INTHUB_DATABASE_URL"),
    )
    parser.add_argument("--expect-version", type=int, required=True)
    parser.add_argument("--require-backward-compatible", action="store_true")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if not args.database_url:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "DATABASE_URL_REQUIRED",
                        "message": "INTHUB_DATABASE_URL or --database-url is required",
                    },
                }
            )
        )
        return 2
    if not args.require_backward_compatible:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "MIGRATION_POLICY_REQUIRED",
                        "message": "production migration requires the backward-compatible gate",
                    },
                }
            )
        )
        return 2
    if args.expect_version != LATEST_SCHEMA_VERSION:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "SCHEMA_VERSION_MISMATCH",
                        "message": "candidate schema version does not match its migration code",
                    },
                }
            )
        )
        return 1

    try:
        result = migrate_target(
            args.database_url,
            require_backward_compatible=True,
        )
    except Exception as exc:  # pragma: no cover - exact backend errors vary
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "DATABASE_MIGRATION_FAILED",
                        "message": str(exc),
                    },
                }
            )
        )
        return 1

    if result["to_version"] != args.expect_version:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "SCHEMA_VERSION_MISMATCH",
                        "message": "database did not reach the candidate schema version",
                    },
                }
            )
        )
        return 1
    print(json.dumps({"ok": True, "result": result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

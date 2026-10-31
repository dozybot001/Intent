#!/usr/bin/env python3
"""Run only the tests a change can affect. The full suite runs at release time and in CI.

    python scripts/changed_tests.py           # uncommitted changes
    python scripts/changed_tests.py HEAD~2    # everything since a commit
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ["tests/test_inthub_web_ui.py"]
SERVER = ["tests/test_inthub_api_server.py", "tests/test_inthub_auth.py", "tests/test_inthub_db.py", "tests/test_inthub_device_login.py",
          "tests/test_inthub_hosted_limits.py", "tests/test_inthub_product_deletion.py", "tests/test_inthub_projects.py",
          "tests/test_inthub_queries.py", "tests/test_inthub_teams.py", "tests/test_inthub_tenon.py"]
SYNC = ["tests/test_cli_polish.py", "tests/test_protocol3.py", "tests/test_protocol3_safety.py", "tests/test_hub_client.py", "tests/test_hub_credentials.py", "tests/test_hub_runtime.py", "tests/test_shared_history.py",
        "tests/test_snapshot_restore.py"]
CLI = ["tests/test_cli_global.py", "tests/test_cli_hub.py", "tests/test_cli_inspect.py", "tests/test_cli_objects.py", "tests/test_cli_storage.py",
       "tests/test_identity.py", "tests/test_maintenance.py", "tests/test_origin.py", "tests/test_output.py",
       "tests/test_relations.py", "tests/test_store_security.py"]
# First match wins. Paths that match nothing, such as docs, need no tests.
AREAS = (
    ("apps/inthub_web/", WEB),
    ("apps/inthub_local/", ["tests/test_inthub_local.py"]),
    ("apps/inthub_api/", SERVER),
    ("src/intent_cli/hub/", SYNC + ["tests/test_inthub_device_login.py"]),
    ("src/intent_cli/", CLI),
    ("scripts/itt_argv.py", ["tests/test_itt_argv.py"]),
    ("deploy/", ["tests/test_inthub_deployment.py"]),
    ("Dockerfile", ["tests/test_inthub_deployment.py"]),
    ("pyproject.toml", ["tests/test_inthub_deployment.py", "tests/test_inthub_local.py"]),
)


def changed_paths(base):
    tracked = subprocess.run(["git", "diff", "--name-only", base], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    return (tracked + untracked).split()


def tests_for(paths):
    selected = []
    for path in paths:
        if path.startswith("tests/"):
            matches = [path] if path.endswith(".py") and "/test_" in path else WEB if path.endswith(".cjs") else []
        else:
            matches = next((tests for prefix, tests in AREAS if path.startswith(prefix)), [])
        selected += [test for test in matches if test not in selected and (ROOT / test).is_file()]
    return selected


def main():
    tests = tests_for(changed_paths(sys.argv[1] if len(sys.argv) > 1 else "HEAD"))
    if not tests:
        print("No tests cover this change.")
        return 0
    print(f"{len(tests)} test files: {' '.join(Path(test).stem for test in tests)}")
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-n", "auto", *tests], cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())

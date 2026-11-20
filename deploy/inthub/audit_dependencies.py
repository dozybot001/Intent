"""Release gate for product standard 15.1.2: no known vulnerability ships.

Runs pip-audit on the qualification environment, which holds the production
dependencies (the `server` extra, pinned like the Dockerfile) and the release
tools. A finding blocks the release unless audit-exemptions.json lists it with
an expiry date no later than one month out; an expired entry blocks too.
Exemptions are only for build and test tools, never for what runs in production.
"""

import datetime
import json
import pathlib
import subprocess
import sys

EXEMPTIONS = pathlib.Path(__file__).with_name("audit-exemptions.json")
FIELDS = {"id", "package", "reason", "expires"}


def load_exemptions(path=EXEMPTIONS, today=None):
    today = today or datetime.date.today()
    entries = json.loads(path.read_text(encoding="utf-8"))
    active = []
    for entry in entries:
        if set(entry) != FIELDS or not all(isinstance(entry[key], str) and entry[key] for key in FIELDS):
            raise SystemExit(f"audit exemption needs exactly {sorted(FIELDS)}: {entry}")
        expires = datetime.date.fromisoformat(entry["expires"])
        if expires < today:
            raise SystemExit(f"audit exemption {entry['id']} for {entry['package']} expired on {expires}")
        if expires > today + datetime.timedelta(days=31):
            raise SystemExit(f"audit exemption {entry['id']} may run at most one month, not to {expires}")
        active.append(entry["id"])
    return active


def main(python):
    command = [python, "-m", "pip_audit", "--progress-spinner", "off", "--desc", "off"]
    for vulnerability in load_exemptions():
        command += ["--ignore-vuln", vulnerability]
    result = subprocess.run(command)
    if result.returncode:
        raise SystemExit("dependency audit found known vulnerabilities; upgrade, or exempt a build-only tool")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else sys.executable)

import datetime
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "inthub" / "audit_dependencies.py"
spec = importlib.util.spec_from_file_location("audit_dependencies", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
TODAY = datetime.date(2026, 11, 20)


def _write(tmp_path, entries):
    path = tmp_path / "exemptions.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def _entry(**changes):
    entry = {"id": "PYSEC-1", "package": "pytest", "reason": "test runner only", "expires": "2026-12-01"}
    return {**entry, **changes}


def test_the_checked_in_list_is_valid_and_the_gate_runs_it():
    assert isinstance(audit.load_exemptions(), list)
    qualify = (SCRIPT.parent / "qualify-release.sh").read_text(encoding="utf-8")
    assert 'audit_dependencies.py" "${QUALIFICATION_PYTHON}"' in qualify


def test_a_current_exemption_is_ignored_by_id(tmp_path):
    assert audit.load_exemptions(_write(tmp_path, [_entry()]), TODAY) == ["PYSEC-1"]


@pytest.mark.parametrize("entry, message", [
    (_entry(expires="2026-11-19"), "expired"),
    (_entry(expires="2027-01-15"), "at most one month"),
    ({"id": "PYSEC-1", "package": "pytest", "expires": "2026-12-01"}, "needs exactly"),
])
def test_expired_long_or_incomplete_exemptions_block_the_release(tmp_path, entry, message):
    with pytest.raises(SystemExit, match=message):
        audit.load_exemptions(_write(tmp_path, [entry]), TODAY)

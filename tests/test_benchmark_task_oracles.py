"""Executable validity evidence for the six semantic continuation tasks."""

from pathlib import Path
import subprocess
import sys

from intent_cli.benchmark.harness import (
    load_task,
    materialize,
    score_repo_with_oracle,
)


def _task_repo(tmp_path, task_id, variant):
    task = load_task(task_id)
    repo = materialize(task, "after_a", tmp_path / variant)
    return task, repo


def _write(repo, relative_path, content):
    path = Path(repo) / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _score(task, repo):
    return score_repo_with_oracle(task, repo, "oracle")


def _assert_after_a_fails(task, repo):
    result = _score(task, repo)
    assert not result["ok"], result


def _assert_reference_passes(task, repo):
    result = _score(task, repo)
    assert result["ok"], result


def _assert_wrong_variant_fails(task, repo, expected_kind):
    visible = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert visible.returncode == 0, visible.stdout + visible.stderr
    result = _score(task, repo)
    assert not result["ok"], result
    failed_kinds = {check["kind"] for check in result["checks"] if not check["passed"]}
    assert expected_kind in failed_kinds, result


def test_utf8_oracle_rejects_single_prefix_special_case(tmp_path):
    task_id = "investigation-utf8-stream-001"
    task, after_a = _task_repo(tmp_path, task_id, "utf8-after-a")
    _assert_after_a_fails(task, after_a)

    task, correct = _task_repo(tmp_path, task_id, "utf8-correct")
    _write(
        correct,
        "streamfeed/reader.py",
        '''import codecs


def decode_chunks(chunks):
    decoder = codecs.getincrementaldecoder("utf-8")()
    decoded = [decoder.decode(chunk, final=False) for chunk in chunks]
    decoded.append(decoder.decode(b"", final=True))
    return "".join(decoded)
''',
    )
    _assert_reference_passes(task, correct)

    task, wrong = _task_repo(tmp_path, task_id, "utf8-single-prefix-wrong")
    _write(
        wrong,
        "streamfeed/reader.py",
        '''def decode_chunks(chunks):
    decoded = []
    pending = b""
    for chunk in chunks:
        data = pending + chunk
        pending = b""
        if data.endswith(b"\\xe5"):
            data, pending = data[:-1], b"\\xe5"
        decoded.append(data.decode("utf-8"))
    if pending:
        pending.decode("utf-8")
    return "".join(decoded)
''',
    )
    _assert_wrong_variant_fails(task, wrong, "hidden_tests")


def test_record_oracle_rejects_fixture_id_hardcoding(tmp_path):
    task_id = "decision-record-extension-001"
    task, after_a = _task_repo(tmp_path, task_id, "record-after-a")
    _assert_after_a_fails(task, after_a)

    task, correct = _task_repo(tmp_path, task_id, "record-correct")
    _write(
        correct,
        "records/normalizer.py",
        '''def normalize_record(record):
    normalized = dict(record)
    if "name" not in normalized:
        normalized["name"] = normalized["display_name"]
    normalized.pop("display_name", None)
    return normalized
''',
    )
    _assert_reference_passes(task, correct)

    task, wrong = _task_repo(tmp_path, task_id, "record-fixture-id-wrong")
    _write(
        wrong,
        "records/normalizer.py",
        '''def normalize_record(record):
    if record["id"] == "user-2":
        return {"id": "user-2", "name": record["display_name"]}
    return {"id": record["id"], "name": record["name"]}
''',
    )
    _assert_wrong_variant_fails(task, wrong, "hidden_tests")


def test_diagnostics_oracle_rejects_known_exception_allowlist(tmp_path):
    task_id = "decision-conflict-diagnostics-001"
    task, after_a = _task_repo(tmp_path, task_id, "diagnostics-after-a")
    _assert_after_a_fails(task, after_a)

    task, correct = _task_repo(tmp_path, task_id, "diagnostics-correct")
    _write(
        correct,
        "web/api.py",
        '''from web.diagnostics import new_request_id


def create_item_response(payload, service, logger):
    try:
        item = service(payload)
        return {"status": 201, "body": {"item": item}}
    except Exception as exc:
        request_id = new_request_id()
        logger.error("create_item_failed", request_id=request_id, exception=exc)
        return {
            "status": 500,
            "body": {"error": "internal_error", "request_id": request_id},
        }
''',
    )
    _assert_reference_passes(task, correct)

    task, wrong = _task_repo(tmp_path, task_id, "diagnostics-known-types-wrong")
    _write(
        wrong,
        "web/api.py",
        '''from web.diagnostics import new_request_id


def create_item_response(payload, service, logger):
    try:
        item = service(payload)
        return {"status": 201, "body": {"item": item}}
    except (RuntimeError, ValueError) as exc:
        request_id = new_request_id()
        logger.error("create_item_failed", request_id=request_id, exception=exc)
        return {
            "status": 500,
            "body": {"error": "internal_error", "request_id": request_id},
        }
    except Exception as exc:
        request_id = new_request_id()
        logger.error("create_item_failed", request_id=request_id, exception=exc)
        return {
            "status": 500,
            "body": {
                "error": "internal_error",
                "request_id": request_id,
                "detail": str(exc),
            },
        }
''',
    )
    _assert_wrong_variant_fails(task, wrong, "hidden_tests")


def test_cache_oracle_rejects_ctime_stat_identity(tmp_path):
    task_id = "correction-cache-mtime-001"
    task, after_a = _task_repo(tmp_path, task_id, "cache-after-a")
    _assert_after_a_fails(task, after_a)

    task, correct = _task_repo(tmp_path, task_id, "cache-correct")
    _write(
        correct,
        "settings/cache.py",
        '''import json
from pathlib import Path


def load_settings(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
''',
    )
    _assert_reference_passes(task, correct)

    task, wrong = _task_repo(tmp_path, task_id, "cache-ctime-stat-wrong")
    _write(
        wrong,
        "settings/cache.py",
        '''import json
from pathlib import Path

_cache = {}


def load_settings(path):
    key = str(Path(path))
    stat = Path(path).stat()
    identity = (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino)
    cached = _cache.get(key)
    if cached is None or cached[0] != identity:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        _cache[key] = (identity, value)
    return _cache[key][1]
''',
    )
    _assert_wrong_variant_fails(task, wrong, "hidden_tests")


def test_multi_intent_oracle_rejects_new_parquet_file(tmp_path):
    task_id = "multi-intent-export-001"
    task, after_a = _task_repo(tmp_path, task_id, "multi-after-a")
    _assert_after_a_fails(task, after_a)

    csv_reference = '''import csv
import io


def export_rows(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["name", "note"], lineterminator="\\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
'''

    task, correct = _task_repo(tmp_path, task_id, "multi-correct")
    _write(correct, "exports/csv_export.py", csv_reference)
    _assert_reference_passes(task, correct)

    task, wrong = _task_repo(tmp_path, task_id, "multi-new-parquet-file-wrong")
    _write(wrong, "exports/csv_export.py", csv_reference)
    _write(
        wrong,
        "exports/parquet_runtime.py",
        '''def encode_rows(rows):
    return {"format": "parquet", "rows": list(rows)}
''',
    )
    _assert_wrong_variant_fails(task, wrong, "only_paths_may_change")


def test_rename_oracle_rejects_copied_formatter_logic(tmp_path):
    task_id = "negative-symbol-rename-001"
    task, after_a = _task_repo(tmp_path, task_id, "rename-after-a")
    _assert_after_a_fails(task, after_a)

    task, correct = _task_repo(tmp_path, task_id, "rename-correct")
    _write(
        correct,
        "display/__init__.py",
        'from display.formatter import format_display_name\n\n__all__ = ["format_display_name"]\n',
    )
    _write(
        correct,
        "display/search.py",
        '''from display.formatter import format_display_name


def search_label(user):
    return f"Result — {format_display_name(user)}"
''',
    )
    _write(
        correct,
        "display/admin.py",
        '''from display import format_display_name


def audit_label(user):
    return f"Audit<{format_display_name(user)}>"
''',
    )
    _assert_reference_passes(task, correct)

    task, wrong = _task_repo(tmp_path, task_id, "rename-copied-logic-wrong")
    _write(
        wrong,
        "display/__init__.py",
        'from display.formatter import format_display_name\n\n__all__ = ["format_display_name"]\n',
    )
    _write(
        wrong,
        "display/profile.py",
        '''def profile_heading(user):
    copied = user["name"].strip().title()
    return f"Profile: {copied}"
''',
    )
    _write(
        wrong,
        "display/search.py",
        '''def search_label(user):
    copied = user["name"].strip().title()
    return f"Result — {copied}"
''',
    )
    _write(
        wrong,
        "display/admin.py",
        '''def audit_label(user):
    copied = user["name"].strip().title()
    return f"Audit<{copied}>"
''',
    )
    _assert_wrong_variant_fails(task, wrong, "hidden_tests")

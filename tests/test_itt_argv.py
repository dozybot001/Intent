import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "scripts" / "itt_argv.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("itt_argv_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _encode(argv):
    return quote(json.dumps(argv, ensure_ascii=False), safe="-._~")


def test_decode_argv_preserves_unicode_and_shell_metacharacters():
    runner = _load_runner()
    argv = [
        "intent",
        "create",
        "修复 '引号'；不执行 $(touch /tmp/nope)",
        "--why",
        "换行\n与 $HOME 保持为数据",
    ]

    assert runner.decode_argv(_encode(argv)) == argv


def test_runner_passes_data_as_argv_without_shell_evaluation(tmp_path):
    fake_itt = tmp_path / "itt"
    fake_itt.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "print(json.dumps({'ok': True, 'action': 'fake', 'result': {'argv': sys.argv[1:]}, 'warnings': []}))\n",
        encoding="utf-8",
    )
    fake_itt.chmod(0o755)
    marker = tmp_path / "must-not-exist"
    semantic_text = f"literal $(touch {marker}) and 'quotes' 中文"
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"

    result = subprocess.run(
        [sys.executable, str(RUNNER_PATH), _encode(["intent", "create", semantic_text])],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    assert json.loads(result.stdout)["result"]["argv"] == [
        "intent",
        "create",
        semantic_text,
    ]
    assert not marker.exists()


def test_runner_rejects_raw_shell_payload():
    result = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "[]; touch /tmp/nope"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert json.loads(result.stdout)["error"]["code"] == "INVALID_INPUT"

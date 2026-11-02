"""After an accepted release the server keeps the current, previous and newest three releases only."""

import importlib.util
import os
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "inthub" / "retain_releases.py"
SPEC = importlib.util.spec_from_file_location("inthub_retain_releases", SCRIPT)
retention = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retention)


def sha(n):
    return f"{n:x}" * 40


class FakeDocker:
    def __init__(self, containers, images, refuse=()):
        self.containers, self.images, self.refuse, self.calls = containers, images, set(refuse), []

    def __call__(self, *args):
        self.calls.append(args)
        if args[0] == "ps":
            return "".join(f"{cid}\t{image}\t{state}\n" for cid, image, state in self.containers)
        if args[:2] == ("image", "ls"):
            return "".join(f"{image}\n" for image in self.images)
        if args[-1] in self.refuse:
            raise subprocess.CalledProcessError(1, args, stderr="image is in use")
        return ""

    def removed(self, kind):
        return [args[-1] for args in self.calls if (args[0] == "rm") == (kind == "container") and "rm" in args[:2]]


@pytest.fixture
def server(tmp_path):
    releases = tmp_path / "releases"
    releases.mkdir()
    (tmp_path / "incoming").mkdir()
    for age, n in enumerate(range(6, 0, -1)):  # release 6 is the newest
        release = releases / sha(n)
        release.mkdir()
        (release / "images.tar.gz").write_bytes(b"x" * 1024)
        (release / "images.tar.gz").chmod(0o444)
        release.chmod(0o500)  # solidified releases are read-only
        os.utime(release, (1_000_000 - age * 60, 1_000_000 - age * 60))
    yield tmp_path
    for directory, _, _ in os.walk(tmp_path):
        os.chmod(directory, 0o755)


def test_keeps_current_previous_newest_three_and_anything_running(server):
    (server / "incoming" / f"{sha(2)}-release-{sha(2)[:12]}-1-20260806T193029Z").mkdir()
    (server / "incoming" / "notes").write_text("not a bundle")
    docker = FakeDocker(
        containers=[("c1", f"inthub:{sha(1)}", "running"), ("c2", f"inthub:{sha(2)}", "exited"),
                    ("c5", f"inthub:{sha(5)}", "exited"), ("pg", "sha256:" + "f" * 64, "running"),
                    ("w", f"wesaid:{sha(2)}", "exited")],
        images=[f"inthub:{sha(n)}" for n in (1, 2, 5, 6, 9)] + ["inthub:latest"])
    report, warnings = retention.retain(server, server / "releases" / sha(6), server / "releases" / sha(5), run=docker)

    assert warnings == []
    assert sorted(path.name for path in (server / "releases").iterdir()) == sorted(sha(n) for n in (1, 4, 5, 6))
    assert docker.removed("container") == ["c2"], "only the stopped container of a removed release"
    assert sorted(docker.removed("image")) == sorted([f"inthub:{sha(2)}", f"inthub:{sha(9)}"])
    assert sorted(path.name for path in (server / "incoming").iterdir()) == ["notes"]
    assert report == {"releases": 2, "containers": 1, "images": 2, "leftovers": 1, "bytes": 2048}


def test_a_dry_run_reports_without_removing(server):
    docker = FakeDocker(containers=[("c2", f"inthub:{sha(2)}", "exited")], images=[f"inthub:{sha(2)}"])
    report, _ = retention.retain(server, server / "releases" / sha(6), "", run=docker, dry_run=True)
    assert report["releases"] == 3 and report["images"] == 1 and report["containers"] == 1
    assert len(list((server / "releases").iterdir())) == 6 and all(call[0] in {"ps", "image"} and "rm" not in call
                                                                   for call in docker.calls)


def test_an_older_release_stays_when_it_is_the_previous_one(server):
    docker = FakeDocker(containers=[], images=[])
    retention.retain(server, server / "releases" / sha(6), server / "releases" / sha(1), run=docker)
    assert sorted(path.name for path in (server / "releases").iterdir()) == sorted(sha(n) for n in (1, 4, 5, 6))


def test_one_failed_removal_is_reported_and_the_rest_continue(server):
    docker = FakeDocker(containers=[], images=[f"inthub:{sha(2)}", f"inthub:{sha(3)}"], refuse={f"inthub:{sha(2)}"})
    report, warnings = retention.retain(server, server / "releases" / sha(6), "", run=docker)
    assert report["images"] == 1 and report["releases"] == 3
    assert len(warnings) == 1 and "image is in use" in warnings[0]


def test_an_unreachable_docker_never_fails_the_release(server, monkeypatch, capsys):
    monkeypatch.setattr(retention, "docker", lambda *args: (_ for _ in ()).throw(FileNotFoundError("sudo")))
    assert retention.main(["--root", str(server), "--current", str(server / "releases" / sha(6))]) == 0
    assert "retention skipped" in capsys.readouterr().err
    assert len(list((server / "releases").iterdir())) == 6


def test_the_release_runs_retention_only_after_acceptance():
    remote = (SCRIPT.parent / "remote-release.sh").read_text(encoding="utf-8")
    assert remote.index("RELEASE_ACCEPTED=true") < remote.index("retain_releases.py") < remote.index("passed candidate")
    assert "|| echo \"WARNING: IntHub release retention did not finish.\"" in remote
    assert "prune" not in SCRIPT.read_text(encoding="utf-8").replace("never pruned", "")

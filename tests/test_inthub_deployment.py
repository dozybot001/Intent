import hashlib
import importlib.util
import io
import json
import os
import tarfile
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


MANIFEST_PATH = REPOSITORY_ROOT / "deploy" / "inthub" / "release_manifest.py"
SPEC = importlib.util.spec_from_file_location("inthub_release_manifest", MANIFEST_PATH)
manifest_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(manifest_module)


def _checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(path):
    return {"path": path.name, "sha256": _checksum(path), "bytes": path.stat().st_size}


def _valid_bundle(tmp_path):
    git_sha = "a" * 40
    version = "6.0.1.dev0+gaaaaaaa"
    for name in manifest_module.EXPECTED_RELEASE_FILES:
        (tmp_path / name).write_bytes(f"release:{name}".encode())
    (tmp_path / "images.tar.gz").write_bytes(b"release:images.tar.gz")

    runtime_lock_bytes = json.dumps(
        {
            "schema_version": 1,
            "images": {
                "database": {
                    "reference": "postgres:18.4-bookworm",
                    "pull_reference": "postgres@sha256:" + "d" * 64,
                    "id": "sha256:" + "c" * 64,
                    "os": "linux",
                    "architecture": "amd64",
                }
            },
        }
    ).encode()
    (tmp_path / "runtime-images.lock.json").write_bytes(runtime_lock_bytes)
    recipe_contents = {
        "Dockerfile": b"FROM scratch\n",
        "pyproject.toml": b"[project]\nname = 'intent-cli'\n",
        "deploy/inthub/runtime-images.lock.json": runtime_lock_bytes,
    }
    with tarfile.open(tmp_path / "source.tar.gz", mode="w:gz") as archive:
        for relative_path, payload in recipe_contents.items():
            info = tarfile.TarInfo(f"Intent-{git_sha}/{relative_path}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    manifest = {
        "schema_version": 1,
        "project_id": "inthub",
        "git_sha": git_sha,
        "dirty": False,
        "github_sync": "pending",
        "version": version,
        "target": {"os": "linux", "architecture": "amd64"},
        "artifacts": {
            key: _record(tmp_path / name)
            for key, name in manifest_module.EXPECTED_ARTIFACTS.items()
        },
        "release_files": {
            name: _record(tmp_path / name)
            for name in manifest_module.EXPECTED_RELEASE_FILES
        },
        "images": {
            "app": {
                "reference": f"inthub:{git_sha}",
                "id": "sha256:" + "b" * 64,
                "os": "linux",
                "architecture": "amd64",
                "repo_digests": [],
                "labels": {
                    "org.opencontainers.image.revision": git_sha,
                    "org.opencontainers.image.source": "https://github.com/dozybot001/Intent",
                    "org.opencontainers.image.version": version,
                },
            },
            "database": {
                "reference": "postgres:18.4-bookworm",
                "id": "sha256:" + "c" * 64,
                "os": "linux",
                "architecture": "amd64",
                "repo_digests": ["postgres@sha256:" + "d" * 64],
                "labels": {},
            },
        },
        "build": {
            "builder": {
                "name": "shared-linux-amd64",
                "driver": "docker-container",
                "buildx_version": "github.com/docker/buildx v0.30.1",
            },
            "recipe": {
                "dockerfile": {
                    "path": "Dockerfile",
                    "sha256": hashlib.sha256(recipe_contents["Dockerfile"]).hexdigest(),
                },
                "dependency_lock": {
                    "path": "pyproject.toml",
                    "sha256": hashlib.sha256(
                        recipe_contents["pyproject.toml"]
                    ).hexdigest(),
                },
                "runtime_images": {
                    "path": "deploy/inthub/runtime-images.lock.json",
                    "sha256": hashlib.sha256(runtime_lock_bytes).hexdigest(),
                },
            },
            "built_at": "2026-08-04T00:00:00+00:00",
        },
        "tests": [
            {"name": name, "result": "passed"}
            for name in sorted(manifest_module.REQUIRED_TESTS)
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    manifest_module.write_checksums(str(tmp_path))
    return manifest


def test_production_image_declares_github_source_and_exact_revision():
    dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert (
        'org.opencontainers.image.source="https://github.com/dozybot001/Intent"'
        in dockerfile
    )
    assert 'org.opencontainers.image.revision="${INTHUB_REVISION}"' in dockerfile
    assert "gitee.com" not in dockerfile


def test_compose_can_only_start_preloaded_images():
    compose = (REPOSITORY_ROOT / "deploy" / "inthub" / "compose.yaml").read_text(
        encoding="utf-8"
    )

    assert "    build:" not in compose
    assert compose.count("pull_policy: never") == 2
    assert "image: inthub:${INTHUB_RELEASE:?set INTHUB_RELEASE}" in compose
    assert (
        "container_name: ${INTHUB_APP_CONTAINER:?set INTHUB_APP_CONTAINER}"
        in compose
    )
    assert "external: true" in compose


def test_release_entry_builds_uploads_and_locks_without_source_remote():
    release = (REPOSITORY_ROOT / "deploy" / "inthub" / "release.sh").read_text(
        encoding="utf-8"
    )

    assert 'bash "${SCRIPT_DIR}/build-release.sh"' in release
    assert "rsync --archive" in release
    assert ".release-lock" in release
    assert "remote-release.sh" in release
    assert "git push" not in release
    assert "git ls-remote" not in release


def test_remote_release_verifies_and_loads_but_never_builds_or_pulls():
    remote = (REPOSITORY_ROOT / "deploy" / "inthub" / "remote-release.sh").read_text(
        encoding="utf-8"
    )

    assert "release_manifest.py\" verify" in remote
    assert "images.tar.gz\" | docker_command load" in remote
    assert "pg_dump" in remote
    assert "--no-build --pull never" in remote
    assert "smoke.sh" in remote
    assert "rollback_release" in remote
    assert "CANDIDATE_SLOT" in remote
    assert "restoring the previous traffic boundary" in remote
    assert "git clone" not in remote
    assert "git pull" not in remote
    assert "docker build" not in remote
    assert "docker pull" not in remote


def test_release_scripts_are_executable():
    for name in (
        "build-release.sh",
        "release.sh",
        "remote-release.sh",
        "smoke.sh",
        "release_manifest.py",
    ):
        assert os.access(REPOSITORY_ROOT / "deploy" / "inthub" / name, os.X_OK)


def test_manifest_verifier_accepts_exact_bundle(tmp_path):
    manifest = _valid_bundle(tmp_path)

    verified = manifest_module.verify_manifest(str(tmp_path), manifest["git_sha"])
    manifest_module.verify_checksums(str(tmp_path))

    assert verified["git_sha"] == manifest["git_sha"]


def test_manifest_verifier_rejects_tampering(tmp_path):
    _valid_bundle(tmp_path)
    (tmp_path / "source.tar.gz").write_bytes(b"tampered")

    with pytest.raises(manifest_module.ManifestError, match="mismatch"):
        manifest_module.verify_manifest(str(tmp_path))


def test_manifest_verifier_rejects_symlink_and_extra_file(tmp_path):
    _valid_bundle(tmp_path)
    smoke = tmp_path / "smoke.sh"
    smoke.unlink()
    smoke.symlink_to(tmp_path / "compose.yaml")

    with pytest.raises(manifest_module.ManifestError, match="regular file"):
        manifest_module.verify_manifest(str(tmp_path))

    smoke.unlink()
    smoke.write_bytes(b"release:smoke.sh")
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    manifest["release_files"]["smoke.sh"] = _record(smoke)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    manifest_module.write_checksums(str(tmp_path))
    (tmp_path / "unexpected.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(manifest_module.ManifestError, match="unexpected"):
        manifest_module.verify_checksums(str(tmp_path))


def test_manifest_verifier_rejects_runtime_image_lock_drift(tmp_path):
    manifest = _valid_bundle(tmp_path)
    runtime_lock = json.loads(
        (tmp_path / "runtime-images.lock.json").read_text(encoding="utf-8")
    )
    runtime_lock["images"]["database"]["id"] = "sha256:" + "9" * 64
    (tmp_path / "runtime-images.lock.json").write_text(
        json.dumps(runtime_lock), encoding="utf-8"
    )
    manifest["release_files"]["runtime-images.lock.json"] = _record(
        tmp_path / "runtime-images.lock.json"
    )
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    manifest_module.write_checksums(str(tmp_path))

    with pytest.raises(manifest_module.ManifestError, match="runtime lock"):
        manifest_module.verify_manifest(str(tmp_path))


def test_source_scan_rejects_high_confidence_credentials(tmp_path):
    (tmp_path / "safe.txt").write_text("ith_pat_test-placeholder", encoding="utf-8")
    manifest_module.scan_source(str(tmp_path))

    (tmp_path / "secret.txt").write_text(
        "ith_pat_" + "a" * 40,
        encoding="utf-8",
    )
    with pytest.raises(manifest_module.ManifestError, match="credential-like"):
        manifest_module.scan_source(str(tmp_path))


def test_manifest_verifier_cross_checks_recipe_against_source_archive(tmp_path):
    manifest = _valid_bundle(tmp_path)
    manifest["build"]["recipe"]["dockerfile"]["sha256"] = "0" * 64
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    manifest_module.write_checksums(str(tmp_path))

    with pytest.raises(manifest_module.ManifestError, match="source recipe checksum"):
        manifest_module.verify_manifest(str(tmp_path))


def test_manifest_verifier_rejects_unsafe_source_archive_entry(tmp_path):
    manifest = _valid_bundle(tmp_path)
    with tarfile.open(tmp_path / "source.tar.gz", mode="w:gz") as archive:
        info = tarfile.TarInfo(f"Intent-{manifest['git_sha']}/unsafe-link")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../outside"
        archive.addfile(info)
    manifest["artifacts"]["source_archive"] = _record(tmp_path / "source.tar.gz")
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    manifest_module.write_checksums(str(tmp_path))

    with pytest.raises(manifest_module.ManifestError, match="non-regular"):
        manifest_module.verify_manifest(str(tmp_path))

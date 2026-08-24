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


def _docker_save_stream(reference, config_digest):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        manifest = json.dumps(
            [
                {
                    "Config": f"blobs/sha256/{config_digest}",
                    "RepoTags": [reference],
                    "Layers": [],
                }
            ]
        ).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest)
        archive.addfile(info, io.BytesIO(manifest))
    payload.seek(0)
    return payload


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
        "apps/inthub_api/db.py": b"LATEST_SCHEMA_VERSION = 2\n",
        "apps/inthub_api/migrate.py": b"# migration entry\n",
        "deploy/inthub/runtime-images.lock.json": runtime_lock_bytes,
    }
    with tarfile.open(tmp_path / "source.tar.gz", mode="w:gz") as archive:
        for relative_path, payload in recipe_contents.items():
            info = tarfile.TarInfo(f"Intent-{git_sha}/{relative_path}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    recipe = {
        key: {
            "path": relative_path,
            "sha256": hashlib.sha256(recipe_contents[relative_path]).hexdigest(),
        }
        for key, relative_path in manifest_module.REQUIRED_RECIPE_PATHS.items()
    }
    manifest = {
        "schema_version": 4,
        "project_id": "inthub",
        "bundle_id": git_sha,
        "git_sha": git_sha,
        "dirty": False,
        "version": version,
        "source": {
            "transport": "gitee-exact-commit",
            "repository": "https://gitee.com/dozybot/Intent.git",
            "ref": "refs/heads/main",
            "commit": git_sha,
        },
        "target": {"os": "linux", "architecture": "amd64"},
        "database_schema": {
            "version": 2,
            "migration_policy": "expand-contract",
            "backward_compatible": True,
            "migration_sha256": manifest_module._migration_recipe_checksum(recipe),
        },
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
                    "org.opencontainers.image.source": "https://gitee.com/dozybot/Intent",
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
                "name": "default",
                "driver": "docker",
                "buildx_version": "github.com/docker/buildx v0.30.1",
                "buildkit_version": "v0.31.2",
            },
            "base_images": {
                "app": "python:3.13-slim@sha256:" + "e" * 64,
                "database": "postgres@sha256:" + "d" * 64,
            },
            "qualification": {
                "python_version": "3.13.5",
                "pytest_version": "8.4.2",
            },
            "recipe": recipe,
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


def test_production_image_declares_gitee_source_and_exact_revision():
    dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert (
        'org.opencontainers.image.source="https://gitee.com/dozybot/Intent"'
        in dockerfile
    )
    assert 'org.opencontainers.image.revision="${INTHUB_REVISION}"' in dockerfile
    assert 'io.inthub.database-schema-version="${INTHUB_SCHEMA_VERSION}"' in dockerfile
    assert "ARG INTHUB_SCHEMA_VERSION=2" in dockerfile
    assert "github.com/dozybot001/Intent" not in dockerfile


def test_compose_uses_explicit_immutable_images_and_disables_auto_migration():
    compose = (REPOSITORY_ROOT / "deploy" / "inthub" / "compose.yaml").read_text(
        encoding="utf-8"
    )

    assert "    build:" not in compose
    assert compose.count("pull_policy: never") == 2
    assert "image: ${INTHUB_APP_IMAGE:?set INTHUB_APP_IMAGE}" in compose
    assert "image: ${INTHUB_DATABASE_IMAGE:?set INTHUB_DATABASE_IMAGE}" in compose
    assert (
        "container_name: ${INTHUB_APP_CONTAINER:?set INTHUB_APP_CONTAINER}"
        in compose
    )
    assert "external: true" in compose
    assert 'INTHUB_AUTO_MIGRATE: "0"' in compose


def test_release_entry_uses_the_gitee_exact_commit_path():
    release = (REPOSITORY_ROOT / "deploy" / "inthub" / "release.sh").read_text(
        encoding="utf-8"
    )

    server_release = (REPOSITORY_ROOT / "deploy" / "inthub" / "release-from-gitee.sh").read_text(
        encoding="utf-8"
    )

    assert 'GITEE_URL="https://gitee.com/dozybot/Intent.git"' in release
    assert 'bash "${SCRIPT_DIR}/qualify-release.sh"' in release
    assert 'git push "${GITEE_URL}" "${RELEASE_SHA}:${GITEE_REF}"' in release
    assert release.count("git ls-remote") == 2
    assert "release-from-gitee.sh" in release
    assert "local-release.sh" not in release
    assert "rsync" not in release
    assert "github.com" not in release
    assert not (REPOSITORY_ROOT / "deploy" / "inthub" / "local-release.sh").exists()

    assert 'GITEE_URL="https://gitee.com/dozybot/Intent.git"' in server_release
    assert "git ls-remote" in server_release
    assert "fetch --prune --tags" in server_release
    assert 'checkout -B main "${RELEASE_SHA}"' in server_release
    assert "INTHUB_BUILDER=default" in server_release
    assert 'bash deploy/inthub/build-release.sh' in server_release
    assert "INTHUB_RELEASE_SOURCE=gitee-exact-commit" in server_release
    assert "git pull" not in server_release
    assert "github.com" not in server_release


def test_local_build_qualifies_commit_and_exports_images_once():
    build = (REPOSITORY_ROOT / "deploy" / "inthub" / "build-release.sh").read_text(
        encoding="utf-8"
    )

    assert 'BUILDER="${INTHUB_BUILDER:-default}"' in build
    assert 'EXPECTED_BUILDER_DRIVER="${INTHUB_BUILDER_DRIVER:-docker}"' in build
    assert 'bash "${SCRIPT_DIR}/prepare-release-env.sh"' in build
    assert "git archive" in build
    assert 'bash "${SCRIPT_DIR}/qualify-release.sh" "${RELEASE_SHA}"' in build
    assert "BUILDKIT_VERSION=" in build
    assert 'docker image inspect "${APP_BASE_IMAGE}"' in build
    assert build.count("docker buildx build") == 1
    assert "docker save" in build
    assert "image-config-id" in build
    assert 'BUNDLE_DIRECTORY="${STAGING_DIRECTORY}"' in build
    assert build.rindex('rm -rf -- "${CONTEXT_DIRECTORY}"') < build.rindex(
        'mv "${STAGING_DIRECTORY}" "${FINAL_DIRECTORY}"'
    )
    assert build.rindex('chmod -R a-w "${BUNDLE_DIRECTORY}"') < build.rindex(
        'mv "${STAGING_DIRECTORY}" "${FINAL_DIRECTORY}"'
    )
    assert "release_manifest.py\" verify" in build
    assert "docker push" not in build
    assert "ghcr.io" not in build


def test_local_qualification_does_not_build_the_application_image():
    qualify = (REPOSITORY_ROOT / "deploy" / "inthub" / "qualify-release.sh").read_text(
        encoding="utf-8"
    )

    assert "INTHUB_TEST_POSTGRES_URL=" in qualify
    assert "git archive" in qualify
    assert "release_manifest.py\" scan" in qualify
    assert "git diff --check" in qualify
    assert "docker buildx build" not in qualify


def test_gitee_bootstrap_only_installs_the_stable_launcher():
    bootstrap = (
        REPOSITORY_ROOT / "deploy" / "inthub" / "bootstrap-gitee-deployment.sh"
    ).read_text(encoding="utf-8")

    assert 'rsync --archive "${LAUNCHER}"' in bootstrap
    assert "sha256sum" in bootstrap
    assert "release-from-gitee.sh" in bootstrap
    assert "git ls-remote https://gitee.com/dozybot/Intent.git" in bootstrap
    assert "build-release.sh" not in bootstrap
    assert "remote-release.sh" not in bootstrap
    assert "docker compose" not in bootstrap


def test_github_has_no_actions_workflows():
    workflow_directory = REPOSITORY_ROOT / ".github" / "workflows"

    assert not workflow_directory.exists() or not list(workflow_directory.iterdir())


def test_remote_release_verifies_and_loads_but_never_builds_or_pulls():
    remote = (REPOSITORY_ROOT / "deploy" / "inthub" / "remote-release.sh").read_text(
        encoding="utf-8"
    )

    assert "release_manifest.py\" verify" in remote
    assert "images.tar.gz\" | docker_command load" in remote
    assert "pg_dump" in remote
    assert "--no-build --pull never" in remote
    assert "run --rm --no-deps --pull never app" in remote
    assert "run --rm --no-deps --no-build" not in remote
    assert "smoke.sh" in remote
    assert "rollback_release" in remote
    assert "CANDIDATE_SLOT" in remote
    assert "apps.inthub_api.migrate" in remote
    assert "release source must be the verified Gitee exact Commit" in remote
    assert remote.index('release_manifest.py" verify') < remote.index(
        'mkdir "${RELEASE_LOCK}"'
    )
    assert "write_release_state baking" in remote
    assert "BAKE_SECONDS" in remote
    assert remote.index('chmod u+w "${SCRIPT_DIRECTORY}"') < remote.index(
        'mv "${SCRIPT_DIRECTORY}" "${RELEASE_DIRECTORY}"'
    )
    assert remote.index('mv "${SCRIPT_DIRECTORY}" "${RELEASE_DIRECTORY}"') < remote.index(
        'chmod -R a-w "${RELEASE_DIRECTORY}"'
    )
    assert "restoring the previous traffic boundary" in remote
    assert "git clone" not in remote
    assert "git pull" not in remote
    assert "docker build" not in remote
    assert "docker pull" not in remote


def test_release_scripts_are_executable():
    for name in (
        "bootstrap-gitee-deployment.sh",
        "build-release.sh",
        "prepare-release-env.sh",
        "qualify-release.sh",
        "release.sh",
        "release-from-gitee.sh",
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
    assert verified["bundle_id"] == manifest["git_sha"]


def test_image_config_id_is_portable_across_docker_image_stores():
    reference = "postgres:18.4-bookworm"
    config_digest = "c" * 64

    assert manifest_module._archive_image_config_id(
        _docker_save_stream(reference, config_digest), reference
    ) == f"sha256:{config_digest}"


def test_manifest_rejects_remote_sync_state(tmp_path):
    manifest = _valid_bundle(tmp_path)
    manifest["github_sync"] = "confirmed"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    manifest_module.write_checksums(str(tmp_path))

    with pytest.raises(manifest_module.ManifestError, match="top-level"):
        manifest_module.verify_manifest(str(tmp_path))


def test_manifest_rejects_non_gitee_source_provenance(tmp_path):
    manifest = _valid_bundle(tmp_path)
    manifest["source"]["repository"] = "https://github.com/dozybot001/Intent.git"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    manifest_module.write_checksums(str(tmp_path))

    with pytest.raises(manifest_module.ManifestError, match="Gitee main Commit"):
        manifest_module.verify_manifest(str(tmp_path))


def test_manifest_rejects_non_server_builder(tmp_path):
    manifest = _valid_bundle(tmp_path)
    manifest["build"]["builder"]["name"] = "desktop-linux"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    manifest_module.write_checksums(str(tmp_path))

    with pytest.raises(manifest_module.ManifestError, match="server default Docker Builder"):
        manifest_module.verify_manifest(str(tmp_path))


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

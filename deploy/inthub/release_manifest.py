#!/usr/bin/env python3
"""Create and verify IntHub release bundle manifests.

The helper intentionally depends only on the Python standard library so the
same verifier can run on the build machine and the production host before any
image is loaded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


SCHEMA_VERSION = 4
PROJECT_ID = "inthub"
SOURCE_REPOSITORY = "https://gitee.com/dozybot/Intent.git"
SOURCE_REF = "refs/heads/main"
GIT_SHA_RE = re.compile(r"[0-9a-f]{40,64}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
SAFE_FILENAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
EXPECTED_ARTIFACTS = {
    "source_archive": "source.tar.gz",
    "image_archive": "images.tar.gz",
}
EXPECTED_RELEASE_FILES = (
    "compose.yaml",
    "inthub.caddy",
    "release_manifest.py",
    "remote-release.sh",
    "runtime-images.lock.json",
    "smoke.sh",
)
SECRET_PATTERNS = {
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(
        rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})"
    ),
    "inthub-token": re.compile(rb"ith_pat_[A-Za-z0-9_-]{32,}"),
    "provider-key": re.compile(rb"sk-[A-Za-z0-9_-]{32,}"),
    "aws-access-key": re.compile(rb"AKIA[0-9A-Z]{16}"),
}
MAX_SOURCE_MEMBERS = 20_000
MAX_SOURCE_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
REQUIRED_RECIPE_PATHS = {
    "dockerfile": "Dockerfile",
    "dependency_lock": "pyproject.toml",
    "database_schema": "apps/inthub_api/db.py",
    "database_migration_entry": "apps/inthub_api/migrate.py",
    "runtime_images": "deploy/inthub/runtime-images.lock.json",
}
REQUIRED_TESTS = {
    "pytest",
    "git-diff-check",
    "tracked-secret-scan",
    "image-local-smoke",
}


class ManifestError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_image_config_id(fileobj, reference: str) -> str:
    """Return the portable config digest for one image in a docker-save stream.

    Docker's containerd image store reports an OCI manifest or index digest as
    ``docker image inspect .Id``, while the classic image store reports the
    config digest.  The docker-save Config member is stable across both stores
    and across transfer to the production host.
    """

    manifest_payload = None
    try:
        archive = tarfile.open(fileobj=fileobj, mode="r|*")
    except (tarfile.TarError, OSError) as exc:
        raise ManifestError("image archive is not a readable tar stream") from exc
    with archive:
        for member in archive:
            if member.name != "manifest.json":
                continue
            if not member.isfile():
                raise ManifestError("image archive manifest.json is not a regular file")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ManifestError("could not read image archive manifest.json")
            if manifest_payload is not None:
                raise ManifestError("image archive contains duplicate manifest.json")
            manifest_payload = extracted.read()

    if manifest_payload is None:
        raise ManifestError("image archive is missing manifest.json")
    try:
        manifest = json.loads(manifest_payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError("image archive manifest.json is invalid") from exc
    if not isinstance(manifest, list) or not manifest:
        raise ManifestError("image archive manifest.json must be a non-empty array")

    matches = []
    for entry in manifest:
        if not isinstance(entry, dict):
            raise ManifestError("image archive contains invalid image metadata")
        repo_tags = entry.get("RepoTags")
        if repo_tags is not None and (
            not isinstance(repo_tags, list)
            or any(not isinstance(tag, str) for tag in repo_tags)
        ):
            raise ManifestError("image archive RepoTags must be an array or null")
        if repo_tags and reference in repo_tags:
            matches.append(entry)
    if not matches and len(manifest) == 1:
        matches = [manifest[0]]
    if len(matches) != 1:
        raise ManifestError(f"could not identify exactly one archived image: {reference}")

    config = matches[0].get("Config")
    if not isinstance(config, str):
        raise ManifestError("image archive Config must be a string")
    match = re.fullmatch(r"(?:blobs/sha256/)?([0-9a-f]{64})(?:\.json)?", config)
    if match is None:
        raise ManifestError("image archive Config is not a SHA-256 digest path")
    return f"sha256:{match.group(1)}"


def _docker_image_config_id(reference: str) -> str:
    process = subprocess.Popen(
        ["docker", "image", "save", reference],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        config_id = _archive_image_config_id(process.stdout, reference)
    except Exception:
        process.kill()
        process.wait()
        raise
    stderr = process.stderr.read().decode("utf-8", errors="replace").strip()
    return_code = process.wait()
    if return_code != 0:
        raise ManifestError(
            f"docker image save failed for {reference}: {stderr or f'exit {return_code}'}"
        )
    return config_id


def _regular_file(bundle: Path, name: str) -> Path:
    if SAFE_FILENAME_RE.fullmatch(name) is None or Path(name).name != name:
        raise ManifestError(f"Unsafe bundle filename: {name!r}")
    path = bundle / name
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise ManifestError(f"Missing bundle file: {name}") from exc
    if not stat.S_ISREG(mode):
        raise ManifestError(f"Bundle entry is not a regular file: {name}")
    return path


def _image_metadata(reference: str) -> dict:
    result = subprocess.run(
        ["docker", "image", "inspect", reference],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, list) or len(payload) != 1:
        raise ManifestError(f"Could not inspect exactly one image: {reference}")
    image = payload[0]
    labels = image.get("Config", {}).get("Labels") or {}
    repo_digests = image.get("RepoDigests") or []
    return {
        "reference": reference,
        "id": _docker_image_config_id(reference),
        "os": image.get("Os"),
        "architecture": image.get("Architecture"),
        "repo_digests": sorted(
            digest for digest in repo_digests if isinstance(digest, str)
        ),
        "labels": {
            key: labels[key]
            for key in (
                "org.opencontainers.image.revision",
                "org.opencontainers.image.source",
                "org.opencontainers.image.version",
            )
            if isinstance(labels.get(key), str)
        },
    }


def _runtime_lock(bundle: Path) -> dict:
    path = _regular_file(bundle, "runtime-images.lock.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError("runtime-images.lock.json is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "images"}:
        raise ManifestError("runtime image lock has an invalid top-level schema")
    if payload.get("schema_version") != 1:
        raise ManifestError("runtime image lock schema_version must be 1")
    images = payload.get("images")
    if not isinstance(images, dict) or set(images) != {"database"}:
        raise ManifestError("runtime image lock must contain exactly the database image")
    database = images["database"]
    expected_keys = {"reference", "pull_reference", "id", "os", "architecture"}
    if not isinstance(database, dict) or set(database) != expected_keys:
        raise ManifestError("database runtime image lock has an invalid schema")
    for key in expected_keys:
        _expect_string(database.get(key), f"runtime_images.database.{key}")
    if database["reference"] != "postgres:18.4-bookworm":
        raise ManifestError("database runtime reference must be postgres:18.4-bookworm")
    if re.fullmatch(r"postgres@sha256:[0-9a-f]{64}", database["pull_reference"]) is None:
        raise ManifestError("database pull_reference must use an immutable SHA-256 digest")
    if not database["id"].startswith("sha256:") or SHA256_RE.fullmatch(database["id"][7:]) is None:
        raise ManifestError("database runtime config digest must be SHA-256")
    if database["os"] != "linux" or database["architecture"] != "amd64":
        raise ManifestError("database runtime image must target linux/amd64")
    return database


def _file_record(bundle: Path, name: str) -> dict:
    path = _regular_file(bundle, name)
    return {
        "path": name,
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def _recipe_records(repository: Path) -> dict:
    return {
        key: {
            "path": relative_path,
            "sha256": _sha256(repository / relative_path),
        }
        for key, relative_path in REQUIRED_RECIPE_PATHS.items()
    }


def _migration_recipe_checksum(recipe: dict) -> str:
    digest = hashlib.sha256()
    for key in ("database_schema", "database_migration_entry"):
        record = recipe[key]
        digest.update(record["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(record["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _app_base_image(repository: Path) -> str:
    for line in (repository / "Dockerfile").read_text(encoding="utf-8").splitlines():
        fields = line.strip().split()
        if fields and fields[0].upper() == "FROM" and len(fields) >= 2:
            reference = fields[1]
            if re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._/:+-]*@sha256:[0-9a-f]{64}",
                reference,
            ) is None:
                raise ManifestError("Application base image must use a SHA-256 digest")
            return reference
    raise ManifestError("Dockerfile does not contain a base image")


def create_manifest(args: argparse.Namespace) -> dict:
    bundle = Path(args.bundle).resolve()
    repository = Path(args.repository).resolve()
    if GIT_SHA_RE.fullmatch(args.git_sha) is None:
        raise ManifestError("git_sha must be a full hexadecimal Git object ID")
    if args.database_schema_version < 1:
        raise ManifestError("database_schema_version must be positive")

    app = _image_metadata(args.app_image)
    database = _image_metadata(args.database_image)
    database_lock = _runtime_lock(bundle)
    expected_revision = app["labels"].get("org.opencontainers.image.revision")
    expected_version = app["labels"].get("org.opencontainers.image.version")
    if expected_revision != args.git_sha:
        raise ManifestError("Application image revision label does not match git_sha")
    if expected_version != args.version:
        raise ManifestError("Application image version label does not match version")
    for key in ("reference", "id", "os", "architecture"):
        if database.get(key) != database_lock[key]:
            raise ManifestError(f"Database image does not match runtime lock field: {key}")

    recipe = _recipe_records(repository)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "bundle_id": args.git_sha,
        "git_sha": args.git_sha,
        "dirty": False,
        "version": args.version,
        "source": {
            "transport": "gitee-exact-commit",
            "repository": SOURCE_REPOSITORY,
            "ref": SOURCE_REF,
            "commit": args.git_sha,
        },
        "target": {"os": "linux", "architecture": "amd64"},
        "database_schema": {
            "version": args.database_schema_version,
            "migration_policy": "expand-contract",
            "backward_compatible": True,
            "migration_sha256": _migration_recipe_checksum(recipe),
        },
        "artifacts": {
            key: _file_record(bundle, filename)
            for key, filename in EXPECTED_ARTIFACTS.items()
        },
        "release_files": {
            name: _file_record(bundle, name) for name in EXPECTED_RELEASE_FILES
        },
        "images": {
            "app": app,
            "database": database,
        },
        "build": {
            "builder": {
                "name": args.builder,
                "driver": args.builder_driver,
                "buildx_version": args.buildx_version,
                "buildkit_version": args.buildkit_version,
            },
            "base_images": {
                "app": _app_base_image(repository),
                "database": database_lock["pull_reference"],
            },
            "qualification": {
                "python_version": args.python_version,
                "pytest_version": args.pytest_version,
            },
            "recipe": recipe,
            "built_at": datetime.now(timezone.utc).isoformat(),
        },
        "tests": [
            {"name": "pytest", "result": "passed"},
            {"name": "git-diff-check", "result": "passed"},
            {"name": "tracked-secret-scan", "result": "passed"},
            {"name": "image-local-smoke", "result": "passed"},
        ],
    }
    output = bundle / "manifest.json"
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _expect_dict(value, field: str) -> dict:
    if not isinstance(value, dict):
        raise ManifestError(f"{field} must be an object")
    return value


def _expect_string(value, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{field} must be a non-empty string")
    return value


def _verify_file_record(bundle: Path, record, field: str, expected_name: str) -> None:
    record = _expect_dict(record, field)
    name = _expect_string(record.get("path"), f"{field}.path")
    if name != expected_name:
        raise ManifestError(f"{field}.path must be {expected_name}")
    checksum = _expect_string(record.get("sha256"), f"{field}.sha256")
    if SHA256_RE.fullmatch(checksum) is None:
        raise ManifestError(f"{field}.sha256 must be lowercase SHA-256")
    size = record.get("bytes")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ManifestError(f"{field}.bytes must be a positive integer")
    path = _regular_file(bundle, name)
    if path.stat().st_size != size:
        raise ManifestError(f"Size mismatch for {name}")
    if _sha256(path) != checksum:
        raise ManifestError(f"Checksum mismatch for {name}")


def _verify_image(image, field: str, git_sha: str, version: str) -> None:
    image = _expect_dict(image, field)
    reference = _expect_string(image.get("reference"), f"{field}.reference")
    image_id = _expect_string(image.get("id"), f"{field}.id")
    if not image_id.startswith("sha256:") or SHA256_RE.fullmatch(image_id[7:]) is None:
        raise ManifestError(f"{field}.id must be a sha256 image config digest")
    if image.get("os") != "linux" or image.get("architecture") != "amd64":
        raise ManifestError(f"{field} must target linux/amd64")
    repo_digests = image.get("repo_digests")
    if not isinstance(repo_digests, list) or any(
        not isinstance(digest, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*@sha256:[0-9a-f]{64}", digest) is None
        for digest in repo_digests
    ):
        raise ManifestError(f"{field}.repo_digests must be an array")
    labels = _expect_dict(image.get("labels"), f"{field}.labels")
    if field.endswith(".app"):
        expected_labels = {
            "org.opencontainers.image.revision",
            "org.opencontainers.image.source",
            "org.opencontainers.image.version",
        }
        if set(labels) != expected_labels:
            raise ManifestError("Application image labels must contain the exact OCI evidence set")
        if reference != f"inthub:{git_sha}":
            raise ManifestError("Application image reference must use the full Git SHA")
        if labels.get("org.opencontainers.image.revision") != git_sha:
            raise ManifestError("Application image revision label mismatch")
        if labels.get("org.opencontainers.image.version") != version:
            raise ManifestError("Application image version label mismatch")
        if labels.get("org.opencontainers.image.source") != "https://gitee.com/dozybot/Intent":
            raise ManifestError("Application image source label mismatch")
    elif reference != "postgres:18.4-bookworm":
        raise ManifestError("Database image reference must be postgres:18.4-bookworm")


def _verify_source_recipe(bundle: Path, manifest: dict) -> None:
    source_path = _regular_file(bundle, "source.tar.gz")
    git_sha = manifest["git_sha"]
    prefix = PurePosixPath(f"Intent-{git_sha}")
    expected_content = {
        prefix / relative_path: (key, record)
        for key, relative_path in REQUIRED_RECIPE_PATHS.items()
        for record in (manifest["build"]["recipe"][key],)
    }
    observed_names = set()
    observed_recipe = {}
    member_count = 0
    total_size = 0
    try:
        archive = tarfile.open(source_path, mode="r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise ManifestError("source.tar.gz is not a valid gzip-compressed tar archive") from exc
    with archive:
        for member in archive:
            member_count += 1
            if member_count > MAX_SOURCE_MEMBERS:
                raise ManifestError("source archive contains too many entries")
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not name.parts:
                raise ManifestError(f"source archive contains unsafe path: {member.name}")
            if name in observed_names:
                raise ManifestError(f"source archive contains duplicate path: {member.name}")
            observed_names.add(name)
            if name.parts[0] != str(prefix):
                raise ManifestError("source archive contains an entry outside its commit prefix")
            if member.isdir():
                continue
            if not member.isfile():
                raise ManifestError(f"source archive contains a non-regular entry: {member.name}")
            total_size += member.size
            if total_size > MAX_SOURCE_UNCOMPRESSED_BYTES:
                raise ManifestError("source archive expands beyond the allowed size")
            if name in expected_content:
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ManifestError(f"could not read source recipe file: {member.name}")
                digest = hashlib.sha256()
                for chunk in iter(lambda: extracted.read(1024 * 1024), b""):
                    digest.update(chunk)
                observed_recipe[name] = digest.hexdigest()

    if set(observed_recipe) != set(expected_content):
        raise ManifestError("source archive is missing a required build recipe file")
    for path, (key, record) in expected_content.items():
        if observed_recipe[path] != record["sha256"]:
            raise ManifestError(f"source recipe checksum mismatch: {REQUIRED_RECIPE_PATHS[key]}")
    runtime_checksum = _sha256(_regular_file(bundle, "runtime-images.lock.json"))
    if runtime_checksum != manifest["build"]["recipe"]["runtime_images"]["sha256"]:
        raise ManifestError("bundled runtime image lock does not match the source recipe")


def verify_manifest(bundle_value: str, expected_sha: str | None = None) -> dict:
    bundle = Path(bundle_value).resolve()
    manifest_path = _regular_file(bundle, "manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError("manifest.json is not valid UTF-8 JSON") from exc
    manifest = _expect_dict(manifest, "manifest")

    expected_top_level = {
        "schema_version",
        "project_id",
        "bundle_id",
        "git_sha",
        "dirty",
        "version",
        "source",
        "target",
        "database_schema",
        "artifacts",
        "release_files",
        "images",
        "build",
        "tests",
    }
    if set(manifest) != expected_top_level:
        raise ManifestError("manifest contains missing or unknown top-level fields")

    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(f"Unsupported schema_version: {manifest.get('schema_version')!r}")
    if manifest.get("project_id") != PROJECT_ID:
        raise ManifestError("project_id must be inthub")
    bundle_id = _expect_string(manifest.get("bundle_id"), "bundle_id")
    git_sha = _expect_string(manifest.get("git_sha"), "git_sha")
    if GIT_SHA_RE.fullmatch(git_sha) is None:
        raise ManifestError("git_sha must be a full hexadecimal Git object ID")
    if expected_sha is not None and git_sha != expected_sha:
        raise ManifestError("manifest git_sha does not match the requested release")
    if bundle_id != git_sha:
        raise ManifestError("bundle_id must equal the immutable full Git commit")
    if manifest.get("dirty") is not False:
        raise ManifestError("dirty must be false")
    version = _expect_string(manifest.get("version"), "version")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", version) is None:
        raise ManifestError("version contains unsupported characters")
    source = _expect_dict(manifest.get("source"), "source")
    if source != {
        "transport": "gitee-exact-commit",
        "repository": SOURCE_REPOSITORY,
        "ref": SOURCE_REF,
        "commit": git_sha,
    }:
        raise ManifestError("source must identify the verified Gitee main Commit")
    if manifest.get("target") != {"os": "linux", "architecture": "amd64"}:
        raise ManifestError("target must be linux/amd64")
    database_schema = _expect_dict(
        manifest.get("database_schema"), "database_schema"
    )
    if set(database_schema) != {
        "version",
        "migration_policy",
        "backward_compatible",
        "migration_sha256",
    }:
        raise ManifestError("database_schema contains missing or unknown fields")
    if (
        not isinstance(database_schema.get("version"), int)
        or isinstance(database_schema.get("version"), bool)
        or database_schema["version"] < 1
    ):
        raise ManifestError("database_schema.version must be a positive integer")
    if database_schema.get("migration_policy") != "expand-contract":
        raise ManifestError("database_schema.migration_policy must be expand-contract")
    if database_schema.get("backward_compatible") is not True:
        raise ManifestError("database_schema must be backward compatible")
    migration_sha256 = _expect_string(
        database_schema.get("migration_sha256"),
        "database_schema.migration_sha256",
    )
    if SHA256_RE.fullmatch(migration_sha256) is None:
        raise ManifestError("database_schema.migration_sha256 must be SHA-256")

    artifacts = _expect_dict(manifest.get("artifacts"), "artifacts")
    if set(artifacts) != set(EXPECTED_ARTIFACTS):
        raise ManifestError("artifacts must contain the exact required artifact set")
    for key, filename in EXPECTED_ARTIFACTS.items():
        _verify_file_record(bundle, artifacts.get(key), f"artifacts.{key}", filename)

    release_files = _expect_dict(manifest.get("release_files"), "release_files")
    if set(release_files) != set(EXPECTED_RELEASE_FILES):
        raise ManifestError("release_files must contain the exact required file set")
    for name in EXPECTED_RELEASE_FILES:
        _verify_file_record(bundle, release_files.get(name), f"release_files.{name}", name)

    images = _expect_dict(manifest.get("images"), "images")
    if set(images) != {"app", "database"}:
        raise ManifestError("images must contain exactly app and database")
    _verify_image(images.get("app"), "images.app", git_sha, version)
    _verify_image(images.get("database"), "images.database", git_sha, version)
    database_lock = _runtime_lock(bundle)
    database_image = images["database"]
    for key in ("reference", "id", "os", "architecture"):
        if database_image.get(key) != database_lock[key]:
            raise ManifestError(f"Database manifest does not match runtime lock field: {key}")

    build = _expect_dict(manifest.get("build"), "build")
    if set(build) != {
        "builder",
        "base_images",
        "qualification",
        "recipe",
        "built_at",
    }:
        raise ManifestError("build contains missing or unknown fields")
    builder = _expect_dict(build.get("builder"), "build.builder")
    if set(builder) != {"name", "driver", "buildx_version", "buildkit_version"}:
        raise ManifestError("build.builder contains missing or unknown fields")
    for key in ("name", "driver", "buildx_version", "buildkit_version"):
        _expect_string(builder.get(key), f"build.builder.{key}")
    if builder.get("name") != "default" or builder.get("driver") != "docker":
        raise ManifestError("production Bundle must use the server default Docker Builder")
    base_images = _expect_dict(build.get("base_images"), "build.base_images")
    if set(base_images) != {"app", "database"}:
        raise ManifestError("build.base_images must contain exactly app and database")
    app_base = _expect_string(base_images.get("app"), "build.base_images.app")
    if re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._/:+-]*@sha256:[0-9a-f]{64}", app_base
    ) is None:
        raise ManifestError("build.base_images.app must use a SHA-256 digest")
    if base_images.get("database") != database_lock["pull_reference"]:
        raise ManifestError("build.base_images.database does not match runtime lock")
    qualification = _expect_dict(build.get("qualification"), "build.qualification")
    if set(qualification) != {"python_version", "pytest_version"}:
        raise ManifestError("build.qualification contains missing or unknown fields")
    python_version = _expect_string(
        qualification.get("python_version"), "build.qualification.python_version"
    )
    pytest_version = _expect_string(
        qualification.get("pytest_version"), "build.qualification.pytest_version"
    )
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", python_version) is None:
        raise ManifestError("build.qualification.python_version must be semantic")
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", pytest_version) is None:
        raise ManifestError("build.qualification.pytest_version must be semantic")
    built_at = _expect_string(build.get("built_at"), "build.built_at")
    try:
        parsed_built_at = datetime.fromisoformat(built_at)
    except ValueError as exc:
        raise ManifestError("build.built_at must be ISO-8601") from exc
    if parsed_built_at.tzinfo is None:
        raise ManifestError("build.built_at must include a timezone")
    recipe = _expect_dict(build.get("recipe"), "build.recipe")
    if set(recipe) != set(REQUIRED_RECIPE_PATHS):
        raise ManifestError("build.recipe contains missing or unknown fields")
    for key, expected_path in REQUIRED_RECIPE_PATHS.items():
        record = _expect_dict(recipe.get(key), f"build.recipe.{key}")
        if set(record) != {"path", "sha256"}:
            raise ManifestError(f"build.recipe.{key} contains missing or unknown fields")
        if record.get("path") != expected_path:
            raise ManifestError(f"build.recipe.{key}.path must be {expected_path}")
        checksum = _expect_string(record.get("sha256"), f"build.recipe.{key}.sha256")
        if SHA256_RE.fullmatch(checksum) is None:
            raise ManifestError(f"build.recipe.{key}.sha256 must be SHA-256")
    if _migration_recipe_checksum(recipe) != migration_sha256:
        raise ManifestError("database migration recipe checksum mismatch")
    tests = manifest.get("tests")
    if not isinstance(tests, list) or not tests:
        raise ManifestError("tests must be a non-empty array")
    test_names = set()
    for item in tests:
        if not isinstance(item, dict) or set(item) != {"name", "result"}:
            raise ManifestError("every test record must contain exactly name and result")
        if item.get("result") != "passed" or not isinstance(item.get("name"), str):
            raise ManifestError("every recorded test must have result=passed")
        if item["name"] in test_names:
            raise ManifestError("tests must not contain duplicate names")
        test_names.add(item["name"])
    if test_names != REQUIRED_TESTS:
        raise ManifestError("tests must contain the exact required release checks")
    _verify_source_recipe(bundle, manifest)
    return manifest


def write_checksums(bundle_value: str) -> None:
    bundle = Path(bundle_value).resolve()
    names = [
        *EXPECTED_ARTIFACTS.values(),
        *EXPECTED_RELEASE_FILES,
        "manifest.json",
    ]
    output = bundle / "SHA256SUMS"
    lines = [f"{_sha256(_regular_file(bundle, name))}  {name}" for name in sorted(names)]
    output.write_text("\n".join(lines) + "\n", encoding="ascii")


def verify_checksums(bundle_value: str) -> None:
    bundle = Path(bundle_value).resolve()
    checksum_path = _regular_file(bundle, "SHA256SUMS")
    lines = checksum_path.read_text(encoding="ascii").splitlines()
    expected_names = {
        *EXPECTED_ARTIFACTS.values(),
        *EXPECTED_RELEASE_FILES,
        "manifest.json",
    }
    directory_names = {entry.name for entry in bundle.iterdir()}
    if directory_names != expected_names | {"SHA256SUMS"}:
        raise ManifestError("release bundle contains missing or unexpected directory entries")
    observed_names = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)", line)
        if match is None:
            raise ManifestError("SHA256SUMS contains an invalid line")
        checksum, name = match.groups()
        if name in observed_names:
            raise ManifestError(f"SHA256SUMS contains duplicate entry: {name}")
        observed_names.add(name)
        if _sha256(_regular_file(bundle, name)) != checksum:
            raise ManifestError(f"SHA256SUMS mismatch for {name}")
    if observed_names != expected_names:
        raise ManifestError("SHA256SUMS does not contain the exact release file set")


def scan_source(source_value: str) -> None:
    source = Path(source_value).resolve()
    if not source.is_dir():
        raise ManifestError("source scan target must be a directory")
    findings = []
    for path in sorted(source.rglob("*")):
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError as exc:
            raise ManifestError("source changed while it was being scanned") from exc
        if stat.S_ISLNK(mode):
            target = os.readlink(path).encode("utf-8", errors="surrogateescape")
            payload = target
        elif stat.S_ISREG(mode):
            payload = path.read_bytes()
        elif stat.S_ISDIR(mode):
            continue
        else:
            raise ManifestError(
                f"source contains unsupported file type: {path.relative_to(source)}"
            )
        for pattern_name, pattern in SECRET_PATTERNS.items():
            if pattern.search(payload):
                findings.append(f"{path.relative_to(source)}:{pattern_name}")
    if findings:
        raise ManifestError(
            "tracked source contains credential-like material: " + ", ".join(findings[:20])
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--bundle", required=True)
    create.add_argument("--repository", required=True)
    create.add_argument("--git-sha", required=True)
    create.add_argument("--version", required=True)
    create.add_argument("--database-schema-version", required=True, type=int)
    create.add_argument("--builder", required=True)
    create.add_argument("--builder-driver", required=True)
    create.add_argument("--buildx-version", required=True)
    create.add_argument("--buildkit-version", required=True)
    create.add_argument("--python-version", required=True)
    create.add_argument("--pytest-version", required=True)
    create.add_argument("--app-image", required=True)
    create.add_argument("--database-image", required=True)

    checksums = subparsers.add_parser("checksums")
    checksums.add_argument("--bundle", required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--bundle", required=True)
    verify.add_argument("--expected-sha")

    scan = subparsers.add_parser("scan")
    scan.add_argument("--source", required=True)

    image_config_id = subparsers.add_parser("image-config-id")
    image_config_id.add_argument("--reference", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            manifest = create_manifest(args)
        elif args.command == "checksums":
            write_checksums(args.bundle)
            manifest = verify_manifest(args.bundle)
            verify_checksums(args.bundle)
        elif args.command == "verify":
            manifest = verify_manifest(args.bundle, args.expected_sha)
            verify_checksums(args.bundle)
        elif args.command == "scan":
            scan_source(args.source)
            print(json.dumps({"ok": True, "result": {"scan": "passed"}}))
            return 0
        else:
            print(_archive_image_config_id(sys.stdin.buffer, args.reference))
            return 0
    except (ManifestError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {"ok": False, "error": {"code": "INVALID_RELEASE_BUNDLE", "message": str(exc)}},
                ensure_ascii=False,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "result": {
                    "bundle_id": manifest["bundle_id"],
                    "git_sha": manifest["git_sha"],
                    "version": manifest["version"],
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

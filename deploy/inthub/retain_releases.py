#!/usr/bin/env python3
"""Keep the serving IntHub release, the one it replaced and the newest three.

Runs after an accepted release. Every other release directory goes, together
with its leftover bundle in incoming/, its stopped containers and its
inthub:<sha> image. A release whose image a running container uses is kept.
Only inthub:<sha> tags are removed: base images, other products' images and
the build cache are never pruned. An older Commit can be rebuilt from Gitee.
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

KEEP_NEWEST = 3
SHA = re.compile(r"[0-9a-f]{40,64}")
LEFTOVER = re.compile(r"([0-9a-f]{40,64})(?:-.+)?")
STOPPED = {"created", "exited", "dead"}


def docker(*args):
    return subprocess.run(["sudo", "-n", "docker", *args], check=True, capture_output=True, text=True).stdout


def _size(path):
    total = 0
    for directory, _, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(directory, name)).st_size
            except OSError:
                pass
    return total


def _remove_tree(path):
    # Releases are made read-only once solidified; their directories need write access to be emptied.
    if path.is_dir() and not path.is_symlink():
        for directory, _, _ in os.walk(path):
            os.chmod(directory, os.stat(directory).st_mode | stat.S_IWUSR | stat.S_IXUSR)
        shutil.rmtree(path)
    else:
        path.unlink()


def keep_set(releases_root, current, previous, keep=KEEP_NEWEST):
    releases = sorted((path for path in releases_root.iterdir()
                       if path.is_dir() and not path.is_symlink() and SHA.fullmatch(path.name)),
                      key=lambda path: path.stat().st_mtime, reverse=True)
    kept = {path.name for path in releases[:keep]}
    for path in (current, previous):
        if path and Path(path).resolve().parent == releases_root.resolve():
            kept.add(Path(path).name)
    return releases, kept


def retain(root, current, previous, run=docker, keep=KEEP_NEWEST, dry_run=False):
    """Remove what the rule does not keep. Returns (report, warnings); never raises for one failed removal."""
    root = Path(root)
    releases, kept = keep_set(root / "releases", current, previous, keep)
    containers = [line.split("\t") for line in run("ps", "--all", "--no-trunc", "--format",
                                                   "{{.ID}}\t{{.Image}}\t{{.State}}").splitlines() if line]
    in_use = {image for _, image, state in containers if state not in STOPPED}
    tagged = set()
    for line in run("image", "ls", "--format", "{{.Repository}}:{{.Tag}}", "inthub").splitlines():
        repository, _, tag = line.partition(":")
        if repository == "inthub" and SHA.fullmatch(tag):
            tagged.add(tag)
    # A running container's release stays, whatever its age.
    kept |= {sha for sha in tagged | {path.name for path in releases} if f"inthub:{sha}" in in_use}
    report = {"releases": 0, "containers": 0, "images": 0, "leftovers": 0, "bytes": 0}
    warnings = []

    def attempt(action, label, *args):
        if dry_run:
            return True
        try:
            action(*args)
            return True
        except (OSError, subprocess.CalledProcessError) as exc:
            warnings.append(f"could not remove {label}: {getattr(exc, 'stderr', '') or exc}".strip())
            return False

    for sha in sorted(tagged - kept):
        for container_id, image, _ in containers:
            if image == f"inthub:{sha}":
                report["containers"] += attempt(run, f"container {container_id[:12]}", "rm", container_id)
        report["images"] += attempt(run, f"image inthub:{sha}", "image", "rm", f"inthub:{sha}")
    for path in releases:
        if path.name not in kept:
            size = _size(path)
            if attempt(_remove_tree, f"release {path.name}", path):
                report["releases"] += 1
                report["bytes"] += size
    incoming = root / "incoming"
    for path in sorted(incoming.iterdir()) if incoming.is_dir() else []:
        match = LEFTOVER.fullmatch(path.name)
        if match and match.group(1) not in kept:
            size = _size(path)
            if attempt(_remove_tree, f"leftover bundle {path.name}", path):
                report["leftovers"] += 1
                report["bytes"] += size
    return report, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", default="")
    parser.add_argument("--dry-run", action="store_true", help="report what would go, remove nothing")
    args = parser.parse_args(argv)
    try:
        report, warnings = retain(args.root, args.current, args.previous, dry_run=args.dry_run)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"WARNING: IntHub release retention skipped: {exc}", file=sys.stderr)
        return 0
    for warning in warnings:
        print(f"WARNING: IntHub release retention {warning}", file=sys.stderr)
    print("IntHub release retention {verb} {releases} releases, {leftovers} leftover bundles, {images} images "
          "and {containers} stopped containers, {mib} MiB of release files.".format(
        verb="would remove" if args.dry_run else "removed", mib=report["bytes"] // 2**20, **report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

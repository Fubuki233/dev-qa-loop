#!/usr/bin/env python3
"""Export a scoped cumulative patch without changing Git's index or creating commits."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from qa_common import ToolError, emit


def git(repo: Path, args: list[str], allowed: tuple[int, ...] = (0,)) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-c", "color.ui=false", "-C", str(repo), *args],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ToolError("Git unavailable or snapshot command timed out") from error
    if result.returncode not in allowed:
        raise ToolError(f"Git snapshot command failed ({result.returncode}); check paths and HEAD")
    return result.stdout


def selected_paths(values: list[str]) -> list[str]:
    paths = []
    for value in values:
        path = PurePosixPath(value)
        if path.is_absolute() or not path.parts or any(p in {"..", ".git"} for p in path.parts):
            raise ValueError("Select relative paths, excluding .git and parent traversal")
        paths.append(str(path))
    return sorted(set(paths))


def patch_for(repo: Path, paths: list[str]) -> bytes:
    specs = [f":(literal){path}" for path in paths]
    raw = git(repo, ["diff", "--raw", "--ignore-submodules=none", "HEAD", "--", *specs])
    if any(b"160000" in line.split(b"\t", 1)[0] for line in raw.splitlines()):
        raise ToolError("Submodule changes need a separate commit-based handoff")
    patch = git(
        repo,
        [
            "diff",
            "--binary",
            "--no-ext-diff",
            "--no-textconv",
            "--no-renames",
            "HEAD",
            "--",
            *specs,
        ],
    )
    untracked = git(repo, ["ls-files", "--others", "--exclude-standard", "-z", "--", *specs])
    for raw_path in sorted(filter(None, untracked.split(b"\0"))):
        relative = os.fsdecode(raw_path)
        file = repo / relative
        if file.is_dir() and not file.is_symlink():
            raise ToolError("Nested repositories/directories need a separate handoff")
        patch += git(
            repo,
            [
                "diff",
                "--no-index",
                "--binary",
                "--no-ext-diff",
                "--no-textconv",
                "--",
                "/dev/null",
                relative,
            ],
            allowed=(0, 1),
        )
    return patch


def identity(manifest: dict[str, Any]) -> str:
    fields = {key: manifest[key] for key in ("base_sha", "patch_sha256", "paths")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def capture(repo: Path, output: Path, paths: list[str]) -> dict[str, Any]:
    repo = Path(os.fsdecode(git(repo, ["rev-parse", "--show-toplevel"])).strip()).resolve()
    paths = selected_paths(paths)
    base = git(repo, ["rev-parse", "HEAD"]).decode().strip()
    patch = patch_for(repo, paths)
    # Detect edits during capture, including content edits that leave porcelain status unchanged.
    if base != git(repo, ["rev-parse", "HEAD"]).decode().strip() or patch != patch_for(repo, paths):
        raise ToolError("Source changed during capture; pause edits and publish a new snapshot")
    manifest: dict[str, Any] = {
        "version": 1,
        "base_sha": base,
        "source_worktree": str(repo),
        "paths": paths,
        "patch_sha256": hashlib.sha256(patch).hexdigest(),
        "patch_bytes": len(patch),
    }
    manifest["snapshot_id"] = identity(manifest)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    with (output / "changes.patch").open("xb") as stream:
        stream.write(patch)
    with (output / "snapshot.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return manifest


def verify(directory: Path) -> dict[str, Any]:
    manifest = json.loads((directory / "snapshot.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ValueError("Unsupported snapshot manifest")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", str(manifest.get("base_sha", ""))):
        raise ValueError("Invalid snapshot base SHA")
    paths = manifest.get("paths")
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
        raise ValueError("Invalid snapshot paths")
    if selected_paths(paths) != paths:
        raise ValueError("Snapshot paths are not canonical")
    patch = (directory / "changes.patch").read_bytes()
    if (
        hashlib.sha256(patch).hexdigest() != manifest.get("patch_sha256")
        or len(patch) != manifest.get("patch_bytes")
        or identity(manifest) != manifest.get("snapshot_id")
    ):
        raise ValueError("Snapshot integrity check failed")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("capture", help="Export selected changes relative to HEAD")
    export.add_argument("--repo", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True, help="New snapshot directory")
    export.add_argument("--path", action="append", required=True, dest="paths")
    check = commands.add_parser("verify", help="Verify an exported snapshot without applying it")
    check.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = (
            capture(args.repo, args.output, args.paths)
            if args.command == "capture"
            else verify(args.snapshot)
        )
        emit(data)
        return 0
    except (OSError, ValueError, KeyError, ToolError) as error:
        emit({"status": "error", "message": str(error)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

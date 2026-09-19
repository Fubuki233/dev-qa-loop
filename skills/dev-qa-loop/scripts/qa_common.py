"""Small, read-only GitHub helpers shared by the QA commands (stdlib only)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class ToolError(Exception):
    """An actionable error without dumping subprocess output or credentials."""


def repo_slug(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise ValueError("--repo must be an owner/repository slug")
    return value


def full_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", value):
        raise ValueError("--head must be a full commit SHA")
    return value.lower()


def gh_env() -> dict[str, str]:
    return {**os.environ, "GH_PROMPT_DISABLED": "1", "GH_PAGER": "cat", "NO_COLOR": "1"}


def gh_json(args: list[str], timeout: float = 30) -> Any:
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            env=gh_env(),
            timeout=max(0.001, timeout),
            check=False,
        )
    except FileNotFoundError as error:
        raise ToolError("GitHub CLI gh is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise ToolError("GitHub CLI request timed out") from error
    if result.returncode:
        raise ToolError(
            f"GitHub CLI exited {result.returncode}; check gh auth status and repository access"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ToolError("GitHub CLI returned invalid JSON") from error


def write_json(path: Path | None, data: dict[str, Any]) -> None:
    """Atomically replace this caller-owned report; never follow a destination symlink."""
    if path is None:
        return
    if path.is_symlink():
        raise ToolError("Report destination must not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def emit(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, sort_keys=True), flush=True)

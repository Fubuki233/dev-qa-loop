#!/usr/bin/env python3
"""Collect run/attempt metadata; optionally save bounded failure logs locally."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from qa_common import ToolError, emit, gh_env, gh_json, repo_slug, write_json

BAD = {"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale"}
FIELDS = "databaseId,headSha,headBranch,event,attempt,status,conclusion,url,workflowName,jobs"


def summarize(run: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(run, dict) or not isinstance(run.get("jobs"), list):
        raise ToolError("Run response is missing jobs")
    required = ("databaseId", "headSha", "attempt", "status", "conclusion", "url")
    if any(key not in run for key in required):
        raise ToolError("Run response is missing version/attempt fields")
    if type(run["attempt"]) is not int or run["attempt"] < 1:
        raise ToolError("Run response has an invalid attempt")
    for job in run["jobs"]:
        if not isinstance(job, dict) or not isinstance(job.get("steps", []), list):
            raise ToolError("Run response contains invalid jobs")
        if not all(isinstance(step, dict) for step in job.get("steps", [])):
            raise ToolError("Run response contains invalid steps")
    report = {key: run.get(key) for key in (*required, "event", "headBranch", "workflowName")}
    report["failed_jobs"] = [
        {
            "id": job.get("databaseId"),
            "name": job.get("name"),
            "url": job.get("url"),
            "conclusion": job.get("conclusion"),
            "failed_steps": [
                {
                    "name": step.get("name"),
                    "number": step.get("number"),
                    "conclusion": step.get("conclusion"),
                }
                for step in job.get("steps", [])
                if str(step.get("conclusion", "")).lower() in BAD
            ],
        }
        for job in run["jobs"]
        if str(job.get("conclusion", "")).lower() in BAD
    ]
    return report


def save_logs(repo: str, run_id: int, attempt: int, path: Path, max_bytes: int) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    # A temporary spool prevents large logs from filling model context or RAM.
    with tempfile.TemporaryFile() as spool:
        try:
            result = subprocess.run(
                [
                    "gh",
                    "run",
                    "view",
                    str(run_id),
                    "--repo",
                    repo,
                    "--attempt",
                    str(attempt),
                    "--log-failed",
                ],
                stdout=spool,
                stderr=subprocess.PIPE,
                env=gh_env(),
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ToolError("Failure logs unavailable; metadata is still available") from error
        if result.returncode:
            raise ToolError(f"Failure log request exited {result.returncode}; metadata retained")
        total = spool.tell()
        spool.seek(max(0, total - max_bytes))
        data = spool.read(max_bytes)
    # Exclusive creation avoids clobbering prior evidence or following a symlink.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
    return {
        "path": str(path.resolve()),
        "bytes": len(data),
        "truncated": total > max_bytes,
        "empty": total == 0,
        "may_contain_sensitive_data": True,
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.output and args.log_output and args.output.resolve() == args.log_output.resolve():
        raise ValueError("Metadata and log output must use different files")
    run = gh_json(
        [
            "run",
            "view",
            str(args.run),
            "--repo",
            args.repo,
            "--json",
            FIELDS,
        ]
    )
    report = summarize(run)
    report["repo"] = args.repo
    if report["databaseId"] != args.run:
        raise ToolError("GitHub returned a different run ID")
    # Pin metadata and logs to the same attempt even if another attempt starts concurrently.
    pinned = summarize(
        gh_json(
            [
                "run",
                "view",
                str(args.run),
                "--repo",
                args.repo,
                "--attempt",
                str(report["attempt"]),
                "--json",
                FIELDS,
            ]
        )
    )
    if any(pinned[key] != report[key] for key in ("databaseId", "headSha", "attempt")):
        raise ToolError("Run identity changed while collecting the pinned attempt")
    report.update(pinned)
    report["collection_status"] = "collected"
    code = 0
    if args.log_output:
        try:
            report["logs"] = save_logs(
                args.repo,
                args.run,
                report["attempt"],
                args.log_output,
                args.max_log_bytes,
            )
        except (OSError, ToolError) as error:
            report["logs"] = {"error": str(error)}
            code = 2
    write_json(args.output, report)
    return report, code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run", required=True, type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--log-output", type=Path)
    parser.add_argument("--max-log-bytes", type=int, default=262144)
    args = parser.parse_args()
    try:
        args.repo = repo_slug(args.repo)
        if args.run <= 0 or not 1 <= args.max_log_bytes <= 2_097_152:
            raise ValueError("Use a positive run ID and max-log-bytes in 1..2097152")
        report, code = collect(args)
        emit(report)
        return code
    except (OSError, ValueError, ToolError) as error:
        emit({"status": "error", "message": str(error)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Wait for PR checks on one fixed head; never treat absent checks as a pass."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from qa_common import ToolError, emit, full_sha, gh_json, repo_slug, write_json

EXIT = {
    "passed": 0,
    "failed": 1,
    "error": 2,
    "timeout": 3,
    "superseded": 4,
    "cancelled": 5,
    "inactive": 6,
    "needs_review": 7,
    "pending": 8,
}


def check_result(check: dict[str, Any]) -> dict[str, str]:
    if check.get("__typename") == "StatusContext":
        name = check.get("context", "")
        state = str(check.get("state", "")).upper()
        result = {
            "SUCCESS": "passed",
            "PENDING": "pending",
            "EXPECTED": "pending",
            "ERROR": "failed",
            "FAILURE": "failed",
        }.get(state, "unknown")
        url = check.get("targetUrl", "")
    else:
        name = check.get("name", "")
        status = str(check.get("status", "")).upper()
        state = str(check.get("conclusion") or "").upper()
        if status in {"QUEUED", "IN_PROGRESS", "WAITING", "PENDING", "REQUESTED"}:
            result = "pending"
        elif status == "COMPLETED":
            result = {
                "SUCCESS": "passed",
                "FAILURE": "failed",
                "TIMED_OUT": "failed",
                "ACTION_REQUIRED": "failed",
                "STARTUP_FAILURE": "failed",
                "STALE": "failed",
                "CANCELLED": "cancelled",
                "SKIPPED": "skipped",
                "NEUTRAL": "skipped",
            }.get(state, "unknown")
        else:
            result = "unknown"
        url = check.get("detailsUrl", "")
    return {"name": str(name), "result": result, "conclusion": state, "url": str(url or "")}


def evaluate(
    pr: dict[str, Any],
    expected_head: str,
    expected: list[str],
    allowed_skips: list[str],
) -> dict[str, Any]:
    if not isinstance(pr, dict) or not isinstance(pr.get("headRefOid"), str):
        raise ToolError("PR response is missing headRefOid")
    report: dict[str, Any] = {
        "pr": pr.get("number"),
        "url": pr.get("url"),
        "expected_head": expected_head,
        "actual_head": pr["headRefOid"],
        "expected_checks": sorted(set(expected)),
        "checks": [],
        "missing_checks": [],
        "allowed_skips": [],
    }
    if pr["headRefOid"].lower() != expected_head:
        report["status"] = "superseded"
        return report
    if pr.get("state") != "OPEN":
        report["status"] = "inactive" if pr.get("state") in {"CLOSED", "MERGED"} else "needs_review"
        return report
    raw = pr.get("statusCheckRollup") or []
    if not isinstance(raw, list) or not all(isinstance(c, dict) for c in raw):
        raise ToolError("PR response contains invalid checks")
    checks = sorted((check_result(c) for c in raw), key=lambda c: (c["name"], c["url"]))
    selected = [c for c in checks if not expected or c["name"] in expected]
    missing = sorted(set(expected) - {c["name"] for c in selected})
    report.update(checks=checks, missing_checks=missing)
    results = set()
    for check in selected:
        result = check["result"]
        if result == "skipped" and check["name"] in allowed_skips:
            report["allowed_skips"].append(check["name"])
            result = "passed"
        results.add(result)
    if "failed" in results:
        status = "failed"
    elif "cancelled" in results:
        status = "cancelled"
    elif missing or not selected or "pending" in results:
        status = "pending"
    elif results - {"passed"}:
        status = "needs_review"
    else:
        status = "passed"
    report["status"] = status
    return report


def observe(args: argparse.Namespace) -> int:
    deadline = time.monotonic() + args.timeout
    last = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            report = {**(last or {}), "status": "timeout"}
        else:
            try:
                pr = gh_json(
                    [
                        "pr",
                        "view",
                        str(args.pr),
                        "--repo",
                        args.repo,
                        "--json",
                        "number,url,state,headRefOid,statusCheckRollup",
                    ],
                    timeout=min(30, remaining),
                )
                report = evaluate(pr, args.head, args.expect_check, args.allow_skipped)
                report["repo"] = args.repo
                if time.monotonic() >= deadline:
                    report["status"] = "timeout"
            except ToolError as error:
                report = {
                    "repo": args.repo,
                    "pr": args.pr,
                    "expected_head": args.head,
                    "status": "timeout" if time.monotonic() >= deadline else "error",
                    "message": str(error),
                }
        write_json(args.output, report)
        if report != last:
            emit(report)
        if report["status"] != "pending" or args.once:
            return EXIT[report["status"]]
        last = report
        time.sleep(min(args.interval, max(0, deadline - time.monotonic())))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--head", required=True)
    parser.add_argument("--expect-check", action="append", default=[])
    parser.add_argument("--allow-skipped", action="append", default=[])
    parser.add_argument("--interval", type=float, default=30)
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        args.repo, args.head = repo_slug(args.repo), full_sha(args.head)
        if not 1 <= args.interval <= 60 or not 0 < args.timeout <= 86400 or args.pr <= 0:
            raise ValueError("Use interval 1..60s, timeout 0..86400s, and a positive PR")
        return observe(args)
    except (OSError, ValueError, ToolError) as error:
        emit({"status": "error", "message": str(error)})
        return 2
    except KeyboardInterrupt:
        emit({"status": "interrupted"})
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

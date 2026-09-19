"""Behavioral regression tests: real temporary Git repos and fixture GitHub responses."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "dev-qa-loop" / "scripts"
sys.path.insert(0, str(SCRIPTS))
snapshot = importlib.import_module("snapshot")
watch = importlib.import_module("watch_checks")
collect = importlib.import_module("collect_failures")
common = importlib.import_module("qa_common")

HEAD = "a" * 40
OTHER = "b" * 40


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "QA Fixture",
            "GIT_AUTHOR_EMAIL": "qa@example.test",
            "GIT_COMMITTER_NAME": "QA Fixture",
            "GIT_COMMITTER_EMAIL": "qa@example.test",
        },
    ).stdout


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    repo.mkdir()
    git(repo, "init", "--initial-branch=main")
    (repo / "src").mkdir()
    (repo / "src/module.py").write_text("value = 1\n")
    (repo / "src/deleted.txt").write_text("remove this\n")
    (repo / "src/data.bin").write_bytes(b"\0\1\2\3")
    (repo / "other.txt").write_text("unrelated\n")
    (repo / ".gitignore").write_text("*.secret\n")
    git(repo, "add", ".")
    git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-m", "Fixture baseline")
    return repo


def test_snapshot_preserves_index_and_roundtrips_new_deleted_binary_files(
    repository: Path,
    tmp_path: Path,
) -> None:
    repo = repository
    (repo / "src/module.py").write_text("value = 2\n")
    git(repo, "add", "src/module.py")
    (repo / "src/module.py").write_text("value = 3\n")
    (repo / "src/new file.py").write_text("new = True\n")
    (repo / "src/data.bin").write_bytes(b"\0new\xff\0")
    (repo / "src/new.bin").write_bytes(b"\0\xff\0new")
    (repo / "src/deleted.txt").unlink()
    (repo / "src/hidden.secret").write_text("must not be exported")
    (repo / "other.txt").write_text("unrelated changed\n")
    index_before = (repo / ".git/index").read_bytes()
    out = tmp_path / "snapshot"
    manifest = snapshot.capture(repo, out, ["src"])
    assert snapshot.verify(out) == manifest
    assert (repo / ".git/index").read_bytes() == index_before
    assert b"must not be exported" not in (out / "changes.patch").read_bytes()
    qa = tmp_path / "qa"
    git(tmp_path, "clone", "--no-hardlinks", str(repo), str(qa))
    (qa / "qa_test.py").write_text("# QA work in progress\n")
    git(qa, "apply", "--check", str(out / "changes.patch"))
    git(qa, "apply", str(out / "changes.patch"))
    assert (qa / "src/module.py").read_text() == "value = 3\n"
    assert (qa / "src/new file.py").exists()
    assert (qa / "src/data.bin").read_bytes() == b"\0new\xff\0"
    assert (qa / "src/new.bin").read_bytes() == b"\0\xff\0new"
    assert not (qa / "src/deleted.txt").exists()
    assert (qa / "other.txt").read_text() == "unrelated\n"
    (repo / "src/module.py").write_text("value = 4\n")
    newer = tmp_path / "snapshot2"
    snapshot.capture(repo, newer, ["src"])
    git(qa, "apply", "--reverse", "--check", str(out / "changes.patch"))
    git(qa, "apply", "--reverse", str(out / "changes.patch"))
    git(qa, "apply", str(newer / "changes.patch"))
    assert (qa / "src/module.py").read_text() == "value = 4\n"
    assert (qa / "qa_test.py").read_text() == "# QA work in progress\n"


def test_literal_path_selection_and_immutable_output(repository: Path, tmp_path: Path) -> None:
    (repository / "src/[ab].txt").write_text("selected\n")
    (repository / "src/a.txt").write_text("excluded\n")
    out = tmp_path / "snapshot"
    snapshot.capture(repository, out, ["src/[ab].txt"])
    original = (out / "changes.patch").read_bytes()
    assert b"selected" in original and b"excluded" not in original
    with pytest.raises(FileExistsError):
        snapshot.capture(repository, out, ["src"])
    assert (out / "changes.patch").read_bytes() == original
    (out / "changes.patch").write_bytes(original + b"tampered")
    with pytest.raises(ValueError, match="integrity"):
        snapshot.verify(out)


@pytest.mark.parametrize("path", [".", "../src", "/tmp/src", ".git/config", "src/../../x"])
def test_snapshot_rejects_unbounded_paths(path: str) -> None:
    with pytest.raises(ValueError):
        snapshot.selected_paths([path])


def test_empty_snapshot_and_cli(repository: Path, tmp_path: Path) -> None:
    out = tmp_path / "empty"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "snapshot.py"),
            "capture",
            "--repo",
            str(repository),
            "--output",
            str(out),
            "--path",
            "src",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["patch_bytes"] == 0
    assert snapshot.verify(out)["patch_bytes"] == 0


def test_source_change_rejects_publication(
    repository: Path, tmp_path: Path, monkeypatch: Any
) -> None:
    patches = iter([b"first", b"second"])
    monkeypatch.setattr(snapshot, "patch_for", lambda *args: next(patches))
    with pytest.raises(common.ToolError, match="changed during capture"):
        snapshot.capture(repository, tmp_path / "unstable", ["src"])
    assert not (tmp_path / "unstable").exists()


def check(name: str = "quality", conclusion: str = "SUCCESS", status: str = "COMPLETED") -> dict:
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "detailsUrl": "https://github.com/o/r/actions/runs/12",
    }


def pr(checks: list | None = None, head: str = HEAD, state: str = "OPEN") -> dict:
    return {
        "number": 42,
        "url": "https://github.com/o/r/pull/42",
        "headRefOid": head,
        "state": state,
        "statusCheckRollup": checks,
    }


@pytest.mark.parametrize(
    ("checks", "expected", "allowed", "status"),
    [
        ([], [], [], "pending"),
        ([check()], ["quality", "docker-build"], [], "pending"),
        ([check()], ["quality"], [], "passed"),
        ([check(), check(conclusion="FAILURE")], ["quality"], [], "failed"),
        ([check(conclusion="CANCELLED")], [], [], "cancelled"),
        ([check(conclusion="SKIPPED")], [], [], "needs_review"),
        ([check(conclusion="NEUTRAL")], [], [], "needs_review"),
        ([check(conclusion="SKIPPED")], [], ["quality"], "passed"),
        ([check(conclusion="", status="IN_PROGRESS")], [], [], "pending"),
        ([check(conclusion="TIMED_OUT")], [], [], "failed"),
        ([check(conclusion="FUTURE_STATE")], [], [], "needs_review"),
        ([check(), check(name="optional", conclusion="SKIPPED")], ["quality"], [], "passed"),
        (
            [{"__typename": "StatusContext", "context": "legacy", "state": "ERROR"}],
            [],
            [],
            "failed",
        ),
    ],
)
def test_check_states(checks: list, expected: list, allowed: list, status: str) -> None:
    assert watch.evaluate(pr(checks), HEAD, expected, allowed)["status"] == status


def test_old_head_and_closed_pr_never_pass() -> None:
    assert watch.evaluate(pr([check()], OTHER), HEAD, [], [])["status"] == "superseded"
    assert watch.evaluate(pr([check()], state="MERGED"), HEAD, [], [])["status"] == "inactive"


def args(tmp_path: Path, **extra: Any) -> argparse.Namespace:
    return argparse.Namespace(
        **{
            "repo": "o/r",
            "pr": 42,
            "head": HEAD,
            "expect_check": ["quality"],
            "allow_skipped": [],
            "timeout": 10,
            "interval": 2,
            "once": False,
            "output": tmp_path / "ci.json",
            **extra,
        }
    )


def install_clock(monkeypatch: Any) -> list[float]:
    now = [0.0]
    monkeypatch.setattr(watch.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(watch.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now


def test_watch_deduplicates_and_follows_fixed_head(
    tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    install_clock(monkeypatch)
    responses = iter([pr([]), pr([]), pr([check()], head=OTHER)])
    monkeypatch.setattr(watch, "gh_json", lambda *a, **kw: next(responses))
    assert watch.observe(args(tmp_path)) == 4
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [event["status"] for event in events] == ["pending", "superseded"]
    assert json.loads((tmp_path / "ci.json").read_text())["actual_head"] == OTHER


def test_missing_checks_timeout_and_once(tmp_path: Path, monkeypatch: Any) -> None:
    install_clock(monkeypatch)
    monkeypatch.setattr(watch, "gh_json", lambda *a, **kw: pr([]))
    assert watch.observe(args(tmp_path, timeout=3)) == 3
    assert watch.observe(args(tmp_path, once=True)) == 8


def test_late_success_cannot_override_deadline(tmp_path: Path, monkeypatch: Any) -> None:
    now = install_clock(monkeypatch)

    def late(*a: Any, **kw: Any) -> dict:
        now[0] += 11
        return pr([check()])

    monkeypatch.setattr(watch, "gh_json", late)
    assert watch.observe(args(tmp_path)) == 3


def test_gh_failure_does_not_leak_stderr(monkeypatch: Any) -> None:
    def fail(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args, 1, "", "secret-auth-header")

    monkeypatch.setattr(common.subprocess, "run", fail)
    with pytest.raises(common.ToolError) as caught:
        common.gh_json(["pr", "view", "42"])
    assert "secret-auth-header" not in str(caught.value)


def run_data(attempt: int = 2) -> dict:
    return {
        "databaseId": 12,
        "headSha": HEAD,
        "attempt": attempt,
        "status": "completed",
        "conclusion": "failure",
        "url": "https://github.com/o/r/actions/runs/12",
        "headBranch": "feature",
        "event": "pull_request",
        "workflowName": "CI",
        "jobs": [
            {
                "databaseId": 99,
                "name": "unit",
                "conclusion": "failure",
                "url": "job-url",
                "steps": [
                    {"name": "Setup", "number": 1, "conclusion": "success"},
                    {"name": "Test", "number": 2, "conclusion": "failure"},
                ],
            }
        ],
    }


def test_collect_pins_attempt_and_preserves_failure_metadata(
    tmp_path: Path, monkeypatch: Any
) -> None:
    calls = []

    def fetch(arguments: list[str]) -> dict:
        calls.append(arguments)
        return run_data()

    monkeypatch.setattr(collect, "gh_json", fetch)
    options = argparse.Namespace(repo="o/r", run=12, output=tmp_path / "run.json", log_output=None)
    report, code = collect.collect(options)
    assert code == 0 and report["conclusion"] == "failure"
    assert report["collection_status"] == "collected"
    assert report["failed_jobs"][0]["failed_steps"] == [
        {"name": "Test", "number": 2, "conclusion": "failure"},
    ]
    assert "--attempt" in calls[1] and calls[1][calls[1].index("--attempt") + 1] == "2"


def test_collect_rejects_attempt_drift(tmp_path: Path, monkeypatch: Any) -> None:
    responses = iter([run_data(2), run_data(3)])
    monkeypatch.setattr(collect, "gh_json", lambda *args: next(responses))
    with pytest.raises(common.ToolError, match="identity changed"):
        collect.collect(argparse.Namespace(repo="o/r", run=12, output=None, log_output=None))


def test_logs_are_bounded_private_and_never_overwritten(tmp_path: Path, monkeypatch: Any) -> None:
    def logs(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        assert "--attempt" in arguments
        kwargs["stdout"].write(b"sensitive-log-payload")
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(collect.subprocess, "run", logs)
    output = tmp_path / "failure.log"
    report = collect.save_logs("o/r", 12, 2, output, max_bytes=7)
    assert report["truncated"] and output.read_bytes() == b"payload"
    assert output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        collect.save_logs("o/r", 12, 2, output, max_bytes=7)
    assert output.read_bytes() == b"payload"


def test_log_failure_preserves_run_report(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(collect, "gh_json", lambda *a: run_data())

    def fail(*args: Any) -> None:
        raise common.ToolError("Logs unavailable")

    monkeypatch.setattr(collect, "save_logs", fail)
    output = tmp_path / "run.json"
    report, code = collect.collect(
        argparse.Namespace(
            repo="o/r",
            run=12,
            output=output,
            log_output=tmp_path / "failure.log",
            max_log_bytes=200,
        )
    )
    assert code == 2 and report["conclusion"] == "failure"
    assert json.loads(output.read_text())["logs"]["error"] == "Logs unavailable"


def test_report_symlink_preserves_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("existing")
    link = tmp_path / "report"
    link.symlink_to(target)
    with pytest.raises(common.ToolError):
        common.write_json(link, {"status": "passed"})
    assert target.read_text() == "existing"

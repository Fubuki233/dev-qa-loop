# CI observation and diagnosis

English | [简体中文](../locales/zh-CN/ci.md) | [日本語](../locales/ja/ci.md)

Requires Python 3.10+, GitHub CLI `gh`, and an existing login. No GitHub App installation or comments.
The helpers reuse gh, adding pinned heads, missing-check handling, and change-only output; no other
skill is required. Logs are supported for GitHub Actions only; preserve URLs for external checks.

## Watch a specific PR version

```bash
gh pr view '<PR-number>' --repo '<owner/repo>' --json headRefOid
python3 '<skill-dir>/scripts/watch_checks.py' \
  --repo '<owner/repo>' --pr '<PR-number>' --head '<full-SHA>' \
  --expect-check quality --expect-check docker-build \
  --timeout 1800 --interval 30 --output '<task-state-dir>/ci.json'
```

Repeat `--expect-check` to name gates. When specified, only those gates determine the result, but the
report includes all checks. Without it, evaluate the current rollup; no checks never means success.
Wait for missing expected checks. Skipped/neutral checks require review by default; add
`--allow-skipped '<check-name>'` only when that skip is accepted. Every same-named check must qualify.
Verify branch protection and actual project gates before delivery; the script does not configure or infer them.

Each query reads head and rollup from the same PR response; a changed head returns `superseded`.
Do not equate the PR test merge SHA with its head SHA; diagnostic reports retain the actual run SHA.
Scripts do not call models and emit JSON lines only on state changes and exit.

Use host-supported background processes and retain their handles. Wait at most 60 seconds per tool
call and continue independent work. Avoid frequent model-driven gh polling. `--once` queries once;
`--timeout` bounds observation, and each gh request is capped by the remaining time and 30 seconds.

| Exit | Meaning |
| --- | --- |
| 0 | Selected gates passed; disclose explicitly allowed skips |
| 1 | Selected gates failed |
| 2 | Argument, authentication, network, or data error |
| 3 | Timeout; not success |
| 4 | PR head changed; evidence is stale |
| 5 | Selected checks cancelled |
| 6 | PR closed/merged; observation ended without proving CI success |
| 7 | Skipped, neutral, or unknown status needs review |
| 8 | `--once` found pending or missing checks |

## Collect failures

Take the GitHub Actions run ID from the failed check URL, verifying its repository. Do not select the
branch's latest run: it may belong to another commit. By default, collect metadata only:

```bash
python3 '<skill-dir>/scripts/collect_failures.py' \
  --repo '<owner/repo>' --run '<run-id>' \
  --output '<task-state-dir>/run-<run-id>.json'
```

Reports retain run ID, actual head SHA, event, branch, attempt, conclusion, failed jobs/steps, and URL.
Associate the run through the PR check link; for a test merge SHA, verify the run's PR association.
Before another repair, confirm the PR head still matches the observed version.

Add `--log-output '<local-log-path>'` if failure logs are needed. The script pins the attempt, writes
a bounded local file with mode 0600, marks truncation, and **does not print logs to stdout**.
Logs may contain secrets/personal data; do not commit, upload, or forward them verbatim to the main
agent. Return only necessary sanitized summaries. Report log-download failures separately; never
convert them into success. The script neither downloads artifacts nor reruns workflows.
Collector exit code 0 means collection succeeded, not CI success; read the report's `conclusion`.

CI evidence does not replace local acceptance. This version observes PR checks; use the project's
existing operations workflow for deployment. Cross-session wake-up requires an external host scheduler.

# Snapshots and handoff

English | [简体中文](../locales/zh-CN/handoff.md) | [日本語](../locales/ja/handoff.md)

Run scripts with `python3`. `<skill-dir>` is the absolute directory containing the entrypoint `SKILL.md`.
Replace and quote placeholders before running examples; never concatenate task text into shell code.

## Coordination records

Create `.agents/dev-qa-loop/<task-id>/` in the shared repository associated with the Git common dir.
Only the main agent maintains `state.json`, writing a temporary file and replacing it atomically after each handoff:

```json
{
  "task_id": "feature-notifications",
  "contract_version": 1,
  "phase": "parallel",
  "main_assignment": "<assignment-id>",
  "qa_assignment": "<another-assignment-id>",
  "qa_agent_id": "<host-returned-id>",
  "qa_model_requested": "<selected-model-id; null when inheriting>",
  "qa_model_actual": null,
  "qa_reasoning_effort": null,
  "qa_model_reason": "<task, capability, latency, and budget rationale>",
  "language": "en",
  "main_worktree": "<absolute-path>",
  "qa_worktree": "<another-absolute-path>",
  "implementation_paths": ["src/notifications.py"],
  "test_paths": ["tests/test_notifications.py"],
  "latest_snapshot": "<snapshot-directory-or-commit-sha>",
  "qa_state_file": "<QA-owned-state-file>",
  "last_qa_report": "<QA-owned-report-file>",
  "repair_round": 0,
  "max_repair_rounds": 3,
  "pr": null,
  "expected_pr_head": null,
  "ci_process_handle": null,
  "authorized_actions": ["local implementation", "isolated tests"],
  "next_action": "<specific-next-action>"
}
```

Use `language` values `en` (default), `zh-CN`, or `ja`.
Use phases `contract / parallel / validating / integrating / watching_ci / needs_input / complete`.
Record actual authorization; the example grants none. On resume, check whether agents/processes remain
alive before starting another worker. If an agent cannot be resumed across sessions, explicitly take
ownership of the existing assignment before creating a replacement; preserve completed work.

QA alone maintains `qa-state.json`: `applied_snapshot_id`, `applied_snapshot_path`, `base_sha`,
`test_process_handle`, `phase`, and the last report path. Update applied fields only after successful
application. The main record's `latest_snapshot` is the published version, potentially ahead of QA;
never use it to reverse the previous patch. Reconcile QA state with actual implementation paths on
resume. If uncertain, preserve the worktree and coordinate rather than guessing a baseline.

## Initial QA message

```text
You own tests for this task. Requested model: <selected model ID or host default>;
only the host can confirm the actual model. Report language: <en / zh-CN / ja>.
Model choice rationale: <brief explanation>.
Read <project AGENTS.md>; restore your independent assignment/worktree: <path, branch, ID>.
Requirements/specification: <file or concise content>; contract version: 1.
Interfaces, error behavior, acceptance cases: <details>.
Writable paths: <tests and fixtures>; the main agent owns product implementation.
Start designing cases and writing tests while the main agent implements and prepares snapshots.
Validation commands/environment: <project-specific choices>.
Mark missing implementation as waiting_implementation; report completed tests and next steps, without implementing product code.
Write results to your own <report path>, send a brief summary, and do not modify coordination state.json.
```

Choose a host-supported model and reasoning effort for the task; user choices and budgets take precedence.
Set native dispatch parameters, for example `task_name="qa"`, `model="<selected-model-id>"`,
`reasoning_effort="<supported-effort>"`, `fork_turns="none"`, omitting fields the host does not support.
Use null for `qa_model_requested` when inheriting the default, `qa_model_actual` when the host does not
report it, and `qa_reasoning_effort` when unset. A requested model is not verified runtime identity.
Keep legacy `qa_model` only as historical information, not proof of the actual model.
Before replacing QA, save tests/reports, stop the old writer, and transfer its assignment without losing work.

This uses the native host, not a new model API. The main agent continues development after dispatch.
QA may idle after designing cases; use host follow-up/resume for the next snapshot instead of file polling.

## Publish uncommitted implementation

Select only the smallest task-owned paths; never package the entire repository, secrets, `.env`, or
another person's changes. Pause edits to selected source paths during capture. Each output must be a new directory:

```bash
python3 '<skill-dir>/scripts/snapshot.py' capture \
  --repo '<implementation-worktree>' --output '<task-state-dir>/snapshots/001' \
  --path src/notifications.py --path src/contracts.py
```

Output: `snapshot.json` and `changes.patch`. The identifier binds the base commit, patch, and selected
paths. Renames appear as delete/add; ignored new files are omitted, and Git does not track empty directories.
The source index remains unchanged. Hand off submodule changes through separate commits.

Send the contract version, absolute snapshot path, `snapshot_id`, and implemented/pending behaviors.
QA verifies before applying:

```bash
python3 '<skill-dir>/scripts/snapshot.py' verify --snapshot '<snapshot-dir>'
git -C '<QA-worktree>' status --short
git -C '<QA-worktree>' rev-parse HEAD
git -C '<QA-worktree>' apply --check '<snapshot-dir>/changes.patch'
git -C '<QA-worktree>' apply '<snapshot-dir>/changes.patch'
```

First verify QA's implementation baseline matches the manifest's `base_sha`. Test edits/commits may
exist, but product paths must still match that baseline. Do not apply an empty patch. The script verifies
snapshot integrity; it neither verifies the target worktree baseline nor applies the patch.

Snapshots from the same HEAD are **cumulative patches**. Before replacing one, QA verifies it has not
edited implementation paths, runs `git apply --reverse --check` on the previously applied patch, reverses
it only after that check passes, and then applies the new patch. Do not stack cumulative patches.
If the baseline changed, implementation paths were modified, or a check fails, preserve the worktree
and resolve ownership/conflicts. Do not reset, stash, overwrite tests, or rebuild the worktree.
The project's coordinating agent serializes branch merges/integration for commit-based handoffs.

Apply, test, and report serially in a QA worktree. Queue snapshots while tests run; switch only after
reporting or orderly test shutdown. Read the applied snapshot ID from QA state for each round; do not
replace it with a newly received ID while tests are running.

## QA reports and integration

Bind each report to the contract version, snapshot ID (or implementation commit), test version/patch,
commands, exit codes, and evidence paths. Classify results:

- `passed`: specified behavior passed on this snapshot; list uncovered/unexecuted checks.
- `waiting_implementation`: agreed behavior is still missing; not completion.
- `product_defect`: contract violation with a minimal reproduction.
- `test_defect`: fixture/assertion/harness problem; fix tests before rerunning.
- `environment_blocked` / `flaky`: environmental evidence or instability; one green run is not a resolution.

The main agent imports only QA-owned tests, never reapplies the implementation snapshot to its own
branch. Without commit authorization, QA also uses snapshot.py with **test paths only** to export a
patch. Validate the final combined version with affected checks and record it; do not reuse interim QA evidence.

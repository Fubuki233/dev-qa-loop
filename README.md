# dev-qa-loop

English (default) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

A Codex skill for parallel implementation and test development, immutable code handoffs,
and GitHub Actions feedback. The main agent selects a suitable QA model for each task;
no particular model is required.

Skill entrypoint: [skills/dev-qa-loop/SKILL.md](skills/dev-qa-loop/SKILL.md).

## Features

- Contract-based implementation and QA ownership in separate branches and worktrees.
- Uncommitted code snapshots, including selected new/binary files, without changing the Git index.
- Results tied to the applied snapshot, with cumulative patch replacement and interruption recovery.
- PR checks pinned to a head SHA, distinguishing failure, cancellation, skipped/missing checks, timeout, and new commits.
- Failure collection for a specific run/attempt, with optional local raw logs.

Scripts require Python 3.10+ and Git; CI tools also require authenticated `gh`.
Parallel execution uses the Codex host's subagent capability. The skill does not install a model service
or independently authorize pushes, merges, or deployments.

## Install and use

Ask Codex's built-in installer to install the skill for your user:

```text
$skill-installer Install skills/dev-qa-loop from Fubuki233/dev-qa-loop.
```

Public repository: https://github.com/Fubuki233/dev-qa-loop.
Start a new session if needed to discover the installation across projects. Reinstall to update,
or link a local checkout during development (replace the path; do not overwrite an existing target):

```bash
mkdir -p .agents/skills
ln -s /absolute/path/to/dev-qa-loop/skills/dev-qa-loop .agents/skills/dev-qa-loop
```

### Automatic activation

`policy.allow_implicit_invocation: true` allows Codex to match ordinary development requests without
an explicit `$dev-qa-loop` mention. For example, “Implement a paginated API” or “Fix duplicate sends
on retry” can start parallel QA when tests can progress independently. Read-only questions, documentation,
cosmetic edits, and trivial changes skip the parallel workflow. User workflow choices take precedence.

The host selects skills from their descriptions; activation is not guaranteed for every development
message. Codex detects skill updates automatically; restart if an update does not appear. This does not
provide cross-session wake-up. See [official skill documentation](https://developers.openai.com/codex/skills/).

### Model selection and language

The main agent chooses among host-supported QA models and reasoning settings based on task complexity,
required capabilities, latency, and known cost/budget. Explicit user model and budget constraints take
precedence. If selection is unsupported, QA inherits the host default and reports that limitation.
The handoff records the requested model separately from any model actually reported by the host.

English is the default for documentation and UI metadata. Reports follow an explicit language request,
then the conversation language (English, Chinese, or Japanese), with English as the fallback. Commands,
JSON fields, and status values stay stable across languages; the CLI's machine-readable output remains English.

Explicit invocation:

```text
$dev-qa-loop Implement a paginated API; choose a suitable QA model, write tests in parallel, and track PR CI.
```

Without commit authorization, use patch handoffs. Without a PR, complete local validation and report
CI as not run. Target-project `AGENTS.md`, requirements, and validation rules take precedence.
Read the Mailfly reference only for Mailfly; the scripts and tests have no Mailfly dependency.

## Development and validation

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/mypy
```

Tests use temporary Git repositories and GitHub fixtures, without live GitHub requests or API keys.
See [handoff details](skills/dev-qa-loop/references/handoff.md) for script usage.
GitHub Actions runs these checks on pushes and pull requests with Python 3.10 and 3.13.

Maintain English, Chinese, and Japanese documentation together. The installed skill has one discovery
entrypoint; localized guides under `locales/` are references, not additional skills. Read only the needed language.

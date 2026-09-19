# Mailfly integration

English | [简体中文](../locales/zh-CN/mailfly.md) | [日本語](../locales/ja/mailfly.md)

Read only when the target repository is Mailfly. The checked-out project's `AGENTS.md` is authoritative.

- Read `documentation/agent-workflow.md`: main and QA each have independent branches/worktrees under
  `.agents/worktrees/` and shared `.agents/assignments/` bindings. The shared root is for coordination
  and read-only inspection. Resume the same task after compaction; keep records in shared `.agents/dev-qa-loop/`.
- Use `python3 scripts/agent_context.py <affected-path>...` to select required documents and checks.
  Read existing Spec Kit artifacts as needed; do not regenerate specs/plans/tasks just for this skill.
- Visual-only changes need visual evidence; interactions need a minimal user path. Identity/permissions/
  redirects require real clicks and rejection paths for all four identities, recorded in
  `documentation/click-flow-qa.md`. Database/RLS/locking semantics require isolated PostgreSQL.
- Read `documentation/tender-implementation-rules.md` before protected tender paths. Follow
  `documentation/monitoring-alerting.md` for new runtime components or exception/alert behavior.
- Run integration tests in each worktree's isolated environment. Do not use deprecated `make testenv-*`;
  staging is read-only for diagnosis. The coordinator serializes merges, migrations, and deployments.
- PR gates are usually `quality` and `docker-build`; verify current workflows and branch policies.
  Deployment follows work-branch PR → main → staging PR → CI.
- This skill is maintained in the independent dev-qa-loop repository and used through installation or
  a discovery link. Mailfly's project skill installer does not manage it. Edit and validate it in its own repository.

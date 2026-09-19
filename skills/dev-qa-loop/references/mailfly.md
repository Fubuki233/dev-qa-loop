# Mailfly 接入

仅在目标仓库是 Mailfly 时读取。规则来源是目标 checkout 的 `AGENTS.md`。

- 先读 `documentation/agent-workflow.md`：主 Agent 与 QA 各有 `.agents/worktrees/`
  下的独立目录/分支及共享 `.agents/assignments/` 绑定；共享主目录只做协调/只读检查。
  压缩恢复延续原任务。协调数据放共享 `.agents/dev-qa-loop/`。
- 用 `python3 scripts/agent_context.py <受影响路径>...` 选择必读文档与检查；
  已有 Spec Kit 文件按需读取，不为本技能重新生成 spec/plan/tasks。
- 纯视觉改动提供视觉证据；交互提供最小用户路径；身份/权限/回跳涉及四身份真实点击
  和拒绝路径，更新 `documentation/click-flow-qa.md`。数据库/RLS/锁语义使用独立 PostgreSQL。
- 招投标受保护路径先读 `documentation/tender-implementation-rules.md`；
  新运行组件或异常/告警行为依 `documentation/monitoring-alerting.md` 接入。
- 本地集成使用各自 worktree 隔离环境，禁用废弃的 `make testenv-*`；staging 只读诊断。
  合并、迁移和部署由协调 Agent 串行处理。
- PR CI 汇总门禁通常为 `quality`、`docker-build`，使用前核对当前工作流和分支策略。
  部署仍走工作分支 PR → main → staging PR → CI。
- 本技能由独立的 dev-qa-loop 仓库维护，通过安装或发现链接使用；
  Mailfly 的项目技能安装器不管理此技能来源。修改和验证在技能自己的仓库执行。

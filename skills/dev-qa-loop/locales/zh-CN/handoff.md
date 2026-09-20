# 快照与交接

[English](../../references/handoff.md) | 简体中文 | [日本語](../ja/handoff.md)

脚本用 `python3` 执行，`<skill-dir>` 指当前 `SKILL.md` 所在绝对目录。
执行前替换并引用示例占位符；不要把任务文本拼接成 shell 代码。

## 协调记录

在 Git common dir 对应共享仓库下创建 `.agents/dev-qa-loop/<task-id>/`。
主 Agent 单独维护 `state.json`，先写临时文件再原子替换，每次消息/交接后更新：

```json
{
  "task_id": "feature-notifications",
  "contract_version": 1,
  "phase": "parallel",
  "main_assignment": "<assignment-id>",
  "qa_assignment": "<另一个assignment-id>",
  "qa_agent_id": "<宿主返回的ID>",
  "qa_model_requested": "<所选模型ID；继承默认时为null>",
  "qa_model_actual": null,
  "qa_reasoning_effort": null,
  "qa_cost_basis": null,
  "qa_escalation_reason": null,
  "qa_upgrade_count": 0,
  "qa_upgrade_limit": 1,
  "qa_model_reason": "<具体子任务、较便宜备选及能力依据>",
  "language": "en",
  "main_worktree": "<绝对路径>",
  "qa_worktree": "<另一个绝对路径>",
  "implementation_paths": ["src/notifications.py"],
  "test_paths": ["tests/test_notifications.py"],
  "latest_snapshot": "<快照目录或提交SHA>",
  "qa_state_file": "<QA独占的状态文件>",
  "last_qa_report": "<QA独占的报告文件>",
  "repair_round": 0,
  "max_repair_rounds": 3,
  "pr": null,
  "expected_pr_head": null,
  "ci_process_handle": null,
  "authorized_actions": ["local implementation", "isolated tests"],
  "next_action": "<具体下一步>"
}
```

`language` 使用 `en`（默认）、`zh-CN` 或 `ja`。
phase 使用 `contract / parallel / validating / integrating / watching_ci / needs_input / complete`。
记录真实已获授权的动作；示例不是权限授予。恢复时检查 Agent 和进程是否仍存活，
不能仅凭记录再开一个相同 worker。跨会话无法恢复原 Agent 时，明确接管旧绑定后才新建 QA；
复用既有工作成果，不重建整个任务。

QA 单独维护 `qa-state.json`，记录 `applied_snapshot_id`、`applied_snapshot_path`、
`base_sha`、`test_process_handle`、`phase` 和最后报告路径。成功应用后才更新 applied 字段。
主记录的 latest_snapshot 是已发布版本，可能比 QA 已应用版本更新，不能拿它来撤销旧 patch。
恢复时先核验 QA 状态与实际实现路径；状态不明就保留现场并协调，不能猜测基线。

## 首次 QA 消息

```text
你负责本任务的测试。请求模型：<所选模型ID或宿主默认>；实际模型仅以宿主报告为准。
报告语言：<en / zh-CN / ja>；模型选择原因：<简述>。
先读 <项目AGENTS.md>，恢复独立 assignment/worktree：<路径、分支、ID>。
需求/规格：<文件或简短内容>；契约版本：1。
接口、错误行为、验收案例：<具体内容>。
可写路径：<测试及fixture路径>；业务实现归主Agent。
开始设计用例并编写测试；主Agent正在并行实现，稍后发送代码快照。
验证命令及环境：<按项目选择>。
缺少实现时标记 waiting_implementation，报告已完成测试和下一步，不去实现业务代码。
结果写到你独占的 <报告路径>，回传精简摘要；不要修改协调 state.json。
```

优先选择宿主支持、能胜任子任务的最低成本模型和足够的最低推理强度，用户指定及预算约束优先。
`qa_model_reason` 记录具体子任务和考虑过的较便宜候选；`qa_cost_basis` 记录宿主/用户成本依据，没有则记未知。
初始选择更强模型或升级时，在 `qa_escalation_reason` 记录能力缺口及较便宜候选的局限，不能只写“质量更好”；无需升级时为 null。
`qa_upgrade_count` 累计模型/推理强度升级次数，替换 Agent 不重置它或修复轮次。`qa_upgrade_limit` 默认 1，
之后由主 Agent 接手或缩小困难部分。初始直接选强模型仍需证据；用户明确指定的模型优先，并把该要求记为理由。
产品缺陷、CI 红灯、未实现、环境/认证故障不是升级依据。价格可记未知；经济型/轻量标签是启发信息，不是已验证价格。
这些记录约束决策；脚本不负责强制执行选模或金额限制。
使用原生派发工具的实际参数，例如 `task_name="qa"`、`model="<所选模型ID>"`、
`reasoning_effort="<宿主支持的强度>"`、`fork_turns="none"`，按宿主能力省略不支持的字段。
继承宿主默认时 `qa_model_requested` 记为 null；宿主不公开实际模型时 `qa_model_actual` 保持 null。
不要把请求型号当作已核验的实际型号。没有设置推理强度时 `qa_reasoning_effort` 也为 null。
旧记录的 `qa_model` 仅保留作历史信息，不能自动证明实际运行型号。
切换 Agent 前保存测试/报告、停止旧写入者并移交绑定，不丢弃已有成果。
这不是需要安装的新 API。主 Agent 派发后继续开发；QA 暂时完成用例设计时允许空闲，
下一快照用宿主 follow-up/resume 能力唤醒同一 Agent，不让它自行轮询文件。

## 发布未提交实现

只选择本任务拥有的最小路径，不能把整个仓库、Secret、`.env` 或别人的修改打包进去。
源工作区在捕获期间停止修改这些路径。每次输出必须是新目录：

```bash
python3 '<skill-dir>/scripts/snapshot.py' capture \
  --repo '<开发worktree>' --output '<任务状态目录>/snapshots/001' \
  --path src/notifications.py --path src/contracts.py
```

输出 `snapshot.json` 和 `changes.patch`。标识绑定基线提交、patch 和选择路径。
rename 按删除/新增表示；ignored 新文件不会进入 patch，空目录不受 Git 管理。
源工作区 index 不变；submodule 改动走独立的提交交接。

发送契约版本、快照绝对路径、`snapshot_id`、已可测试/尚未实现的行为。
QA 首先核验文件：

```bash
python3 '<skill-dir>/scripts/snapshot.py' verify --snapshot '<快照目录>'
git -C '<QA-worktree>' status --short
git -C '<QA-worktree>' rev-parse HEAD
git -C '<QA-worktree>' apply --check '<快照目录>/changes.patch'
git -C '<QA-worktree>' apply '<快照目录>/changes.patch'
```

先核对 QA 实现基线与 manifest 的 `base_sha` 相符；测试可以有自己的修改或提交，
但业务路径必须仍对应基线。空 patch 不需要 `git apply`。
脚本只核验快照完整性，不保证目标 worktree 基线，也不负责应用。

同一 HEAD 导出的快照是**累计 patch**。更换时，QA 确认没有自行修改实现路径，
对上一份 patch 执行 `git apply --reverse --check`，通过后再 reverse，最后应用新 patch。
不能在上一快照上直接叠加新累计 patch。若基线变了、实现路径被修改或检查失败，
保留现场并协调冲突；不要 reset、stash、覆盖测试或重建 worktree。
提交方式交接的分支合并/集成由项目指定协调 Agent 串行处理。

同一个 QA worktree 的应用、测试、报告必须串行。测试进程未结束时先排队快照，
完成报告或有序停止测试后再切换。每轮从 QA 状态中读取实际应用的快照 ID，
不能在测试运行期间更新为刚收到的新 ID。

## QA 报告与整合

每份报告绑定契约版本、快照 ID（或实现 commit）、测试版本/patch 摘要、
命令、退出码和证据路径。结果分类：

- `passed`：本快照指定行为通过；列出未覆盖/未执行项。
- `waiting_implementation`：约定尚未实现的行为，不是最终完成。
- `product_defect`：契约不满足，提供最小复现。
- `test_defect`：fixture、断言或 harness 问题，先修测试再复跑。
- `environment_blocked` / `flaky`：环境证据或不稳定表现；偶尔一次绿灯不算解决。

主 Agent 只接收 QA 拥有的测试改动，不把用于测试的实现快照再次应用到主分支。
未授权提交时，QA 也用 snapshot.py **仅选择测试路径**发布 patch。
最后在包含两者的版本上运行受影响检查，记录最终版本，不能沿用中间 QA 报告。

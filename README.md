# dev-qa-loop

面向 Codex 的独立 skill：主模型开发功能，`gpt-5.6-luna` 并行编写测试，
通过明确的代码快照交接，并跟进 GitHub Actions 检查。

技能入口：[skills/dev-qa-loop/SKILL.md](skills/dev-qa-loop/SKILL.md)。

## 能做什么

- 按接口契约分配开发与 QA 工作，各自使用独立分支和 worktree。
- 导出未提交的代码快照，包含选定范围内的新文件和二进制变更，不修改 Git index。
- 把测试结果绑定到实际应用的快照，支持累计 patch 替换和中断恢复。
- 固定 PR head 观察 CI，区分失败、取消、跳过、缺失检查、超时和新提交。
- 采集指定 run/attempt 的失败信息；原始日志可选保存在本地。

运行脚本需要 Python 3.10+ 和 Git；CI 工具还需要已登录的 `gh`。
并行执行由 Codex 宿主的子 Agent 能力提供；模型不可用时会明确报告。
本仓库不安装后台模型服务，也不会自动推送、合并或部署。

## 安装与使用

在 Codex 中使用内置 skill-installer 安装到用户级技能目录：

```text
$skill-installer 从 Fubuki233/dev-qa-loop 的 skills/dev-qa-loop 目录安装技能。
```

仓库公开地址：https://github.com/Fubuki233/dev-qa-loop 。
安装完成后开启新会话，即可在不同项目中调用。更新时需重新安装或使用下面的本地开发链接。

本地开发时，在目标项目根目录创建指向仓库检出的符号链接
（将路径替换成实际位置；目标已存在时先核对，不要覆盖）：

```bash
mkdir -p .agents/skills
ln -s /absolute/path/to/dev-qa-loop/skills/dev-qa-loop .agents/skills/dev-qa-loop
```

### 自动启用

已启用 `policy.allow_implicit_invocation: true`。安装后可直接提出需要测试的开发需求，
不必每次输入 `$dev-qa-loop`。例如“实现分页查询接口”或“修复重试导致重复发送”，
在存在可独立推进的 QA 工作时，Codex 可自动选择本技能，让 Luna 同步编写测试。
解释问题、仅改文档/样式和简单小改动不启动并行工作线；用户指定的执行方式优先。

自动匹配由 Codex 根据 skill 的 description 判断，并非每条开发消息都会强制启动。
Codex 会自动检测技能变更；更新未出现时重启 Codex。此机制不提供会话结束后的自动唤醒。
配置依据：[OpenAI 官方技能文档](https://developers.openai.com/codex/skills/)。

显式调用示例（需要明确指定本技能时使用）：

```text
$dev-qa-loop 实现分页查询 API，主模型开发，Luna 同步写测试，按快照验证并跟进 PR CI。
```

没有提交授权时用 patch 交接；没有 PR 时完成本地验证并说明 CI 未执行。
目标项目已有的 `AGENTS.md`、需求文档和验证约定优先。Mailfly 的接入参考仅在目标是
Mailfly 时读取，脚本和测试不依赖 Mailfly。

## 开发与验证

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/mypy
```

测试使用临时 Git 仓库和 GitHub 响应 fixture，不访问真实 GitHub，不需要 API Key。
脚本参数和交接约定见技能内的 [参考文档](skills/dev-qa-loop/references/handoff.md)。

GitHub Actions 在 push 和 pull request 时运行上述检查，覆盖 Python 3.10 和 3.13。

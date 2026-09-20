# dev-qa-loop

[English (default)](README.md) | 简体中文 | [日本語](README.ja.md)

面向 Codex 的独立 skill：主 Agent 开发功能，QA 子 Agent 并行编写测试，
通过明确的代码快照交接，并跟进 GitHub Actions 检查。主 Agent 优先选择能胜任任务的最低成本 QA 模型，不固定某个型号。

技能入口：[SKILL.md（英文）](skills/dev-qa-loop/SKILL.md)；[中文使用指南](skills/dev-qa-loop/locales/zh-CN/guide.md)。

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
在存在可独立推进的 QA 工作时，Codex 可自动选择本技能，让 QA 同步编写测试。
解释问题、仅改文档/样式和简单小改动不启动并行工作线；用户指定的执行方式优先。

自动匹配由 Codex 根据 skill 的 description 判断，并非每条开发消息都会强制启动。
Codex 会自动检测技能变更；更新未出现时重启 Codex。此机制不提供会话结束后的自动唤醒。
配置依据：[OpenAI 官方技能文档](https://developers.openai.com/codex/skills/)。

### 模型选择与语言

先选择已知能胜任 QA 子任务的最低成本可用模型和足够的最低推理强度。常规测试与 CI 摘要从经济型模型开始。
初始选择更强模型或中途升级，都需要具体能力缺口及较便宜候选无法胜任的理由；CI 红灯、产品缺陷或泛称任务复杂均不够。
每个 QA assignment 默认最多一次自动模型/推理强度升级，之后由主 Agent 接手或缩小困难部分。
替换 QA 不重置次数，普通工作不同时启动多个模型比答案。

依据宿主成本信息或用户提供的排序；只知道经济型/轻量标签时用作启发式选择，价格记为未知，不编造价格或节省金额。
用户指定的模型及预算优先。交接记录保存较便宜的备选、选模理由、升级证据，并区分请求模型与宿主报告的实际模型。
宿主不能选模时，仅在符合用户约束的情况下继承默认模型并说明限制。
这些是选模规则；硬金额上限需要宿主的用量统计和限制机制，skill 本身不能保证不超支。

文档和 UI 元数据默认使用英文。报告优先遵从用户指定语言，其次使用当前对话的英文、中文或日文，
没有语言信号时回退到英文。命令、JSON 字段和状态值保持一致，CLI 的机器可读输出仍为英文。

显式调用示例（需要明确指定本技能时使用）：

```text
$dev-qa-loop 实现分页查询 API，主模型开发，优先选择能胜任的最低成本 QA 模型并行写测试，按快照验证并跟进 PR CI。
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
脚本参数和交接约定见技能内的 [参考文档](skills/dev-qa-loop/locales/zh-CN/handoff.md)。

GitHub Actions 在 push 和 pull request 时运行上述检查，覆盖 Python 3.10 和 3.13。

中、英、日文档应同步维护。安装目录只有一个技能发现入口，`locales/` 下是语言参考文档；使用时只读取所需语言。

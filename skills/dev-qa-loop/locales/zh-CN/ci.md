# CI 观察与诊断

[English](../../references/ci.md) | 简体中文 | [日本語](../ja/ci.md)

依赖 Python 3.10+、GitHub CLI `gh` 和现有登录。不安装 GitHub App，不发送评论。
复用 gh 取数据，额外处理固定 head、缺失门禁和状态变化，不要求安装其他技能。
只支持 GitHub Actions 日志，外部检查保留 URL。

## 观察指定 PR 版本

```bash
gh pr view '<PR号>' --repo '<owner/repo>' --json headRefOid
python3 '<skill-dir>/scripts/watch_checks.py' \
  --repo '<owner/repo>' --pr '<PR号>' --head '<完整SHA>' \
  --expect-check quality --expect-check docker-build \
  --timeout 1800 --interval 30 --output '<任务状态目录>/ci.json'
```

`--expect-check` 可重复；指定时只以这些门禁决定结果，报告仍包含全部检查。
不指定时检查当前 rollup 全部检查；没有任何检查不能算通过。
缺失的预期门禁继续等待。跳过/neutral 单独列出，默认需要审查；
确认允许跳过时才加 `--allow-skipped '<检查名>'`。同名多项检查都必须满足要求。
交付前核对分支保护和项目实际门禁，脚本不自行配置或推测必需检查。

每次查询在同一 PR 响应读取 head 和 rollup，head 变化返回 superseded。
不把 PR 测试 merge SHA 强行等同于 head SHA；诊断报告保留 run 的实际 SHA。
脚本没有调用模型的逻辑，只在状态变化和退出时输出 JSON 行。

使用宿主支持的后台进程并保存句柄；单次工具等待不超过 60 秒，其间继续独立工作。
不要通过模型频繁调用 gh。`--once` 做一次查询；`--timeout` 是观察截止时间，
每个 gh 调用也受剩余时间和 30 秒上限约束。

| 退出码 | 含义 |
| --- | --- |
| 0 | 所选门禁通过，注明显式允许的跳过项 |
| 1 | 所选门禁失败 |
| 2 | 参数、认证、网络或数据错误 |
| 3 | 等待超时，不能视为通过 |
| 4 | PR head 更新，证据已过期 |
| 5 | 所选检查被取消 |
| 6 | PR 已关闭/合并，结束观察但不证明通过 |
| 7 | 跳过、neutral 或未知状态，需要审查 |
| 8 | --once 时仍在运行或缺少门禁 |

## 提取失败

从 watcher 失败检查 URL 取得 GitHub Actions run ID，检查 URL 仓库。
不要取分支“最近一次运行”，它可能属于别的提交。默认只取元数据：

```bash
python3 '<skill-dir>/scripts/collect_failures.py' \
  --repo '<owner/repo>' --run '<run-id>' \
  --output '<任务状态目录>/run-<run-id>.json'
```

报告保留 run ID、实际 head SHA、event、branch、attempt、结论、失败 job/step 和 URL。
用 PR 检查链接关联该 run；若 SHA 是合并测试提交，核验运行的 PR 关联。
重新修复前再核对 PR head 仍是观察目标。

需要失败日志时追加 `--log-output '<本地日志路径>'`。脚本固定 attempt，
保存权限 0600 的本地文件，**不打印日志到 stdout**；限量保留，截断会标注。
日志可能仍含 Secret/个人数据：不要提交、上传或原样发给主模型，只回传必要且脱敏的摘要。
日志拉取失败单独报告，不能因此标记通过。脚本不下载制品、不重跑任务。
采集脚本退出码 0 只表示采集成功，CI 结论必须读取报告的 `conclusion`。

CI 证据不替代本地验收。此版本观察 PR checks；部署跟进用项目已有运维技能。
跨会话唤醒需要外部宿主，本技能不安装调度服务。

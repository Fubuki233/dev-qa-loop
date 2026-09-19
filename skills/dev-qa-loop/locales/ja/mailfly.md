# Mailfly との連携

[English](../../references/mailfly.md) | [简体中文](../zh-CN/mailfly.md) | 日本語

対象リポジトリが Mailfly の場合だけ読みます。チェックアウト内の `AGENTS.md` を規則の基準にします。

- `documentation/agent-workflow.md` を読みます。メインと QA は `.agents/worktrees/` 以下にそれぞれ専用のブランチ・worktree を持ち、
  共有 `.agents/assignments/` で担当を記録します。共有ルートは調整と読み取り専用の確認に限ります。
  コンテキスト圧縮後も同じタスクを再開し、調整データは共有 `.agents/dev-qa-loop/` に置きます。
- `python3 scripts/agent_context.py <affected-path>...` で必要な文書と検証を選びます。
  既存の Spec Kit 文書は必要に応じて読み、スキル利用だけを理由に spec/plan/tasks を再生成しません。
- 見た目だけの変更には視覚的証拠、操作には最小ユーザーパスが必要です。アカウント種別・権限・戻り先の変更では、
  四つのユーザー種別で実クリックと拒否経路を確認し、`documentation/click-flow-qa.md` を更新します。
  データベース、RLS、ロックの意味論は独立した PostgreSQL で検証します。
- 入札関連の保護されたパスを変更する前に `documentation/tender-implementation-rules.md` を読みます。
  新しい実行コンポーネントや例外・アラート動作には `documentation/monitoring-alerting.md` に従います。
- 統合テストは各 worktree の独立環境で行い、廃止された `make testenv-*` は使いません。staging の診断は読み取り専用です。
  マージ、マイグレーション、デプロイは調整 Agent が直列に行います。
- PR の必須チェックは通常 `quality`、`docker-build` ですが、実際のワークフローとブランチ規則を確認します。
  デプロイは作業ブランチ PR → main → staging PR → CI の順に進めます。
- このスキルは独立した dev-qa-loop リポジトリで管理し、インストールまたは検出用リンクで利用します。
  Mailfly のプロジェクト用スキルインストーラーの管理対象ではありません。修正・検証はスキル自身のリポジトリで行います。

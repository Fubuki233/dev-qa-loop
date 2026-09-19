# dev-qa-loop

[English (default)](README.md) | [简体中文](README.zh-CN.md) | 日本語

実装とテスト作成を並行して進め、変更不可のコードスナップショットで引き継ぎ、
GitHub Actions の結果を追跡する Codex スキルです。メイン Agent がタスクに適した QA モデルを選びます。
特定のモデルには固定しません。

スキルの入口：[SKILL.md（英語）](skills/dev-qa-loop/SKILL.md)。
[日本語ガイド](skills/dev-qa-loop/locales/ja/guide.md)も利用できます。

## 機能

- インターフェース契約に基づき、実装と QA を別々のブランチ・worktree に割り当てます。
- Git index を変更せず、選択した新規ファイルやバイナリ変更を含む未コミットのスナップショットを作成します。
- テスト結果を適用済みスナップショットに紐付け、累積パッチの入れ替えや中断後の再開に対応します。
- PR の head SHA を固定し、失敗、キャンセル、スキップ、チェックの欠落、タイムアウト、新しいコミットを区別します。
- 特定の run/attempt の失敗情報を収集し、必要に応じて生ログをローカルに保存します。

スクリプトには Python 3.10+ と Git が必要です。CI ツールには認証済みの `gh` も必要です。
並行実行には Codex ホストのサブ Agent 機能を使います。モデルサービスをインストールしたり、
このスキルだけで push、マージ、デプロイを許可したりするものではありません。

## インストールと使い方

Codex の組み込みインストーラーに、ユーザー単位でのインストールを依頼します。

```text
$skill-installer Fubuki233/dev-qa-loop の skills/dev-qa-loop をインストールしてください。
```

公開リポジトリ：https://github.com/Fubuki233/dev-qa-loop 。
必要に応じて新しいセッションを開始すると、各プロジェクトから利用できます。更新時は再インストールするか、
開発用チェックアウトへのリンクを使います。パスは実際の場所に置き換え、既存のリンクを上書きしないでください。

```bash
mkdir -p .agents/skills
ln -s /absolute/path/to/dev-qa-loop/skills/dev-qa-loop .agents/skills/dev-qa-loop
```

### 自動起動

`policy.allow_implicit_invocation: true` を有効にしています。毎回 `$dev-qa-loop` と指定する必要はありません。
「ページ分割 API を実装して」「リトライによる重複送信を修正して」など、QA が独立して進められる開発依頼では、
Codex がこのスキルを選択してテスト作成を並行できます。質問への回答、文書だけの変更、見た目だけの変更、
小さな変更では並行作業を開始しません。ユーザーが指定した進め方を優先します。

自動選択はホストがスキルの description に基づいて判断し、すべての開発メッセージで必ず起動するわけではありません。
Codex はスキルの更新を自動検出します。反映されない場合は再起動してください。セッション終了後の自動起動は提供しません。
設定の根拠：[OpenAI 公式スキル文書](https://developers.openai.com/codex/skills/)。

### モデル選択と言語

メイン Agent はタスクの難易度、必要な能力、応答時間、既知の費用・予算を考慮し、ホストで利用可能な QA モデルと
推論強度を選びます。ユーザーが指定したモデル・予算を優先します。ホストが選択に対応しない場合は既定モデルを
継承し、その制約を報告します。要求したモデルとホストが報告した実際のモデルは別々に記録します。

文書と UI メタデータの既定言語は英語です。報告では明示的な言語指定を優先し、次に会話の英語・中国語・日本語を
使います。判断材料がなければ英語を使います。コマンド、JSON フィールド、状態値は翻訳せず、CLI の機械可読出力は英語のままです。

明示的に使う場合：

```text
$dev-qa-loop ページ分割 API を実装し、適切な QA モデルを選んでテストを並行作成し、PR の CI を追跡してください。
```

コミットの許可がなければパッチで引き継ぎます。PR がなければローカル検証を完了し、CI は未実行と報告します。
対象プロジェクトの `AGENTS.md`、要件、検証ルールを優先します。Mailfly の参考文書は Mailfly を扱う場合だけ読みます。
スクリプトとテストは Mailfly に依存しません。

## 開発と検証

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/mypy
```

テストは一時 Git リポジトリと GitHub レスポンスの fixture を使い、実際の GitHub アクセスや API キーを必要としません。
スクリプトの使い方は[引き継ぎ文書](skills/dev-qa-loop/locales/ja/handoff.md)を参照してください。
GitHub Actions は push と pull request 時に Python 3.10、3.13 で検証します。

英語・中国語・日本語の文書は同時に更新します。スキル検出の入口は一つだけです。
`locales/` 以下は翻訳された参考文書であり、別のスキルではありません。必要な言語だけを読んでください。

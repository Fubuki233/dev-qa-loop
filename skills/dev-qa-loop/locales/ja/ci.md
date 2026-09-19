# CI の監視と診断

[English](../../references/ci.md) | [简体中文](../zh-CN/ci.md) | 日本語

Python 3.10+、GitHub CLI `gh`、既存のログインが必要です。GitHub App のインストールやコメント投稿は行いません。
gh を利用し、head の固定、欠けたチェックの処理、状態変化の出力を追加します。他のスキルは不要です。
ログ収集は GitHub Actions のみ対応し、外部チェックは URL を保持します。

## 特定の PR 版を監視する

```bash
gh pr view '<PR-number>' --repo '<owner/repo>' --json headRefOid
python3 '<skill-dir>/scripts/watch_checks.py' \
  --repo '<owner/repo>' --pr '<PR-number>' --head '<full-SHA>' \
  --expect-check quality --expect-check docker-build \
  --timeout 1800 --interval 30 --output '<task-state-dir>/ci.json'
```

`--expect-check` は複数指定できます。指定時はそのチェックだけで合否を決めますが、報告には全チェックを含めます。
未指定時は現在の rollup を評価します。チェックが一件もない状態を成功とは扱いません。
期待するチェックが欠けていれば待機します。skipped/neutral は既定で確認が必要です。スキップが許容されている場合だけ
`--allow-skipped '<check-name>'` を追加します。同名のチェックもすべて条件を満たす必要があります。
納品前にブランチ保護と実際の必須チェックを確認します。スクリプトは必須条件を設定・推測しません。

各照会は同じ PR レスポンスから head と rollup を読み、head が変わると `superseded` を返します。
PR 検証用 merge SHA を head SHA と同一視しません。診断報告には実際の run SHA を保持します。
スクリプトはモデルを呼び出さず、状態変化と終了時だけ JSON 行を出力します。

ホスト対応のバックグラウンド処理を使い、ハンドルを保存します。一回のツール待機は 60 秒以内にし、独立した作業を続けます。
モデルから頻繁に gh を呼び出すポーリングは避けます。`--once` は一度だけ照会し、`--timeout` は監視期限です。
各 gh 呼び出しも残り時間と 30 秒の上限に従います。

| 終了コード | 意味 |
| --- | --- |
| 0 | 選択したチェックが成功。明示的に許容したスキップを報告 |
| 1 | 選択したチェックが失敗 |
| 2 | 引数、認証、ネットワーク、データのエラー |
| 3 | タイムアウト。成功ではない |
| 4 | PR head が更新され、証拠が古くなった |
| 5 | 選択したチェックがキャンセルされた |
| 6 | PR が閉じられたかマージ済み。監視終了であり CI 成功の証明ではない |
| 7 | skipped、neutral、不明な状態で確認が必要 |
| 8 | `--once` 時点で実行待ち・実行中、またはチェックが欠けている |

## 失敗を収集する

失敗したチェックの URL から GitHub Actions run ID を取得し、対象リポジトリを確認します。
ブランチの最新 run は別コミットかもしれないため使いません。既定ではメタデータだけを取得します。

```bash
python3 '<skill-dir>/scripts/collect_failures.py' \
  --repo '<owner/repo>' --run '<run-id>' \
  --output '<task-state-dir>/run-<run-id>.json'
```

報告には run ID、実際の head SHA、event、branch、attempt、結論、失敗 job/step、URL を保持します。
PR チェックのリンクで run を関連付け、検証用 merge SHA の場合は run と PR の関連を確認します。
再修正前には PR head が監視対象の版のままか確認します。

ログが必要なら `--log-output '<local-log-path>'` を追加します。スクリプトは attempt を固定し、サイズ制限のある
ローカルファイルを権限 0600 で保存して切り詰めを明示します。**ログは stdout に出力しません**。
Secret や個人情報を含む可能性があるため、ログをコミット・アップロードしたり、そのままメイン Agent に渡したりしません。
必要部分を取り出して機密情報を除いた要約だけを返します。ログ取得失敗は別に報告し、成功へ変換しません。
成果物のダウンロードやワークフロー再実行は行いません。収集スクリプトの終了コード 0 は収集成功であり、CI 成功ではありません。
CI の結論は報告の `conclusion` を読みます。

CI の証拠はローカル受け入れ検証の代わりにはなりません。この版は PR チェックを観察します。
デプロイ追跡はプロジェクト既存の運用手順を使います。セッションをまたぐ自動起動には外部のスケジューラーが必要です。

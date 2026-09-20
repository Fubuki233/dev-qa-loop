# スナップショットと引き継ぎ

[English](../../references/handoff.md) | [简体中文](../zh-CN/handoff.md) | 日本語

スクリプトは `python3` で実行します。`<skill-dir>` は入口の `SKILL.md` があるディレクトリの絶対パスです。
例のプレースホルダーは置き換えて引用符で囲みます。タスクの文章を shell コードに連結しないでください。

## 調整記録

Git common dir に対応する共有リポジトリに `.agents/dev-qa-loop/<task-id>/` を作ります。
`state.json` はメイン Agent だけが更新し、引き継ぎごとに一時ファイルを書いてからアトミックに置き換えます。

```json
{
  "task_id": "feature-notifications",
  "contract_version": 1,
  "phase": "parallel",
  "main_assignment": "<assignment-id>",
  "qa_assignment": "<another-assignment-id>",
  "qa_agent_id": "<host-returned-id>",
  "qa_model_requested": "<selected-model-id; null when inheriting>",
  "qa_model_actual": null,
  "qa_reasoning_effort": null,
  "qa_cost_basis": null,
  "qa_escalation_reason": null,
  "qa_upgrade_count": 0,
  "qa_upgrade_limit": 1,
  "qa_model_reason": "<subtask, cheaper alternative, and capability rationale>",
  "language": "en",
  "main_worktree": "<absolute-path>",
  "qa_worktree": "<another-absolute-path>",
  "implementation_paths": ["src/notifications.py"],
  "test_paths": ["tests/test_notifications.py"],
  "latest_snapshot": "<snapshot-directory-or-commit-sha>",
  "qa_state_file": "<QA-owned-state-file>",
  "last_qa_report": "<QA-owned-report-file>",
  "repair_round": 0,
  "max_repair_rounds": 3,
  "pr": null,
  "expected_pr_head": null,
  "ci_process_handle": null,
  "authorized_actions": ["local implementation", "isolated tests"],
  "next_action": "<specific-next-action>"
}
```

`language` は `en`（既定）、`zh-CN`、`ja` のいずれかを使います。
phase は `contract / parallel / validating / integrating / watching_ci / needs_input / complete` を使います。
実際に許可された操作を記録します。この例は許可を付与しません。再開時には Agent とプロセスがまだ生きているか確認し、
同じ worker を重複起動しません。セッションをまたいで復帰できない場合は、既存の assignment を明示的に引き継いでから
新しい QA を作成し、完了済みの作業を保持します。

QA だけが `qa-state.json` を管理し、`applied_snapshot_id`、`applied_snapshot_path`、`base_sha`、
`test_process_handle`、`phase`、最新の報告パスを記録します。applied フィールドは適用成功後に更新します。
メイン記録の `latest_snapshot` は公開された版であり、QA の適用済み版より新しい場合があります。古いパッチを取り消す根拠には使いません。
再開時に QA 状態と実装パスを照合します。不明なら作業状態を保持して調整し、基準版を推測しません。

## 最初の QA メッセージ

```text
このタスクのテストを担当してください。要求モデル：<選択したモデル ID またはホスト既定値>。
実際のモデルはホストの報告だけを根拠にします。報告言語：<en / zh-CN / ja>。
モデル選択理由：<短い説明>。
<プロジェクト AGENTS.md> を読み、専用 assignment/worktree を復元：<パス、ブランチ、ID>。
要件・仕様：<ファイルまたは要約>。契約バージョン：1。
インターフェース、エラー動作、受け入れケース：<具体的な内容>。
編集可能パス：<テストと fixture>。製品実装はメイン Agent が担当します。
メイン Agent が実装とスナップショットの準備を進める間に、ケースの設計とテスト作成を開始してください。
検証コマンドと環境：<プロジェクトに応じた内容>。
未実装は waiting_implementation とし、完了済みテストと次の作業を報告してください。製品コードは実装しません。
自分専用の <報告パス> に結果を書き、短い要約を返してください。調整用 state.json は変更しません。
```

ホスト対応で個別タスクを遂行できる最も低コストなモデルと十分な最低限の推論強度を優先し、ユーザー指定と予算を守ります。
`qa_model_reason` に個別タスクと検討した安い候補を、`qa_cost_basis` にホスト・ユーザー由来の費用の根拠、または不明と記録します。
最初から強いモデルを使う場合や昇格時は、`qa_escalation_reason` に能力不足と安い候補の制限を記録し、「品質が良い」だけを理由にしません。
昇格が不要なら null にします。`qa_upgrade_count` はモデル・推論強度の引き上げ回数を Agent 交代後も累積し、修正回数もリセットしません。
`qa_upgrade_limit` の既定値は 1 です。その後はメイン Agent が難所を担当するか範囲を絞ります。初期の強いモデルにも証拠が必要です。
ユーザーの明示的なモデル指定は優先し、その指定を理由として記録します。製品の不具合、CI 失敗、未実装、環境・認証障害は昇格の根拠になりません。
価格は不明でも構いません。経済的・軽量という表示は目安であり、検証済みの価格ではありません。
これらは判断用の記録です。スクリプト自体はモデル選択や金額の上限を強制しません。派発ツールの実際のパラメーターで
`task_name="qa"`、`model="<selected-model-id>"`、`reasoning_effort="<supported-effort>"`、
`fork_turns="none"` などを指定し、非対応フィールドは省略します。既定モデルを継承する場合は `qa_model_requested` を null、
実モデルが報告されない場合は `qa_model_actual` を null、推論強度が未指定なら `qa_reasoning_effort` を null にします。
要求モデルを確認済みの実モデルとして扱いません。旧記録の `qa_model` は履歴として保持し、実モデルの証明には使いません。
QA を置き換える前にテストと報告を保存し、旧担当の書き込みを止め、assignment を移して既存作業を保持します。

これはホストの機能を利用するもので、新しいモデル API ではありません。メイン Agent は派発後に開発を続けます。
QA はケース設計が終われば待機して構いません。次のスナップショットではホストの follow-up/resume を使い、ファイルを巡回させません。

## 未コミットの実装を発行する

このタスクが所有する最小範囲のパスだけを選びます。リポジトリ全体、Secret、`.env`、他者の変更を含めません。
取得中は対象パスの編集を止めます。出力先は毎回新しいディレクトリを指定します。

```bash
python3 '<skill-dir>/scripts/snapshot.py' capture \
  --repo '<implementation-worktree>' --output '<task-state-dir>/snapshots/001' \
  --path src/notifications.py --path src/contracts.py
```

`snapshot.json` と `changes.patch` が生成され、識別子は基準コミット、パッチ、対象パスに紐付きます。
rename は削除と追加で表し、ignored の新規ファイルは含みません。空ディレクトリは Git の対象外です。
元の index は変更しません。submodule の変更は別のコミットで引き継ぎます。

契約バージョン、絶対パス、`snapshot_id`、テスト可能な動作と未実装の動作を送ります。QA は適用前に検証します。

```bash
python3 '<skill-dir>/scripts/snapshot.py' verify --snapshot '<snapshot-dir>'
git -C '<QA-worktree>' status --short
git -C '<QA-worktree>' rev-parse HEAD
git -C '<QA-worktree>' apply --check '<snapshot-dir>/changes.patch'
git -C '<QA-worktree>' apply '<snapshot-dir>/changes.patch'
```

最初に QA の実装基準が manifest の `base_sha` と一致することを確認します。テスト側には変更やコミットがあっても構いませんが、
製品パスは基準版に一致している必要があります。空パッチに `git apply` は不要です。スクリプトが確認するのはスナップショットの完全性であり、
対象 worktree の基準版の確認やパッチ適用は行いません。

同じ HEAD から作ったスナップショットは**累積パッチ**です。入れ替える前に、QA が実装パスを独自に編集していないことを確認します。
直前に適用したパッチに `git apply --reverse --check` を実行し、通過してから reverse し、新しいパッチを適用します。
累積パッチを重ねてはいけません。基準版が変わった、実装パスが編集された、チェックが失敗した場合は状態を保持して衝突を調整します。
reset、stash、テストの上書き、worktree の作り直しは行いません。コミットでの引き継ぎでは、プロジェクトの調整 Agent が統合を直列に実行します。

一つの QA worktree では適用、テスト、報告を直列に行います。テスト中の新スナップショットは待機させ、報告完了または
テストの正常な停止後に切り替えます。各巡回では QA 状態の適用済み ID を読み、実行中に新着 ID へ書き換えません。

## QA 報告と統合

各報告に契約バージョン、スナップショット ID または実装コミット、テスト版・パッチ、コマンド、終了コード、証拠パスを記録します。

- `passed`：このスナップショットの対象動作が成功。未カバー・未実行項目を列挙します。
- `waiting_implementation`：合意した動作が未実装。完了ではありません。
- `product_defect`：契約違反。最小再現を添えます。
- `test_defect`：fixture、アサーション、harness の問題。テストを直してから再実行します。
- `environment_blocked` / `flaky`：環境の証拠または不安定な動作。一度成功しただけでは解決としません。

メイン Agent は QA 所有のテスト変更だけを取り込み、検証用の実装スナップショットを再び自分のブランチに適用しません。
コミットが未許可なら QA も snapshot.py で**テストパスだけ**を選んでパッチを発行します。
両方を含む最終版で影響範囲を検証して版を記録し、中間報告を最終証拠として流用しません。

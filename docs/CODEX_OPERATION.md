# Codexで投資調査を運用する

2026-10-24の運用方針は、**このプロジェクトを開いたCodexとの会話で調査し、結果をローカルに保存する**ことです。アプリ化、公開、デプロイ、常駐サーバーは通常の調査に必要ありません。既存の画面は希望した場合だけ開く補助資料として残します。既存のReflex公開環境や外部設定の停止・削除は行いません。

## 普段の依頼

| Codexへの依頼 | 処理 |
|---|---|
| 投資更新 | 日米の市場・価格を明示更新し、地合いと強い業種・テーマをチャットで説明 |
| 日本だけ更新 / 米国だけ更新 | 対象市場の価格を更新 |
| 保存済み結果を見せて / 地合いを見せて | 新規取得せず保存された観測日から説明 |
| 業績も更新して | 無料の四半期候補を明示取得。資料確認済みとは区別 |
| トヨタを詳しく調べて | 銘柄を指定して既存分析と原資料確認を実行 |
| 図で見せて | 希望時だけ保存済みHTMLを補助表示 |

「現状」という依頼でも、保存データの観測日を確認し、閲覧と新しい取得を区別します。取得に失敗した値を0や合格にしません。中期基調、短期変化、市場参加、外部環境を分け、業種・テーマの中期相対優位と最近の改善を混同しません。銘柄の条件成立は売買指示ではありません。

## Codexが使う入口

全てこのリポジトリを作業フォルダーにします。通常の依頼に`--open`を付けません。別チャットでもこのプロジェクトの`investment-research` Skillと`AGENTS.md`が入口になります。

```powershell
# 取得なし・保存や基準日も変更しない。標準出力を読んでチャットへ回答する。
.venv\Scripts\python.exe scripts\research.py saved
.venv\Scripts\python.exe scripts\research.py saved --scope JP
# 明示した更新だけ実行。完了後に保存されたMarkdown/JSONを読む。
.venv\Scripts\python.exe scripts\research.py update --profile standard
.venv\Scripts\python.exe scripts\research.py update --scope US
.venv\Scripts\python.exe scripts\research.py update --include-fundamentals
# 保存価格から候補を絞る。必要なときだけ業績も明示取得する。
.venv\Scripts\python.exe scripts\research.py screen --market JP
.venv\Scripts\python.exe scripts\research.py screen --market US --refresh-fundamentals
```

チャット用レポートはPythonで保存済み値を表にし、Codexが根拠・反証・次の確認を説明します。独立したモデルAPI契約や常時稼働は不要です。銘柄を指定した深掘り、会計照合、企業価値、原資料の確認記録は引き続き利用できます。確認していない資料の確認日を更新しません。

## 保存と復元

- 分析の原本は`.states/research_runs/<保存ID>/research.json`。同じ入力の`summary.md`と任意の`dashboard.html`を併記します。新規保存はv3、既存v1/v2も読めます。
- `.states/research_workbench/current.json`は最新の保存ディレクトリを指します。名前にworkbenchが含まれますが、サーバーを起動せずCLIでも共有する保存先です。
- `saved`は標準出力へMarkdownを返すだけです。元ファイル・価格取得日・資料確認日・ポインターを変更しません。
- ソースはGitで履歴管理。ローカルの分析データ・キャッシュ・秘密情報はコミットしません。今回の分析バックアップはGit対象外の`backups/research/`に保存し、SHA-256とJSON再読込で復元可能性を確認します。
- 復元はCodexに「分析バックアップを検証して復元して」と依頼。まずZIPを別の一時フォルダーに読み、manifestの各SHA-256と`validate_bundle`を確認します。その後、新しい`.states/research_runs/<新ID>/`へ保存し、既存の保存結果を残してポインターを切り替えます。観測日・確認日を復元日へ変えません。

バックアップも同じPC内なので、PC自体の故障に備えた別媒体への複製は別途必要です。GitHubのコードだけでローカル分析データが戻るとは扱いません。データをクラウドへ送信する運用は追加していません。

## ソースの保全と既存アプリとの境界

この作業のソースは`codex/codex-research-operation`ブランチに保存します。既存CIではmain/masterへのpushが本番デプロイを起動するため、そのブランチへのmerge/pushはしません。専用ブランチの検証とGit保存までを今回の完了範囲にします。main公開・Hugging Face・外部設定の変更は通常の調査と分離します。

既存Web用の変更が作業フォルダーに残っている場合は、今回の保存に混ぜません。Codex研究の既存未記録モジュールと必要な共有計算・出典契約だけを含め、元のWeb表示変更は保持します。

指標・母集団・無料データの不足・原資料確認例は[地合い・業種・テーマの仕様と受入](TOPDOWN_RESEARCH.md)、取得と会計・評価の詳細は[操作・入力契約](CODEX_RESEARCH.md)。将来の投資成果や全銘柄の財務判定を保証するものではありません。

## 運用切替の確認記録

- 保存対象の96ファイルと既存HEADだけを分離したコピーで、標準`check.py --coverage`が全585テスト・71.73%カバレッジ、lint/format/mypy、既存Reflexの書き出し・9ルート静的検査まで合格。旧Web表示の未記録変更1件はこのコピー・コミット対象から除外しました。新しいアプリを公開する検査ではありません。
- `saved --scope US/JP`の実データ出力と、閲覧で更新・ブラウザ起動・元JSON変更が起きない回帰検証を確認。中期上昇と短期下落、負値/0/欠損、相対基準が不良の場合を区別します。両repo Skillsの形式検証も合格。
- ローカル分析バックアップは`backups/research/codex-research-20261023T152430Z.zip`（日時はUTC）。`research.json`・`summary.md`・SHA-256 manifestを含み、別フォルダーでハッシュと`validate_bundle`による復元確認を実施しました。元の60JSONと最新ポインターは不変です。
- 検証記録はGit対象外の`.states/codex_operation_20261024/`。タスク用8770プレビューは停止済み。市場価格の新規取得・原資料の再確認・外部設定変更は、この運用切替では行っていません。

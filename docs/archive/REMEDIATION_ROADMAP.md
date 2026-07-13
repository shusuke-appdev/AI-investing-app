# 根本改修ロードマップ（履歴資料）

> 履歴資料: 初期監査時点の計画です。完了済み項目を含むため、現行の責務境界と残作業は `PRODUCT_REFACTOR_ROADMAP.md` を正本とします。

## 目標

現行機能を維持しながら、外部API依存、UI二重化、保存契約の曖昧さ、AI入力の検証困難さを解消し、将来の機能追加と不具合予防に耐える構造へ移行します。

## 基本方針

- Reflex を現行UIの正本とする
- [完了] 旧Streamlit資産は履歴保全ブランチへ退避し、現行の保守対象から除外した
- 外部データ取得は「値」だけでなく「取得元、鮮度、失敗理由」を返す
- UI state は画面状態に集中し、業務ロジックは `src/services/` と `src/advisor/` に寄せる
- AIに渡す入力は自然文へ直結せず、構造化コンテキストを経由する
- 改修はテスト可能な単位で進め、データ取得系はモックを標準化する

## Phase 0: 開発・検証基盤の復旧

目的: 変更できる状態を作る。

実施内容:
- `.venv` を再作成し、`python -m pytest -q` を復旧
- `python -m compileall src frontend tests` をCIにも追加
- `ruff check .` と `ruff format --check .` をCIに追加
- `.github/workflows/sync_to_hub.yml` の Hugging Face 同期をテスト成功後に限定
- README、`.env.example`、運用資料を現行Reflexに同期

完了条件:
- ローカルとCIで lint / test / compile が通る
- 初回セットアップ手順だけで Reflex が起動できる

## Phase 1: 現行機能の契約固定

目的: 既存機能を壊さずに、改修可能な境界を作る。

実施内容:
- Market / Stock / Portfolio / Knowledge の入出力モデルを定義
- `DataProvider` の戻り値に `source`、`fetched_at`、`is_stale`、`error` を追加する設計を導入
- 外部APIを呼ばない単体テストを増やす
- yfinance / Finnhub / J-Quants / EDINET のレスポンス差異を fixture 化
- UIに「取得失敗」「推定値」「キャッシュ値」を表示する最小ルールを定義

完了条件:
- 欠損データが 0.0 や中立判定に静かに変換されない
- AIレポートで使われたデータソースと欠損が追跡できる

## Phase 2: UI state の薄型化

目的: Reflex state から業務ロジックを分離する。

実施内容:
- `frontend/state/market_state.py` の分析調整を `src/services/market_dashboard_service.py` へ移す
- `frontend/state/stock_state.py` の銘柄取得・分析調整を `src/services/stock_dashboard_service.py` へ移す
- `frontend/state/portfolio_state.py` の保存・分析調整を `src/services/portfolio_dashboard_service.py` へ移す
- UI表示用モデルとドメインモデルを分ける
- state は入力値、ロード中フラグ、エラーメッセージ、表示モデルの保持に限定する

完了条件:
- サービス層をUIなしでテストできる
- UI state の各ファイルが主に状態遷移と表示モデル変換だけを持つ

## Phase 3: データ取得基盤の再設計

目的: 外部API変動に強くする。

実施内容:
- `src/network.py` にタイムアウト、リトライ、レート制限、User-Agent、キャッシュ方針を集約
- `src/cache.py` のキー設計とTTLをデータ種別ごとに明示
- yfinance / Finnhub のフォールバック順を仕様化
- APIごとのエラー型を定義し、握りつぶしを減らす
- オプション分析は取得と計算を分け、取得失敗時のUI表示を明確化

完了条件:
- 外部API障害時でも、どの機能が degraded mode か画面とログで判断できる
- 計算ロジックは取得済みDataFrameだけでテストできる

## Phase 4: AI分析パイプラインの堅牢化

目的: AI出力の品質と再現性を上げる。

実施内容:
- `AnalysisContext` を導入し、AI入力を構造化
- 市場、銘柄、ポートフォリオ、知識DBの各コンテキストを共通形式にする
- プロンプトに「欠損データを断定しない」「取得元を明記する」制約を追加
- 参照知識の重複排除、古さ表示、プロンプト注入対策を追加
- AI出力の最低限の形式検証を行う

完了条件:
- AI分析に使った入力データをログまたはデバッグ表示で追跡できる
- 欠損データがある場合、AI出力にその前提が明示される

## Phase 5: 旧UIと不要資産の整理

目的: 将来の保守コストを下げる。

実施内容:
- [完了] `src/ui/` と `legacy_streamlit/` は別ブランチ退避後、現行ツリーから削除した
- `backend.zip`、`frontend.zip`、`pip_dry_run.txt`、`opt_res.txt` などの生成物をGit管理対象から外す方針を決める
- `.gitignore` を再点検し、キャッシュ、アップロード、ローカルDB、生成物を整理
- ドキュメントを Reflex 正本に統一

完了条件:
- 新規開発者が修正すべきUIを迷わない
- 生成物・キャッシュがレビュー差分に混入しない

## Phase 6: 機能拡張に備えた設計

目的: 新しい分析機能を安全に追加できる状態にする。

候補:
- 指標・セクター・テーマの設定をコード直書きから設定ファイル化
- ユーザー別ポートフォリオ、複数ウォッチリスト、アラート機能
- AI分析結果の履歴保存と比較
- データ取得ジョブのバックグラウンド化
- Supabase RLS と認証の導入
- 監視対象銘柄ごとの取得頻度制御

完了条件:
- 新機能追加時に UI、取得、分析、保存、AI のどこを変更するかが明確
- 既存機能の回帰テストが自動で走る

## 最優先で直すべき具体項目

1. `.venv` 再作成とテスト復旧
2. `ruff --fix` で安全な整形・import順・空白を解消
3. `frontend/pages/knowledge.py` の未使用 `icon_map` を削除または実利用
4. `src/advisor/base_recognition.py` の未使用 `drawdown` を削除または判定に利用
5. `src/services/market_analyst_service.py` の不要f-stringと重複市場監視処理を整理
6. `frontend/state/*` からサービス層へ業務ロジックを移す
7. 外部API結果のステータスモデルを導入
8. GitHub Actions に lint/test を追加し、Hugging Face 同期をゲートする

## リスクと対策

- リスク: UI移行中に表示が壊れる  
  対策: 画面単位のスモークテストと主要stateの単体テストを先に作る

- リスク: 外部APIモックが現実とずれる  
  対策: 実APIレスポンスの匿名fixtureを定期更新する

- リスク: AI出力の自由度を落としすぎる  
  対策: 構造化コンテキストは厳密にし、最終文章生成は自由度を残す

- リスク: Streamlit削除で過去機能を失う  
  対策: 削除前に機能棚卸しを行い、Reflex未移行機能を明示する

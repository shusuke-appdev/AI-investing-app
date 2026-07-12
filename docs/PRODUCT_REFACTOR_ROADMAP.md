# Product Refactor Review and Roadmap

更新日: 2026-06-18

## プロダクト契約

- 本アプリは個人用の投資調査ダッシュボードであり、売買助言・投資一任を目的としない。
- 主UIと新規開発の正本は `frontend/` のReflexアプリとする。
- `APP_MODE=private` は個人データの読み書き、AI生成、外部コンテンツ取り込みを許可する。
- `private` は認証機能ではなく、ローカルまたは外部アクセス制御済み環境だけで使う。
- 未設定時と公開配置では `APP_MODE=public_readonly` とし、Portfolio、Knowledge、Trading Plan互換データの読み書き、AI生成、URL・YouTube取り込みを禁止する。
- 保存先の既定値はローカルJSONとし、Supabaseは明示選択時のみ使用する。

## 分析機能の責務マップ

| 機能 | 主な責務 | 主な出力・連携先 |
| --- | --- | --- |
| Market Summary | 指数・市場設定の軽量取得 | `MarketContext`、Market UI |
| Market Watch | IBD、需給、モメンタム、資金フロー、信用、歪み、ボラティリティ | `MarketContext`、Market Watch、Market AI |
| Options | SPY/QQQ/IWMのPCR、IV、Max Pain、Skew等 | `OptionContext`、市場環境評価 |
| Theme Ranking | テーマと構成銘柄の期間別順位 | Market Watch、Market AI、個別株テーマ評価 |
| Stock Analysis | 企業情報、価格、ニュース、テクニカル、確率・トレンド・FOMO・Entry診断 | `StockSignalContext`、Stock UI、Stock AI |
| Stock Trade Analysis | 個別銘柄分析済みデータを使った重要水準、タイミング、無効化条件、需給根拠の整理 | Stock UI。通常UIでは保存・レビュー機能を持たない |
| Trading Plan互換コード | 既存のR基準計画データ・`trade_plans`保存層の互換維持 | 通常ナビゲーションからは使用しない |
| Portfolio | 保有比率、損益、集中度、調査レポート | Portfolio UI、Portfolio AI |
| Knowledge DB | ユーザー資料の保存と安全な引用 | Stock AI、Portfolio AI |

## 2026-06-12 実施済み

- Portfolio AIの入力契約とTheme Bottom5誤表示を修正した。
- 市場分析の同名ステータス置換と依存順序を修正した。
- 個別株の任意診断を部分失敗可能にした。
- Trading Plan一覧表示から銘柄ごとのネットワーク取得を除去した。
- `StockAnalysisInputs` を導入し、個別株分析中の価格・企業情報・ニュース・ベンチマーク取得を共有・メモ化した。
- Trading PlanのT+1/T+3候補更新を一覧描画から分離し、明示操作時のみ銘柄ごと1回取得するようにした。
- ローカルJSON保存をファイル単位ロックと原子的置換へ統一した。
- Knowledge URLのSSRF防御、リダイレクト検査、容量・Content-Type・ファイル形式制限を追加した。
- `.dockerignore`、CIのconstraints適用、Reflex export検証を追加した。
- 個人ポートフォリオJSONをGit追跡から外した。

## 2026-06-14 実施済み

- 公開モードの境界を読み取り、AI生成、外部コンテンツ取得まで拡張し、個人ページをナビゲーションから除外した。
- Knowledge URLのリダイレクト先を接続前に検査し、応答ストリームを確実に解放するようにした。
- J-Quants Freeの遅延価格系列を汎用現在値・履歴経路から除外した。
- 市場データ取得失敗を `0.0` として表示せず、利用不可項目として省略するようにした。
- Theme Rankingへ要求期間、実測期間、構成銘柄取得率、最低取得数を追加した。
- 直接利用する外部HTTP・yfinance一括取得へタイムアウトを設定した。

## 次期ロードマップ

### P1: 分析入力の共有と待ち時間削減

- Portfolio AIへ共有 `MarketContext` を渡し、市場データの再取得とUIとの差異をなくす。

### P1: データ品質

- `MarketContext` と `StockSignalContext` の主要な `dict[str, Any]` を型付きサブコンテキストへ移行する。
- provider層の曖昧な空値を、出所と失敗理由を持つ結果型へ移行する。

### P2: 責務分割

- `market_dashboard_service.py` をステージ実行、依存分析、コンテキスト統合へ分割する。
- `option_analyst.py` と大型UIコンポーネントを計算・整形・表示へ分割する。
- [完了] `legacy_streamlit/` と `src/ui/` は `codex/archive-streamlit-assets` へ履歴保持し、現行ツリーから削除した。

## 受入基準

- 一部の外部API・任意診断が失敗しても、取得済み分析と品質警告を表示できる。
- UIとAIが同一コンテキストを再利用し、同一更新内で結論が矛盾しない。
- 公開読み取り専用モードでは個人データを読み書きできず、AI生成と任意URL・YouTube取得も実行できない。
- pytest、ruff、format check、compileall、Reflex frontend exportがCIで通る。

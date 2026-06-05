# アーキテクチャ概要

## 目的

このアプリは、投資判断に必要な市場データ、ニュース、テクニカル指標、テーマ別動向、ポートフォリオ情報、個人の参照知識を集約し、AIで要約・分析する調査支援システムです。

中核は「外部データを取得し、分析ロジックで構造化し、UIとAIレポートへ渡す」流れです。

## 実行入口

- Reflex UI: `frontend/frontend.py`
- ルート定義:
  - `/`: Market Intelligence
  - `/market-watch`: 市場監視
  - `/stock`: 個別銘柄分析
  - `/portfolio`: ポートフォリオ分析
  - `/knowledge`: 参照知識管理
- 旧Streamlit UI: `legacy_streamlit/app.py` と `src/ui/`

## レイヤー構成

```text
UI
  frontend/pages/*
  frontend/components/*
  frontend/state/*

ユースケース調整
  src/services/*
  src/services/market_presentation_service.py
  src/services/temporal_alignment.py
  src/services/analysis_run.py
  src/services/analysis_jobs.py
  src/portfolio_advisor.py
  src/stock_analyst.py
  src/news_analyst.py

ドメイン分析
  src/advisor/*
  src/option_analyst.py
  src/theme_analyst.py
  src/momentum_monitor.py
  src/market_microstructure.py

データ取得
  src/data_provider.py
  src/market_data.py
  src/stock_data_provider.py
  src/market_index_provider.py
  src/news_provider.py
  src/news_aggregator.py
  src/finnhub_client.py
  src/jquants_client.py
  src/edinet_client.py

永続化
  src/storage/base.py
  src/portfolio_storage.py
  src/knowledge_storage.py
  src/settings_storage.py
  src/supabase_client.py
  src/gas_client.py

横断関心
  src/cache.py
  src/persistent_cache.py
  src/network.py
  src/log_config.py
  src/constants.py
  src/services/analysis_diagnostics.py
```

## 主要なデータフロー

### Market Intelligence

1. `MarketState.fetch_market_summary_fast()` がUIロードで実行され、`.states/market_context_cache` の最後の軽量サマリーを優先表示する
2. 軽量サマリーは `market_data.get_market_indices()` と `market_config.get_market_config()` のみを取得し、起動時にオプション取得を行わない
3. `MarketState.refresh_market_details()` が、既存の `MarketContext` を再利用しながら市場環境、IBD式市場状態、マイクロストラクチャー、テーマ、監視指標、信用ストレス、セクター/テーマ歪みを更新する
4. 詳細更新では `sector_flow_service` が米国セクターETFと日本テーマバスケットから資金流入セクター、確信度、継続性、調査判断を計算し、`japan_market_conditions` が日経平均上昇の6条件を直接データまたは代理指標として評価する
5. `MarketState.refresh_options()` が SPY / QQQ / IWM のオプション取得を明示的に実行し、取得結果、キャッシュ鮮度、品質警告を `OptionContext` に保存する
6. Reflex state に整形済みデータを保存し、画面が再描画される
7. 表示用の整形は `services.market_presentation_service.build_market_display_context()` が担い、`MarketState` はイベント、loading/error、表示モデル保持に集中する
8. AI Market Recap は `services.market_analyst_service.generate_market_analysis_report()` から Gemini へ渡り、通常経路では既に取得済みの `MarketContext`、オプション品質情報、日米セクター流入、日経6条件、ユーザー指定の追加分析項目をプロンプトに含める。レポートは米国市場を主軸にし、日本市場は米国との連動・乖離を読む補助コーナーとして扱う

### 市場監視

- `/market-watch` は、総合市場監視、IBD式市場状態、状態別固定プレイブック、テーマモメンタム、テーマランキング、オプション分析、市場の歪み検知を集約する
- 市場監視の詳細更新は、低難易度のキャッシュ/サマリー、中難易度の市場状態・資金フロー、高難易度のFRED信用ストレス・歪み検知、オプション分析の順に `MarketState` が yield し、各ブロックの `status`、`cache_status`、`fetched_at`、`quality_warnings` を表示モデルへ渡す
- IBD式市場状態は `advisor.ibd_market_regime.classify_ibd_market_regime()` が SPY / Nasdaq 100 代理データから判定する。分類は `confirmed_uptrend`、`uptrend_under_pressure`、`rally_attempt`、`market_in_correction`
- `services.market_playbook` は市場状態ごとの「現在考えるべきこと」「今やること」「避けること」を固定データとして返す
- `advisor.sector_theme_diagnostics.detect_market_distortions()` はテーマごとのファンダメンタルスコアとフロースコアの乖離から、強気/弱気の歪み候補を上位5件ずつ返す

### 個別銘柄

1. `StockState.fetch_stock_data()` がティッカー入力後に実行される
2. `market_data` 経由で企業情報、価格、ニュース、テクニカルを取得
3. `advisor.smart_criteria.evaluate_smart_criteria()` で成長株観点の条件を評価
4. `advisor.probabilistic_signal.generate_probabilistic_stock_signal()` が過去の類似局面、forward return、walk-forward検証、サイジング目安を作る
5. `advisor.trend_follow_diagnostics.generate_trend_follow_diagnostics()` が日足トレンドフォローを診断軸として評価し、OOS、コスト耐性、遅延耐性、右テール依存、Buy & Hold比較を `StockSignalContext` に追加する
6. `advisor.sector_theme_diagnostics.evaluate_stock_sector_theme_context()` が対象銘柄のセクター/テーマを、ファンダメンタル優位とフロー優位の両面から評価して `StockSignalContext` に追加する
7. `StockSignalContext` は表示済みニュース見出し、SMART基準、テクニカルも保持し、AI分析は `stock_analyst.analyze_stock()` が同じ入力を再利用してプロンプトを組み立てる

### ポートフォリオ

1. UI入力を `PortfolioState.holdings` に保持
2. `portfolio_storage` が local / GAS / Supabase の保存先を抽象化
3. `portfolio_advisor.analyze_portfolio()` が銘柄別情報、評価額、テーマ露出、リスク要素を集計
4. `portfolio_advisor.generate_portfolio_advice()` がAIアドバイスを生成

### 参照知識

1. `KnowledgeState` がテキスト、URL、YouTube、ファイルアップロードを受け取る
2. `knowledge_extractor` が本文抽出・要約・タイトル生成を行う
3. `knowledge_storage` が local / GAS / Supabase に保存する
4. `knowledge_storage.get_knowledge_for_ai_context()` が銘柄分析プロンプトに注入される

## 重要な設計判断

- `src/data_provider.py` は facade と依存性注入の入口を兼ねており、テスト時に外部APIを差し替えられる
- `src/cache.py` は Streamlit 依存を避けるためのフレームワーク非依存TTLキャッシュ。エントリごとに `created_at`、`expires_at`、`ttl`、`namespace` を持ち、関数単位の `.clear_cache()` と名前空間単位のクリアに対応する
- `src/persistent_cache.py` は `.states` 配下のJSONキャッシュ共通基盤。schema/version付きの原子的書き込み、破損JSON無視、fresh/stale/expired判定、ファイル名安全化を担う
- yfinance系の重い取得は、メモリTTLに加えて `.states/market_context_cache` と `.states/option_chain_cache` のJSONキャッシュを使う。`source`、`fetched_at`、`is_stale`、`cache_status`、`quality_warnings` をUIとAIプロンプトへ渡す
- Market AI Recap は `MarketContext` がある場合に市場監視やテーマランキングを再取得せず、context 内の monitoring / momentum / option 情報を優先する。context 構築に失敗した互換パスだけ旧取得ロジックへフォールバックする
- Stock AI Recap は `StockSignalContext` がある場合に表示済みのテクニカル、SMART基準、ニュース見出し、確率シグナルを使い、UIとAIの材料ズレを避ける
- 日経平均上昇6条件は、日証金売り残、1570信用倍率、海外投資家買越額などの直接データがない場合に `proxy` または `unavailable` として明示する。代理評価は断定ではなく、AIプロンプトにもデータ品質として渡す
- ETFリーダーシップproxyは市場全体のリスクオン/オフ確認に使い、資金流入セクター判定は米国セクターETFと `JP_THEMES` の代表銘柄バスケットから具体候補を出す。スコアは相対騰落率、5日/20日継続性、出来高比、上昇参加率から作り、売買指示ではなく「乗る候補」「押し目待ち」「観察」「見送り」の調査支援ラベルに留める
- HTTPキャッシュは `src/network.py` が `.states/http_cache` 配下で用途別セッションとして管理し、ルート直下にSQLiteを作らない
- yfinanceオプションデータはGreeks欠損が多いため、Gammaが取得できない場合はGEXを非表示にし、`data_quality` と `quality_warnings` でUIとAIに明示する
- Reflex state では `dict[str, Any]` の深いアクセスが壊れやすいため、`pydantic.BaseModel` でUI表示用モデルを定義している
- 外部APIの失敗はアプリ全体を止めず、機能単位で degraded mode に落とす設計が多い
- Two Sigma OSSからは依存ではなく設計要素を取り込む。`temporal_alignment.py` は Flint 型の許容時間差付き as-of join を pandas で提供し、`AnalysisRun` は BeakerX 型の再現可能な分析成果物、`analysis_jobs.py` は Cook 型の重い分析ジョブ状態管理、`analysis_diagnostics.py` は Marbles 型の説明的テスト失敗メッセージを担う
- `.states/analysis_jobs` はローカルジョブ状態の永続化専用で、Kubernetesや外部スケジューラは前提にしない

## 現在の構造的な弱点

- Reflex UI と Streamlit UI が同居し、どちらが正本か判断しづらい
- データ取得、分析、UI整形が `frontend/state/*` と `src/services/*` にまたがって重複している
- 外部APIエラーが握りつぶされる箇所が多く、ユーザーに「何が古いデータか」「何が取得失敗か」が伝わりにくい
- 保存先の抽象化はあるが、local / GAS / Supabase のスキーマ契約・移行手順が不足している
- AIプロンプトへの入力データが一部文字列連結中心で、検証可能な中間データ構造が不足している

## トレンドフォロー診断レイヤー

- 初回実装は個別株の日足専用。新しいデータAPIや発注機能は追加せず、既存の yfinance 経路とキャッシュを使う
- 主診断は 50/200日移動平均の long-only。補助診断として 20/80日、20/120日、50/150日、50/200日のパラメータ比較を持つ
- シグナルは当日終値で判定し、翌営業日の Open で約定したものとして評価する。Open欠損時だけ Close を実行価格プロキシにする
- `diagnostic_rating` は売買推奨ではなく頑健性ラベル。既存の `overall_signal`、`Probabilistic Stock Signal`、SMART基準を置き換えない
- `StockSignalContext.trend_follow_diagnostics` は StockページUIと AI Stock Recap の共通入力で、AIには「OOSや右テール除外が弱い場合はエッジを断定しない」前提を渡す

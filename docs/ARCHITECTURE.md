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
  - `/theme`: トレンド/テーマ
  - `/data-quality`: Provider状態・来歴・欠損確認
  - `/portfolio`: ポートフォリオ分析
  - `/knowledge`: 参照知識管理
- 旧Streamlit UI: `codex/archive-streamlit-assets` ブランチへ履歴保全し、現行ツリーから撤去済み

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
  src/marketdata_client.py
  src/marketdata_option_provider.py
  src/jquants_client.py
  src/edinet_client.py

永続化
  src/storage/base.py
  src/portfolio_storage.py
  src/knowledge_storage.py
  src/settings_storage.py
  src/supabase_client.py

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
3. `MarketState.refresh_market_details()` が、既存の `MarketContext` を再利用しながら `Theme/Flow → Credit/Risk → Vol/Sentiment → Options` の依存順で更新する。信用ストレスはvolレジームと短期予測より先に確定する
4. 詳細更新では `sector_flow_service` が米国セクターETFと日本テーマバスケットから資金流入セクター、確信度、継続性、調査判断を計算し、`japan_market_conditions` が日経平均上昇の6条件を直接データまたは代理指標として評価する
5. `MarketState.refresh_options()` が SPY / QQQ / IWM のオプション取得を明示的に実行し、current / 1W / 1M の満期別チェーン、想定変動幅、Skew、GEX、キャッシュ鮮度、品質警告を `OptionContext.items` と `OptionContext.horizons` に保存する
6. Reflex state に整形済みデータを保存し、画面が再描画される
7. 表示用の整形は `services.market_presentation_service.build_market_display_context()` が担い、`MarketState` はイベント、loading/error、表示モデル保持に集中する
8. AI Market Recap は `services.market_analyst_service.generate_market_analysis_report()` から Gemini へ渡り、通常経路では既に取得済みの `MarketContext`、オプション品質情報、オプション期間構造、日米セクター流入、日経6条件、ユーザー指定の追加分析項目をプロンプトに含める。レポートは米国市場を主軸にし、日本市場は米国との連動・乖離を読む補助コーナーとして扱う

### 市場監視

- `/market-watch` は判断に必要な概要を常時表示し、市場レジーム・資金フロー、リスク・信用・予測、オプションの重い詳細だけを明示更新する。段階状態・警告・来歴は `/data-quality` に集約する
- 市場監視の詳細更新は、Core、Theme/Flow、Credit/Risk、Vol/Sentiment、Optionsの順に `MarketState` がyieldし、各ブロックの`status`、`cache_status`、`fetched_at`、`quality_warnings`を表示モデルへ渡す。例外がなくても必須結果が欠損・stale・research-onlyなら`partial`とする
- トレンド/テーマは `theme_analyst.get_ranked_themes_result()` が `FetchResult` として返し、provider失敗と正当な空結果を区別する。12時間のrepo-local永続キャッシュを再起動後も利用する。`ThemeState` は市場・期間・request idを組にして、後から完了した旧リクエストが現在の画面状態を上書きしないようにする
- `/market-watch` の `prepare_market_watch` は前回の詳細コンテキストを即時表示し、主要指数、Theme/Flowだけを自動更新する。SPY、Nasdaq 100、TLT、米10年債の価格履歴は `MarketAnalysisInputs` が1更新内で共有し、信用/歪みとオプションを同時開始してから派生分析を再計算する
- IBD式市場状態は `advisor.ibd_market_regime.classify_ibd_market_regime()` が SPY / Nasdaq 100 代理データから判定する。分類は `confirmed_uptrend`、`uptrend_under_pressure`、`rally_attempt`、`market_in_correction`
- `services.market_playbook` は市場状態ごとの「現在考えるべきこと」「今やること」「避けること」を固定データとして返す
- `advisor.sector_theme_diagnostics.detect_market_distortions()` はテーマごとのファンダメンタルスコアとフロースコアの乖離から、強気/弱気の歪み候補を上位5件ずつ返す

### 個別銘柄

1. `StockState.fetch_stock_data()` がティッカー入力後に実行される
2. `market_data` 経由で企業情報、価格、ニュース、テクニカルを取得
3. `advisor.smart_criteria.evaluate_smart_criteria()` で成長株観点の条件を評価
4. `advisor.probabilistic_signal.generate_probabilistic_stock_signal()` が過去の類似局面、forward return、walk-forward検証、サイジング目安を作る
   - 類似局面0件、benchmark欠損、vol欠損は0へ置換せず`None`を維持する
   - 独立した主要診断は最大4並列、各8秒・グループ16秒の上限で実行する
5. `advisor.trend_follow_diagnostics.generate_trend_follow_diagnostics()` が日足トレンドフォローを診断軸として評価し、OOS、コスト耐性、遅延耐性、右テール依存、Buy & Hold比較を `StockSignalContext` に追加する
6. `advisor.sector_theme_diagnostics.evaluate_stock_sector_theme_context()` が対象銘柄のセクター/テーマを、ファンダメンタル優位とフロー優位の両面から評価して `StockSignalContext` に追加する
7. `advisor.trade_setup.evaluate_trade_setup()` が市場/セクター相対強度、VCP、RVOL、ATR拡張、200MAトレンドを日足Entry Frameworkとして評価し、`StockSignalContext.trade_setup` に追加する
8. `StockSignalContext` は表示済みニュース見出し、SMART基準、テクニカル、Entry Frameworkも保持し、AI分析は `stock_analyst.analyze_stock()` が同じ入力を再利用してプロンプトを組み立てる
9. `StockState.show_trade_analysis()` はユーザーが「トレード分析」を押した場合だけ、既存の `StockSignalContext` から重要水準、押し目/ブレイク条件、無効化条件、需給根拠を生成する

### Trading Plan互換コード

1. 独立した `/trading-plan` ルートと通常ナビゲーションは廃止し、通常利用はStockページ内の「トレード分析」に統合する
2. `trading_plan_state`、`trading_plan_service`、`trading_plan_storage`、Supabase `trade_plans` は既存データ互換用に残す
3. 新規の通常ワークフローでは保存・レビュー機能をStockへ移植せず、分析データを使った条件整理だけを行う

### ポートフォリオ

1. UI入力を `PortfolioState.holdings` に保持
2. `portfolio_storage` が local / Supabase の保存先を抽象化
3. `portfolio_advisor.analyze_portfolio()` が各銘柄を現地通貨で評価し、共有`MarketContext`のUSD/JPY、なければ1回だけの`JPY=X` quoteで円換算する
4. 全銘柄を換算できる場合だけ円換算総額・構成比・セクター/日米テーマ露出・top1/top3/HHIを計算する。為替不足時は通貨別小計だけを返す
5. `portfolio_advisor.generate_portfolio_advice()` は同じ集約結果と現在/保存済み`MarketContext`を再利用してAIアドバイスを生成する

### 参照知識

1. `KnowledgeState` がテキスト、URL、YouTube、ファイルアップロードを受け取る
2. `knowledge_extractor` が本文抽出・要約・タイトル生成を行う
3. `knowledge_storage` が local / Supabase に保存する
4. `knowledge_storage.get_knowledge_for_ai_context()` が銘柄分析プロンプトに注入される

## 重要な設計判断

- `src/data_provider.py` は facade と依存性注入の入口を兼ねており、テスト時に外部APIを差し替えられる
- `market_dashboard_service.py` は既存呼び出し向けの公開facadeとして残す一方、抽出済みの `market_dashboard_support.py` / `market_dashboard_workflows.py` は wildcard import や全global同期を行わない。provider・cache・orchestration関数を `MarketDashboardSupportDependencies` / `MarketDashboardWorkflowDependencies` へ明示し、通常時は既定依存、移行中の互換テストは列挙済みfacade依存、直接テストは注入済み依存を使用する
- `src/cache.py` は Streamlit 依存を避けるためのフレームワーク非依存TTLキャッシュ。エントリごとに `created_at`、`expires_at`、`ttl`、`namespace` を持ち、関数単位の `.clear_cache()` と名前空間単位のクリアに対応する
- `src/persistent_cache.py` は `.states` 配下のJSONキャッシュ共通基盤。schema/version付きの原子的書き込み、破損JSON無視、fresh/stale/expired判定、ファイル名安全化を担う
- yfinance系の重い取得は、メモリTTLに加えて `.states/market_context_cache` と `.states/option_chain_cache` のJSONキャッシュを使う。オプションは ticker だけでなく target DTE 別のcache keyを使い、current / 1W / 1M が混線しないようにする。`source`、`fetched_at`、`is_stale`、`cache_status`、`quality_warnings` をUIとAIプロンプトへ渡す
- Market AI Recap は `MarketContext` がある場合に市場監視やテーマランキングを再取得せず、context 内の monitoring / momentum / option 情報を優先する。context 構築に失敗した互換パスだけ旧取得ロジックへフォールバックする
- Stock AI Recap は `StockSignalContext` がある場合に表示済みのテクニカル、SMART基準、ニュース見出し、確率シグナルを使い、UIとAIの材料ズレを避ける
- Entry Frameworkは日足専用で、LoD、ORH、寄付き後30分、1-2時間確認などの分足依存ルールを成立済みと仮定しない。`blocked`判定はAIが上書きしない
- 日経平均上昇6条件は、日証金売り残、1570信用倍率、海外投資家買越額などの直接データがない場合に `proxy` または `unavailable` として明示する。代理評価は断定ではなく、AIプロンプトにもデータ品質として渡す
- ETFリーダーシップproxyは市場全体のリスクオン/オフ確認に使い、資金流入セクター判定は選択市場ごとに分離する。USは広義セクターETFと細分化テーマETF proxyを優先し、JPは日本テーマ代表銘柄バスケットで具体候補を出す。スコアは相対騰落率、5日/20日継続性、出来高比、上昇参加率から作り、売買指示ではなく「乗る候補」「押し目待ち」「観察」「見送り」の調査支援ラベルに留める
- HTTPキャッシュは `src/network.py` が `.states/http_cache` 配下で用途別セッションとして管理し、ルート直下にSQLiteを作らない
- yfinanceオプションデータはGreeks欠損が多いため、Gammaが取得できない場合はGEXを非表示にし、`data_quality` と `quality_warnings` でUIとAIに明示する
- MarketData.appは米国オプションのpreferred経路として使う。対象はSPY / QQQ / IWM、統合トレンドランキング上位のテーマETF proxy、個別銘柄分析で所属テーマのETF option proxyを明示分析する場合に限定する。`off`ではyfinanceのみ、`shadow`ではyfinance表示を維持しながら比較取得、`preferred`ではMarketData.appを優先して失敗時にyfinance/cacheへフォールバックする。起動時や単なる描画時にはMarketData.appを呼ばない
- MarketData.appの解決済み満期チェーンは専用キャッシュへ保存し、IV・Greeks・OI・Volumeを直接値として扱う。同日満期は米国東部時間の有効時間帯だけ使い、引け後・週末・live smokeでは次回有効満期へ切り替える。1W / 1M は満期一覧から目標DTEに最も近い有効満期を選ぶ。PCR、Max Pain、GEXはローカル算出であり、GEXのディーラー方向は簡易仮定として来歴へ残す
- `src/services/data_fetch_manifest.py` は画面・分析ごとの必須/任意データ、許容鮮度、fallback/cache方針を定義する軽量マニフェスト。欠損監査やlive smoke拡張時はここを基準にする
- 分析機能の責務、許可される連携、欠損契約は `docs/ANALYSIS_FEATURE_CATALOG.md` を正本とする
- Reflex state では `dict[str, Any]` の深いアクセスが壊れやすいため、`pydantic.BaseModel` でUI表示用モデルを定義している
- 外部APIの失敗はアプリ全体を止めず、機能単位で degraded mode に落とす設計が多い
- Two Sigma OSSからは依存ではなく設計要素を取り込む。`temporal_alignment.py` は Flint 型の許容時間差付き as-of join を pandas で提供し、`AnalysisRun` は BeakerX 型の再現可能な分析成果物、`analysis_jobs.py` は Cook 型の重い分析ジョブ状態管理、`analysis_diagnostics.py` は Marbles 型の説明的テスト失敗メッセージを担う
- `.states/analysis_jobs` はローカルジョブ状態の永続化専用で、Kubernetesや外部スケジューラは前提にしない

## 現在の構造的な弱点

- 旧課題だったUI正本の曖昧さは、Reflexへの一本化とStreamlit資産の履歴ブランチ退避で解消済み
- データ取得、分析、UI整形が `frontend/state/*` と `src/services/*` にまたがって重複している
- 外部APIエラーが握りつぶされる箇所が多く、ユーザーに「何が古いデータか」「何が取得失敗か」が伝わりにくい
- 保存先の抽象化はあるが、local / Supabase のスキーマ契約・移行手順が不足している
- AIプロンプトへの入力データが一部文字列連結中心で、検証可能な中間データ構造が不足している

## トレンドフォロー診断レイヤー

- 初回実装は個別株の日足専用。新しいデータAPIや発注機能は追加せず、既存の yfinance 経路とキャッシュを使う
- 主診断は 50/200日移動平均の long-only。補助診断として 20/80日、20/120日、50/150日、50/200日のパラメータ比較を持つ
- シグナルは当日終値で判定し、翌営業日の Open で約定したものとして評価する。Open欠損時だけ Close を実行価格プロキシにする
- `diagnostic_rating` は売買推奨ではなく頑健性ラベル。既存の `overall_signal`、`Probabilistic Stock Signal`、SMART基準を置き換えない
- `StockSignalContext.trend_follow_diagnostics` は StockページUIと AI Stock Recap の共通入力で、AIには「OOSや右テール除外が弱い場合はエッジを断定しない」前提を渡す

## 適応型分析レイヤー（2026-06-23）

- `volume_profile_service.py`: 取得済み日足OHLCVだけから126営業日・24帯の
  POC/Value Area/支持抵抗帯を生成する純粋計算層。
- `fundamental_profile_service.py`: 時価総額→バリュー/グロース→業種の三層分類と、
  5評価軸の適応型スコアを生成する。基準は
  `src/data/fundamental_benchmarks_2026.json`から読み、ランタイム通信しない。
- `purchase_evidence_service.py`: テクニカル側とファンダメンタル・テーマ側の
  調和平均を取り、既存Entry/Stage/FOMO/確率シグナルを上限制約として再利用する。
- `StockSignalContext`が上記3 payloadの正本。Stock UI、オンデマンドトレード分析、
  AI銘柄分析は同一payloadを読み、再取得・再採点しない。
- `MarketContext.important_levels`はSPY/QQQまたは1306.T/1321.Tのprofileを保持する。
  v1では`strategy_regime`の採点へ入力しない。
- 詳細な計算契約、閾値、業種除外、出典は
  `docs/ADAPTIVE_STOCK_ANALYSIS.md`を参照する。

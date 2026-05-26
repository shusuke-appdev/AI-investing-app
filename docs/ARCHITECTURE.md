# アーキテクチャ概要

## 目的

このアプリは、投資判断に必要な市場データ、ニュース、テクニカル指標、テーマ別動向、ポートフォリオ情報、個人の参照知識を集約し、AIで要約・分析する調査支援システムです。

中核は「外部データを取得し、分析ロジックで構造化し、UIとAIレポートへ渡す」流れです。

## 実行入口

- Reflex UI: `frontend/frontend.py`
- ルート定義:
  - `/`: Market Intelligence
  - `/stock`: 個別銘柄分析
  - `/theme`: テーマ別トレンド
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
```

## 主要なデータフロー

### Market Intelligence

1. `MarketState.fetch_market_summary_fast()` がUIロードで実行され、`.states/market_context_cache` の最後の軽量サマリーを優先表示する
2. 軽量サマリーは `market_data.get_market_indices()` と `market_config.get_market_config()` のみを取得し、起動時にオプション取得を行わない
3. `MarketState.refresh_market_details()` が、既存の `MarketContext` を再利用しながら市場環境、マイクロストラクチャー、テーマ、監視指標を更新する
4. `MarketState.refresh_options()` が SPY / QQQ / IWM のオプション取得を明示的に実行し、取得結果、キャッシュ鮮度、品質警告を `OptionContext` に保存する
5. Reflex state に整形済みデータを保存し、画面が再描画される
6. AI Market Recap は `services.market_analyst_service.generate_market_analysis_report()` から Gemini へ渡り、`MarketContext` とオプション品質情報をプロンプトに含める

### 個別銘柄

1. `StockState.fetch_stock_data()` がティッカー入力後に実行される
2. `market_data` 経由で企業情報、価格、ニュース、テクニカルを取得
3. `advisor.smart_criteria.evaluate_smart_criteria()` で成長株観点の条件を評価
4. AI分析は `stock_analyst.analyze_stock()` がプロンプトを組み立て、Gemini に渡す

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
- HTTPキャッシュは `src/network.py` が `.states/http_cache` 配下で用途別セッションとして管理し、ルート直下にSQLiteを作らない
- yfinanceオプションデータはGreeks欠損が多いため、Gammaが取得できない場合はGEXを非表示にし、`data_quality` と `quality_warnings` でUIとAIに明示する
- Reflex state では `dict[str, Any]` の深いアクセスが壊れやすいため、`pydantic.BaseModel` でUI表示用モデルを定義している
- 外部APIの失敗はアプリ全体を止めず、機能単位で degraded mode に落とす設計が多い

## 現在の構造的な弱点

- Reflex UI と Streamlit UI が同居し、どちらが正本か判断しづらい
- データ取得、分析、UI整形が `frontend/state/*` と `src/services/*` にまたがって重複している
- 外部APIエラーが握りつぶされる箇所が多く、ユーザーに「何が古いデータか」「何が取得失敗か」が伝わりにくい
- 保存先の抽象化はあるが、local / GAS / Supabase のスキーマ契約・移行手順が不足している
- AIプロンプトへの入力データが一部文字列連結中心で、検証可能な中間データ構造が不足している

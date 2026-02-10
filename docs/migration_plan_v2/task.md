# Finnhub移行タスク

## タスク一覧

- [x] **Component 1: finnhub_client.py 新規作成**
  - [x] レート制限・リトライ・キャッシュ付きクライアント

- [x] **Component 2: market_data.py 改修**
  - [x] get_stock_data → Finnhub candles
  - [x] get_stock_info → Finnhub profile + financials
  - [x] get_market_indices → Finnhub quote（米国）
  - [x] get_stock_news → Finnhub company_news（Yahoo代替）
  - [x] get_option_chain → yfinance維持 + リトライ強化

- [x] **Component 2.5: news_aggregator.py 改修**
  - [x] merge_with_yfinance_news → merge_with_finnhub_news に変更
  - [x] Google News (gnews) は維持

- [x] **Component 3: theme_analyst.py 改修**
  - [x] yf.download → Finnhub candles ループ (Plan準拠)

- [x] **Component 4: earnings_data.py 改修**
  - [x] yf.Ticker → Finnhub earnings API

- [x] **Component 5: financials.py 改修**
  - [x] 決算サプライズ → Finnhub earnings_surprises
  - [x] 四半期財務 → Finnhub financials_reported (Plan準拠)

- [x] **Component 6: option_analyst.py リスク緩和**
  - [x] リトライ + フォールバック追加（market_data.py側で対応）

- [x] **Component 7: 設定・依存関係**
  - [x] requirements.txt 更新
  - [x] sidebar.py にFinnhub APIキー設定UI追加
  - [x] settings_storage.py にFinnhub key保存追加

- [ ] **検証**
  - [x] test_finnhub_client.py 作成・実行（Setting連動確認）
  - [ ] 実機での動作確認（APIキー設定後）
  - [ ] マニュアル動作確認

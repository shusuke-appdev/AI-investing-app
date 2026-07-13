# yfinance → Finnhub 移行計画 v2（履歴資料）

yfinanceからFinnhub APIへ情報収集基盤を移行する。  
yfinanceが優位な機能は維持しつつ、リスク緩和策を講じるハイブリッド構成。

---

## yfinance リスク分析

> [!CAUTION]
> **yfinanceは非公式API（Webスクレイピング）** — Yahoo Finance公式のAPIは存在しない。
> yfinanceはYahooのWebページ/内部エンドポイントをスクレイピングしており、以下のリスクがある。

| リスク | 深刻度 | 詳細 |
|:---|:---|:---|
| **突然の仕様変更** | 🔴 高 | Yahoo側のHTML/API構造変更で予告なく動作不能になる（過去に複数回発生） |
| **レート制限・IP Ban** | 🟡 中 | ~2,000 req/h超でスロットリング、429エラー、IP一時Ban（1h） |
| **法的リスク** | 🟡 中 | Yahoo ToS違反の可能性（商用利用は特に注意）。CFAA・著作権問題 |
| **データ品質** | 🟡 中 | 非公式のためデータ欠損・遅延・フォーマット変動が無保証 |
| **メンテナンス停止** | 🟡 中 | OSSコミュニティ依存。メンテナー離脱でYahoo変更への追従が遅れる可能性 |

---

## 移行判定: 機能ごとの方針

| 機能 | 現在 | 移行先 | 理由 |
|:---|:---|:---|:---|
| 株価OHLCV | yfinance | **Finnhub** | 公式API。安定性・信頼性向上 |
| 企業情報 | yfinance | **Finnhub** | 公式API。30年分の財務データ |
| ニュース | yfinance | **Finnhub** | 公式API。マーケットニュースも取得可能 |
| 市場指数 | yfinance | **Finnhub** | 公式API |
| 決算データ | yfinance | **Finnhub** | 公式API。カレンダーAPI一括取得で効率化 |
| 四半期財務 | yfinance | **Finnhub** | 公式API。標準化された財務諸表 |
| テーマ別騰落率 | yfinance | **Finnhub** | 公式API。ただしレート制限対策要 |
| **オプションチェーン** | yfinance | **yfinance維持** | Finnhub Free Tierでオプション提供なし |
| **日本市場データ** | Stooq | **Stooq維持** | Finnhub Free Tierで日本株カバー不足 |

---

## User Review Required

> [!IMPORTANT]
> **Finnhub APIキー**: Free Tier利用（要無料登録）。`st.secrets` / 環境変数で管理。

> [!WARNING]
> **yfinance維持部分のリスク緩和策**（オプション分析）:
> - **リトライ+指数バックオフ**: 429エラー時に自動リトライ
> - **フォールバック設計**: yfinance障害時にエラーを握りつぶさず、UIに「データ取得不可」と表示
> - **将来の完全脱却パス**: 有料オプションデータAPI（CBOE, Tradier等）への移行を視野に

> [!CAUTION]
> **レート制限**: Finnhub Free = 60 calls/min。テーマ分析（~50銘柄）でバッチ処理+キャッシュ必須。

---

## Proposed Changes

### Component 1: Finnhubクライアントモジュール

#### [NEW] [finnhub_client.py](file:///c:/Users/shusk/.gemini/antigravity/workspace/AI-investing-app/src/finnhub_client.py)

Finnhub APIラッパー。レート制限・リトライ・キャッシュ内蔵。

```python
# 主要関数
get_quote(symbol)              # リアルタイム株価
get_candles(symbol, res, from, to) # OHLCV → pd.DataFrame
get_company_profile(symbol)    # 企業プロフィール
get_company_news(symbol, from, to) # 銘柄ニュース
get_market_news(category)      # マーケットニュース
get_basic_financials(symbol)   # P/E, EPS 等
get_financials_reported(symbol)# 四半期財務諸表
get_earnings_surprises(symbol) # EPSサプライズ
get_earnings_calendar(from, to)# 決算カレンダー
```

- レート制限: `time.sleep` + リトライ（指数バックオフ）
- キャッシュ: `@st.cache_data`（quote: 5min, fundamentals: 12h）

---

### Component 2: market_data.py 改修

#### [MODIFY] [market_data.py](file:///c:/Users/shusk/.gemini/antigravity/workspace/AI-investing-app/src/market_data.py)

| 関数 | 変更 |
|:---|:---|
| `get_stock_data()` | yfinance → Finnhub candles |
| `get_multiple_stocks_data()` | ループ + レート制限 |
| `get_stock_info()` | yfinance → Finnhub profile + financials |
| `get_market_indices()` | 米国: Finnhub / 日本: Stooq維持 |
| `get_stock_news()` | yfinance → Finnhub company_news |
| `get_option_chain()` | **yfinance維持** + リトライ + フォールバック |

---

### Component 3: theme_analyst.py 改修

#### [MODIFY] [theme_analyst.py](file:///c:/Users/shusk/.gemini/antigravity/workspace/AI-investing-app/src/theme_analyst.py)

- `yf.download()` 一括 → Finnhub candles ループ
- バッチ処理: 50銘柄を1秒間隔でリクエスト（60/min以内）
- キャッシュ: 12h TTL維持

---

### Component 4: earnings_data.py 改修

#### [MODIFY] [earnings_data.py](file:///c:/Users/shusk/.gemini/antigravity/workspace/AI-investing-app/src/earnings_data.py)

- 個別`yf.Ticker()` → `finnhub_client.get_earnings_calendar()` 一括取得
- EPSサプライズ: `get_earnings_surprises()` で効率化

---

### Component 5: financials.py 改修

#### [MODIFY] [financials.py](file:///c:/Users/shusk/.gemini/antigravity/workspace/AI-investing-app/src/ui/components/stock/financials.py)

- 四半期財務: Finnhub `get_financials_reported()`（レスポンス変換が必要）
- 決算サプライズ: Finnhub `get_earnings_surprises()`

---

### Component 6: option_analyst.py — yfinance維持 + リスク緩和

#### [MODIFY] [option_analyst.py](file:///c:/Users/shusk/.gemini/antigravity/workspace/AI-investing-app/src/option_analyst.py)

**yfinance維持**。以下のリスク緩和策を追加:

- リトライ（指数バックオフ、最大3回）
- エラーハンドリング強化（429, ConnectionError, JSONDecodeError）
- フォールバック: 取得失敗時に「オプションデータ取得不可」メッセージをUI表示
- 将来の脱却パス: 関数インターフェースを維持し、内部実装のみ差し替え可能な設計

---

### Component 7: 設定・依存関係

#### [MODIFY] [requirements.txt](file:///c:/Users/shusk/.gemini/antigravity/workspace/AI-investing-app/requirements.txt)
- `finnhub-python>=2.4.0` 追加
- `yfinance>=0.2.40` **維持**（オプション分析用）

#### [MODIFY] [app.py](file:///c:/Users/shusk/.gemini/antigravity/workspace/AI-investing-app/app.py)
- Finnhub APIキー設定UI（サイドバー）

---

## Verification Plan

### 自動テスト
- `test_finnhub_client.py`: モック使用の各関数テスト
- 既存テスト（`test_option_analyst.py`, `test_news_aggregator.py`）パス確認

### 統合テスト
- `verify_finnhub_migration.py`: データ形式・レート制限動作の検証

### マニュアルテスト
- 全タブの動作確認（Market / Stock / テーマ / オプション）
- yfinance障害シミュレーション（オプション分析のフォールバック確認）

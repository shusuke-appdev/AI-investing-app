---
title: AI Investing App
emoji: 📈
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: Market intelligence and investment research dashboard
---

# AI Investing App

AI Investing App は、米国株・日本株を対象に、市場環境、テーマ別モメンタム、個別銘柄、ポートフォリオ、ユーザー知識ベースを横断して分析する投資調査ダッシュボードです。

現行UIは **Reflex** で、画面の入口は `frontend/` です。移行前のStreamlit資産は `codex/archive-streamlit-assets` ブランチへ履歴保全し、現行ツリーから撤去済みです。

> 注意: 本アプリは投資判断を補助する調査ツールです。売買助言、投資一任、金融商品の推奨を目的としたものではありません。

## 主な機能

- Market Intelligence: 主要指数、セクター、コモディティ、為替、暗号資産、VIX、米国債利回りを一覧化
- 市場環境評価: トレンド、モメンタム、ボラティリティ、マーケットブレッドス、オプションセンチメントを統合評価
- 短期市場予測: SPY / QQQの1・5・20営業日をwalk-forward検証し、VIX・SKEW・VVIX・期間構造・breadth・OCC Put/Call・Gammaを複合判定。検証未達は研究表示に限定し、個別株には警戒方向のガードレールだけを適用
- オプション分析: SPY / QQQ / IWM と主要テーマETF proxy の Put/Call Ratio、Gamma Exposure、Max Pain、ATM IV、Skew を算出。MarketData.appを米国オプションの preferred 経路として利用し、失敗時はyfinance/cacheへフォールバック
- トレンド/テーマ: AI、半導体、エネルギー、ヘルスケアなどのテーマを期間別に比較
- 個別銘柄分析: 企業概要、価格チャート、ニュース、テクニカル、SMART基準、日足Entry Framework、トレード分析、AI分析レポート
- ポートフォリオ分析: 現地通貨時価、USD/JPY確認後の円換算総額、通貨別小計、構成比、セクター・日米テーマ露出、集中度、AIアドバイス。為替欠損時は異なる通貨を合算しません
- 参照知識管理: テキスト、URL、YouTube、ファイルから知識を登録し、AI分析のコンテキストに利用

## 技術スタック

- UI: Reflex
- データ取得: yfinance、Finnhub、J-Quants、EDINET、Google News
- AI: Google Gemini API
- 保存先: ローカルJSON、Supabase
- グラフ・数値処理: pandas、numpy、scipy、plotly、statsmodels、arch
- 品質確認: pytest、ruff

## ディレクトリ構成

```text
AI-investing-app/
  frontend/                Reflex UI、ページ、状態管理
  src/                     データ取得、分析、保存、AI連携の本体
    advisor/               テクニカル、ボラティリティ、市場環境、ポートフォリオ分析
    services/              AI市場分析などのユースケース調整層
    storage/               保存先の抽象インターフェース
  tests/                   単体テスト
  docs/                    現行仕様・運用・来歴台帳とarchive済み履歴資料
  scripts/                 検証・デバッグ用スクリプト
```

## セットアップ

Python 3.12 を推奨します。このワークスペースでは `py -3.12` で Python 3.12.10 を起動できます。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt -c constraints.txt
```

`.env.example` を参考に `.env` を作成します。

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL_NAME=gemini-3.6-flash
FINNHUB_API_KEY=your_finnhub_api_key_here
JQUANTS_API_KEY=your_jquants_api_key_here
EDINET_API_KEY=your_edinet_api_key_here
MARKETDATA_TOKEN=your_marketdata_token_here
MARKETDATA_OPTIONS_MODE=preferred
SUPABASE_URL=your_supabase_url_here
SUPABASE_SECRET_KEY=your_supabase_secret_key_here
# SUPABASE_SERVICE_ROLE_KEY=your_legacy_service_role_key_here
# SUPABASE_KEY=your_legacy_supabase_key_here
```

アプリは個人利用の単一モードです。Portfolio・Knowledge、AI生成、URL・YouTube取り込みを常に利用できます。ローカル実行にはモード設定は不要です。Hugging Face Spaces では、最初に Space を **Private** にし、その反映を確認した後でだけ `PRIVATE_DEPLOYMENT_ACK=1` を設定してください。Public のまま ACK だけを追加する運用は禁止です。`SPACE_ID` がある環境で確認値がなければ、アプリは安全側に倒して起動を拒否します。
既存Trading Plan互換データは保存層に残りますが、通常UIではStockページ内の「トレード分析」を使います。
保存先の既定値はローカルJSONです。

MarketData.app の live オプション取得を厳格に検証するには、ローカル `.env` に `MARKETDATA_TOKEN` と `MARKETDATA_OPTIONS_MODE=preferred` を設定してください。未設定時はアプリ障害ではなく `MarketData未設定 / yfinance・cache fallback中` として扱います。SPY の current / 1W / 1M 期間構造まで確認する場合は次を実行します。

```powershell
.\.venv\Scripts\python.exe scripts\live_smoke.py --require-marketdata --marketdata-tickers SPY --marketdata-min-dte 1 --marketdata-horizon-dtes 7,30
```

その他の実APIを必須検証にする場合は、用途に応じて `--require-supabase`、`--require-finnhub`、`--require-edinet`、`--require-yfinance-options` を付けます。従来の `--require-optional` は `--require-supabase` の互換エイリアスです。

公式OCCの日次Put/Call履歴をローカルへ蓄積し、短期予測・複合判定を実データで確認する場合は次を実行します。Cboe/CFTC/OCC用の追加キーは不要です。

```powershell
.\.venv\Scripts\python.exe scripts\backfill_market_sentiment.py --symbols SPY,QQQ --sessions 252
.\.venv\Scripts\python.exe scripts\live_smoke.py --require-market-forecast
```

J-Quants Freeの価格系列は遅延するため、汎用の現在値・価格履歴には使用しません。日本株の現在値・履歴はyfinanceを使い、J-Quantsは企業マスター・財務情報の補完に限定します。

## 起動

Reflex 版:

```powershell
reflex run
```

Docker / Hugging Face Spaces 相当:

```powershell
docker build -t ai-investing-app .
docker run --env-file .env -p 7860:7860 ai-investing-app
```

Hugging Face への本番反映は、Private 化、Supabase の `ACTIVE_HEALTHY` 復旧、`SUPABASE_SECRET_KEY` による `scripts/live_smoke.py --require-supabase`、Space secret と ACK の登録、deploy の順で行います。CI は push 時に作成した Hugging Face commit SHA が Hub の現在 SHA と一致し、その revision が `RUNNING` になった後で、認証付き `/_health` の HTTP 200 と `{"status": true}` を確認します。新 secret で本番確認が完了するまで、互換用 `SUPABASE_KEY` は削除しません。

`requirements.txt` はReflex本番用、`requirements-dev.txt` はテスト・lint用です。

## 品質確認

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

このワークスペースでは、Python 3.12.10ベースのrepo-local `.venv` を使用します。現在の検証手順は [運用・環境設定ガイド](docs/OPERATIONS.md) を参照してください。過去の復旧・監査記録は `docs/archive/` に保存しています。

## 必読資料

- [文書索引](docs/README.md)
- [分析・予測機能カタログ](docs/ANALYSIS_FEATURE_CATALOG.md)
- [アーキテクチャ概要](docs/ARCHITECTURE.md)
- [運用・環境設定ガイド](docs/OPERATIONS.md)
- [市場監視・予測の役割分担](docs/MARKET_MONITORING_PREDICTION.md)
- [Supabase Data API grants 対応](docs/SUPABASE_DATA_API_GRANTS.md)
- [データ取得・分析機能レビュー](docs/DATA_ANALYSIS_REVIEW.md)
- [分析データ来歴台帳](docs/ANALYSIS_DATA_PROVENANCE.md)
- [実行タスク](task.md)

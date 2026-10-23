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

AI Investing App は、米国株・日本株を対象に、基本市況、テーマ・トレンド、成長株の順張り条件と個別銘柄の詳細を分析する投資調査ダッシュボードです。

日常の投資調査は **Codexとの会話とローカルPython** で運用します。[運用手順](docs/CODEX_OPERATION.md)を参照してください。画面の自動起動やアプリ公開は行いません。既存Web実装はReflexで、入口は`frontend/`です。移行前のStreamlit資産は `codex/archive-streamlit-assets` ブランチへ履歴保全し、現行ツリーから撤去済みです。

> 注意: 本アプリは投資判断を補助する調査ツールです。売買助言、投資一任、金融商品の推奨を目的としたものではありません。

## Codexでローカル調査を使う

2026-10-24方針：通常はCodexで「投資更新」「保存済み結果を見せて」と依頼します。CLIは`research.py update` / `research.py saved`。結果をチャットとMarkdown/JSONで確認し、以下のローカル画面は希望時だけ利用する補助です。[Codex運用](docs/CODEX_OPERATION.md)。

2026-10-23：ローカル版に地合い4観点、日米業種ETF、強さ・勢い図、銘柄条件一覧、四半期業績加速を追加。市場・価格／業績／両方の更新を選べます。操作とデータ不足の扱いは[地合い・業種・テーマ調査](docs/TOPDOWN_RESEARCH.md)を参照してください。

追加のモデルAPI契約なしでPython分析をCodexから実行し、オフラインのダッシュボードに保存できます。`Open-Investment-Research.cmd` を開き「投資更新」を押すと、日米の市場・テーマ・代表銘柄・接続分析・方針・取得状態を一括更新。標準は5つの問いに整理し、旧29項目の研究詳細も明示更新できます。別のCodexチャットでもこのプロジェクトを選び「投資更新」で利用可能。CLIは `.venv\Scripts\python.exe scripts\research.py update --profile standard --open`。個別株・会計・評価の基準日は一括更新で変更しません。[操作説明](docs/CODEX_RESEARCH.md)、[市場再構成の受入記録](docs/MARKET_REDESIGN_ACCEPTANCE.md)、設計Skill `.agents/skills/research-dashboard/SKILL.md` を参照してください。旧Reflex本番は停止・公開移行していません。

2026-10-07のローカル移行対象は、専門チャート/全操作と日米6社の会計・全セグメント照合まで含みます。[全機能対応表](docs/RESEARCH_FEATURE_PARITY.md)と[実データ・検証記録](docs/RESEARCH_MIGRATION_ACCEPTANCE.md)で、確認済み事実・仮定・取得不能・非開示を区別しています。資料ベースの4評価方式と複数方式表示を備えますが、仮定不足の会社価値は作りません。ChatGPT/Vercelへの公開接続や本番停止は対象外です。

## 主な機能

- Market Intelligence: 主要指数、セクター、コモディティ、為替、暗号資産、VIX、米国債利回りを一覧化
- 市場環境評価: トレンド、モメンタム、ボラティリティ、マーケットブレッドス、オプションセンチメントを統合評価
- 短期市場予測: SPY / QQQの1・5・20営業日をwalk-forward検証し、VIX・SKEW・VVIX・期間構造・breadth・OCC Put/Call・Gammaを複合判定。検証未達は研究表示に限定し、個別株では市場参考情報として別枠表示
- オプション分析: SPY / QQQ / IWM と主要テーマETF proxy の Put/Call Ratio、Gamma Exposure、Max Pain、ATM IV、Skew を算出。MarketData.appを米国オプションの preferred 経路として利用し、失敗時はyfinance/cacheへフォールバック
- トレンド/テーマ: 価格、市場相対強度、価格・出来高による資金注目度、広がりを100点で総合順位化。別ページの明示操作時だけ、登録代表と一次資料で検証したGemini探索銘柄をStage 2・相対強度・価格出来高・適応型ファンダメンタルで絞る
- 基本市況: S&P 500・Nasdaq 100・TOPIXを上段チャートで比較し、株式指数を米国・日本・その他地域へ小分類。金利は株式指数から分離して表示
- 企業価値分析: 個別株の明示操作時だけ、企業類型に応じた理論株価レンジと割安性を決定論的に算出し、検証済み一次資料からセグメント・会社見通し・カタリスト・リスクを整理
- 個別銘柄分析: 企業概要、価格チャート、ニュース、テクニカル、SMART基準、日足Entry Framework、トレード分析、AI分析レポート

## 技術スタック

- UI: Reflex
- データ取得: yfinance、Finnhub、J-Quants、EDINET
- AI: Google Gemini API
- 状態・分析キャッシュ: ローカルファイル（個人データ用DBなし）
- グラフ・数値処理: pandas、numpy、scipy、plotly、statsmodels、arch
- 品質確認: pytest、ruff

## ディレクトリ構成

```text
AI-investing-app/
  frontend/                Reflex UI、ページ、状態管理
  src/                     データ取得、分析、保存、AI連携の本体
    advisor/               テクニカル、ボラティリティ、市場環境分析
    services/              市場・テーマ・個別株のユースケース調整層
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
python -m pip install pip==25.3 setuptools==82.0.1 wheel==0.48.0
python -m pip install -r requirements-dev-lock.txt
```

`requirements.txt` / `requirements-dev.txt` は直接依存、`requirements-lock.txt` /
`requirements-dev-lock.txt` はPython 3.12向けの推移依存を含む固定済み環境です。

`.env.example` を参考に `.env` を作成します。

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL_NAME=gemini-3.8-flash
FINNHUB_API_KEY=your_finnhub_api_key_here
JQUANTS_API_KEY=your_jquants_api_key_here
EDINET_API_KEY=your_edinet_api_key_here
MARKETDATA_TOKEN=your_marketdata_token_here
MARKETDATA_OPTIONS_MODE=preferred
```

個人利用のPrivateアプリです。基本市況を起動画面とし、個別銘柄の主画面は条件確認、詳細欄は既存の参考分析です。ポートフォリオ・知識管理・旧売買日誌・Supabase接続は撤去済みです。Hugging FaceはPrivateを維持し、確認後に`PRIVATE_DEPLOYMENT_ACK=1`を設定します。

[機能対応表・分析境界・外部廃止手順](docs/FEATURE_REORGANIZATION.md)を参照してください。

MarketData.app の live オプション取得を厳格に検証するには、ローカル `.env` に `MARKETDATA_TOKEN` と `MARKETDATA_OPTIONS_MODE=preferred` を設定し、クレジット消費を `--allow-marketdata-credits` で明示承認してください。承認フラグなしでは通信せず `SKIP` とします。SPY の current / 1W / 1M 期間構造まで確認する場合は次を実行します。

```powershell
.\.venv\Scripts\python.exe scripts\live_smoke.py --allow-marketdata-credits --require-marketdata --marketdata-tickers SPY --marketdata-min-dte 1 --marketdata-horizon-dtes 7,30
```

その他の実APIを必須検証にする場合は、`--require-finnhub`、`--require-edinet`、`--require-yfinance-options`を使用します。

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

Hugging Faceへの本番反映はPrivate確認後に行い、CIで対象revisionの起動と認証付きhealthを検証します。DB接続は不要です。

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

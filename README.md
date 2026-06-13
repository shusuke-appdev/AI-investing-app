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

現在の主UIは **Reflex** です。Streamlit 実装は `src/ui/` と `legacy_streamlit/` に残っていますが、現行画面の入口は `frontend/` です。

> 注意: 本アプリは投資判断を補助する調査ツールです。売買助言、投資一任、金融商品の推奨を目的としたものではありません。

## 主な機能

- Market Intelligence: 主要指数、セクター、コモディティ、為替、暗号資産、VIX、米国債利回りを一覧化
- 市場環境評価: トレンド、モメンタム、ボラティリティ、マーケットブレッドス、オプションセンチメントを統合評価
- オプション分析: SPY / QQQ / IWM の Put/Call Ratio、Gamma Exposure、Max Pain、ATM IV、Skew を算出。MarketData.appを任意の直接Greeks補完経路として利用可能
- テーマランキング: AI、半導体、エネルギー、ヘルスケアなどのテーマを期間別にランキング
- 個別銘柄分析: 企業概要、価格チャート、ニュース、テクニカル、SMART基準、日足Entry Framework、AI分析レポート
- Trading Plan: 3段階ストップ、R基準サイジング、T+1/T+3確認、利確・ジャーナル管理
- ポートフォリオ分析: 保有銘柄、評価額、セクター・テーマ露出、AIアドバイス
- 参照知識管理: テキスト、URL、YouTube、ファイルから知識を登録し、AI分析のコンテキストに利用

## 技術スタック

- UI: Reflex
- 旧UI: Streamlit
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
    ui/                    旧Streamlit UI
  tests/                   単体テスト
  docs/                    設計・運用・点検・改修計画
  scripts/                 検証・デバッグ用スクリプト
  legacy_streamlit/        旧Streamlitアプリ
```

## セットアップ

Python 3.12 を推奨します。このワークスペースでは `py -3.12` で Python 3.12.10 を起動できます。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -c constraints.txt
```

`.env.example` を参考に `.env` を作成します。

```env
APP_MODE=private
GEMINI_API_KEY=your_gemini_api_key_here
FINNHUB_API_KEY=your_finnhub_api_key_here
JQUANTS_API_KEY=your_jquants_api_key_here
EDINET_API_KEY=your_edinet_api_key_here
MARKETDATA_TOKEN=your_marketdata_token_here
MARKETDATA_OPTIONS_MODE=shadow
SUPABASE_URL=your_supabase_url_here
SUPABASE_SECRET_KEY=your_supabase_secret_key_here
# SUPABASE_SERVICE_ROLE_KEY=your_legacy_service_role_key_here
# SUPABASE_KEY=your_legacy_supabase_key_here
```

`APP_MODE=private` は個人利用向けで、Portfolio・Knowledge・Trading Plan、AI生成、URL・YouTube取り込みを許可します。
公開配置では `APP_MODE=public_readonly` を設定してください。公開モードでは個人データを読み書きせず、個人ページをナビゲーションから除外し、AI生成とURL・YouTube取り込みも拒否します。
保存先の既定値はローカルJSONです。

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

旧Streamlit版:

```powershell
streamlit run legacy_streamlit/app.py
```

## 品質確認

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

このワークスペースでは、2026-05-14 に `.venv\Scripts\python.exe` の起動不全を復旧し、Python 3.12.10 ベースで `.venv` を再作成済みです。現在は上記の通常コマンドで `pytest`、`compileall`、`ruff check`、`ruff format --check` が通ります。詳細は [コード点検結果](docs/CODE_AUDIT.md) を参照してください。

## 必読資料

- [総合リファクタリング・分析責務マップ](docs/PRODUCT_REFACTOR_ROADMAP.md)
- [アーキテクチャ概要](docs/ARCHITECTURE.md)
- [運用・環境設定ガイド](docs/OPERATIONS.md)
- [Supabase Data API grants 対応](docs/SUPABASE_DATA_API_GRANTS.md)
- [コード点検結果](docs/CODE_AUDIT.md)
- [データ取得・分析機能レビュー](docs/DATA_ANALYSIS_REVIEW.md)
- [分析データ来歴台帳](docs/ANALYSIS_DATA_PROVENANCE.md)
- [UI総合改善計画](docs/UI_IMPROVEMENT_PLAN.md)
- [根本改修ロードマップ](docs/REMEDIATION_ROADMAP.md)
- [実行タスク](task.md)

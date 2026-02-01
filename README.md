# AI投資アプリ

金融市場分析と投資戦略検証のためのPythonアプリケーション。

## 機能

### 1. Market Intelligence (市場サマリー)
- **Flash Summary**: 主要指数、金利、為替、商品の速報
- **オプション分析**: SPY/QQQ/IWMのGEX、PCR、Gamma Wall
- **AI Market Recap**: Gemini APIを使用したナラティブ形式の市況解説

### 2. テーマ別トレンド
- 18種類の投資テーマ（AI半導体、宇宙、レアアースなど）
- 期間別（1日〜3ヶ月）の騰落ランキング
- テーマごとの構成銘柄とパフォーマンス詳細

### 3. 個別銘柄分析
- 株価チャート（ローソク足）
- 企業概要と事業内容
- 基本指標（PER、時価総額など）
- 関連ニュース

### 4. バックテスト
- 3種類の戦略（SMAクロスオーバー、RSI、MACD）
- パラメータ調整可能
- 資産曲線の可視化

## セットアップ

### 1. 仮想環境の作成
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
```

### 2. 依存関係のインストール
```bash
pip install -r requirements.txt
```

### 3. 環境変数の設定
`.env.example` をコピーして `.env` を作成し、Gemini APIキーを設定：
```
GEMINI_API_KEY=your_api_key_here
```

### 4. アプリの起動
```bash
streamlit run app.py
```

## ファイル構成

```
AI-investing-app/
├── app.py                  # メインアプリケーション
├── themes_config.py        # テーマと銘柄の定義
├── requirements.txt        # 依存関係
├── .env                    # 環境変数（要作成）
├── .env.example            # 環境変数テンプレート
├── README.md               # このファイル
└── src/
    ├── __init__.py
    ├── market_data.py      # 市場データ取得
    ├── theme_analyst.py    # テーマ分析
    ├── option_analyst.py   # オプション分析
    ├── news_analyst.py     # AIレポート生成
    ├── strategies.py       # 売買戦略定義
    └── backtester.py       # バックテストエンジン
```

## 使用技術

- **UI**: Streamlit
- **データ**: yfinance
- **AI**: Google Gemini API
- **可視化**: Plotly
- **バックテスト**: backtesting.py

## 注意事項

- yfinanceの無料APIには制限があります
- Gemini APIキーはGoogle AI Studioで取得できます
- 本アプリは投資助言を目的としていません

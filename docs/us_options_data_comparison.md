# 米国株オプションデータ取得方法の比較

現在の `yfinance` (無料・非公式) と、より詳細なGreeks / IVを取得するAPIの比較です。2026-06-16時点ではMarketData.appをSPY / QQQ / IWMと主要テーマETF proxyのpreferred経路として実装済みです。

| 特徴 | yfinance | **MarketData.app（実装済み）** | ThetaData | Polygon.io | Interactive Brokers (IBKR) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Greeks (Δ,Γ,Θ,ν)** | 欠損が多い | **API直接値** | API直接値 | API直接値 | API直接値 |
| **IV** | 欠損あり | **API直接値** | API直接値 | API直接値 | API直接値 |
| **現在のアプリ利用** | フォールバック | **主要ETF・テーマETF proxyの明示更新、個別銘柄の所属テーマETF確認** | 未統合 | 未統合 | 未統合 |
| **制約** | 非公式・不安定 | クレジット制、プラン別遅延、0DTE限定取得 | 別契約 | 別契約 | Gateway常時起動 |

## 推奨案

### 現在の推奨運用 → **MarketData.app preferred**
- Hugging Face Secretsに `MARKETDATA_TOKEN`、Variablesまたは環境変数に `MARKETDATA_OPTIONS_MODE=preferred` を設定する
- MarketData.appを米国オプションの主ソースにし、204 no data、API失敗、必須列不足、トークン未設定時だけyfinance/cacheへフォールバックする
- `MARKETDATA_OPTIONS_MODE=shadow` は比較検証用として残し、yfinance表示を維持したまま直接Greeks、データ基準時刻、クレジット消費を確認する用途に限定する

### B. IB証券(米国)の口座をお持ちなら → **IBKR API**
- **メリット**: 口座があればデータ利用料だけで済みます。発注もAPI化可能です。
- **実装**: SBI証券と同じく、ローカルで「IB Gateway」等のソフトを起動しておく必要があります（同期エージェント方式）。
- **注意**: 構築の難易度は高めです。

### C. 現状維持 (yfinance) でGreeksを計算する
- **概要**: 取得した価格データをもとに、Pythonライブラリ (`py_vollib` 等) でGreeksを自行計算する。
- **メリット**: 無料。
- **デメリット**: 計算負荷がかかる。元データ（価格）が遅延しているため、Greeksの精度も落ちる。

## 結論
「詳細なオプション情報」を重視する場合、yfinanceだけでは限界があります。現在はMarketData.appを段階導入し、他サービスへの追加移行はMarketData.appの品質・費用評価後に判断します。

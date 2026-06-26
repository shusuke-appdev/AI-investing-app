# 米国株オプションデータ取得方法の比較

現在の `yfinance` (無料・非公式) と、より詳細なGreeks / IVを取得するAPIの比較です。2026-06-26時点ではMarketData.appをSPY / QQQ / IWMと主要テーマETF proxyのpreferred経路として実装済みです。Market Watch では current / 1W / 1M の満期別チェーンからオプション市場の想定変動幅・歪みを読み、AI Recap と市場時間軸別見通しにも同じ context を渡します。

| 特徴 | yfinance | **MarketData.app（実装済み）** | ThetaData | Polygon.io | Interactive Brokers (IBKR) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Greeks (Δ,Γ,Θ,ν)** | 欠損が多い | **API直接値** | API直接値 | API直接値 | API直接値 |
| **IV** | 欠損あり | **API直接値** | API直接値 | API直接値 | API直接値 |
| **現在のアプリ利用** | フォールバック、token未設定時の継続経路 | **主要ETF・テーマETF proxyの明示更新、current / 1W / 1M の期間構造、個別銘柄の所属テーマETF確認** | 未統合 | 未統合 | 未統合 |
| **制約** | 非公式・不安定、Greeks欠損 | クレジット制、プラン別遅延、米国オプション特化。汎用市場データ源ではない | 別契約 | 別契約 | Gateway常時起動 |

## 推奨案

### 現在の推奨運用 → **MarketData.app preferred**
- Hugging Face Secretsに `MARKETDATA_TOKEN`、Variablesまたは環境変数に `MARKETDATA_OPTIONS_MODE=preferred` を設定する
- MarketData.appを米国オプションの主ソースにし、204 no data、API失敗、必須列不足、トークン未設定時だけyfinance/cacheへフォールバックする
- current / 1W / 1M は満期一覧から有効満期を選ぶ。1W / 1M は目標DTEに最も近い満期を使い、同じtickerでも満期別cache keyで保存する
- 検証用途では0DTE固定にせず、`--marketdata-min-dte 1` の次回有効満期と `--marketdata-horizon-dtes 7,30` で確認する。アプリ本体は米国東部時間の同日満期が有効な時間帯だけ0DTEを使い、それ以外は次回有効満期へ切り替える
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

# テスト

このディレクトリには、外部APIをできるだけモック化した単体テストを配置します。

## 実行

```powershell
python -m pytest -q
python -m pytest tests/ --cov=src --cov-report=html
```

## 主な対象

- `test_option_analyst.py`: PCR、GEX、Max Pain、IV、Skew などの計算
- `test_option_analyst_logic.py`: オプション分析の境界値、current / 1W / 1M の期間構造
- `test_marketdata_client.py`: MarketData.app認証、HTTP 203/204、APIエラー
- `test_marketdata_option_provider.py`: MarketData.app列正規化、0DTE/目標DTEの満期解決、取得量制限
- `test_data_fetch_manifest.py`: 画面別データ取得マニフェスト
- `test_data_provider.py`: データプロバイダの差し替え
- `test_news_aggregator.py`: ニュース統合・重複排除
- `test_jquants_client.py`: J-Quants クライアント
- `test_mean_reversion.py`: ミーンリバージョン分析
- `test_volatility_clustering.py`: ボラティリティクラスタリング
- `test_advisor_phase3.py`: 市場監視、SMART基準、ベース認識

## 方針

- 実APIを直接呼ぶテストは標準テストに含めない
- APIレスポンスの形が変わりやすい箇所は fixture を用意する
- 取得処理と計算処理を分け、計算処理は純粋関数としてテストする
- Reflex state は、画面描画ではなく状態遷移とサービス呼び出し結果を中心にテストする

# 文書索引

## 現行仕様の正本

- [分析・予測機能カタログ](ANALYSIS_FEATURE_CATALOG.md): 各機能の目的、入力、出力、責務、連携、欠損時動作
- [アーキテクチャ](ARCHITECTURE.md): UI、サービス、共有コンテキスト、データ取得の全体構造
- [運用ガイド](OPERATIONS.md): 環境変数、更新操作、検証、障害時の確認方法
- [市場監視・予測](MARKET_MONITORING_PREDICTION.md): 市場レイヤー間の役割分担と予測の利用制約
- [分析データ来歴台帳](ANALYSIS_DATA_PROVENANCE.md): direct / proxy / model output / unavailable の区別
- [適応型個別株分析](ADAPTIVE_STOCK_ANALYSIS.md): Stock分析の評価境界
- [米国オプションデータ比較](us_options_data_comparison.md): MarketData.appとyfinance/cacheの使い分け
- [Supabase Data API権限](SUPABASE_DATA_API_GRANTS.md): 個人データ保存の権限設計

## 補助レビュー

- [データ取得・分析機能レビュー](DATA_ANALYSIS_REVIEW.md): 継続的な品質監査の記録

## 履歴資料

`archive/` は過去の監査、ロードマップ、SBI連携案、Finnhub移行計画を削除せず保存する場所です。現行仕様の判断には使用しません。

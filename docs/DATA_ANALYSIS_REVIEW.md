# データ取得・分析機能レビュー

更新日: 2026-06-04

## 全体像

本アプリのデータ取得・分析機能は、投資調査用の「現在の市場環境を読む機能」と「個別銘柄を評価する機能」に大きく分かれる。

- 市場分析: `MarketContext` を中心に、Market Intelligence UI、`/market-watch`、AI Market Recap が同じ市場監視データを共有する
- 個別銘柄分析: `StockSignalContext` を中心に、Stock UI と AI Stock Recap が同じ銘柄データ、テクニカル、確率シグナル、トレンド診断、セクター/テーマ評価を共有する
- データ取得: yfinance、Finnhub、FRED、J-Quants、EDINET、Google News を無料・公開データ優先で使う
- キャッシュ: `.states` 配下の persistent cache と TTL cache で、重い取得や失敗時の stale fallback を扱う

## 市場分析の配置

通常の市場分析フローは次の3段階に整理されている。

1. 軽量概要: `build_market_summary_context()` が指数、セクター、商品、FX、暗号資産などの初期表示に必要な市場データだけを取得する
2. 詳細監視: `build_market_details_context()` が市場環境評価、IBD式市場状態、マイクロストラクチャー、テーマモメンタム、信用ストレス、ETFフローproxy、日経平均6条件、資金流入セクター判定、市場の歪み検知を追加する
3. オプション更新: `build_market_options_context()` が SPY / QQQ / IWM のオプション分析を明示操作で更新し、オプション依存の市場環境評価だけを再計算する

今回の整理で、Reflex state 内にあった市場表示用の整形処理を `src/services/market_presentation_service.py` に移し、`frontend/state/market_state.py` はイベント、loading/error、表示モデル保持に集中する形へ寄せた。

## 個別銘柄分析の配置

通常の個別銘柄分析フローは `src/services/stock_dashboard_service.py` を入口にする。

- 企業概要、株価履歴、ニュース、テクニカル、SMART基準を取得・計算する
- `probabilistic_signal` は類似局面、forward return、walk-forward、サイジング目安を返す
- `trend_follow_diagnostics` は日足トレンドフォローの頑健性診断であり、売買推奨ではない
- `sector_theme_context` は対象銘柄のファンダメンタル優位とフロー優位を評価する
- AI Stock Recap は、表示済みニュース見出し、テクニカル、SMART基準、確率シグナル、トレンド診断、セクター/テーマ文脈を再利用する

今回の整理で、AI Stock Recap が画面に表示済みのニュースと `StockSignalContext` 内のテクニカル/SMART評価を使うようにし、AI生成時の不要な再計算と表示内容とのズレを減らした。

## 解消した重複・干渉

- 市場表示整形が `frontend/state/market_state.py` に集中していた問題を、UI非依存の presentation service へ移した
- AI Market Recap が通常経路でテーマや市場トレンドを追加取得する重複を減らし、`MarketContext` の momentum / option / monitoring 情報を優先するようにした
- 個別銘柄AIが表示済みニュースを使っていなかった問題を修正した
- 個別銘柄AIが `StockSignalContext` のテクニカル/SMART評価を使わずに再計算しうる経路を縮小した

## 残るプロダクト改善ロードマップ

1. Market Watch UI component の分割  
   `frontend/components/flash_summary.py` はまだ大きい。市場概要、IBD/プレイブック、信用/フロー、日経条件、市場歪みを別コンポーネントへ分ける。

2. DataResult 契約の全データ取得層への拡張  
   現在は主要 context に `source`、`is_partial`、`cache_status` が伝播しているが、低レベル provider にはまだ `None` / 空配列 fallback が残る。外部API失敗と中立評価が混ざらないよう、段階的に status 付き戻り値へ寄せる。

3. AI入力の構造化をさらに強化  
   Market / Stock では context-first になったが、プロンプト直前はまだ自然文整形が多い。将来的には `AnalysisRun` と組み合わせ、AIに渡した入力を保存・比較できるようにする。

4. 旧Streamlit資産の扱いを固定  
   `src/ui/` と `legacy_streamlit/` は現行UIの正本ではない。保管、削除、別ブランチ退避のどれにするかを決め、今後の修正対象から明確に外す。

5. 運用時の観測性  
   stale cache、partial data、provider failure をユーザーに見せるだけでなく、機能別に最後の成功時刻と失敗理由を一覧できる診断ビューを追加する。

# データ取得・分析機能レビュー

更新日: 2026-06-04

## 全体像

本アプリのデータ取得・分析機能は、投資調査用の「現在の市場環境を読む機能」と「個別銘柄を評価する機能」に大きく分かれる。

- 市場分析: `MarketContext` を中心に、Market Intelligence UI、`/market-watch`、AI Market Recap が同じ市場監視データを共有する
- 個別銘柄分析: `StockSignalContext` を中心に、Stock UI と AI Stock Recap が同じ銘柄データ、テクニカル、確率シグナル、トレンド診断、セクター/テーマ評価を共有する
- 実行品質: `StockSignalContext.trade_setup` が日足Entry Gateを共有し、専用Trading PlanがR基準の手動実行管理を担う
- データ取得: yfinance、Finnhub、FRED、J-Quants、EDINET、Google News を無料・公開データ優先で使う
- キャッシュ: `.states` 配下の persistent cache と TTL cache で、重い取得や失敗時の stale fallback を扱う

## 市場分析の配置

通常の市場分析フローは次の4段階に整理されている。

1. 軽量概要: `build_market_summary_context()` が指数、セクター、商品、FX、暗号資産などの初期表示に必要な市場データだけを取得する
2. 中難易度詳細: `build_market_medium_context()` が市場環境評価、IBD式市場状態、マイクロストラクチャー、テーマモメンタム、総合市場監視、ETFリーダーシップproxy、日経平均6条件、資金流入セクター判定を追加する
3. 高難易度詳細: `build_market_high_context()` がFRED信用ストレスと市場の歪み検知を追加し、FREDが遅い場合はstale cacheまたは部分成功として扱う
4. オプション更新: `build_market_options_context()` が SPY / QQQ / IWM のオプション分析を明示操作で更新し、オプション依存の市場環境評価だけを再計算する

今回の整理で、Reflex state 内にあった市場表示用の整形処理を `src/services/market_presentation_service.py` に移し、`frontend/state/market_state.py` はイベント、loading/error、表示モデル保持に集中する形へ寄せた。

## 個別銘柄分析の配置

通常の個別銘柄分析フローは `src/services/stock_dashboard_service.py` を入口にする。

- 企業概要、株価履歴、ニュース、テクニカル、SMART基準を取得・計算する
- `probabilistic_signal` は類似局面、forward return、walk-forward、サイジング目安を返す
- `trend_follow_diagnostics` は日足トレンドフォローの頑健性診断であり、売買推奨ではない
- `trade_setup` は日足で判定可能な相対強度、VCP、RVOL、ATR拡張、200MAトレンドをEntry Gateとして整理する
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

## 2026-06-11 来歴契約とUI改善

- `ProvenanceKind` と `ProvenanceItem` を追加し、Market、Stock、PortfolioのUIとAI共有contextで、直接値・算出値・proxy・推定値・モデル出力・stale cache・利用不可を追跡できるようにした
- PCR `0.8`、米10年債利回り `4.0%`、SPY PER `22`、NDX PER `30` の固定フォールバックを廃止し、必要データ不足時は利用不可として扱うようにした
- ポートフォリオでは価格未取得銘柄をゼロ時価で集計せず、警告付きで分析対象から除外するようにした
- 詳細な正本は [分析データ来歴台帳](ANALYSIS_DATA_PROVENANCE.md)、UI方針は [UI総合改善計画](UI_IMPROVEMENT_PLAN.md) を参照

## 2026-06-13 データ取得耐性・判定契約レビュー

- J-Quantsは廃止済みV1相当パスを修正し、公式V2の `equities/bars/daily`、`equities/master`、`fins/summary` とページネーションへ移行した
- yfinance取得に15分のレート制限クールダウンを追加し、株価履歴は24時間、企業情報は7日間の最終成功キャッシュを利用できるようにした。市場指数も同じ履歴取得経路を使う
- 通常の個別銘柄分析ではオプションをライブ更新せず、24時間以内の保存済みデータだけを利用する。明示的なオプション更新経路は従来どおりライブ取得できる
- FREDはstale cache優先と部分成功を維持し、利用者向け警告を日本語化した
- 歪み検知は欠損を `0.00` として扱わず、銘柄ごとに2指標以上、テーマごとに2銘柄以上かつ40%以上の網羅率を満たす場合だけ算出する
- FundamentalまたはFlowが不足する場合は「算出不可」とし、歪み候補へ分類しない
- 長期移動平均の未計算値をゼロとしてサポート判定する不具合を修正し、テクニカルカテゴリスコアを正規化してから0〜100点へ変換する
- SMARTは達成・未達・判定不能を区別し、ROA proxyでROE条件を達成扱いしない。Neutralまたは低信頼度の確率シグナルは監視・配分0%に制限する
- 個別銘柄UIはテクニカル、確率シグナル、トレンド堅牢性、セクター評価の日本語表示を追加し、各評価が独立した分析軸であることを明示した

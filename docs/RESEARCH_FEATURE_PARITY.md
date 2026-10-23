# ローカル移行版の機能・操作対応表

2026-10-23追補：[地合い・業種・テーマ調査](TOPDOWN_RESEARCH.md)に市場参加、日米業種ETF、回転・出来高図、候補一覧、Code33参考と取得/原資料確認の所有境界を追加しました。旧29項目は市場の研究詳細、個別17項目は保存分析から操作できます。

2026-10-09：標準は5つの問いと条件付き接続に再構成。取得プロフィール、29項目のstandard/advanced対応、順位の意図的変更、固定・実データ・ブラウザ検証は [市場再構成の受入記録](MARKET_REDESIGN_ACCEPTANCE.md)。以下の旧研究方式はadvanced／保存結果の研究詳細として維持します。

2026-10-08 UI改善：市場29項目は `market.js` の `MARKET_GROUPS` に一意に対応し、「市場構造・研究姿勢」「テーマと資金」「リスク」「見通し」「基本市況・価格」「日本固有条件」「明示取得参考」に整理。観測は常時表示、内訳・出典は同じ欄で展開。専用の価格履歴・予測/OOS・オプション表示は維持。市場→テーマ名リンクは対象市場を保持し該当行を展開、方針へも移動できる。

テーマ名クリック／Enter／Spaceで直下の代表銘柄を開閉。登録順の代表銘柄と候補を区別し、未取得銘柄も残す。並べ替えは順位行と詳細を同じtbodyとして移動。1w/1m/6mの取得率表示も選択期間に連動する。銘柄リターンは現行保存の20営業日で固定（テーマ1mは21営業日）；旧形式で期間不明なら不明と表示。受入：固定対応の2追加contract＋実ブラウザで全29欄/72フィルター/行内展開/負値・0・欠損/読込。配置変更で共有計算は変えない。

確認日: 2026-10-07。対象は現在有効なReflex分析。廃止済み個人データ管理、売買、旧Streamlitは対象外。画面のピクセル一致ではなく、同じ数値・条件・欠損状態と判断材料を操作できることを受入とする。

## 共通の検証経路

以下の表のM/Sは検証ケースの省略記号であり、単なる保存済みマークではない。

- **M**: `tests/test_research_migration_acceptance.py::test_fixed_market_fields_preserve_shared_service_contract`。旧共有サービスを固定入力にし、新出力の29フィールド全体、負値・0・null・false・研究用状態を比較。市場画面では29の名称付き詳細を全て開き、基本市況の専用一覧、3履歴グラフ、予測・OOS・オプション専用表示を別に確認。
- **S**: 同ファイル `test_fixed_all_stock_fields_preserve_shared_service_contract`。17フィールドを同じ共有入力と比較。6社を選択し主条件・複数評価・財務表・全セグメント・調整表を表示。株価チャートは5期間×線形/対数、凡例6系列、日付キー操作と欠測分断を確認。
- **R**: `tests/test_research_dashboard_contract.py::test_resume_keeps_all_saved_calculations_and_never_calls_provider` と実6社の再計算・再読込。資料追加後も元のanalysis全体、252価格行/社を不変確認。
- **B**: [受入記録](RESEARCH_MIGRATION_ACCEPTANCE.md)と `.states/migration_browser_final/acceptance.json`。ブラウザ操作を実施した記録であり、`catalog.coverage_state=captured`とは別。

全CLIの先頭は `.venv\Scripts\python.exe scripts\research.py`。新規 `market --market US|JP` は標準段階を取得、部分更新は `market --market US|JP --refresh <research.json> --stage <段階>`。段階は必要な派生表示も再計算するが、無関係な保存結果・来歴は維持。optionsとFOMOは自動取得しない。

旧市場所有者は `frontend/state/market_state.py` → `src/services/market_dashboard_service.py` → `MarketContext` → 旧ページ/市場AI。同じPythonサービスを `src/research/runner.py` から呼ぶ。次表の取得元はこの共有サービスの呼出先/入力系列。旧AIの自然言語自体は同一出力保証の対象ではない。

## 市場: 基本2項目＋既存27項目

|フィールド|取得元・共有計算|新画面で使う場所|段階・操作|受入|
|---|---|---|---|---|
|market_data|market_data/get_market_indices、指数・金利・商品・FX provider|市場の資産別一覧、総覧環境|summary|M/B|
|market_charts|build_market_chart_context、SPY/QQQ/^N225履歴|市場3専用価格グラフ、日付値確認|summary|M/B|
|evaluation|evaluate_market_environment、保存市場系列|総覧環境・市場環境、名称付き根拠|theme-flow|M/B|
|ibd_regime|classify_ibd_market_regime、SPY/^NDX価格出来高|総覧構造、市場IBD詳細|theme-flow|M/B|
|regime_playbook|状態に依存する共有playbook|市場の研究課題、方針|theme-flow|M/B|
|microstructure|analyze_market_structure、SPY/保存options|市場構造詳細、代理表示|theme-flow|M/B|
|momentum|get_momentum_themes、テーマ履歴|市場期間別モメンタム詳細|theme-flow|M/B|
|monitor|build_market_monitor_context、価格出来高/利回り|総覧構造、市場監視詳細|theme-flow|M/B|
|market_distortions|detect_market_distortions、テーマ相対価格|市場歪み詳細・候補理由|credit-risk|M/B|
|trend_ranking|build_trend_ranking_context、代表銘柄/flow/歪み|総覧Top5・棒・期間表、テーマ|theme-flow/credit-risk|M/B|
|opportunity_themes|共有順位・相対優位の抽出|市場候補詳細、テーマ比較|theme-flow/credit-risk|M/B|
|important_levels|共有strategyの履歴/volume profile|市場支持抵抗・価格帯別根拠|theme-flow|M/B|
|market_timeframes|共有strategyの期間別入力|市場時間軸別詳細|theme-flow/vol-sentiment|M/B|
|strategy_regime|build_market_strategy_context、状態別条件|総覧姿勢、市場詳細、方針|依存段階から再計算|M/B|
|market_driver_monitor|共有strategy、金利・商品・FX|市場ドライバー詳細|theme-flow|M/B|
|japan_conditions|build_japan_conditions_context、実値/明示proxy|日本市場の個別条件、未確認表示|JP theme-flow|M/B|
|sector_flow|build_sector_flow_context、価格出来高proxy|市場セクター注目度詳細|theme-flow|M/B|
|credit_stress|build_credit_stress_monitor、信用系列|総覧信用、市場信用詳細・対象市場|credit-risk|M/B|
|flow_monitor|build_sector_flow_monitor、ETF価格出来高|市場ETFリーダーシップ詳細|theme-flow|M/B|
|flow_alignment|共有flow/strategyの整合判定|市場・テーマ整合性詳細|依存段階から再計算|M/B|
|cross_market|日米共有比較系列|市場間比較詳細|theme-flow|M/B|
|volatility_regime|build_market_volatility_regime、Cboe/履歴|総覧ボラ、市場詳細|vol-sentiment|M/B|
|vix_sq_alert|共有ボラ・SQ条件|市場VIX/SQ詳細|vol-sentiment|M/B|
|sentiment|CNN/Cboe/価格系、build_local_sentiment_composite|市場センチメント詳細|vol-sentiment|M/B|
|short_horizon_forecast|共有予測/OOS、SPY/QQQ、Cboe/CFTC等|専用予測確率・範囲・検証表|vol-sentiment|M/B|
|composite_sentiment|build_market_composite_sentiment|市場複合条件、confirmed/研究用区別|vol-sentiment|M/B|
|top_risk_signposts|build_top_risk_signposts、信用/センチメント|市場リスク兆候詳細|credit-risk/vol-sentiment|M/B|
|fomo_scan|scan_fomo_universe、既存米国ユニバース|市場過熱候補・除外理由|新規US market/policy --scan-fomo|M、opt-in固定入力/B|
|options|get_major_indices_option_status、既存US provider|専用成熟度/期間/term structure、詳細|options --allow-options|M、許可/JP拒否固定入力/B|

optionsは信用消費の可能性があるため、今回の実取得には含めない。未許可状態と固定入力の専門表示を検証し、live成功とは記載しない。日本に米国の信用参考系列を出す場合は対象市場を明示する。

## 銘柄: 基本2項目＋既存15項目

旧所有者は `frontend/state/stock_state.py` → `src/services/stock_dashboard_service.py::build_stock_dashboard_context` → StockDashboardContext/StockSignalContext → 旧ページ/個別株AI。同じcontextを保存。新規取得は `stock --ticker <ticker>`、日本は `--market JP --ticker 7203.T`。

|フィールド|取得元・共有計算|新画面で使う場所|Codex操作|受入|
|---|---|---|---|---|
|info|StockAnalysisInputs.info、get_stock_info|企業概要・指標専用パネル|stock|S/B|
|news|StockAnalysisInputs.news、get_stock_news_with_status|ニュース/公表日時/取得状態|stock|S/B|
|technical_data|analyze_technical、同じ価格履歴|テクニカル名称付き詳細|stock|S/B|
|smart_criteria|evaluate_smart_criteria、企業指標/cache市場|SMART参考詳細|stock|S/B|
|probabilistic_signal|generate_probabilistic_stock_signal、5年/benchmark|確率・類似局面参考詳細|stock|S/B|
|trend_follow_diagnostics|generate_trend_follow_diagnostics|Trend Follow過去検証詳細|stock|S/B|
|fomo_regime|analyze_fomo_volatility_regime|過熱・急変参考詳細|stock|S/B|
|trade_setup|evaluate_trade_setup|Entry・無効化主条件/詳細|stock|S/B|
|sector_theme_context|evaluate_stock_sector_theme_context|所属セクター・テーマ詳細|stock|S/B|
|fundamental_profile|evaluate_fundamental_profile|業態別ファンダメンタル詳細|stock/資料resume|S/R/B|
|volume_profile|build_volume_profile、日足出来高近似|価格帯別横棒・POC/Value Area、別表示|stock|S/B|
|purchase_evidence|evaluate_purchase_evidence|根拠一致度参考詳細、主条件とは別|stock|S/B|
|purchase_evidence_health|共有一致度の必要入力状態|欠損/警告の名称付き詳細|stock|S/B|
|market_risk_guardrail|build_cached_market_risk_guardrail|cache-only市場参考、主条件へ不介入|stock|S/B|
|japan_supply_demand|build_japan_supply_demand_context|日本需給期日・確認状態|JP stock|S/B|
|primary_conditions|build_primary_conditions|Stage2/RS/VCP/出来高/成長/Entry主条件表|stock|S/B|
|stock_signal_context|同一取得入力/共有context|表示・トレード参考・Codex参照入力|stock/資料resume|S/R/B|

chart_dataの終値/MA10/20/50/200/出来高を専用SVGで表示。線形/対数、1/3/6か月/1年/全期間、系列切替、ポインター/矢印/Home/Endの日付値。null・非正の対数値は線分を分断し、全価格系列を消しても出来高のみ表示できる。企業価値はprovider参考値と資料方式一覧を分離し、同一銘柄DCF/SOTPを併存。原数値・単位・期間・調整・全セグメント・適用不能理由を財務照合専用パネルに表示する。

## 全操作・AI・運用

2026-10-08追加：非個別の大まかな依頼は `research.py update` に集約。日米（またはJP/US）の市場全標準段階、指数、テーマ/構成銘柄/既存範囲候補、市場方針、取得状態を1回で保存。`Open-Investment-Research.cmd` → loopback入口の更新ボタンが同じ処理を呼び、特定チャットへの依存なし。個別株/会計/評価/解釈の元基準日を保持。原文確認やoptions/FOMOを自動化したという意味ではない。受入は `tests/test_research_workbench.py`：全体/市場別境界、旧値/失敗の分離、保存読込、後から追加した銘柄の集約、OSロック/二重更新、Host/Origin/token/本文/任意ファイル拒否。

|旧イベント/操作|ローカル移行操作と画面|受入ケース|
|---|---|---|
|market prepare_market_watch/fetch_market_summary_fast/refresh_market_details|overview/market新規、または段階refresh、総覧/市場|M、refresh_summary_preserves_unrelated、refresh_failure_retains_previous、repeated_refresh_failure_is_not_a_success|
|refresh_theme_flow/refresh_credit_distortion/refresh_volatility_sentiment|theme-flow/credit-risk/vol-sentiment指定、依存結果のみ更新|段階固定入力、前回値と今回失敗を別表示|
|refresh_options/refresh_fomo_scan|明示US opt-in、無許可/JPを拒否|refresh_options_scope、fomo_is_opt_in_us_only|
|日米・指数期間切替|日米ボタン、指数5期間、実値と日付|B、exact-common-calendar/no-fillテスト|
|テーマset_period/direction/sort/top10/bottom10|1週/1月/6月、全て/上昇/下降、総合/騰落上下/取得率、全順位一覧|B:36組合せ、検索0件/解除。上下各10列は全一覧の同じ順位・上下ソートで比較|
|テーマprepare/discover/deep_dive/select_ticker|theme取得、資料external_candidates、Codex解釈resume、候補→保存銘柄/未保存CLI|registered_discovery_never_calls_model、外部資料拒否、B候補リンク/未保存案内|
|銘柄set_ticker/submit_stock_search/select_ticker/fetch_stock_data|stock新規、保存済みselect、日米識別保持|S/B6社、混在入力JP銘柄選択|
|show_trade_analysis/hide_trade_analysis|同じ共有入力のトレード参考details展開/収納|S/B、主条件と参考の分離|
|generate_ai_analysis/run_company_research|Codex原文調査→evidence→resume、観測/会社見通し/仮定/反証パネル|interpretation_preserves_analysis、JSONPointer参照、不正run/path拒否、R|
|取得状態・来歴・例外|データ状況の元run/各status/source/manifest/quality警告|B、nested_market_failures_are_not_completed、失敗しても以前の表示を保持|
|保存/再計算/読込|replay、resume、--attach、複数ローカルJSON読込|R、v1/v2、atomic_import_browser、不正混在/未確認出典/型違い拒否|
|オフライン閲覧・キーボード・明暗/幅|自己完結HTML、CSP connect-src none、表示選択、panel内scroll|B:6画面×4幅×2配色、通信停止中操作、負値/0/null fixture|

## 意図した変更と限界

旧themeには1日/3月/24月等の選択肢がある一方、現行fetch_themesの表示performanceは固定performance_1wを使用する。新画面は実際に保存される1w/1m/6mだけを選択し、存在しない期間計算を装わない。構成銘柄performanceの保存算定期間は切替で再計算されないと明示する。

旧Gemini本文の再現ではなく、Codexが開いた一次資料と元run/入力へ接続する。解釈文は数値条件の入力に使わない。日本の欠損を0点にした総合判定や未確認EPS/海外フロー代理の確定扱いを除去。計算変更をUI移植に紛れ込ませない。

外部providerの非開示、キー未設定、403、履歴不足は機能停止/確認待ちとして表示する。全ての値を必ず取得できる保証ではない。公開・停止・旧依存撤去・ChatGPT/Vercel接続は今回のローカル完了対象外。

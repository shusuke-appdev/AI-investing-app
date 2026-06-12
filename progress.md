# AI投資アプリ - 進捗メモ

## 最終セッション: 2026-05-13 (市場データ取得の高速化)
- [x] UIフリーズの解消: `market_state.py` 内のバックエンド処理の遅延インポートをモジュールレベルへ移動し、イベントループのブロックを防止
- [x] バックエンド処理の非同期並行化: `asyncio.gather` を使用し、各種分析（環境、マイクロストラクチャー、モメンタム、市場監視）を同時実行化
- [x] APIリクエストのマルチスレッド化: `market_index_provider.py` における `yfinance` / `Finnhub` データ取得を `ThreadPoolExecutor` で並列化し、ネットワーク待機時間を削減

## 過去セッション: 2026-05-13 (全コード総点検)
- [x] 17件のバグ修正・堅牢性改善を14ファイルに実施
- **致命的バグ修正**:
  - PCR型エラーによる天井警戒シグナル常時発火を修正 (market_analyst_service.py)
  - AI分析ボタンが ImportError で常時失敗する問題を修正 (stock_analyst.py)
  - yfinance NaN値によるフロントエンド表示崩壊を修正 (market_index_provider.py)
  - 5y期間マッピング欠落で長期MA(250/500/750日)が常に計算不能だった問題を修正 (stock_data_provider.py)
  - Reflexコンパイル時のUntypedVarError群を修正 
    - `MarketMonitorData` の型をPydantic BaseModelで厳密化しUIの属性アクセスへ変更 (market_state.py, flash_summary.py)
    - `StockState.smart_criteria` の型を `SmartCriteria` BaseModelで厳密化し、UIコンポーネントでの `ObjectItemOperation` による型エラー(`>=` 等)を解消 (stock_state.py, stock.py)
- **分析ロジック修正**: RSIゼロ除算防止強化、ボラティリティweight不均衡修正、iv変数スコープ修正
- **機能間連携**: Flash Summaryキー名修正、決算Placeholder→Finnhub委譲、query_generatorキー修正
- **堅牢性**: キャッシュメモリリーク防止、Gemini 429/503リトライ、フォールバックキャッシュ排他制御、Stooqタイムアウト
- **追加修正 (第2パス)**:
  - GARCH Mockテスト失敗を修正 — persistence変数の型ガード追加 (volatility_clustering.py)
  - オプション取得のyfinance Rate Limit対策: 期限数3に制限、期限間0.3秒・銘柄間2.0秒待機
  - オプションデータのカラム名正規化（yfinanceバージョン間差分吸収）
  - PCR/GEX計算でNaN値の安全なfillna(0)処理
  - stock.options取得のtry/except追加
- pytest 38/38 全通過

## 最終セッション: 2026-05-01 (UI改善・データ拡充)
- [x] 株式指数をETF→生指数（^GSPC, ^NDX等）に変更
- [x] 欧州（FTSE 100, DAX, CAC 40）・アジア（Hang Seng, STI）指数を追加
- [x] VIX指数を追加、米国債利回りを「株式指数・金利」パネルに統合
- [x] サイドバー上部に🇺🇸/🇯🇵市場切り替えセグメントコントロールを追加
- [x] コモディティ/仮想通貨の表示順反転（Commodity上・Crypto下）
- [x] 総合市場監視ダッシュボードを2カラム水平レイアウトに変更
- [x] オプション分析をアセットクラス別概要の下に移動
- [x] AI Market Recapボタンをヘッダーに大きめ配置
- [x] オプションデータ取得のエラーハンドリング強化
- Reflexコンパイル 38/38 成功

### 設計判断
- J-Quants: Freeプランでは指数データ取得不可 → Stooq継続
- 生指数（^始まり）はFinnhubで取得不可 → yfinanceに自動ルーティング
- オプション分析は引き続きETF（SPY, QQQ, IWM）を対象

## セキュリティ対応: 2026-05-01

## 最終セッション: 2026-04-29

### 完了したタスク（Reflex移行）
- [x] **Phase 1**: SPAルーティングとグローバルレイアウト構築
  - `frontend/template.py`, `frontend/components/sidebar_nav.py`
- [x] **Phase 2**: Market Intelligenceページの移植
  - `frontend/state/market_state.py`, `frontend/pages/index.py`
  - 環境スコア、AI市況レポート（Gemini）
- [x] **Phase 3**: 個別銘柄分析ページの移植
  - `frontend/state/stock_state.py`, `frontend/pages/stock.py`
  - チャート(Recharts)、テクニカル分析、AIレポート
- [x] **Phase 4**: テーマ＆ポートフォリオページの移植
  - `frontend/state/theme_state.py`, `frontend/pages/theme.py`
  - `frontend/state/portfolio_state.py`, `frontend/pages/portfolio.py`
- [x] `reflex export` で 34/34 コンパイル成功

### 設計判断メモ
- **Reflex 0.9**: `rx.Base` は廃止 → `pydantic.BaseModel` を使用
- **非同期**: `asyncio.to_thread()` + `yield` パターンで状態更新
- **ストレージ**: PortfolioStateは `storage_type` を自前で管理し、Streamlit非依存
- **型安全**: `Dict[str, Any]` では `rx.foreach` が型推論できない → 明示的なモデルクラスが必須

### 過去セッション完了分
- [x] コードベース全体の総点検（src/ 31ファイル + tests/ 8ファイル）
- [x] ruff Lintエラー 99件 → 0件に修正
- [x] pytest環境構築 + 33/33テスト全通過

### 既知の課題（未着手）
- [ ] Knowledge（知識DB）ページの移植
- [ ] チャットUI（`render_chat_component`）の各ページへの統合
- [ ] ポートフォリオのストレージタイプ選択UI
- [ ] `google.generativeai` → `google.genai` への移行（非推奨警告）

### 起動方法
```bash
# Reflexアプリ（新UI）
reflex run

# レガシーStreamlit（退避済み）
streamlit run legacy_streamlit/app.py
```
# Session update: 2026-05-19 market monitoring / prediction integration
- Added shared `MarketContext`, `OptionContext`, and `StockSignalContext` data structures.
- Moved Market Intelligence fetching through `build_market_context()` so UI state and AI market recap can reuse the same monitoring data.
- Updated AI market recap generation to avoid recomputing market monitoring when a UI-fetched context is supplied.
- Added tests for market context generation, option-data failure degradation, and AI report context reuse.
- Validation: compileall passed, ruff check passed, ruff format --check passed, pytest passed with 47 tests.

# Session update: 2026-05-19 stock analysis / market data reliability
- Fixed Reflex stock-analysis state normalization so mutable state proxies are converted to plain containers before analysis services and AI prompt context use them.
- Added repo-local yfinance cache configuration under `.states/yfinance_cache`, avoiding the inaccessible AppData yfinance SQLite cache.
- Suppressed invalid Finnhub keys for the current process after 401/403 so market data can fall back to yfinance without repeated auth failures.
- Added option retrieval status metadata for available, partial, failed, and JP not-applicable states.
- Validation: compileall passed, ruff check passed, ruff format --check passed, pytest passed with 56 tests; live US market smoke returned 30 indices, 3 option rows, monitor data, and no context errors.

# Session update: 2026-05-19 stock/options/market data reliability follow-up
- Removed hidden Gemini translation from stock info fetch paths used by Reflex stock analysis and market monitor PE lookup; AI generation now stays behind the explicit AI recap/analysis actions.
- Added Finnhub auth status reporting so invalid 401/403 keys short-circuit news fetches with source status and error reason instead of silent empty data.
- Covered remaining direct yfinance paths with the repo-local `.states/yfinance_cache` initialization and repaired local Reflex Bun/Node validation.
- Hardened option and market-monitor UI models with server-formatted option prices and enum-like yield-spread levels instead of localized string matching.
- Validation: compileall passed, ruff check passed, ruff format --check passed, pytest passed with 61 tests; live US smoke returned 30 indices, 3 option rows, monitor data, AAPL info without Gemini translation, Finnhub invalid status for news, and no context errors; Reflex frontend export passed after using the bundled Node path.

# Session update: 2026-05-20 plugin initialization / test environment fix
- **Plugin Operation Errorの修正**: `google-antigravity-sdk` プラグイン初期化時のパス未検出エラーに対応するため、不足していた `C:\Users\shusk\.gemini\config\plugins\google-antigravity-sdk\examples\getting_started` および `references` ディレクトリを手動作成。
- **pytest実行環境の堅牢化**: 一時フォルダへのアクセス制限 (`PermissionError`) を回避するため、`--basetemp=tmp` を追加。
- **動作検証**: pytest 61件がすべて正常にパスすることを確認。

# Session update: 2026-05-20 startup warning cleanup
- Removed the fragile OpenBB runtime dependency from stock data paths; `stock_data_provider.py` now uses direct yfinance for quotes, history, profile, and valuation metrics.
- Routed Yahoo-only market symbols such as raw indices, futures, crypto pairs, and FX directly to yfinance instead of probing Finnhub first.
- Moved Reflex theme configuration from deprecated `App(theme=...)` to `RadixThemesPlugin`, lazy-loaded EDINET tools, and disabled app logger propagation to reduce duplicate startup warnings.
- Removed stale OpenBB artifacts (`pip_dry_run.txt`, `scripts/test_openbb.py`) and updated docs/requirements/tests to match the yfinance/Finnhub runtime contract.
- Validation: ruff check passed, ruff format check passed, compileall passed, pytest passed with 65 tests, Reflex frontend export passed, and startup import smoke passed.
- Release: pushed commit `9fe90d3 Clean startup warnings` to `origin/main`.

# Session update: 2026-05-21 startup/data/options/AI recap hardening
- Split Market Intelligence loading into lightweight startup summary, explicit detail refresh, and explicit option refresh; root `on_load` no longer runs the full market context or yfinance option chain fetch.
- Added `.states/market_context_cache` and `.states/option_chain_cache` JSON caches so startup and option refreshes can reuse last successful data before hitting yfinance again.
- Added `source`, `fetched_at`, `is_stale`, `is_partial`, and `quality_warnings` to `MarketContext` / `OptionContext`, plus option-level `data_quality`.
- Stopped showing synthetic GEX when yfinance lacks Greeks/Gamma; the UI now displays `-` with quality warnings instead of misleading large values.
- AI Market Recap now receives option data quality warnings and Gemini model selection can be overridden with `GEMINI_MODEL_NAME` or `GEMINI_MODEL`.
- Fixed Reflex validation on this Windows/Codex setup by making `rxconfig.py` prefer the runnable Codex runtime Node over the inaccessible WindowsApps `OpenAI.Codex...\node.EXE`; `reflex export --frontend-only --no-zip` now passes.

# Session update: 2026-05-21 review remediation implementation
- Made `tools/migrate_to_supabase.py` dry-run by default; remote writes require `--execute`, destructive table clearing requires `--confirm-destroy`, and a pre-clear backup must succeed.
- Fixed the public `calculate_atm_iv(ticker=...)` path so it handles option metadata from `_fetch_option_data()`, with a regression test.
- Added `DataResult` status metadata to market and stock analysis contexts, moved stock dashboard orchestration and portfolio validation/analysis serialization into service modules, and moved market option presentation formatting out of Reflex state.
- Hardened Knowledge DB AI context with sanitized `KnowledgeContextItem` blocks, deduplication, source/created-at context, and explicit prompt-injection instructions that treat saved notes as untrusted quoted data.
- Fixed portfolio holding UX by preserving update ticker names in success messages and rejecting zero/negative shares before save or analysis.
- Removed tracked local cache/debug artifacts (`app_cache.sqlite`, `yfinance_cache.sqlite`, root debug scripts/results), ignored future local verification artifacts, and moved pytest basetemp under `.states/pytest_tmp`.
- Added `constraints.txt` and wired local/Docker install docs to use `-c constraints.txt` for reproducible deploy dependency versions.
- Validation: ruff check passed, ruff format check passed, compileall passed, and pytest passed with 84 tests.

# Session update: 2026-05-21 stock analysis display regression fix
- Fixed the Reflex stock page regression where dict values rendered through `.to_string()` appeared with JSON quotes such as `"PLTR"` and `"Strong Buy"`.
- Added stock dashboard display fields for company name, exchange, sector, market cap, PER, dividend yield, and summary so the UI no longer renders raw `null` values.
- Reclassified missing company profile details as a partial-data warning when price/technical data is available, instead of showing a fatal red error for the whole stock analysis.
- Added yfinance `fast_info` fallback for market cap when the full profile endpoint is unavailable.
- Validation: targeted stock/provider tests passed, ruff check passed, compileall passed, and Reflex frontend export passed.

# Session update: 2026-05-27 cache foundation refresh
- Rebuilt `src/cache.py` so in-memory TTL entries track `created_at`, `expires_at`, `ttl`, and namespace; long-lived 12h/24h caches are no longer swept by a fixed 30-minute cutoff.
- Added a shared `.states` JSON persistent cache layer with atomic writes, safe file keys, schema/version wrapping, corrupt-cache ignore behavior, and fresh/stale/expired read results.
- Moved HTTP `requests-cache` storage under `.states/http_cache`, kept yfinance under `.states/yfinance_cache`, and added lightweight cache status inspection APIs.
- Propagated `cache_status` and cache age metadata through market/option/stock data status so UI and AI paths can distinguish live, persistent cache, stale cache, memory cache, computed, and failed data.
- Updated architecture/operations docs with current cache locations and stale-data handling rules.

# Session update: 2026-05-27 Two Sigma OSS design extraction
- Added a pandas-based temporal as-of alignment service inspired by Flint, with tolerance-aware unmatched-row quality metadata.
- Added Marbles-style diagnostic assertion helpers for analysis-context pytest failures.
- Added `AnalysisRun` artifacts for reproducible stock/market analysis exports in Markdown and notebook-style JSON.
- Added local JSON-backed analysis job lifecycle state for heavy option refresh, walk-forward, backtest, and batch-news style workloads.
- Added focused regression tests and updated architecture/operations docs for the new service boundaries.

# Session update: 2026-05-27 trend-follow diagnostics layer
- Added a daily individual-stock trend-follow diagnostics engine that checks 50/200 MA trend participation against Buy & Hold, OOS behavior, cost sensitivity, entry-lag sensitivity, top-trade dependency, random-direction baselines, max drawdown, and time under water.
- Wired `trend_follow_diagnostics` into `StockSignalContext`, Stock page state/UI, and AI Stock Recap context as a diagnostic lens, not a replacement for existing probabilistic signals or trade recommendations.
- Added focused tests for no-lookahead execution, tail dependency, deterministic random baselines, dashboard context propagation, and AI context formatting.

# Session update: 2026-05-27 Supabase Data API grant readiness
- Added `supabase/public_tables.sql` with explicit Data API grants for `user_settings`, `portfolios`, and `knowledge_items`, plus RLS enablement.
- Updated Supabase connection handling to prefer server-side `SUPABASE_SECRET_KEY`, while keeping `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_KEY` as compatibility fallbacks.
- Added `tools/migrate_to_supabase.py --print-setup-sql` so the required Supabase setup SQL is part of the documented migration flow.
- Documented the 2026-05-30 / 2026-10-30 Supabase Data API rollout and the required operator steps in `docs/SUPABASE_DATA_API_GRANTS.md` and `docs/OPERATIONS.md`.
- Validation: Supabase setup SQL print smoke passed, ruff check passed, ruff format check passed, compileall passed, and pytest passed with 123 tests.

# Session update: 2026-05-28 Supabase live project grant application
- Restored the inactive Supabase project `pbdwzpktugztklejzvhn` (`AI-investing-app`) and applied live migrations for the three public storage tables.
- Applied explicit Data API grants to `service_role`, revoked `anon`/`authenticated` table access, enabled RLS, and removed existing permissive `Enable all access for all users` policies.
- Opted the `postgres` role's future `public` table/function/sequence default privileges into explicit-grant behavior; `supabase_admin` default privileges could not be changed by the connector due to ownership permissions.
- Verified `service_role` insert/select/delete smoke tests for all three tables, checked migration history, and reran Supabase Security/Performance Advisors.

# Session update: 2026-06-04 market watch / IBD regime / recap focus
- Added a dedicated Reflex `市場監視` route and moved market monitoring, theme momentum, detailed theme ranking, option analysis, and distortion detection out of the top-level Market page.
- Added IBD-style free-data market regime classification (`confirmed_uptrend`, `uptrend_under_pressure`, `rally_attempt`, `market_in_correction`) and fixed state playbooks for stance, risk budget, what to think about, and what to avoid.
- Added theme/sector diagnostics that compare fundamental advantage against flow advantage, surfacing bullish and bearish market distortions in MarketContext and AI Market Recap.
- Added Market Recap custom-focus input via the small plus button next to report generation.
- Added individual stock sector/theme context so Stock UI and AI Stock Recap evaluate whether both fundamental and flow advantages exist.
- Validation: compileall passed, ruff check passed, targeted tests passed, and full pytest passed with 137 tests.

# Session update: 2026-06-03 credit stress and leadership flow monitor
- Recovered `pandas_datareader` on the Python 3.12 / pandas 3 environment by adding pinned `setuptools` and a small decorator compatibility shim before import.
- Added FRED economic data retrieval with bounded FRED CSV requests first, recovered pandas-datareader fallback, and `.states/economic_data_cache` stale fallback.
- Added US credit-stress velocity diagnostics using BAA10Y and KCFSI three-month z-score acceleration, with HY/BBB/stress/claims/order and credit/bank ETF confirmation rows.
- Added a free ETF flow-pressure proxy monitor using signed dollar volume, relative returns, flow z-scores, and 50-day trend status for sector, AI/semiconductor, credit, and bank ETFs.
- Wired the new diagnostics into `MarketContext`, the Market Intelligence UI, and AI Market Recap context without adding them to lightweight startup summary loading.

# Session update: 2026-06-03 Japan market / sector flow Market Recap expansion
- Added US-primary/Japan-supplemental sector flow diagnostics for Market Intelligence, using US sector ETFs and Japanese theme baskets to score inflow strength, confidence, continuation, and research action labels.
- Added Nikkei upside six-condition diagnostics to `MarketContext`, with direct optional environment inputs for JSF short balance, 1570 margin ratio, and foreign investor net buying, plus proxy/unavailable labeling when free direct data is not available.
- Wired the new diagnostics into the Reflex Market Intelligence dashboard and AI Market Recap prompt so the recap remains US-main while explicitly discussing Japan as a cross-market corner.
- Expanded JP market summary fetching so Japan mode also shows configured commodities, FX, crypto, and remaining Yahoo-compatible JP index proxies rather than only Stooq index rows.

# Session update: 2026-06-04 analysis function consolidation
- Reviewed the data-fetching and analysis surfaces across Market Intelligence, Market Watch, AI Market Recap, and individual stock analysis, then documented the current ownership and remaining roadmap in `docs/DATA_ANALYSIS_REVIEW.md`.
- Moved MarketContext-to-Reflex display formatting out of `frontend/state/market_state.py` into `src/services/market_presentation_service.py`, so MarketState now focuses on events, loading/error flags, and display model assignment.
- Changed AI Market Recap to reuse supplied/built `MarketContext` momentum, options, and monitoring data instead of refetching theme and market trend data on the normal path; legacy fallback remains only when context construction fails.
- Extended `StockSignalContext` with SMART criteria and news headlines, and changed AI Stock Recap to reuse displayed stock context instead of silently dropping displayed news or recomputing technical/SMART inputs.

# Session update: 2026-06-06 staged market watch / theme ranking / stock route
- Added staged `/market-watch` detail fetching: low cache/summary, medium market state and flows, high FRED credit stress and distortions, then options, with per-stage status and cache metadata in `MarketContext` and Reflex display state.
- Hardened FRED credit stress retrieval to prefer stale cache and skip slow pandas-datareader fallback for the market-watch high stage, while keeping proxy warnings instead of blocking the dashboard.
- Renamed Theme Trend surfaces to Theme Ranking, removed the `5日` and `2週間` selector windows, and replaced the theme list with cards that show rank, performance, and constituent stock rows.
- Preserved the stock analysis data path while adding `/stock` page-load flag normalization and a wider clickable sidebar link target.

# Session update: 2026-06-12 daily Entry Framework / Trading Plan
- Added a daily-data Entry Framework to `StockSignalContext` and the Stock UI, covering market/sector relative strength, transparent VARS proxy, VCP/tightness, RVOL, pocket-pivot proxy, ADR%, ATR extension, and declining-200MA hard rules.
- US sector relative strength uses the mapped sector ETF; JP theme relative strength uses the median return of up to five peers in the configured theme, with 1306.T fallback.
- Added a dedicated `/trading-plan` surface for R-based sizing, three-stop planning, maximum three new positions per entry date, T+1/T+3 daily-session checks, realized-R review, journal notes, and mistake tags.
- Exposed the 4x/6x/8x/10x ATR% extension profit-taking guide on both the Stock Entry Framework and Trading Plan cards.
- Added local JSON and Supabase `trade_plans` persistence; GAS Trading Plan storage remains explicitly unsupported.
- Kept Market Watch, probabilistic signals, trend-follow diagnostics, and Portfolio responsibilities unchanged.
- Validation: compileall, ruff check, ruff format check, full pytest (`163 passed`), and Reflex frontend export passed.

# Session update: 2026-06-11 UI総合改善 / 分析データ来歴
- Product Designブリーフに基づき、現行の青・グレー基調と既存機能を維持したまま、全5画面の共通ヘッダー、読込・空状態、レスポンシブナビを改善。
- `ProvenanceKind` / `ProvenanceItem` を追加し、Market、Market Watch、Stock、Portfolioへ「データの来歴・信頼性」表示を追加。
- PCR `0.8`、米10年債利回り `4.0%`、SPY PER `22`、NDX PER `30` の固定フォールバックを廃止し、欠損時は利用不可として扱うように変更。
- ポートフォリオの価格未取得銘柄をゼロ時価で集計せず、警告付きで分析対象から除外。
- UI改善の正本を `docs/UI_IMPROVEMENT_PLAN.md`、proxy・推定・モデル出力・stale cache等の正本を `docs/ANALYSIS_DATA_PROVENANCE.md` に保存。
- MarketContextとStockSignalContextの来歴をAI入力にも再利用し、proxy・推定・欠損制約をAI判断へ伝播。
- Product Design / Browser監査で全5ルートをdesktop・tablet・mobile幅で確認し、モバイルナビを左ドロワー化。監査証跡を `docs/ui-audit/2026-06-11/` に保存。
- 検証結果: compileall、ruff check、ruff format check、全pytest `146 passed`、Reflex frontend export、Browser監査通過。
- その後に並行追加されたTrading Plan関連コードを含む最終ワークツリーでは、`frontend/pages/trading_plan.py` の未型付け文字列連結によりReflex exportが停止。UI・来歴変更範囲のruffは通過し、全pytestは引き続き `146 passed`。

# Session update: 2026-06-12 volatility / sentiment / top-risk / FOMO intelligence
- Fixed the existing market-volatility integration so normalized OHLCV automatically produces log returns before volatility-clustering evaluation.
- Added official-Cboe-history market volatility intelligence with persistent stale fallback, historical analog outcomes, and staged `Defensive / Watch / Pilot / Staged` posture.
- Added a reproducible local Fear & Greed-style composite. CNN Fear & Greed is best-effort external reference only and cannot block or directly weight decisions.
- Added a clearly labeled non-official BofA-inspired top-risk subset with exact/proxy/unknown handling; proprietary Sell Side, LT-growth, and M&A indicators remain intentionally omitted.
- Added the FOMO Volatility Regime to individual-stock context/UI and an explicit bounded `/market-watch` scan for high-volatility semiconductor names.
- Preserved the existing probabilistic stock signal and staged MarketContext loading; new diagnostics are parallel context, not replacement trade signals.
- Validation: full pytest passed, live Cboe/FRED/SPY/NVDA smoke passed, and target Stock/Market Watch page imports passed. Reflex export remains blocked by the pre-existing uncommitted `frontend/pages/trading_plan.py` string/ObjectItemOperation type error.

# Session update: 2026-06-12 product refactor P0/P1
- Fixed the Portfolio AI serialized-technical contract and reframed its output as investment research rather than direct order instructions.
- Fixed Market AI theme laggards, market-stage status replacement, and volatility/sentiment dependency order.
- Made optional stock diagnostics preserve partial dashboard results instead of failing the whole stock analysis.
- Removed per-plan market fetches from Trading Plan list rendering.
- Added atomic locked local JSON writes, public-readonly write guards, Knowledge SSRF/upload defenses, and Docker exclusions.
- Changed the default storage policy to local-first and removed the tracked personal portfolio JSON while keeping the local file.
- Added CI constraints and Reflex export checks, plus `docs/PRODUCT_REFACTOR_ROADMAP.md` as the current responsibility map and remaining roadmap.

# Session update: 2026-06-12 live integration verification
- Suppressed the four known `pandas_datareader.compat` distutils deprecation warnings only at the third-party import boundary and added a warning regression test.
- Added `scripts/live_smoke.py` for real SPY, FRED, Finnhub, public-readonly, Supabase, and GAS checks with explicit PASS/FAIL/SKIP boundaries.
- Restored the inactive AI-investing-app Supabase project for live CRUD verification.
- Added the missing live `trade_plans` table and verified rollback-cleaned CRUD across `user_settings`, `portfolios`, `knowledge_items`, and `trade_plans`.
- Verified the production frontend build with `APP_MODE=public_readonly`; the first sandboxed Node build hit `spawn EPERM`, while the approved execution surface passed.
- Separated Reflex disk session state into `.reflex_states/` so production startup no longer attempts to delete application cache directories under `.states/`.
- Verified `APP_MODE=public_readonly` production startup and HTTP 200 on port 8765 after the state-directory split.
- Live smoke now reports FRED provider outages as `DEGRADED` when the app's credit-stress recovery path remains usable.

# Session update: 2026-06-12 GAS removal
- Removed Google Apps Script as a storage backend and deleted the GAS client and Apps Script implementation.
- Storage selection, Portfolio, Knowledge, Trading Plan, legacy settings UI, documentation, and live smoke now support only local JSON and Supabase.
- Legacy saved `storage_type=gas` values safely fall back to local storage.

# AI投資アプリ - 進捗メモ

## Session update: 2026-06-25 Market/Stock data completeness and UI reorganization
- Added option completeness metadata across provider, analysis, context, presentation, Market/Stock state, and trend/theme diagnostics: direct MarketData.app status, fallback reason, Gamma coverage, and complete/fallback/partial status now travel together.
- Hid GEX unless MarketData.app direct Greeks are active; yfinance fallback and token-unconfigured states are explicit limitations instead of being treated as complete option acquisition.
- Reworked Market detail refresh into visible stage actions for Theme/Flow, Vol/Sentiment, Credit/Risk, Options, and all stages, with target descriptions, per-stage timestamps, and per-stage errors.
- Reorganized Market and Stock initial screens around compact summary tiles, update/data-status surfaces, and accordions for deeper analysis, while preserving the existing detailed panels.
- Made adaptive fundamentals easier to read by separating score summary, missing/cap reasons, KPI table, and volume profile; added Stock data_status entries for fundamentals, volume profile, purchase evidence, and SMART criteria.
- Validation: targeted option/market/stock regression tests passed (`22 passed`), full read-only release check passed (`267 passed` plus Reflex frontend export). MarketData.app live smoke is still skipped locally because `MARKETDATA_TOKEN` is not configured.
- UI smoke: static export pages for Market and Stock rendered over local HTTP. Reflex dev-server browser smoke is blocked in this Windows/Codex surface by `PermissionError: [WinError 5]` during multiprocessing startup; classified with `codex_env_triage.py`.

## Session update: 2026-06-24 P0 missing-data / research-contract remediation
- Changed insufficient probabilistic outputs from numeric zeroes to unavailable values and added display-safe `算出不可` formatting.
- Made theme rank a required purchase-evidence input, renamed the output to neutral `根拠一致度` high/medium/low labels, and prevented missing theme data from becoming a real zero score.
- Kept Stock theme-option context on the cache-only path during normal stock loading, while preserving live option analysis for explicit update flows.
- Reframed Stock AI and primary display labels from direct buy/sell/action language to research stance, confirmation, invalidation, and risk-reference language.
- Added regression coverage for missing probabilistic values, missing theme ranks, cache-only option enrichment, display labels, and missing AI prompt metrics.
- Validation: compileall passed, ruff check passed, ruff format check passed, full pytest passed (`264 passed`), and Reflex frontend export passed.

## Session update: 2026-06-18 stock trade integration / market cleanup / detail refresh staging
- Removed the normal `/trading-plan` route and navigation entry while keeping the legacy trade plan storage/code for compatibility; Stock now exposes trade analysis only after the user presses the `トレード分析` button.
- Added Stock trade analysis generation from existing `StockSignalContext` assets, including timing scenarios, key levels, invalidation/risk levels, supply-demand checks, and the existing entry-quality panel inside the expanded trade analysis surface.
- Expanded Minervini stage analysis with MA50/150/200, 200-day slope, 52-week positioning, Stage 2 pass/fail conditions, warnings, and VCP breakout details in the Stock technical section.
- Unified US/JP market index, commodity, FX, and crypto configs; JP sectors now use NEXT FUNDS TOPIX-17 ETFs (`1617.T`-`1633.T`), GBP/USD was removed, and crypto order is Ethereum then Bitcoin.
- Moved Data Quality navigation to the bottom of the sidebar/drawer, moved expected provider/options/AI recap notices out of the global market error flow, and fixed the CNN Fear & Greed reference routing.
- Split detailed market refresh into staged updates (`core`, `theme_flow`, `volatility_sentiment`, `credit_distortion`, `options`) and reduced duplicate theme/trend downloads by deriving multiple periods from one maximum-window fetch.
- Updated product/provenance/operations/architecture docs for the new Stock, Market, data-quality, and staged-refresh behavior.
- Validation: compileall passed, ruff check passed, ruff format check passed, full pytest passed (`240 passed`), and Reflex frontend export passed.

## Session update: 2026-06-17 product review roadmap implementation
- Changed Reflex Portfolio storage to use the shared local/Supabase storage setting instead of forcing `local`; added a Portfolio-page storage selector/status and regression coverage for shared storage defaults.
- Hardened Docker build context exclusions for local secrets and personal data, including Streamlit secrets, `data/*.json`, backups/history, uploads, downloads, keys, and pem files; added a `.dockerignore` regression test.
- Added persistent provider health snapshots under `.states/provider_health_snapshot` and surfaced last success/failure/cache state on `/data-quality`; Market, Stock, and Portfolio analysis paths now record their DataResult health.
- Updated Portfolio AI advice to reuse the current MarketContext when available and skip hidden macro/market/sector refetches on that path; stale/proxy/provenance context now reaches the prompt.
- Added typed subcontext wire shapes for high-churn Market/Stock payloads and split MarketContext cache I/O into `src/services/market_context_cache.py` while keeping existing helper compatibility.
- Marked `legacy_streamlit/` and `src/ui/` as frozen archives in README, architecture docs, and local directory README files.
- Validation: compileall passed, ruff check passed, ruff format check passed, full pytest passed (`227 passed`), and Reflex frontend export passed.

## Session update: 2026-06-16 Hugging Face Spaces sync fix
- Root cause: GitHub Actions quality checks were passing, but Hugging Face Spaces rejected direct history pushes because tracked `docs/ui-audit/2026-06-11/*.png` binary audit artifacts were present in `main`.
- Changed Spaces sync to deploy a clean `git archive HEAD` worktree, remove `docs/ui-audit` from that deploy-only tree, and force-push the generated deploy commit to Hugging Face.
- Updated GitHub Actions checkout/setup-python actions to Node 24-compatible v6 releases to clear the Node 20 deprecation warning.

## Session update: 2026-06-14 product review high-risk remediation
- Expanded `APP_MODE=public_readonly` from write-only protection to a complete public boundary: personal-data reads, AI generation, and URL/YouTube ingestion are blocked; personal pages are hidden from navigation and show a direct-access notice.
- Changed Knowledge URL redirects to validate every destination before connection and close streamed responses reliably.
- Removed delayed J-Quants Free price/history from generic live-price paths, omitted unavailable market items instead of emitting `0.0`, and required full-window observations plus minimum theme coverage for Theme Ranking.
- Added external-call timeouts, Knowledge user-visible errors, Theme Ranking coverage UI, and focused regression tests for the new contracts.

## Session update: 2026-06-13 MarketData.app options complement
- Added an optional MarketData.app REST path for explicit SPY / QQQ / IWM option refreshes, with Bearer authentication, HTTP 203/204 handling, bounded 0DTE requests, direct IV/Greeks/OI/Volume normalization, and provider-specific persistent cache.
- Added `MARKETDATA_OPTIONS_MODE=off|shadow|preferred`; `shadow` keeps yfinance output while recording MarketData.app comparison metadata, and `preferred` falls back to yfinance on failure.
- Kept startup, individual-stock option analysis, and market-microstructure option calls on the existing yfinance path to cap API-credit usage.
- Propagated option source, data timestamp, data mode, and credit metadata through OptionContext/UI/provenance, and added a MarketData.app live smoke check.
- Validation: compileall, ruff check, ruff format check, full pytest (`198 passed`), Reflex frontend export, and live smoke passed; MarketData.app live smoke was skipped because `MARKETDATA_TOKEN` is not configured.

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

# Session update: 2026-06-16 data acquisition / MarketData / data-quality UI
- Fixed the option-data facade mismatch by threading `cache_only` through `DataProviderProtocol`, `DefaultDataProvider`, `DataProvider`, and `src.market_data.get_option_chain`.
- Confirmed the prior option failure was not a MarketData.app live failure: local `MARKETDATA_TOKEN` and `MARKETDATA_OPTIONS_MODE` are unset, so MarketData live validation is intentionally `SKIP` and yfinance/cache fallback is the correct behavior.
- Changed preferred/shadow MarketData option mode so token-missing local runs do not attempt MarketData calls and instead record explicit fallback warnings.
- Added `/data-quality` plus sidebar navigation, provider configuration status without secrets, Market/Stock data-status panels, and provenance/warning aggregation; removed the prominent top provenance panels from Market, Market Watch, Stock, and Portfolio.
- Reused the already-fetched SPY option analysis inside market microstructure to avoid a duplicate SPY option fetch.
- Made opportunity themes return multiple candidates by supplementing with top observation candidates, and added parent sector / ETF proxy / option proxy display.
- Changed Theme Ranking rows so constituent tickers are hidden behind a disclosure control instead of always shown.
- Extended `scripts/live_smoke.py` with multi-ticker MarketData options diagnostics and `--require-marketdata`.
- Updated README, `docs/OPERATIONS.md`, and `docs/ANALYSIS_DATA_PROVENANCE.md` for token setup, dedicated data-quality placement, and proxy/stale-cache handling.
- Validation: compileall, ruff check, ruff format check, full pytest (`221 passed`), Reflex frontend export, live smoke, direct option-status/microstructure smoke, and Browser checks for `/data-quality` and `/theme` passed. Live smoke still reports FRED as `DEGRADED` with app recovery and MarketData options as `SKIP` until `MARKETDATA_TOKEN` is set.

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

# Session update: 2026-06-13 stock / Trading Plan P1 completion
- Added memoized `StockAnalysisInputs` so one stock-analysis run shares target and benchmark histories, company information, news, and peer/provider requests across technical, probabilistic, trend, FOMO, Entry Framework, and sector/theme diagnostics.
- Changed technical multi-timeframe analysis to derive its views from supplied daily history instead of issuing three additional target-ticker requests.
- Added an explicit Trading Plan T+1/T+3 candidate refresh action that fetches each active ticker once, preserves partial successes, and never performs network work during list rendering.

# Session update: 2026-06-13 provider resilience / analysis contract / Japanese stock UI
- Migrated J-Quants calls from invalid legacy-style V2 paths to the official V2 daily bars, equity master, and financial summary endpoints with pagination and response-field mapping.
- Added yfinance history/profile last-success persistence, 429 cooldown, shared market-index history retrieval, and cache-only option use during normal stock analysis to reduce repeated provider pressure.
- Kept the existing FRED stale-cache/partial-success design and localized user-facing FRED recovery messages.
- Changed sector/theme distortion scoring so missing fundamentals or flows are unavailable rather than factual zeroes; added minimum metric/ticker coverage and coverage-aware display.
- Fixed false long-term-MA support signals, normalized technical category scores before the 0-100 mapping, made SMART proxy/unknown states explicit, and limited Neutral/Low-confidence probabilistic signals to Watch with 0% allocation.
- Added centralized Japanese display labels and enlarged/clarified Stock technical, probabilistic, trend robustness, sector/theme, SMART, and Entry Framework evaluations.
- Validation: compileall, ruff check, ruff format check, full pytest (`202 passed`), Reflex frontend export, live FRED smoke, live AAPL stock-context smoke, and HTTP 200 on `/stock`. In-app Browser localhost access remained blocked by the browser execution surface.

# Session update: 2026-06-13 primary evaluation badge consistency
- Audited primary Stock evaluation badges and confirmed the earlier change enlarged Buy/Sell and Robust/Fragile symmetrically, but found inconsistent colors and smaller SMART, sector/theme, and FOMO evaluations.
- Added one shared prominent evaluation-badge primitive and applied it to all primary Stock evaluations: technical Buy/Hold/Sell, probabilistic Add/Hold/Watch/Avoid, trend Robust/Fragile/Watch/Unavailable, SMART, sector/theme, Entry quality, and FOMO regime.
- Positive, negative, neutral/watch, and unavailable states now use symmetric size and semantic colors. Secondary evidence, ticker, provenance, and metric badges intentionally remain compact to avoid visual overload.

# Session update: 2026-06-16 MarketData preferred / strategy regime / integrated trend ranking
- Promoted MarketData.app options to the preferred US options path when `MARKETDATA_TOKEN` is configured; `shadow` remains available only for comparison, and token-missing local runs fall back without failing the app.
- Added theme taxonomy metadata with parent sector, ETF proxy, option proxy, and representative tickers; US sector/theme flow now stays US-only and uses detailed ETF proxies where available, while JP-specific conditions remain in JP mode.
- Added integrated trend ranking and opportunity-theme extraction that combine performance, relative strength, flow proxy, participation, distortion, timeframe fit, and optional theme ETF option asymmetry.
- Added strategy-regime selection (`積極的順張り` / `順張り` / `判断不能(待ち)` / `逆張り` / `積極的逆張り`), timeframe market direction, SPY/QQQ important levels, and macro/volatility drivers to Market Watch and AI context.
- Extended Stock sector/theme context with theme ranking, parent sector, theme ETF proxy, and theme ETF option structure for US names.
- Focused validation passed: `pytest tests\test_trend_ranking_service.py tests\test_market_strategy_service.py tests\test_sector_flow_service.py tests\test_sector_theme_diagnostics.py tests\test_option_data_provider_cache.py tests\test_market_presentation_service.py tests\test_market_context_service.py -q`.

# Session update: 2026-06-23 adaptive fundamentals / volume profile / purchase evidence
- Added daily price-by-volume profiles using 126 sessions, 24 bins, a 60-session minimum, POC, 70% Value Area, concentration zones, and nearest support/resistance zones.
- Added US SPY/QQQ and JP 1306.T/1321.T market index ETF-proxy profiles without changing the v1 strategy-regime score.
- Added adaptive three-layer fundamental classification: market-cap size, value/growth/blend style, and business-model sector profile.
- Added a versioned January 2026 local benchmark snapshot with source URLs, market scope, stale-benchmark warning, and score caps.
- Added bank, insurance, REIT, energy/materials, pharma/biotech, utilities/telecom, software, semiconductor, and general profiles with specialized KPI exclusions.
- Preserved SMART as a growth-only proxy and derived the legacy sector/theme fundamental score from the adaptive score when available.
- Added purchase-evidence confluence using the harmonic mean of technical/Entry and fundamental/theme sides, with Entry, Stage, FOMO, probability, and partial-data caps.
- Extended `StockSignalContext` with `fundamental_profile`, `volume_profile`, and `purchase_evidence`; reused them in Stock UI, trade analysis, AI context, and provenance.
- Added compact Stock classification/evaluation badges plus expandable metric, exclusion, cap, and 24-bin profile details.
- Added unit and acceptance-contract tests for size/style/sector mapping, stale and missing data, bank/REIT/biotech guardrails, purchase caps, and US/JP proxy profiles.
- Design and provenance: `docs/ADAPTIVE_STOCK_ANALYSIS.md` and `docs/ANALYSIS_DATA_PROVENANCE.md`.
- Validation: compileall, ruff check, ruff format check, full pytest (`260 passed`), and Reflex frontend export passed.
- Live classification smoke: NVDA=large/growth/semiconductor available, JPM=large/growth/bank partial-capped, O=REIT unavailable, 7203.T=large/value/general available, and 8306.T=bank unavailable; missing specialized/style inputs stayed unavailable instead of being treated as zero.

# Session update: 2026-06-24 environment validation hardening
- Replaced the mutating `scripts/check.py` workflow with a read-only release check that never installs packages, invokes a shell, formats files, or applies lint fixes.
- Made yfinance cache initialization continue with the repo-local `.states/yfinance_cache` when Python cannot resolve a writable OS temp directory, with a regression test.
- Documented that pytest/Reflex write failures against this repository from another Codex workspace are sandbox-scope failures, not application failures.
- Validation: dependency check, compileall, full Ruff lint/format, full pytest (`264 passed`), and Reflex frontend export all passed through the new read-only script. A first export hit a transient `.web/build` lock; no competing process remained and both the standalone retry and final full-script retry passed.

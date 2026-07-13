# Market Monitoring and Prediction Boundaries

## Current Ownership

Market Monitoring is the current-state diagnostic layer. It gathers market
environment scoring, IBD-style regime classification, option sentiment,
microstructure, momentum themes, distribution days, climax warnings,
yield-spread checks, credit stress, and theme distortion checks into a single
`MarketContext`.

Prediction is the forward-distribution layer. It uses stock features,
technical context, historical forward outcomes, walk-forward validation,
regime fit, trend-follow diagnostics, sector/theme context, and sizing rules to
produce a `StockSignalContext`.

The US Market page also owns a separate market-level short-horizon forecast for
SPY and QQQ at 1, 5, and 20 business days. It combines price trend, breadth,
credit and cyclical relative strength, official Cboe volatility indices, and
weekly CFTC positioning. Every horizon carries its own walk-forward status:
`validated` can inform the qualitative 1W/1M market direction, while
`research_only`, stale, or unavailable output remains visible but cannot be
integrated.

## Composite Sentiment Versus Probability

`composite_sentiment` is an explainable state classifier, not another forecast
probability. It evaluates combinations such as VIX decline plus elevated SKEW,
VIX/VVIX acceleration in negative gamma, term-structure stress, extreme OCC
put/call demand, positive-gamma transition, and weak breadth. Its result may
only preserve or raise the market risk level and cap position sizing. It never
changes `probability_up`, upgrades a stock stance, or creates a buy signal.

The composite status is `confirmed` only when every condition required by the
matched rule is current and usable. Missing OCC history, incomplete or proxy
gamma, a stale source, or missing breadth makes the relevant rule `partial` or
unavailable. Gamma is usable only when the existing MarketData.app option path
reports complete direct coverage; yfinance-estimated gamma is not silently
substituted.

## Shared Contexts

- `MarketContext`: shared by the Market Intelligence UI and AI market recap.
- `OptionContext`: carries option-analysis rows plus retrieval status.
- `StockSignalContext`: shared by the Stock page and AI stock analysis path.

`MarketContext.short_horizon_forecast` and
`MarketContext.composite_sentiment` are also reused by the AI market recap. The
Stock path reads only the cached context through `market_risk_guardrail`: US
stocks may be downgraded from `エントリー検討可` to `監視` or `見送り`, but
the market layer cannot upgrade the stock-specific conclusion. JP stocks are
explicitly outside this guardrail.

The daily Entry Framework is an execution-quality gate inside
`StockSignalContext.trade_setup`. It reuses existing technical and daily OHLCV
data to evaluate relative strength, contraction, volume confirmation, ATR
extension, and hard-rule violations. It does not replace probabilistic signals
or trend-follow diagnostics, and it does not infer intraday-only LoD/ORH rules.

Trade analysis is now integrated into the Stock page as an explicit on-demand
panel. It reuses `StockSignalContext`, technical levels, Entry Framework,
sector/theme context, FOMO regime, trend-follow diagnostics, and probabilistic
signals to organize timing, invalidation, and risk levels. The legacy
Trading Plan storage/state code remains only for existing data compatibility.
Portfolio remains the asset-allocation surface.

IBD-style market regime is a free-data approximation, not an official IBD
Market Pulse clone. The implementation uses SPY and Nasdaq 100 proxy OHLCV,
distribution days, rally attempts, follow-through days, and key moving-average
breaks to classify `confirmed_uptrend`, `uptrend_under_pressure`,
`rally_attempt`, or `market_in_correction`. The classification contributes to
the same weighted qualitative score as other market signals with a high weight
because it acts as the base market-state lens.

Theme distortion detection compares a fundamental score with a flow score.
Bullish distortions are themes with better fundamentals than current flow;
bearish distortions are themes where flow is materially ahead of fundamentals.
The UI shows the top five of each and the AI recap receives them as candidates
for critical narrative evaluation, not as automatic recommendations.

Trend-follow diagnostics are a robustness lens, not a standalone trading
strategy. The first implementation uses daily individual-stock data and checks
moving-average trend participation against Buy & Hold, OOS behavior, cost and
entry-lag sensitivity, random-direction baselines, and top-trade dependency.

The first integration step keeps paid data APIs and QuantLib out of scope. The
US market receives the richest monitoring context because index option data is
available; JP remains monitoring-first until the option data source improves.

## Primary Public Data References

- Cboe official index history: `https://cdn.cboe.com/api/global/us_indices/daily_prices/<SYMBOL>_History.csv`
- CFTC Traders in Financial Futures API: `https://publicreporting.cftc.gov/resource/gpe5-46if.json`
- OCC consolidated option volume query: `https://marketdata.theocc.com/volume-query`

## Credit Stress and Flow Proxy

The US Market Intelligence detail refresh also monitors whether an equity selloff
is spreading into credit and funding stress. The first trigger watches the
three-month velocity of `BAA10Y` and `KCFSI`; `rapid_stress` requires both
velocity z-scores to exceed `+0.5`. This is intended to distinguish a sector or
equity bubble unwind from a GFC-style credit contraction.

FRED data is fetched through bounded FRED graph CSV requests with start/end
parameters, then falls back to recovered `pandas_datareader` and
`.states/economic_data_cache` stale data. `setuptools` remains pinned because
pandas-datareader still imports legacy `distutils` paths, and a repo-local shim
handles pandas 3 decorator drift before import.

Leadership flow is a free proxy, not issuer-reported ETF fund flow. It uses
signed dollar volume, relative returns, flow-pressure z-scores, and 50-day trend
status for liquid US sector, semiconductor, software, credit, and bank ETFs.
Issuer/ETF.com fund-flow feeds, CDX HY, and FRA-OIS are intentionally out of
scope for the first free/local implementation.

## AI Report Behavior

When the UI has already fetched a `MarketContext`, `generate_market_analysis_report`
uses it directly instead of recomputing market monitoring, microstructure,
momentum, and option context. Standalone report calls without a supplied context
preserve the previous behavior and fetch their own data.

The Market page can pass an optional user-specified focus item to the recap
prompt. That focus is appended as a separate input block and must be tied back
to current market state, flow, fundamentals, and invalidation conditions in the
generated report.

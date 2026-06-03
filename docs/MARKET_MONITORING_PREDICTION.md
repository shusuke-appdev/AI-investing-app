# Market Monitoring and Prediction Boundaries

## Current Ownership

Market Monitoring is the current-state diagnostic layer. It gathers market
environment scoring, option sentiment, microstructure, momentum themes,
distribution days, climax warnings, and yield-spread checks into a single
`MarketContext`.

Prediction is the forward-distribution layer. It uses stock features,
technical context, historical forward outcomes, walk-forward validation,
regime fit, trend-follow diagnostics, and sizing rules to produce a
`StockSignalContext`.

## Shared Contexts

- `MarketContext`: shared by the Market Intelligence UI and AI market recap.
- `OptionContext`: carries option-analysis rows plus retrieval status.
- `StockSignalContext`: shared by the Stock page and AI stock analysis path.

Trend-follow diagnostics are a robustness lens, not a standalone trading
strategy. The first implementation uses daily individual-stock data and checks
moving-average trend participation against Buy & Hold, OOS behavior, cost and
entry-lag sensitivity, random-direction baselines, and top-trade dependency.

The first integration step keeps paid data APIs and QuantLib out of scope. The
US market receives the richest monitoring context because index option data is
available; JP remains monitoring-first until the option data source improves.

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

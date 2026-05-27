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

## AI Report Behavior

When the UI has already fetched a `MarketContext`, `generate_market_analysis_report`
uses it directly instead of recomputing market monitoring, microstructure,
momentum, and option context. Standalone report calls without a supplied context
preserve the previous behavior and fetch their own data.

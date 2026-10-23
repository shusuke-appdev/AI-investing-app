---
name: research-dashboard
description: Design and verify this repository's local investment-research dashboard, including index comparisons, ranked themes, stock conditions and source-labelled analysis. Use for dashboard changes, not investment recommendations or deployment.
---

# Research dashboard

2026-10-24 operating decision: daily research is delivered in Codex chat via `scripts/research.py saved`/`update`, without automatically launching a browser or server. This dashboard is an optional local view, not an app to publish. Use this Skill only when the user asks for its visual view or maintenance; preserve the Markdown/JSON research path. See `docs/CODEX_OPERATION.md`.

2026-10-23 approved top-down revision: `docs/TOPDOWN_RESEARCH.md` takes precedence over the older composition below. The local version begins with four independent environment observations, sectors/themes, then stock conditions. `topdown.py` and `quarterly.py` own calculations; `fundamentals.py` owns explicit quarterly acquisition, and `assets/topdown.js` displays saved values. Preserve Reflex and saved accounting/valuation dates.

- Six screens: overview/market/sectors and themes/stocks/conditional checks/data. Add market breadth and diary, ETF down-volume-day proxies, sector summaries, numeric tables, equal-area heatmaps, strength/acceleration quadrants with 12-week trails, and volume activity. Keep all prior research detail accessible.
- Theme and sector periods: 1d/1w/1m/3m/6m/1y = 1/5/21/63/126/252 sessions, default 6m. No composite stock or bullish score. Registered sample and ETF proxies must be labelled; missing relative benchmark stops relative calculations while usable absolute observations remain available.
- Stock candidates support explicit independent conditions, charts/ratio/volume, sector/theme/search/verification filters, CSV and browser-local pins. Keep research-only wording. Pocket-pivot/down-volume-day conditions are documented approximations, not official signals or inferred fund flows.
- v3 writes and v1/v2 reads coexist, bounded at 20MiB/file; mixed imports stay atomic. Update modes are prices/fundamentals/all with the same server protections and update lock. Saved/offline viewing never fetches.
- Quarterly auto candidates and reviewed primary evidence are separate. Require comparable standalone quarters, diluted EPS and scope/split/accounting/ownership/currency definitions. Never subtract cumulative EPS, substitute basic EPS, infer missing history, or turn a turnaround into a Code33 pass. Preserve insufficient/incomparable/not-applicable states and reviewed records during automatic updates.
- Acceptance includes all four widths and both appearances/markets/six screens, 6 periods x 4 views x 2 units x 2 markets, candidate presets/drilldown/return/pins/CSV, v1/v2/v3 mixed imports and failed-import retention, loaded offline operation, shell update modes, source-linked actual-quarter examples and prior-snapshot hashes. Record current source limits separately from implementation checks.

Revise `src/research/assets/` and `src/research/render.py` in place. Python snapshots/existing calculations are authoritative; offline HTML must not call providers/models. Read `docs/RESEARCH_FEATURE_PARITY.md` for full feature/event ownership and `docs/RESEARCH_MIGRATION_ACCEPTANCE.md` for current browser/data acceptance.

`workbench.html` is a separate local update shell; `local_server.py` binds only127.0.0.1 and serves no repository files. Its explicit update action calls `workbench.py`, while the embedded six-screen dashboard remains offline. Preserve Host/Origin/token/body validation and the cross-process update lock. Opening only reads saved snapshots; updates do not refresh saved individual-stock accounting/valuation/interpretation dates. Test shell controls, progress/duplicate prevention/failure retention, both policies and responsive iframe navigation as well as the saved view.

## Approved composition

- Overview layout remains: two index comparison charts; environment; Top5 and same five bars; period table; compact structure/volatility-credit references. Standard Top5 uses six-month constituent-median market-relative rank and six-month bars, explicitly labelled. Legacy composite/one-month bars retain their old labels, dates and research-only status. No stocks on overview.
- Six destinations: 総覧/市場/テーマ/銘柄/方針/データ状況. Stage2/RS/VCP/volume/growth/Entry individually, no new stock composite. Other analyses reference-only.
- `catalog.py` defines29market/17stock fields. JSON retention is not usable UI. Market asset listings/history/forecasts/OOS/options and stock charts/volume profile/multiple valuations/accounting have dedicated displays. Named reference tables preserve actual inputs, status and source dates.

## Encoding and evidence

- Index comparisons: exact common ISO calendar dates, first=100, elapsed-time X, labelled Y/legends/actual prices/returns, pointer+keyboard. No forward-fill/guessed year. Legacy market MM/DD cannot become a fabricated ISO date.
- Index periods1mo/3mo/6mo(default)/1y/2y affect only comparisons. Standard theme1w/1m/6m uses saved5/21/126-session definitions, default6m, constituent median relative rank; require60% and min(3,registered) usable same-period members. Direction/order/coverage filter that period. Legacy composite scores remain unchanged. Never relabel old20-session constituents as21/126-session returns.
- Native TOPIX first; permitted1306.T fallback says TOPIX連動ETF・代理 and adjusted close. No history splicing or ETF price as native index. Observation/fetch/publication/review/report dates remain distinct.
- Stock chart: saved close/MA10/20/50/200/volume, period/log-linear/legend/date controls. Missing/nonpositive log data splits paths; all price series off still shows volume. Price-band volume is a separate daily approximation.
- Preserve zero/null/no rows/insufficient/partial/stale/research_only. Japanese credit cannot disguise US reference data. Mixed bundles preserve issuer market; candidate opens saved issuer or shows exact CLI guidance.
- Valuation shows all methods/3cases/inputs/definitions/assumptions/reverse limits. Accounting shows original units/periods/ownership/source, original signed adjustments, all segments/elimination and amendments. Partial SOTP is not whole-company value.

## Visual system and reusable assets

`dashboard.html` is the template, `charts.js` chart primitives, `dashboard.js` shell, `market.js` connected market groups, `specialized.js` specialized views, `dashboard.css` tokens/responsiveness. Keep responsibilities separate.

Standard market initially answers five questions: medium trend/participation, short price position/events, themes/members, cross-asset risks/JP cash flows, conditional connections/counterevidence/next checks. Python generates observations/relations; JavaScript only displays. Keep important values and counterevidence visible. Source/calculation details and retained29legacy fields may expand. Do not count shared price/VIX derivatives as independent evidence; no aggregate bullish/bearish score. Policy references the same saved connection object. Missing legacy fields are unacquired; retained fields show original dates and outside-this-update status.

Theme rows always show registered first3representatives; their name expands all members directly below the same row. Keep one parent table rather than repeating headers/cards for each theme. Preserve source-bound periods, missing members and selected controls per market. Standard members have period-specific saved returns, old members keep20-session/unknown labels. Keep multiple expansions open for comparison. See `docs/MARKET_REDESIGN_ACCEPTANCE.md` for regression/live limitations.

White/cool-gray, graphite, restrained blue/teal, thin borders,6px radii/tabular numerals. Sidebar128px/header58px/gutters12px. Dense tables, not marketing cards. Consistent light/dark via appearance control; mobile wide tables scroll inside panels without one-character Japanese wrapping.

## Rendered acceptance

Use permitted browser UI tools with real loaded data. Check all6destinations, all filters/reset/numeric sorting, stock selection, source links, charts with pointer/keyboard, multiple valuation/accounting and saved import. Test320/736/1024/1440 light/dark for page overflow/console/clipped marks. Valid v1/v2 multi-import and malformed mixed import must be atomic (20MB/file); failed import preserves previous display. Compare separate negative/zero/null fixtures without replacing real evidence.

For short policy pages, vary height as well as width:736x1440 previously stretched mobile navigation to222px. Its grid row is now45px including border, with44px buttons; test long/short/missing pages without distributing viewport slack into navigation. Verify both loopback iframe and loaded offline HTML. Reload saved view after asset edits; research dates must not change to the UI refresh date.

Verify offline operation without weakening system network/security: self-contained/CSP plus stop only a task-owned preview server and exercise the loaded page, then restore it. Compare final screenshots with approved composition via view_image: chart axes/placement, headings/type, palette, table density/geometry/gutters. Source/date/caveat copy differs only for real inputs, never invented values. Open a useful final preview in Codex. Run code-factory after code changes and rerun affected interactions after fixes.

## Design references

Linear position/length aid fast comparisons: [NN/g dashboard perception](https://www.nngroup.com/articles/dashboards-preattentive/). Semantic headers/aligned numbers/type scale: [GOV.UK tables](https://design-system.service.gov.uk/components/table/) and [type scale](https://design-system.service.gov.uk/styles/type-scale/). These inform clarity, not replacement of the approved layout.

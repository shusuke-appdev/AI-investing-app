"""Trend-following robustness diagnostics for daily stock analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_COST_BPS = 20.0
MIN_HISTORY_DAYS = 260
RANDOM_TRIALS = 500
PARAMETER_GRID = ((20, 80), (20, 120), (50, 150), (50, 200))
COST_GRID_BPS = (0.0, 10.0, 20.0, 50.0)
LAG_GRID_DAYS = (0, 1, 2, 4)


@dataclass(frozen=True)
class TrendFollowConfig:
    """Daily trend-following diagnostic configuration."""

    short_window: int = 50
    long_window: int = 200
    mode: str = "long_only"
    benchmark: str = "SPY"
    period: str = "5y"
    round_trip_cost_bps: float = DEFAULT_COST_BPS
    entry_lag_days: int = 0
    fill_price: str = "next_open"


@dataclass
class TrendFollowTrade:
    """Completed trend-following position segment."""

    entry_date: str
    exit_date: str
    direction: int
    gross_return: float
    net_return: float
    holding_days: int


@dataclass
class TrendFollowDiagnostics:
    """Serialized trend-following diagnostic bundle."""

    ticker: str
    as_of: str
    primary_config: dict[str, Any]
    current_state: dict[str, Any] = field(default_factory=dict)
    diagnostic_rating: str = "Unavailable"
    strategy_metrics: dict[str, Any] = field(default_factory=dict)
    buy_hold_metrics: dict[str, Any] = field(default_factory=dict)
    dev_oos: dict[str, Any] = field(default_factory=dict)
    tail_dependency: dict[str, Any] = field(default_factory=dict)
    cost_sensitivity: list[dict[str, Any]] = field(default_factory=list)
    lag_sensitivity: list[dict[str, Any]] = field(default_factory=list)
    random_direction: dict[str, Any] = field(default_factory=dict)
    parameter_grid: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data_quality: dict[str, Any] = field(default_factory=dict)


@dataclass
class _StrategyRun:
    config: TrendFollowConfig
    returns: pd.Series
    buy_hold_returns: pd.Series
    position_at_open: pd.Series
    trades: list[TrendFollowTrade]
    current_state: dict[str, Any]


def generate_trend_follow_diagnostics(
    ticker: str,
    period: str = "5y",
    benchmark: str = "SPY",
    price_df: pd.DataFrame | None = None,
) -> TrendFollowDiagnostics:
    """Generate robustness diagnostics from existing daily OHLCV data."""

    from src.market_data import get_stock_data

    config = TrendFollowConfig(period=period, benchmark=benchmark)
    try:
        prices = price_df if price_df is not None else get_stock_data(ticker, period)
    except Exception as exc:
        return _fallback_diagnostics(
            ticker, config, f"Price history unavailable: {exc}"
        )

    clean = _clean_ohlcv(prices)
    if len(clean) < MIN_HISTORY_DAYS:
        return _fallback_diagnostics(
            ticker,
            config,
            f"Insufficient daily price history: {len(clean)} rows.",
            rows=len(clean),
        )

    run = _run_strategy(clean, config)
    benchmark_metrics = _metrics(run.buy_hold_returns, [])
    strategy_metrics = _metrics(run.returns, run.trades)
    tail = _tail_dependency(run.trades)
    dev_oos = _dev_oos(run.returns, run.buy_hold_returns)
    cost = _cost_sensitivity(clean, config)
    lag = _lag_sensitivity(clean, config)
    random_direction = _random_direction_test(clean, run, config)
    parameter_grid = _parameter_grid(clean, config)
    warnings = _warnings(strategy_metrics, dev_oos, tail, random_direction, run)
    rating = _diagnostic_rating(
        strategy_metrics, dev_oos, tail, cost, lag, random_direction
    )

    if "Open" not in (prices.columns if prices is not None else []):
        warnings.append(
            "Open prices were unavailable; Close was used as execution proxy."
        )

    return TrendFollowDiagnostics(
        ticker=ticker.upper(),
        as_of=_date_str(clean.index[-1]),
        primary_config=asdict(config),
        current_state=run.current_state,
        diagnostic_rating=rating,
        strategy_metrics=strategy_metrics,
        buy_hold_metrics=benchmark_metrics,
        dev_oos=dev_oos,
        tail_dependency=tail,
        cost_sensitivity=cost,
        lag_sensitivity=lag,
        random_direction=random_direction,
        parameter_grid=parameter_grid,
        warnings=warnings[:8],
        data_quality={
            "status": "ok",
            "rows": int(len(clean)),
            "min_required_rows": MIN_HISTORY_DAYS,
            "execution_price": "open" if "Open" in clean.columns else "close",
        },
    )


def trend_follow_to_dict(diagnostics: TrendFollowDiagnostics) -> dict[str, Any]:
    """Serialize diagnostics with Reflex-friendly display fields."""

    data = _plain(asdict(diagnostics))
    strategy = data.get("strategy_metrics") or {}
    buy_hold = data.get("buy_hold_metrics") or {}
    dev_oos = data.get("dev_oos") or {}
    tail = data.get("tail_dependency") or {}
    random_direction = data.get("random_direction") or {}
    current = data.get("current_state") or {}
    data.update(
        {
            "rating_display": data.get("diagnostic_rating", "Unavailable"),
            "current_state_display": current.get(
                "description", "Trend state unavailable."
            ),
            "strategy_total_return_display": _format_pct(strategy.get("total_return")),
            "strategy_cagr_display": _format_pct(strategy.get("cagr")),
            "strategy_max_drawdown_display": _format_pct(strategy.get("max_drawdown")),
            "strategy_profit_factor_display": _format_number(
                strategy.get("profit_factor")
            ),
            "strategy_trade_count_display": str(strategy.get("trade_count", 0)),
            "strategy_tuw_display": f"{strategy.get('max_tuw_days', 0)} days",
            "buy_hold_total_return_display": _format_pct(buy_hold.get("total_return")),
            "oos_alpha_display": _format_pct(dev_oos.get("oos_alpha_vs_buy_hold")),
            "oos_total_return_display": _format_pct(dev_oos.get("oos_total_return")),
            "top5_removed_display": _format_pct(tail.get("remove_top_5_pct_sum")),
            "random_percentile_display": _format_pct(
                _as_fraction(random_direction.get("actual_percentile"))
            ),
            "warnings_display": "\n".join(
                f"- {item}" for item in data.get("warnings", [])
            )
            or "- No dominant diagnostic warning.",
        }
    )
    return data


def _clean_ohlcv(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy().sort_index()
    if "Close" not in out.columns:
        return pd.DataFrame()
    for column in ("Open", "High", "Low", "Close"):
        if column not in out.columns:
            out[column] = out["Close"]
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if "Volume" not in out.columns:
        out["Volume"] = 0.0
    out["Volume"] = pd.to_numeric(out["Volume"], errors="coerce").fillna(0.0)
    return out.dropna(subset=["Close"])


def _run_strategy(prices: pd.DataFrame, config: TrendFollowConfig) -> _StrategyRun:
    short_ma = prices["Close"].rolling(config.short_window).mean()
    long_ma = prices["Close"].rolling(config.long_window).mean()
    signal = _signal_from_ma(short_ma, long_ma, config.mode)
    execution_price = prices["Open"] if "Open" in prices.columns else prices["Close"]
    position_at_open = signal.shift(1 + config.entry_lag_days).fillna(0.0)
    returns = _returns_from_position(execution_price, position_at_open, config)
    buy_hold_returns = execution_price.pct_change().replace([np.inf, -np.inf], np.nan)
    trades = _build_trades(execution_price, position_at_open, config)
    return _StrategyRun(
        config=config,
        returns=returns,
        buy_hold_returns=buy_hold_returns,
        position_at_open=position_at_open,
        trades=trades,
        current_state=_current_state(
            prices, short_ma, long_ma, position_at_open, config
        ),
    )


def _signal_from_ma(
    short_ma: pd.Series,
    long_ma: pd.Series,
    mode: str,
) -> pd.Series:
    bullish = (short_ma > long_ma).astype(float)
    if mode == "long_short":
        return bullish.replace({0.0: -1.0})
    return bullish


def _returns_from_position(
    execution_price: pd.Series,
    position_at_open: pd.Series,
    config: TrendFollowConfig,
) -> pd.Series:
    price_return = execution_price.pct_change()
    held_position = position_at_open.shift(1).fillna(0.0)
    turnover = position_at_open.diff().abs().fillna(position_at_open.abs())
    cost = turnover * (config.round_trip_cost_bps / 10000.0)
    returns = held_position * price_return - cost
    return returns.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _build_trades(
    execution_price: pd.Series,
    position_at_open: pd.Series,
    config: TrendFollowConfig,
) -> list[TrendFollowTrade]:
    trades: list[TrendFollowTrade] = []
    current_direction = 0
    entry_idx: int | None = None
    entry_price = 0.0
    positions = position_at_open.round().astype(int)
    cost = config.round_trip_cost_bps / 10000.0

    for idx, direction in enumerate(positions):
        if direction == current_direction:
            continue
        if current_direction != 0 and entry_idx is not None:
            trades.append(
                _trade_from_segment(
                    execution_price,
                    entry_idx,
                    idx,
                    current_direction,
                    entry_price,
                    cost,
                )
            )
        current_direction = int(direction)
        entry_idx = idx if current_direction != 0 else None
        entry_price = (
            float(execution_price.iloc[idx]) if current_direction != 0 else 0.0
        )

    if (
        current_direction != 0
        and entry_idx is not None
        and entry_idx < len(execution_price) - 1
    ):
        trades.append(
            _trade_from_segment(
                execution_price,
                entry_idx,
                len(execution_price) - 1,
                current_direction,
                entry_price,
                cost,
            )
        )
    return trades


def _trade_from_segment(
    execution_price: pd.Series,
    entry_idx: int,
    exit_idx: int,
    direction: int,
    entry_price: float,
    cost: float,
) -> TrendFollowTrade:
    exit_price = float(execution_price.iloc[exit_idx])
    gross = direction * (exit_price / entry_price - 1.0) if entry_price else 0.0
    return TrendFollowTrade(
        entry_date=_date_str(execution_price.index[entry_idx]),
        exit_date=_date_str(execution_price.index[exit_idx]),
        direction=direction,
        gross_return=float(gross),
        net_return=float(gross - cost),
        holding_days=int(max(exit_idx - entry_idx, 0)),
    )


def _metrics(returns: pd.Series, trades: list[TrendFollowTrade]) -> dict[str, Any]:
    clean = returns.dropna()
    if clean.empty:
        return _empty_metrics()
    equity = (1.0 + clean).cumprod()
    years = max(len(clean) / 252.0, 1 / 252.0)
    total_return = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1 / years) - 1.0) if equity.iloc[-1] > 0 else -1.0
    std = float(clean.std())
    sharpe = float(clean.mean() / std * np.sqrt(252)) if std > 0 else 0.0
    trade_returns = pd.Series([trade.net_return for trade in trades], dtype=float)
    wins = trade_returns[trade_returns > 0]
    losses = trade_returns[trade_returns < 0]
    profit_factor = (
        float(wins.sum() / abs(losses.sum()))
        if not losses.empty and abs(losses.sum()) > 0
        else float("inf")
        if not wins.empty
        else 0.0
    )
    return {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": _max_drawdown(clean),
        "max_tuw_days": _max_time_under_water(equity),
        "trade_count": int(len(trades)),
        "hit_rate": float((trade_returns > 0).mean())
        if not trade_returns.empty
        else 0.0,
        "profit_factor": profit_factor,
        "avg_trade_return": float(trade_returns.mean())
        if not trade_returns.empty
        else 0.0,
        "avg_win": float(wins.mean()) if not wins.empty else 0.0,
        "avg_loss": float(losses.mean()) if not losses.empty else 0.0,
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "total_return": 0.0,
        "cagr": 0.0,
        "sharpe": 0.0,
        "max_drawdown": 0.0,
        "max_tuw_days": 0,
        "trade_count": 0,
        "hit_rate": 0.0,
        "profit_factor": 0.0,
        "avg_trade_return": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
    }


def _max_drawdown(returns: pd.Series) -> float:
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    peak = equity.cummax()
    return float((equity / peak - 1.0).min())


def _max_time_under_water(equity: pd.Series) -> int:
    peak = equity.cummax()
    underwater = equity < peak
    max_run = 0
    current = 0
    for value in underwater:
        current = current + 1 if value else 0
        max_run = max(max_run, current)
    return int(max_run)


def _tail_dependency(trades: list[TrendFollowTrade]) -> dict[str, Any]:
    returns = pd.Series([trade.net_return for trade in trades], dtype=float)
    if returns.empty:
        return {
            "trade_count": 0,
            "remove_top_1_pct_sum": 0.0,
            "remove_top_5_pct_sum": 0.0,
            "remove_top_10_pct_sum": 0.0,
            "tail_dependent": True,
        }
    sorted_returns = returns.sort_values(ascending=False).reset_index(drop=True)
    base_sum = float(sorted_returns.sum())
    results = {"trade_count": int(len(sorted_returns)), "base_sum": base_sum}
    for pct in (1, 5, 10):
        remove_n = max(1, int(np.ceil(len(sorted_returns) * pct / 100.0)))
        key = f"remove_top_{pct}_pct_sum"
        results[key] = float(sorted_returns.iloc[remove_n:].sum())
    results["tail_dependent"] = bool(results["remove_top_5_pct_sum"] <= 0)
    return results


def _dev_oos(
    strategy_returns: pd.Series, buy_hold_returns: pd.Series
) -> dict[str, Any]:
    split = int(len(strategy_returns) * 0.8)
    dev = strategy_returns.iloc[:split]
    oos = strategy_returns.iloc[split:]
    oos_buy_hold = buy_hold_returns.reindex(strategy_returns.index).iloc[split:]
    dev_metrics = _metrics(dev, [])
    oos_metrics = _metrics(oos, [])
    buy_hold_metrics = _metrics(oos_buy_hold.fillna(0.0), [])
    return {
        "split_index": split,
        "dev_total_return": dev_metrics["total_return"],
        "oos_total_return": oos_metrics["total_return"],
        "oos_cagr": oos_metrics["cagr"],
        "oos_max_drawdown": oos_metrics["max_drawdown"],
        "oos_buy_hold_total_return": buy_hold_metrics["total_return"],
        "oos_alpha_vs_buy_hold": oos_metrics["total_return"]
        - buy_hold_metrics["total_return"],
    }


def _cost_sensitivity(
    prices: pd.DataFrame,
    base_config: TrendFollowConfig,
) -> list[dict[str, Any]]:
    rows = []
    for cost_bps in COST_GRID_BPS:
        config = TrendFollowConfig(
            **{**asdict(base_config), "round_trip_cost_bps": cost_bps}
        )
        run = _run_strategy(prices, config)
        metrics = _metrics(run.returns, run.trades)
        rows.append(
            {
                "round_trip_cost_bps": cost_bps,
                "total_return": metrics["total_return"],
                "cagr": metrics["cagr"],
                "profit_factor": metrics["profit_factor"],
            }
        )
    return rows


def _lag_sensitivity(
    prices: pd.DataFrame,
    base_config: TrendFollowConfig,
) -> list[dict[str, Any]]:
    rows = []
    for lag_days in LAG_GRID_DAYS:
        config = TrendFollowConfig(
            **{**asdict(base_config), "entry_lag_days": lag_days}
        )
        run = _run_strategy(prices, config)
        metrics = _metrics(run.returns, run.trades)
        rows.append(
            {
                "entry_lag_days": lag_days,
                "total_return": metrics["total_return"],
                "cagr": metrics["cagr"],
                "max_drawdown": metrics["max_drawdown"],
            }
        )
    return rows


def _parameter_grid(
    prices: pd.DataFrame,
    base_config: TrendFollowConfig,
) -> list[dict[str, Any]]:
    rows = []
    for short_window, long_window in PARAMETER_GRID:
        if short_window >= long_window:
            continue
        config = TrendFollowConfig(
            **{
                **asdict(base_config),
                "short_window": short_window,
                "long_window": long_window,
            }
        )
        run = _run_strategy(prices, config)
        metrics = _metrics(run.returns, run.trades)
        dev_oos = _dev_oos(run.returns, run.buy_hold_returns)
        rows.append(
            {
                "short_window": short_window,
                "long_window": long_window,
                "total_return": metrics["total_return"],
                "oos_alpha_vs_buy_hold": dev_oos["oos_alpha_vs_buy_hold"],
                "max_drawdown": metrics["max_drawdown"],
                "trade_count": metrics["trade_count"],
            }
        )
    return rows


def _random_direction_test(
    prices: pd.DataFrame,
    run: _StrategyRun,
    config: TrendFollowConfig,
) -> dict[str, Any]:
    rng = np.random.default_rng(42)
    execution_price = prices["Open"] if "Open" in prices.columns else prices["Close"]
    actual_total = _metrics(run.returns, run.trades)["total_return"]
    positions = run.position_at_open.dropna()
    exposure = float((positions.abs() > 0).mean()) if not positions.empty else 0.0
    random_totals: list[float] = []
    for _ in range(RANDOM_TRIALS):
        draws = rng.random(len(positions))
        random_position = pd.Series(
            np.where(draws < exposure, 1.0, 0.0),
            index=positions.index,
            dtype=float,
        )
        random_returns = _returns_from_position(
            execution_price, random_position, config
        )
        random_totals.append(_metrics(random_returns, [])["total_return"])
    random_series = pd.Series(random_totals, dtype=float)
    percentile = float((random_series <= actual_total).mean() * 100.0)
    return {
        "trials": RANDOM_TRIALS,
        "actual_total_return": actual_total,
        "actual_percentile": percentile,
        "random_median_total_return": float(random_series.median()),
        "random_p95_total_return": float(random_series.quantile(0.95)),
        "exposure": exposure,
    }


def _current_state(
    prices: pd.DataFrame,
    short_ma: pd.Series,
    long_ma: pd.Series,
    position_at_open: pd.Series,
    config: TrendFollowConfig,
) -> dict[str, Any]:
    latest_close = float(prices["Close"].iloc[-1])
    short_value = _optional_float(short_ma.iloc[-1])
    long_value = _optional_float(long_ma.iloc[-1])
    position = int(position_at_open.iloc[-1]) if len(position_at_open) else 0
    aligned = bool(
        short_value is not None and long_value is not None and short_value > long_value
    )
    return {
        "short_ma": short_value,
        "long_ma": long_value,
        "latest_close": latest_close,
        "position": position,
        "trend_aligned": aligned,
        "description": (
            f"{config.short_window}D MA is above {config.long_window}D MA; trend-follow lens is active."
            if aligned
            else f"{config.short_window}D MA is not above {config.long_window}D MA; trend-follow lens is inactive."
        ),
    }


def _warnings(
    strategy_metrics: dict[str, Any],
    dev_oos: dict[str, Any],
    tail: dict[str, Any],
    random_direction: dict[str, Any],
    run: _StrategyRun,
) -> list[str]:
    warnings: list[str] = []
    if strategy_metrics.get("trade_count", 0) < 5:
        warnings.append("Trade sample is small; treat the result as exploratory.")
    if dev_oos.get("oos_alpha_vs_buy_hold", 0.0) <= 0:
        warnings.append("OOS return did not beat Buy & Hold.")
    if tail.get("tail_dependent"):
        warnings.append("Removing the top 5% trades erases the edge proxy.")
    if random_direction.get("actual_percentile", 0.0) < 60.0:
        warnings.append("Actual path is not clearly above random-direction baselines.")
    if strategy_metrics.get("max_tuw_days", 0) > 126:
        warnings.append("Time under water exceeded roughly six trading months.")
    if abs(float(run.position_at_open.dropna().mean() or 0.0)) < 0.05:
        warnings.append("The strategy is rarely exposed in the current configuration.")
    return warnings


def _diagnostic_rating(
    strategy_metrics: dict[str, Any],
    dev_oos: dict[str, Any],
    tail: dict[str, Any],
    cost_sensitivity: list[dict[str, Any]],
    lag_sensitivity: list[dict[str, Any]],
    random_direction: dict[str, Any],
) -> str:
    if strategy_metrics.get("trade_count", 0) == 0:
        return "Unavailable"
    if dev_oos.get("oos_alpha_vs_buy_hold", 0.0) <= 0:
        return "Unproven"
    if random_direction.get("actual_percentile", 0.0) < 50.0:
        return "Unproven"

    cost_50 = next(
        (row for row in cost_sensitivity if row["round_trip_cost_bps"] == 50.0),
        {},
    )
    lag_1 = next((row for row in lag_sensitivity if row["entry_lag_days"] == 1), {})
    fragile = (
        bool(tail.get("tail_dependent"))
        or cost_50.get("total_return", 0.0) <= 0
        or lag_1.get("total_return", 0.0) <= 0
    )
    if fragile:
        return "Fragile"
    if (
        random_direction.get("actual_percentile", 0.0) >= 70.0
        and strategy_metrics.get("profit_factor", 0.0) > 1.1
        and strategy_metrics.get("max_drawdown", 0.0) > -0.35
    ):
        return "Robust"
    return "Watch"


def _fallback_diagnostics(
    ticker: str,
    config: TrendFollowConfig,
    warning: str,
    rows: int = 0,
) -> TrendFollowDiagnostics:
    return TrendFollowDiagnostics(
        ticker=ticker.upper(),
        as_of="",
        primary_config=asdict(config),
        diagnostic_rating="Unavailable",
        warnings=[warning],
        data_quality={
            "status": "insufficient_data" if rows < MIN_HISTORY_DAYS else "failed",
            "rows": int(rows),
            "min_required_rows": MIN_HISTORY_DAYS,
        },
    )


def _optional_float(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_str(value: Any) -> str:
    return str(value.date()) if hasattr(value, "date") else str(value)


def _format_pct(value: Any) -> str:
    number = _optional_float(value)
    if number is None:
        return "N/A"
    return f"{number:+.2%}"


def _format_number(value: Any) -> str:
    number = _optional_float(value)
    if number is None:
        return "N/A"
    if np.isinf(number):
        return "inf"
    return f"{number:.2f}"


def _as_fraction(value: Any) -> float | None:
    number = _optional_float(value)
    if number is None:
        return None
    return number / 100.0


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return "inf" if value > 0 else "-inf"
    return value

"""
オプション分析モジュール
GEX (Gamma Exposure)、PCR (Put/Call Ratio)、Gamma Wallの計算を行います。
Finnhub APIから取得したGreeksを活用し、より正確な分析を提供します。
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

from .data_provider import DataProvider
from .log_config import get_logger
from .market_data import get_option_chain
from .option_data_provider import get_option_chain_metadata

logger = get_logger(__name__)

OPTION_HORIZON_SPECS: tuple[dict[str, Any], ...] = (
    {"key": "current", "label": "現在", "target_dte": None, "min_dte": 0},
    {"key": "one_week", "label": "1週間", "target_dte": 7, "min_dte": 1},
    {"key": "one_month", "label": "1か月", "target_dte": 30, "min_dte": 1},
)

# ============================================================
# 内部ヘルパー: データ取得（1回だけ実行）
# ============================================================


def _fetch_option_data(
    ticker: str,
    *,
    allow_marketdata: bool = False,
    cache_only: bool = False,
    target_dte: int | None = None,
    min_dte: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, float, str, dict[str, Any]] | None:
    """
    オプションチェーンと現在価格を1回で取得する内部ヘルパー。

    Returns:
        (calls_df, puts_df, current_price, fetched_at, metadata) のタプル、またはNone
    """
    option_data = get_option_chain(
        ticker,
        allow_marketdata=allow_marketdata,
        cache_only=cache_only,
        target_dte=target_dte,
        min_dte=min_dte,
    )
    if option_data is None:
        return None

    calls, puts = option_data

    # DataFrameが空の場合は早期リターン
    if calls.empty or puts.empty:
        logger.warning(f"[OptionAnalyst] {ticker}: Empty option chain data")
        return None

    metadata = get_option_chain_metadata(ticker, target_dte=target_dte)
    metadata["target_dte"] = target_dte
    current_price = _option_underlying_price(calls, puts)
    if current_price is None:
        # MarketData.app以外の既存経路では従来どおりquoteを取得する。
        current_price = DataProvider.get_current_price(ticker)

    JST = timezone(timedelta(hours=9), "JST")
    now_utc = datetime.now(timezone.utc)
    now_jst = now_utc.astimezone(JST)
    now_str = now_jst.strftime("%Y/%m/%d %H:%M:%S") + " (JST)"

    if not current_price:
        return None

    return calls, puts, current_price, now_str, metadata


# ============================================================
# 個別計算関数（データを引数で受け取る版 + 後方互換のticker版）
# ============================================================


def calculate_pcr(
    ticker: str = "",
    *,
    calls: pd.DataFrame | None = None,
    puts: pd.DataFrame | None = None,
) -> dict | None:
    """
    Put/Call Ratioを計算します。

    Args:
        ticker: 銘柄コード（calls/putsが未指定の場合に使用）
        calls: コールオプションDataFrame（事前取得済みデータ）
        puts: プットオプションDataFrame（事前取得済みデータ）

    Returns:
        PCR情報の辞書
    """
    if calls is None or puts is None:
        if not ticker:
            return None
        option_data = get_option_chain(ticker)
        if option_data is None:
            return None
        calls, puts = option_data

    # Volume PCR (NaN値の安全な処理)
    call_volume = calls["volume"].fillna(0).sum() if "volume" in calls.columns else 0
    put_volume = puts["volume"].fillna(0).sum() if "volume" in puts.columns else 0
    volume_pcr = put_volume / call_volume if call_volume > 0 else 0

    # Open Interest PCR
    call_oi = (
        calls["openInterest"].fillna(0).sum() if "openInterest" in calls.columns else 0
    )
    put_oi = (
        puts["openInterest"].fillna(0).sum() if "openInterest" in puts.columns else 0
    )
    oi_pcr = put_oi / call_oi if call_oi > 0 else 0

    return {
        "ticker": ticker,
        "volume_pcr": volume_pcr,
        "oi_pcr": oi_pcr,
        "total_call_volume": call_volume,
        "total_put_volume": put_volume,
        "total_call_oi": call_oi,
        "total_put_oi": put_oi,
    }


def assess_option_data_quality(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    *,
    metadata: dict[str, Any] | None = None,
    gex: dict | None = None,
    iv: float | None = None,
    max_pain: float | None = None,
) -> dict[str, Any]:
    """Classify option-chain reliability before UI/AI consumers use values."""

    metadata = metadata or {}
    quality = str(metadata.get("data_quality") or "available")
    warnings = [str(item) for item in metadata.get("quality_warnings", []) if item]

    if metadata.get("is_stale"):
        quality = _worse_quality(quality, "stale_cache")

    missing_columns = _missing_option_columns(calls, puts)
    if missing_columns:
        quality = _worse_quality(quality, "unreliable")
        warnings.append("Missing option columns: " + ", ".join(missing_columns))

    call_volume = _column_sum(calls, "volume")
    put_volume = _column_sum(puts, "volume")
    call_oi = _column_sum(calls, "openInterest")
    put_oi = _column_sum(puts, "openInterest")

    if call_volume + put_volume <= 0:
        quality = _worse_quality(quality, "partial")
        warnings.append("Option volume is missing or zero.")

    if call_oi + put_oi <= 0:
        quality = _worse_quality(quality, "unreliable")
        warnings.append(
            "Open interest is missing or zero; Max Pain and GEX are disabled."
        )

    if _real_gamma_count(calls, puts) == 0:
        quality = _worse_quality(quality, "partial")
        warnings.append(
            "Greeks/Gamma are missing from the option provider; GEX is hidden."
        )
    elif gex and gex.get("is_estimated"):
        quality = _worse_quality(quality, "estimated")
        warnings.append("Some Gamma values were estimated; GEX reliability is limited.")
    elif gex and gex.get("is_partial"):
        quality = _worse_quality(quality, "partial")
        warnings.append(
            "Some contracts lacked direct Gamma and were excluded from GEX."
        )

    if iv is None:
        quality = _worse_quality(quality, "partial")
        warnings.append("ATM IV could not be calculated from available strikes.")

    if max_pain is None:
        quality = _worse_quality(quality, "partial")
        warnings.append("Max Pain could not be calculated from available OI/volume.")

    return {
        "data_quality": quality,
        "quality_warnings": _unique_warnings(warnings),
    }


def gamma_coverage(calls: pd.DataFrame, puts: pd.DataFrame) -> dict[str, Any]:
    """Return direct Gamma coverage for the option contracts in both chains."""

    total = int(len(calls) + len(puts))
    with_gamma = _real_gamma_count(calls, puts)
    coverage = with_gamma / total if total else 0.0
    return {
        "gamma_contracts": with_gamma,
        "total_contracts": total,
        "gamma_coverage": round(coverage, 4),
        "gamma_coverage_display": f"{coverage:.0%}",
    }


def _missing_option_columns(calls: pd.DataFrame, puts: pd.DataFrame) -> list[str]:
    required = {"strike", "volume", "openInterest", "impliedVolatility"}
    missing = []
    for side, frame in (("calls", calls), ("puts", puts)):
        for column in sorted(required - set(frame.columns)):
            missing.append(f"{side}.{column}")
    return missing


def _column_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def _real_gamma_count(calls: pd.DataFrame, puts: pd.DataFrame) -> int:
    total = 0
    for frame in (calls, puts):
        if "gamma" not in frame.columns:
            continue
        gamma = pd.to_numeric(frame["gamma"], errors="coerce")
        total += int(((gamma.notna()) & (gamma > 0)).sum())
    return total


def _worse_quality(current: str, candidate: str) -> str:
    order = {
        "available": 0,
        "partial": 1,
        "estimated": 2,
        "stale_cache": 3,
        "unreliable": 4,
        "failed": 5,
    }
    return candidate if order.get(candidate, 0) > order.get(current, 0) else current


def _unique_warnings(warnings: list[str]) -> list[str]:
    seen = set()
    result = []
    for warning in warnings:
        if warning and warning not in seen:
            result.append(warning)
            seen.add(warning)
    return result


def calculate_gex(
    ticker: str = "",
    *,
    calls: pd.DataFrame | None = None,
    puts: pd.DataFrame | None = None,
    current_price: float = 0.0,
    allow_gamma_estimation: bool = True,
) -> dict | None:
    """
    Gamma Exposure (GEX) を計算します。
    Finnhub APIから取得したGreeksを使用し、APIデータがない場合のみ推定値を使用。

    Args:
        ticker: 銘柄コード（データ未指定時に使用）
        calls: コールオプションDataFrame
        puts: プットオプションDataFrame
        current_price: 現在の株価

    Returns:
        GEX情報の辞書（ストライク別GEXとWall情報を含む）
    """
    if calls is None or puts is None or current_price == 0.0:
        if not ticker:
            return None
        fetched = _fetch_option_data(ticker)
        if fetched is None:
            return None
        calls, puts, current_price, _, _ = fetched

    total_oi = _column_sum(calls, "openInterest") + _column_sum(puts, "openInterest")
    if total_oi == 0:
        logger.warning(
            f"[OptionAnalyst] {ticker}: OpenInterest is 0. Cannot calculate GEX."
        )
        return None

    if _real_gamma_count(calls, puts) == 0:
        logger.warning(
            f"[OptionAnalyst] {ticker}: Gamma/Greeks are missing. GEX is hidden."
        )
        return None

    gex_data = []
    estimated_gamma_count = 0
    missing_gamma_count = 0

    # Callsの処理
    for _, row in calls.iterrows():
        strike = row.get("strike", 0)
        oi = row.get("openInterest", 0)
        if pd.isna(oi):
            oi = 0
        gamma = row.get("gamma", 0)

        if pd.isna(gamma) or gamma == 0:
            if not allow_gamma_estimation:
                missing_gamma_count += 1
                continue
            estimated_gamma_count += 1
            moneyness = (
                abs(strike - current_price) / current_price if current_price > 0 else 1
            )
            gamma = max(0.001, 0.05 * np.exp(-5 * moneyness))

        gex = gamma * oi * 100 * current_price
        gex_data.append({"strike": strike, "gex": gex, "type": "call", "oi": oi})

    # Putsの処理
    for _, row in puts.iterrows():
        strike = row.get("strike", 0)
        oi = row.get("openInterest", 0)
        if pd.isna(oi):
            oi = 0
        gamma = row.get("gamma", 0)

        if pd.isna(gamma) or gamma == 0:
            if not allow_gamma_estimation:
                missing_gamma_count += 1
                continue
            estimated_gamma_count += 1
            moneyness = (
                abs(strike - current_price) / current_price if current_price > 0 else 1
            )
            gamma = max(0.001, 0.05 * np.exp(-5 * moneyness))

        gex = -gamma * oi * 100 * current_price
        gex_data.append({"strike": strike, "gex": gex, "type": "put", "oi": oi})

    if not gex_data:
        return None

    df = pd.DataFrame(gex_data)
    strike_gex = df.groupby("strike").agg({"gex": "sum", "oi": "sum"}).reset_index()

    positive_wall = strike_gex[strike_gex["gex"] > 0].nlargest(1, "gex")
    negative_wall = strike_gex[strike_gex["gex"] < 0].nsmallest(1, "gex")

    nearby_range = current_price * 0.03
    nearby_gex = strike_gex[
        (strike_gex["strike"] >= current_price - nearby_range)
        & (strike_gex["strike"] <= current_price + nearby_range)
    ]["gex"].sum()

    return {
        "ticker": ticker,
        "current_price": current_price,
        "strike_gex": strike_gex.to_dict("records"),
        "positive_wall": positive_wall.iloc[0].to_dict()
        if len(positive_wall) > 0
        else None,
        "negative_wall": negative_wall.iloc[0].to_dict()
        if len(negative_wall) > 0
        else None,
        "nearby_net_gex": nearby_gex,
        "total_gex": strike_gex["gex"].sum(),
        "is_estimated": estimated_gamma_count > 0,
        "estimated_gamma_count": estimated_gamma_count,
        "is_partial": missing_gamma_count > 0,
        "missing_gamma_count": missing_gamma_count,
    }


def calculate_max_pain(
    ticker: str = "",
    *,
    calls: pd.DataFrame | None = None,
    puts: pd.DataFrame | None = None,
) -> float | None:
    """Max Pain (最もオプション価値が失効するストライク価格) を計算"""
    if calls is None or puts is None:
        if not ticker:
            return None
        option_data = get_option_chain(ticker)
        if option_data is None:
            return None
        calls, puts = option_data

    if "strike" not in calls or "strike" not in puts:
        return None

    # 建玉データがない場合のフォールバック（週末などのyfinance不具合対策）
    call_oi = calls["openInterest"].fillna(0).sum() if "openInterest" in calls else 0
    put_oi = puts["openInterest"].fillna(0).sum() if "openInterest" in puts else 0
    total_oi = call_oi + put_oi
    use_vol = total_oi == 0
    total_vol = 0
    if use_vol and "volume" in calls.columns and "volume" in puts.columns:
        total_vol = calls["volume"].fillna(0).sum() + puts["volume"].fillna(0).sum()
        if total_vol > 0:
            logger.warning(
                f"[OptionAnalyst] {ticker}: OpenInterest is 0. Falling back to Volume for Max Pain."
            )

    if total_oi == 0 and total_vol == 0:
        logger.warning(
            f"[OptionAnalyst] {ticker}: No valid OI or Volume data. Cannot calculate Max Pain."
        )
        return None

    weight_col = "volume" if use_vol else "openInterest"

    # NaNを0で埋めて計算可能な状態にする
    calls_clean = calls.copy()
    puts_clean = puts.copy()
    if weight_col in calls_clean.columns:
        calls_clean[weight_col] = calls_clean[weight_col].fillna(0)
    else:
        calls_clean[weight_col] = 0

    if weight_col in puts_clean.columns:
        puts_clean[weight_col] = puts_clean[weight_col].fillna(0)
    else:
        puts_clean[weight_col] = 0

    strikes = sorted(
        set(calls_clean["strike"].tolist() + puts_clean["strike"].tolist())
    )
    loss_data = []

    for k in strikes:
        call_loss = (
            calls_clean[calls_clean["strike"] < k]
            .apply(
                lambda r, current_k=k: (current_k - r["strike"]) * r[weight_col], axis=1
            )
            .sum()
        )
        put_loss = (
            puts_clean[puts_clean["strike"] > k]
            .apply(
                lambda r, current_k=k: (r["strike"] - current_k) * r[weight_col], axis=1
            )
            .sum()
        )
        loss_data.append({"strike": k, "loss": call_loss + put_loss})

    if not loss_data:
        return None

    df = pd.DataFrame(loss_data)

    # 全ての loss が 0 または同一値（計算不能状態）の場合は None を返す
    if df["loss"].nunique() <= 1 or df["loss"].sum() == 0:
        logger.warning(
            f"[OptionAnalyst] {ticker}: All strike losses are identical or zero. Returning None."
        )
        return None

    return float(df.loc[df["loss"].idxmin()]["strike"])


def calculate_atm_iv(
    ticker: str = "",
    *,
    calls: pd.DataFrame | None = None,
    puts: pd.DataFrame | None = None,
    current_price: float = 0.0,
) -> float | None:
    """ATM (At The Money) の平均IVを計算"""
    if calls is None or puts is None or current_price == 0.0:
        if not ticker:
            return None
        fetched = _fetch_option_data(ticker)
        if fetched is None:
            return None
        calls, puts, current_price, _, _ = fetched

    if "strike" not in calls or "strike" not in puts:
        return None
    if "impliedVolatility" not in calls or "impliedVolatility" not in puts:
        return None

    nearby_calls = calls[
        (calls["strike"] >= current_price * 0.98)
        & (calls["strike"] <= current_price * 1.02)
    ]
    nearby_puts = puts[
        (puts["strike"] >= current_price * 0.98)
        & (puts["strike"] <= current_price * 1.02)
    ]

    ivs = (
        nearby_calls["impliedVolatility"].tolist()
        + nearby_puts["impliedVolatility"].tolist()
    )
    valid_ivs = []
    for iv in ivs:
        if iv is None or iv == 0:
            continue
        # Finnhubは百分率(例: 15.56)、yfinanceは小数(例: 0.1556)で返す
        if iv > 2:
            iv = iv / 100.0
        if 0 < iv < 2:
            valid_ivs.append(iv)

    if not valid_ivs:
        return None
    return sum(valid_ivs) / len(valid_ivs)


def calculate_skew(
    ticker: str = "",
    *,
    calls: pd.DataFrame | None = None,
    puts: pd.DataFrame | None = None,
    current_price: float = 0.0,
    source: str = "",
    provider_active: bool | None = None,
) -> float | None:
    """
    既存互換の数値スキューを返します。

    正本は流動性を確認した25デルタ・リスクリバーサルで、取得できない
    場合だけ従来の10% OTM値を表示専用proxyとして返します。利用側は
    ``calculate_skew_detail`` のstatus/methodを確認して判断へ使います。
    """
    detail = calculate_skew_detail(
        ticker,
        calls=calls,
        puts=puts,
        current_price=current_price,
        source=source,
        provider_active=provider_active,
    )
    return _float_or_none(detail.get("value"))


def calculate_skew_detail(
    ticker: str = "",
    *,
    calls: pd.DataFrame | None = None,
    puts: pd.DataFrame | None = None,
    current_price: float = 0.0,
    source: str = "",
    provider_active: bool | None = None,
) -> dict[str, Any]:
    """Return a provenance-aware put-minus-call IV skew contract."""

    if calls is None or puts is None or current_price == 0.0:
        if not ticker:
            return _unavailable_skew_detail("Option chain or underlying price missing.")
        fetched = _fetch_option_data(ticker)
        if fetched is None:
            return _unavailable_skew_detail("Option chain is unavailable.")
        calls, puts, current_price, _, metadata = fetched
        source = str(metadata.get("source") or source)
        if provider_active is None:
            provider_active = bool(metadata.get("provider_active"))

    if puts.empty or calls.empty:
        return _unavailable_skew_detail("Both put and call legs are required.")
    if "strike" not in calls or "strike" not in puts:
        return _unavailable_skew_detail("Option strikes are unavailable.")
    if "impliedVolatility" not in calls or "impliedVolatility" not in puts:
        return _unavailable_skew_detail("Option implied volatility is unavailable.")

    direct_allowed = (
        not source or source.startswith("marketdata.app") or provider_active is True
    )
    direct_warnings: list[str] = []
    if direct_allowed:
        put_leg, put_warning = _select_25_delta_leg(
            puts, current_price=current_price, side="put"
        )
        call_leg, call_warning = _select_25_delta_leg(
            calls, current_price=current_price, side="call"
        )
        direct_warnings.extend(item for item in (put_warning, call_warning) if item)
        if put_leg is not None and call_leg is not None:
            return {
                "value": round(put_leg["iv"] - call_leg["iv"], 6),
                "method": "delta_25_direct",
                "status": "direct",
                "put_iv": put_leg["iv"],
                "call_iv": call_leg["iv"],
                "put_delta": -put_leg["abs_delta"],
                "call_delta": call_leg["abs_delta"],
                "put_strike": put_leg["strike"],
                "call_strike": call_leg["strike"],
                "liquidity_status": "ok",
                "warnings": _unique_warnings(direct_warnings),
            }
        direct_warnings.append(
            "Liquid 25-delta put and call legs were not both available."
        )
    else:
        direct_warnings.append(
            "Direct 25-delta skew requires MarketData.app delta and liquidity fields."
        )

    proxy = _calculate_moneyness_proxy(calls, puts, current_price)
    if proxy is None:
        return _unavailable_skew_detail(*direct_warnings)
    proxy["warnings"] = _unique_warnings(
        [
            *direct_warnings,
            "10% OTM moneyness skew is a display-only proxy and is excluded from scoring.",
        ]
    )
    return proxy


def _select_25_delta_leg(
    frame: pd.DataFrame, *, current_price: float, side: str
) -> tuple[dict[str, float] | None, str]:
    required = {
        "strike",
        "impliedVolatility",
        "delta",
        "bid",
        "ask",
        "openInterest",
        "volume",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        return None, f"25-delta {side} fields missing: {', '.join(missing)}."

    candidates: list[dict[str, float]] = []
    for _, row in frame.iterrows():
        strike = _float_or_none(row.get("strike"))
        delta = _float_or_none(row.get("delta"))
        iv = _normalized_iv(row.get("impliedVolatility"))
        bid = _float_or_none(row.get("bid"))
        ask = _float_or_none(row.get("ask"))
        oi = _float_or_none(row.get("openInterest")) or 0.0
        volume = _float_or_none(row.get("volume")) or 0.0
        if strike is None or delta is None or iv is None or bid is None or ask is None:
            continue
        is_otm = strike <= current_price if side == "put" else strike >= current_price
        correct_sign = delta < 0 if side == "put" else delta > 0
        if not is_otm or not correct_sign or bid <= 0 or ask < bid:
            continue
        quoted_mid = _float_or_none(row.get("mid"))
        mid = (
            quoted_mid if quoted_mid is not None and quoted_mid > 0 else (bid + ask) / 2
        )
        if mid <= 0 or (ask - bid) / mid > 0.5:
            continue
        if oi < 50 and volume < 10:
            continue
        candidates.append(
            {
                "iv": iv,
                "strike": strike,
                "abs_delta": abs(delta),
            }
        )

    if not candidates:
        return None, f"No liquid OTM {side} contract passed the 25-delta filters."

    candidates.sort(key=lambda item: item["abs_delta"])
    lower = [item for item in candidates if item["abs_delta"] <= 0.25]
    upper = [item for item in candidates if item["abs_delta"] >= 0.25]
    if lower and upper:
        low = lower[-1]
        high = upper[0]
        if high["abs_delta"] == low["abs_delta"]:
            return dict(low), ""
        weight = (0.25 - low["abs_delta"]) / (high["abs_delta"] - low["abs_delta"])
        return {
            "iv": round(low["iv"] + weight * (high["iv"] - low["iv"]), 6),
            "strike": round(
                low["strike"] + weight * (high["strike"] - low["strike"]), 6
            ),
            "abs_delta": 0.25,
        }, ""

    nearest = min(candidates, key=lambda item: abs(item["abs_delta"] - 0.25))
    if abs(nearest["abs_delta"] - 0.25) <= 0.05:
        return dict(
            nearest
        ), f"Nearest liquid {side} delta used; interpolation unavailable."
    return None, f"Nearest liquid {side} contract was more than 0.05 delta from 0.25."


def _calculate_moneyness_proxy(
    calls: pd.DataFrame, puts: pd.DataFrame, current_price: float
) -> dict[str, Any] | None:
    """Calculate the historical 10% OTM proxy without granting it score authority."""

    # 10% OTMのストライクを目安に
    target_put_strike = current_price * 0.90
    target_call_strike = current_price * 1.10

    valid_puts = puts.copy()
    valid_calls = calls.copy()
    valid_puts["_normalized_iv"] = valid_puts["impliedVolatility"].map(_normalized_iv)
    valid_calls["_normalized_iv"] = valid_calls["impliedVolatility"].map(_normalized_iv)
    valid_puts = valid_puts[valid_puts["_normalized_iv"].notna()]
    valid_calls = valid_calls[valid_calls["_normalized_iv"].notna()]

    if valid_puts.empty or valid_calls.empty:
        return None

    # putはstrike <= current_price のOTM
    otm_puts = valid_puts[valid_puts["strike"] <= current_price]
    if otm_puts.empty:
        return None
    otm_put = otm_puts.iloc[(otm_puts["strike"] - target_put_strike).abs().argmin()]

    # callはstrike >= current_price のOTM
    otm_calls = valid_calls[valid_calls["strike"] >= current_price]
    if otm_calls.empty:
        return None
    otm_call = otm_calls.iloc[(otm_calls["strike"] - target_call_strike).abs().argmin()]

    put_iv = float(otm_put["_normalized_iv"])
    call_iv = float(otm_call["_normalized_iv"])
    return {
        "value": round(put_iv - call_iv, 6),
        "method": "moneyness_10pct_proxy",
        "status": "proxy",
        "put_iv": put_iv,
        "call_iv": call_iv,
        "put_delta": _float_or_none(otm_put.get("delta")),
        "call_delta": _float_or_none(otm_call.get("delta")),
        "put_strike": _float_or_none(otm_put.get("strike")),
        "call_strike": _float_or_none(otm_call.get("strike")),
        "liquidity_status": _proxy_liquidity_status(otm_put, otm_call),
        "warnings": [],
    }


def _normalized_iv(value: Any) -> float | None:
    iv = _float_or_none(value)
    if iv is None:
        return None
    if iv > 2:
        iv /= 100.0
    return float(iv) if 0 < iv < 2 else None


def _proxy_liquidity_status(put: pd.Series, call: pd.Series) -> str:
    statuses = [_row_liquidity_status(put), _row_liquidity_status(call)]
    if "thin" in statuses:
        return "thin"
    if all(item == "ok" for item in statuses):
        return "ok"
    return "unknown"


def _row_liquidity_status(row: pd.Series) -> str:
    bid = _float_or_none(row.get("bid"))
    ask = _float_or_none(row.get("ask"))
    if bid is None or ask is None:
        return "unknown"
    mid = _float_or_none(row.get("mid"))
    if mid is None or mid <= 0:
        mid = (bid + ask) / 2
    oi = _float_or_none(row.get("openInterest")) or 0.0
    volume = _float_or_none(row.get("volume")) or 0.0
    if bid <= 0 or ask < bid or mid <= 0 or (ask - bid) / mid > 0.5:
        return "thin"
    return "ok" if oi >= 50 or volume >= 10 else "thin"


def _unavailable_skew_detail(*warnings: str) -> dict[str, Any]:
    return {
        "value": None,
        "method": "unavailable",
        "status": "unavailable",
        "put_iv": None,
        "call_iv": None,
        "put_delta": None,
        "call_delta": None,
        "put_strike": None,
        "call_strike": None,
        "liquidity_status": "unknown",
        "warnings": _unique_warnings([item for item in warnings if item]),
    }


def estimate_price_range(
    current_price: float, atm_iv: float, days_to_expiry: float = 30.0
) -> tuple[float, float]:
    """
    IVと期間(DTE)から1標準偏差(約68%)の予想変動レンジを算出します。

    Returns:
        (lower_bound, upper_bound)
    """
    if atm_iv is None or atm_iv <= 0:
        return current_price, current_price

    # 予想変動率 = IV * sqrt(DTE / 365)
    expected_move_pct = atm_iv * np.sqrt(max(1.0, days_to_expiry) / 365.0)

    lower_bound = current_price * (1.0 - expected_move_pct)
    upper_bound = current_price * (1.0 + expected_move_pct)

    return lower_bound, upper_bound


def _expected_move_pct(atm_iv: float | None, days_to_expiry: float) -> float | None:
    if atm_iv is None or atm_iv <= 0:
        return None
    return float(atm_iv * np.sqrt(max(1.0, days_to_expiry) / 365.0))


def _chain_dte(
    calls: pd.DataFrame, puts: pd.DataFrame, metadata: dict[str, Any]
) -> float:
    resolved = metadata.get("resolved_dte")
    if resolved is not None:
        try:
            return max(1.0, float(resolved))
        except (TypeError, ValueError):
            pass
    for frame in (calls, puts):
        if "dte" in frame.columns:
            values = pd.to_numeric(frame["dte"], errors="coerce").dropna()
            if not values.empty:
                return max(1.0, float(values.iloc[0]))
        if "expiration" in frame.columns and not frame.empty:
            exp_date_str = frame["expiration"].iloc[0]
            try:
                exp_date = datetime.strptime(str(exp_date_str), "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                return max(1.0, float((exp_date - datetime.now(timezone.utc)).days))
            except Exception:
                continue
    return 30.0


def _analyze_fetched_option_data(
    ticker: str,
    fetched: tuple[pd.DataFrame, pd.DataFrame, float, str, dict[str, Any]],
    *,
    horizon_key: str,
    horizon_label: str,
    target_dte: int | None,
) -> dict[str, Any] | None:
    calls, puts, current_price, fetched_at, metadata = fetched
    source = str(metadata.get("source") or "yfinance")
    provider_active = bool(metadata.get("provider_active")) or source.startswith(
        "marketdata.app"
    )
    gamma_info = gamma_coverage(calls, puts)

    pcr = calculate_pcr(ticker, calls=calls, puts=puts)
    gex = (
        calculate_gex(
            ticker,
            calls=calls,
            puts=puts,
            current_price=current_price,
            allow_gamma_estimation=False,
        )
        if provider_active
        else None
    )
    iv = calculate_atm_iv(ticker, calls=calls, puts=puts, current_price=current_price)
    max_pain = calculate_max_pain(ticker, calls=calls, puts=puts)
    skew_detail = calculate_skew_detail(
        ticker,
        calls=calls,
        puts=puts,
        current_price=current_price,
        source=source,
        provider_active=provider_active,
    )
    skew = _float_or_none(skew_detail.get("value"))
    quality = assess_option_data_quality(
        calls,
        puts,
        metadata=metadata,
        gex=gex,
        iv=iv,
        max_pain=max_pain,
    )
    if not provider_active:
        quality["data_quality"] = _worse_quality(quality["data_quality"], "partial")
        warning = (
            "MarketData.app direct Greeks are unavailable; GEX is hidden."
            if not metadata.get("fallback_reason")
            else str(metadata.get("fallback_reason"))
        )
        quality["quality_warnings"] = _unique_warnings(
            [*quality["quality_warnings"], warning]
        )
    if skew_detail.get("status") != "direct":
        quality["data_quality"] = _worse_quality(quality["data_quality"], "partial")
    quality["quality_warnings"] = _unique_warnings(
        [*quality["quality_warnings"], *list(skew_detail.get("warnings") or [])]
    )

    dte = _chain_dte(calls, puts, metadata)
    price_range = estimate_price_range(current_price, iv, dte) if iv else None
    expected_move_pct = _expected_move_pct(iv, dte)

    if pcr is None and gex is None and iv is None:
        return None

    if pcr and (pcr["total_call_oi"] + pcr["total_put_oi"] < 1000):
        gex = None

    sentiment = "中立"
    analysis = []

    if pcr:
        vol_pcr = pcr["volume_pcr"]
        if vol_pcr > 1.2:
            sentiment = "弱気"
            analysis.append(
                f"{horizon_label} PCR(Vol) ({vol_pcr:.2f}) が高く、プット取引活発"
            )
        elif vol_pcr < 0.7:
            sentiment = "強気"
            analysis.append(
                f"{horizon_label} PCR(Vol) ({vol_pcr:.2f}) が低く、コール取引活発"
            )
        else:
            analysis.append(f"{horizon_label} PCR(Vol) ({vol_pcr:.2f}) は中立水準")

        if gex is None:
            analysis.append("※ Greeks/OIデータ不足のためGEX分析は非表示")

    if gex:
        if gex["nearby_net_gex"] > 0:
            analysis.append(f"{horizon_label} 近傍GEX: 正 (値動き抑制)")
        else:
            analysis.append(f"{horizon_label} 近傍GEX: 負 (ボラ拡大警戒)")

        if gex["positive_wall"]:
            analysis.append(f"+Wall (${gex['positive_wall']['strike']:.0f}): 上値抵抗")
        if gex["negative_wall"]:
            analysis.append(f"-Wall (${gex['negative_wall']['strike']:.0f}): 下値支持")
        if gex.get("is_estimated"):
            analysis.append("※ 一部Gammaは推定値のためGEX信頼度は限定的")

    if iv:
        analysis.append(f"{horizon_label} ATM IV: {iv:.1%}")
        if price_range:
            lower, upper = price_range
            analysis.append(
                f"予想レンジ(1σ, {int(dte)}日): ${lower:.2f} - ${upper:.2f}"
            )

    if skew is not None:
        if skew_detail.get("status") == "direct" and skew > 0.05:
            analysis.append(
                f"{horizon_label} 25Δ IVスキュー (Put IV − Call IV): "
                f"{skew:.1%} (下方向警戒)"
            )
        elif skew_detail.get("status") == "direct" and skew < 0:
            analysis.append(
                f"{horizon_label} 25Δ IVスキュー (Put IV − Call IV): "
                f"{skew:.1%} (負値は上昇評価に未使用)"
            )
        elif skew_detail.get("status") == "direct":
            analysis.append(
                f"{horizon_label} 25Δ IVスキュー (Put IV − Call IV): "
                f"{skew:.1%} (警戒閾値未満)"
            )
        else:
            analysis.append(
                f"{horizon_label} 10% OTM IVスキュー proxy: {skew:.1%} "
                "(表示のみ・スコア未使用)"
            )
    else:
        analysis.append(f"{horizon_label} 25Δ IVスキュー: unavailable")

    if max_pain:
        analysis.append(f"{horizon_label} Max Pain: ${max_pain:.0f}")

    complete_status = _complete_status(
        provider_active=provider_active,
        gex=gex,
        quality=quality["data_quality"],
        is_stale=bool(metadata.get("is_stale", False)),
        fallback_reason=str(metadata.get("fallback_reason") or ""),
        gamma_coverage_value=float(gamma_info["gamma_coverage"]),
    )
    lower = price_range[0] if price_range else None
    upper = price_range[1] if price_range else None
    return {
        "key": horizon_key,
        "label": horizon_label,
        "target_dte": target_dte,
        "ticker": ticker,
        "current_price": current_price,
        "sentiment": sentiment,
        "pcr": pcr,
        "gex": gex,
        "iv": iv,
        "skew": skew,
        "skew_detail": skew_detail,
        "dte": dte,
        "expected_move_pct": expected_move_pct,
        "price_range": price_range,
        "price_range_lower": lower,
        "price_range_upper": upper,
        "max_pain": max_pain,
        "analysis": analysis,
        "fetched_at": fetched_at,
        "data_as_of": str(metadata.get("data_as_of") or ""),
        "data_mode": str(metadata.get("data_mode") or ""),
        "resolved_expiration": str(metadata.get("resolved_expiration") or ""),
        "resolved_dte": metadata.get("resolved_dte"),
        "expiration_policy": str(metadata.get("expiration_policy") or ""),
        "expiration_fallback_reason": str(
            metadata.get("expiration_fallback_reason") or ""
        ),
        "marketdata_options_mode": str(
            metadata.get("marketdata_options_mode") or "off"
        ),
        "credits_consumed": metadata.get("credits_consumed"),
        "credits_remaining": metadata.get("credits_remaining"),
        "shadow_source": str(metadata.get("shadow_source") or ""),
        "shadow_data_as_of": str(metadata.get("shadow_data_as_of") or ""),
        "shadow_data_mode": str(metadata.get("shadow_data_mode") or ""),
        "shadow_credits_consumed": metadata.get("shadow_credits_consumed"),
        "shadow_credits_remaining": metadata.get("shadow_credits_remaining"),
        "shadow_resolved_expiration": str(
            metadata.get("shadow_resolved_expiration") or ""
        ),
        "shadow_resolved_dte": metadata.get("shadow_resolved_dte"),
        "source": source,
        "is_stale": bool(metadata.get("is_stale", False)),
        "cache_status": metadata.get("cache_status", "live"),
        "cache_age_seconds": metadata.get("cache_age_seconds"),
        "data_quality": quality["data_quality"],
        "quality_warnings": quality["quality_warnings"],
        "provider_active": provider_active,
        "fallback_reason": str(metadata.get("fallback_reason") or ""),
        "complete_status": complete_status,
        **gamma_info,
    }


def analyze_option_horizons(
    ticker: str, *, allow_marketdata: bool = False, cache_only: bool = False
) -> list[dict[str, Any]]:
    """Analyze option-implied structure for current, one-week, and one-month horizons."""

    rows: list[dict[str, Any]] = []
    for spec in OPTION_HORIZON_SPECS:
        fetched = _fetch_option_data(
            ticker,
            allow_marketdata=allow_marketdata,
            cache_only=cache_only,
            target_dte=spec["target_dte"],
            min_dte=int(spec["min_dte"]),
        )
        if fetched is None:
            continue
        analysis = _analyze_fetched_option_data(
            ticker,
            fetched,
            horizon_key=str(spec["key"]),
            horizon_label=str(spec["label"]),
            target_dte=spec["target_dte"],
        )
        if analysis is not None:
            rows.append(analysis)
    return rows


def _build_term_structure(horizons: list[dict[str, Any]]) -> dict[str, Any]:
    lookup = {str(item.get("key")): item for item in horizons}
    current = lookup.get("current") or {}
    one_week = lookup.get("one_week") or {}
    one_month = lookup.get("one_month") or {}
    week_iv = _float_or_none(one_week.get("iv"))
    month_iv = _float_or_none(one_month.get("iv"))
    current_iv = _float_or_none(current.get("iv"))
    slope = (
        round(month_iv - week_iv, 4)
        if month_iv is not None and week_iv is not None
        else None
    )
    summary_parts = []
    if current_iv is not None:
        summary_parts.append(f"現在IV={current_iv:.1%}")
    if week_iv is not None:
        summary_parts.append(f"1W IV={week_iv:.1%}")
    if month_iv is not None:
        summary_parts.append(f"1M IV={month_iv:.1%}")
    if slope is not None:
        if slope > 0.03:
            slope_label = "先の満期ほど不確実性が高い"
        elif slope < -0.03:
            slope_label = "短期満期にストレスが集中"
        else:
            slope_label = "期間構造はおおむねフラット"
        summary_parts.append(slope_label)
    return {
        "current_iv": current_iv,
        "one_week_iv": week_iv,
        "one_month_iv": month_iv,
        "iv_slope_1w_1m": slope,
        "summary": " / ".join(summary_parts),
    }


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


# ============================================================
# 統合分析（データを1回取得し、各関数に渡す）
# ============================================================


def analyze_option_sentiment(
    ticker: str, *, allow_marketdata: bool = False, cache_only: bool = False
) -> dict | None:
    """
    オプションセンチメント分析を行います。
    option_chain と quote を1回だけ取得し、全計算に共有します。

    Args:
        ticker: 銘柄コード

    Returns:
        センチメント分析結果
    """
    horizons = analyze_option_horizons(
        ticker, allow_marketdata=allow_marketdata, cache_only=cache_only
    )
    if not horizons:
        return None

    primary = next(
        (item for item in horizons if item.get("key") == "current"), horizons[0]
    )
    term_structure = _build_term_structure(horizons)
    return {
        "ticker": ticker,
        "current_price": primary.get("current_price", 0.0),
        "sentiment": primary.get("sentiment", "中立"),
        "pcr": primary.get("pcr"),
        "gex": primary.get("gex"),
        "iv": primary.get("iv"),
        "skew": primary.get("skew"),
        "skew_detail": primary.get("skew_detail") or _unavailable_skew_detail(),
        "dte": primary.get("dte"),
        "expected_move_pct": primary.get("expected_move_pct"),
        "price_range": primary.get("price_range"),
        "max_pain": primary.get("max_pain"),
        "analysis": list(primary.get("analysis") or []),
        "horizons": horizons,
        "term_structure": term_structure,
        "fetched_at": primary.get("fetched_at", ""),
        "data_as_of": primary.get("data_as_of", ""),
        "data_mode": primary.get("data_mode", ""),
        "resolved_expiration": primary.get("resolved_expiration", ""),
        "resolved_dte": primary.get("resolved_dte"),
        "expiration_policy": primary.get("expiration_policy", ""),
        "expiration_fallback_reason": primary.get("expiration_fallback_reason", ""),
        "marketdata_options_mode": primary.get("marketdata_options_mode", "off"),
        "credits_consumed": primary.get("credits_consumed"),
        "credits_remaining": primary.get("credits_remaining"),
        "shadow_source": primary.get("shadow_source", ""),
        "shadow_data_as_of": primary.get("shadow_data_as_of", ""),
        "shadow_data_mode": primary.get("shadow_data_mode", ""),
        "shadow_credits_consumed": primary.get("shadow_credits_consumed"),
        "shadow_credits_remaining": primary.get("shadow_credits_remaining"),
        "shadow_resolved_expiration": primary.get("shadow_resolved_expiration", ""),
        "shadow_resolved_dte": primary.get("shadow_resolved_dte"),
        "source": primary.get("source", ""),
        "is_stale": any(bool(item.get("is_stale")) for item in horizons),
        "cache_status": _aggregate_cache_status(horizons),
        "cache_age_seconds": _max_cache_age_seconds(horizons),
        "data_quality": primary.get("data_quality", "unavailable"),
        "quality_warnings": _unique_warnings(
            [
                warning
                for item in horizons
                for warning in list(item.get("quality_warnings") or [])
            ]
        ),
        "provider_active": any(bool(item.get("provider_active")) for item in horizons),
        "fallback_reason": primary.get("fallback_reason", ""),
        "complete_status": primary.get("complete_status", "unavailable"),
        "gamma_contracts": primary.get("gamma_contracts", 0),
        "total_contracts": primary.get("total_contracts", 0),
        "gamma_coverage": primary.get("gamma_coverage"),
        "gamma_coverage_display": primary.get("gamma_coverage_display", ""),
    }


from src.option_market_aggregate import (  # noqa: E402, F401
    _aggregate_cache_status,
    _complete_status,
    _max_cache_age_seconds,
    _option_underlying_price,
    get_major_indices_option_status,
    get_major_indices_options,
)

import pandas as pd

from src.option_analyst import (
    calculate_skew,
    calculate_skew_detail,
    estimate_price_range,
)


def _contract(strike, iv, delta, *, bid=1.0, ask=1.2, oi=100, volume=20):
    return {
        "strike": strike,
        "impliedVolatility": iv,
        "delta": delta,
        "bid": bid,
        "ask": ask,
        "mid": (bid + ask) / 2,
        "openInterest": oi,
        "volume": volume,
    }


def test_estimate_price_range():
    # 100ドル、IV 20%、365日 -> 予想変動は 20%
    lower, upper = estimate_price_range(
        current_price=100.0, atm_iv=0.20, days_to_expiry=365.0
    )
    assert lower == 80.0
    assert upper == 120.0

    # DTEが0以下の場合でも最低1日で計算されるはず
    l2, u2 = estimate_price_range(100.0, 0.20, 0.0)
    assert round(l2, 2) == round(100 * (1 - 0.20 * (1 / 365) ** 0.5), 2)


def test_calculate_skew():
    current_price = 100.0

    # Calls: ITM(90) IV 0.2, ATM(100) IV 0.2, OTM(110) (10% OTM) IV 0.15
    calls = pd.DataFrame(
        [
            {"strike": 90, "impliedVolatility": 0.20},
            {"strike": 100, "impliedVolatility": 0.20},
            {"strike": 110, "impliedVolatility": 0.15},
        ]
    )

    # Puts: OTM(90) (10% OTM) IV 0.25, ATM(100) IV 0.2, ITM(110) IV 0.2
    puts = pd.DataFrame(
        [
            {"strike": 90, "impliedVolatility": 0.25},
            {"strike": 100, "impliedVolatility": 0.20},
            {"strike": 110, "impliedVolatility": 0.20},
        ]
    )

    skew = calculate_skew(calls=calls, puts=puts, current_price=current_price)

    # skew = OTM Put IV (0.25) - OTM Call IV (0.15) = 0.10
    assert abs(skew - 0.10) < 1e-6


def test_calculate_skew_handles_empty():
    empty_df = pd.DataFrame(columns=["strike", "impliedVolatility"])
    skew = calculate_skew(calls=empty_df, puts=empty_df, current_price=100.0)
    assert skew is None


def test_calculate_skew_handles_finnhub_scale():
    # FinnhubはIVを%で返すことがある(例: 25.0, 15.0) -> 大小補正されるか
    current_price = 100.0
    calls = pd.DataFrame([{"strike": 110, "impliedVolatility": 15.0}])
    puts = pd.DataFrame([{"strike": 90, "impliedVolatility": 25.0}])
    skew = calculate_skew(calls=calls, puts=puts, current_price=current_price)
    assert abs(skew - 0.10) < 1e-6


def test_calculate_skew_detail_interpolates_liquid_25_delta_legs():
    puts = pd.DataFrame([_contract(90, 0.30, -0.20), _contract(95, 0.34, -0.30)])
    calls = pd.DataFrame([_contract(110, 0.20, 0.20), _contract(105, 0.22, 0.30)])

    detail = calculate_skew_detail(
        calls=calls,
        puts=puts,
        current_price=100,
        source="marketdata.app",
        provider_active=True,
    )

    assert detail["method"] == "delta_25_direct"
    assert detail["status"] == "direct"
    assert detail["value"] == 0.11
    assert detail["put_iv"] == 0.32
    assert detail["call_iv"] == 0.21
    assert detail["put_delta"] == -0.25
    assert detail["call_delta"] == 0.25
    assert detail["liquidity_status"] == "ok"


def test_calculate_skew_detail_uses_nearest_delta_within_tolerance():
    puts = pd.DataFrame([_contract(93, 0.31, -0.23)])
    calls = pd.DataFrame([_contract(107, 0.21, 0.27)])

    detail = calculate_skew_detail(
        calls=calls,
        puts=puts,
        current_price=100,
        source="marketdata.app",
    )

    assert detail["status"] == "direct"
    assert detail["value"] == 0.10
    assert detail["put_delta"] == -0.23
    assert detail["call_delta"] == 0.27
    assert any("Nearest liquid" in item for item in detail["warnings"])


def test_calculate_skew_detail_normalizes_percent_iv_for_direct_legs():
    puts = pd.DataFrame([_contract(93, 31.0, -0.25)])
    calls = pd.DataFrame([_contract(107, 21.0, 0.25)])

    detail = calculate_skew_detail(
        calls=calls, puts=puts, current_price=100, source="marketdata.app"
    )

    assert detail["status"] == "direct"
    assert detail["put_iv"] == 0.31
    assert detail["call_iv"] == 0.21


def test_calculate_skew_detail_rejects_thin_legs_and_returns_proxy():
    puts = pd.DataFrame([_contract(90, 0.30, -0.25, bid=1.0, ask=2.0, oi=5, volume=1)])
    calls = pd.DataFrame([_contract(110, 0.20, 0.25, bid=1.0, ask=2.0, oi=5, volume=1)])

    detail = calculate_skew_detail(
        calls=calls, puts=puts, current_price=100, source="marketdata.app"
    )

    assert detail["method"] == "moneyness_10pct_proxy"
    assert detail["status"] == "proxy"
    assert detail["liquidity_status"] == "thin"


def test_calculate_skew_detail_falls_back_when_one_direct_leg_is_missing():
    puts = pd.DataFrame([_contract(90, 0.30, -0.25)])
    calls = pd.DataFrame([_contract(110, 0.20, 0.45)])

    detail = calculate_skew_detail(
        calls=calls, puts=puts, current_price=100, source="marketdata.app"
    )

    assert detail["status"] == "proxy"
    assert detail["value"] == 0.10


def test_calculate_skew_detail_keeps_yfinance_as_display_only_proxy():
    puts = pd.DataFrame([_contract(90, 0.30, -0.25)])
    calls = pd.DataFrame([_contract(110, 0.20, 0.25)])

    detail = calculate_skew_detail(
        calls=calls, puts=puts, current_price=100, source="yfinance"
    )

    assert detail["status"] == "proxy"
    assert detail["method"] == "moneyness_10pct_proxy"


def test_calculate_skew_detail_preserves_unavailable_instead_of_zero_fill():
    puts = pd.DataFrame([{"strike": 90, "impliedVolatility": None}])
    calls = pd.DataFrame([{"strike": 110, "impliedVolatility": None}])

    detail = calculate_skew_detail(
        calls=calls, puts=puts, current_price=100, source="marketdata.app"
    )

    assert detail["status"] == "unavailable"
    assert detail["method"] == "unavailable"
    assert detail["value"] is None

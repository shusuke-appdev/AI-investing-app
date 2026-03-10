import pandas as pd
import pytest
from src.option_analyst import calculate_skew, estimate_price_range

def test_estimate_price_range():
    # 100ドル、IV 20%、365日 -> 予想変動は 20%
    lower, upper = estimate_price_range(current_price=100.0, atm_iv=0.20, days_to_expiry=365.0)
    assert lower == 80.0
    assert upper == 120.0
    
    # DTEが0以下の場合でも最低1日で計算されるはず
    l2, u2 = estimate_price_range(100.0, 0.20, 0.0)
    assert round(l2, 2) == round(100 * (1 - 0.20 * (1/365)**0.5), 2)

def test_calculate_skew():
    current_price = 100.0
    
    # Calls: ITM(90) IV 0.2, ATM(100) IV 0.2, OTM(110) (10% OTM) IV 0.15
    calls = pd.DataFrame([
        {"strike": 90, "impliedVolatility": 0.20},
        {"strike": 100, "impliedVolatility": 0.20},
        {"strike": 110, "impliedVolatility": 0.15},
    ])
    
    # Puts: OTM(90) (10% OTM) IV 0.25, ATM(100) IV 0.2, ITM(110) IV 0.2
    puts = pd.DataFrame([
        {"strike": 90, "impliedVolatility": 0.25},
        {"strike": 100, "impliedVolatility": 0.20},
        {"strike": 110, "impliedVolatility": 0.20},
    ])
    
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

import numpy as np
import pandas as pd

from src.advisor import analysis as analysis_module
from src.advisor.base_recognition import detect_bases
from src.advisor.market_monitor import evaluate_yield_spread, track_distribution_days
from src.advisor.mode_selector import determine_analysis_mode
from src.advisor.smart_criteria import evaluate_smart_criteria


def test_mode_selector():
    # トレンドフォローモード（順張り）のテスト
    # MA200を上回り、Stage 2、RSI 50
    close_prices = pd.Series([100, 105, 110, 115, 120])
    mode_info = determine_analysis_mode(
        close_prices, stage=2, rsi=60.0, long_term_ma_deviation=0.1
    )
    assert mode_info["mode"] == "trend_following"
    assert mode_info["weights"]["trend"] == 0.40

    # ミーンリバージョンモード（逆張り）のテスト
    # 長期MAを大きく下回る、Stage 4
    mode_info_mr = determine_analysis_mode(
        close_prices, stage=4, rsi=25.0, long_term_ma_deviation=-0.3
    )
    assert mode_info_mr["mode"] == "mean_reversion"
    assert mode_info_mr["weights"]["trend"] == 0.10
    assert mode_info_mr["weights"]["mom"] == 0.40


def test_base_recognition():
    # ダミーデータ作成（長さ50以上必要）
    close = np.linspace(100, 100, 60)
    high = close * 1.05
    low = close * 0.95
    volume = np.ones(60) * 1000

    df = pd.DataFrame({"Close": close, "High": high, "Low": low, "Volume": volume})

    result = detect_bases(df)
    assert "detected" in result
    assert "patterns" in result
    assert result["breakout_count"] is None
    assert "判定不能" in result["message"]


def test_sector_performance_keeps_available_rows_and_omits_failures(monkeypatch):
    calls = []

    def fake_history(ticker, period):
        calls.append((ticker, period))
        if ticker == "XLRE":
            raise TimeoutError("provider timeout")
        return pd.DataFrame({"Close": [100.0, 105.0]})

    monkeypatch.setattr(analysis_module, "get_stock_data", fake_history)

    result = analysis_module.get_sector_performance()

    assert len(calls) == 11
    assert "Real Estate" not in result
    assert result["Technology"]["change_1m"] == 5.0


def test_market_monitor_distribution_days():
    # 売り抜け日のテスト (出来高増かつ0.2%以上下落)
    df = pd.DataFrame(
        {"Close": [100, 101, 100.5, 99.5, 100], "Volume": [1000, 900, 1100, 1200, 1000]}
    )
    # 26件以上データがないとデータ不足となるため拡張する
    df_long = pd.concat([df] * 6, ignore_index=True)
    result = track_distribution_days(df_long)

    assert "count" in result
    assert result["count"] >= 0


def test_evaluate_yield_spread():
    # SPY: 益回り 1/20 = 5%, 10年債 4.0% -> スプレッド 1.0% (債券優位)
    # NDX: 益回り 1/25 = 4%, 10年債 4.0% -> スプレッド 0.0% (債券優位)
    res = evaluate_yield_spread(4.0, {"SPY": 20.0, "NDX": 25.0})
    assert res["spreads"]["SPY"]["status"] == "債券優位 (天井警戒)"

    # SPY: 益回り 1/15 = 6.67%, 10年債 2.0% -> スプレッド 4.67% (株式優位)
    res2 = evaluate_yield_spread(2.0, {"SPY": 15.0})
    assert res2["spreads"]["SPY"]["status"] == "株式優位 (上昇余地あり)"


def test_evaluate_smart_criteria():
    info = {
        "revenueGrowth": 26.0,
        "operatingMargins": 35.0,
        "earningsGrowth": 32.0,
        "returnOnEquity": 0.28,  # 28%として処理される
    }
    res = evaluate_smart_criteria("AAPL", info, "CONFIRMED UPTREND")
    assert res["S"]["met"] is True
    assert res["M"]["met"] is True
    assert res["A"]["met"] is True
    assert res["R"]["met"] is True
    assert res["T"]["met"] is True
    assert res["all_met"] is True

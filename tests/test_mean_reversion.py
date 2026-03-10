import numpy as np
import pandas as pd

from src.advisor.mean_reversion import MeanReversionAnalyzer


def test_too_few_data():
    analyzer = MeanReversionAnalyzer("TEST")
    df = pd.DataFrame({"Close": [1] * 10})
    res = analyzer.analyze(df)
    assert "error" in res


def test_parabolic_extension():
    analyzer = MeanReversionAnalyzer("TEST")

    # 50日分のダミーデータ作成
    dates = pd.date_range("2023-01-01", periods=50)

    # ベース価格100
    close = [100.0] * 45
    # 直近5日で急激に上昇 (10%以上)
    close.extend([102.0, 105.0, 110.0, 115.0, 120.0])

    # 連続陽線のためOpenも作成
    open_price = [99.0] * 45
    open_price.extend([100.0, 103.0, 108.0, 113.0, 118.0])

    df = pd.DataFrame(
        {
            "Close": close,
            "Open": open_price,
            "High": [c + 1 for c in close],
            "Low": [o - 1 for o in open_price],
        },
        index=dates,
    )

    res = analyzer.analyze(df)

    assert "error" not in res
    assert res["ticker"] == "TEST"

    ps = res["parabolic_state"]
    assert ps["is_parabolic"]
    assert "過熱" in ps["description"] or "陽線" in ps["description"]
    assert ps["deviation_10ma"] > 0.05
    assert ps["target_reversion_price"] is not None


def test_perfect_order_rebound():
    analyzer = MeanReversionAnalyzer("TEST")

    # 50日分のダミーデータ
    dates = pd.date_range("2023-01-01", periods=50)

    close = np.linspace(80, 122, 50)
    df = pd.DataFrame(
        {"Close": close, "Open": close - 1, "High": close + 1, "Low": close - 2},
        index=dates,
    )

    res = analyzer.analyze(df)
    rs = res["rebound_state"]
    assert rs["is_perfect_order"]

    # 最後の価格を10MAに非常に近づける
    sma10 = df["Close"].rolling(10).mean().iloc[-2]  # ざっくりとした10MA
    df.iloc[-1, df.columns.get_loc("Close")] = sma10

    res2 = analyzer.analyze(df)
    rs2 = res2["rebound_state"]
    assert rs2["is_dip_buyable"]

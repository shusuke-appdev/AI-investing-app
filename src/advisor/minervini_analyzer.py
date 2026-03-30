from enum import Enum

import pandas as pd

from src.advisor.models import (
    MinerviniFtdResult,
    MinerviniStageResult,
    MinerviniVcpResult,
)


def detect_vcp(
    data: pd.DataFrame,
    min_contractions: int = 2,
    max_contractions: int = 4,
    vol_reduction_threshold: float = 0.5,
) -> tuple[bool, MinerviniVcpResult | None]:
    """
    株価データからVolatility Contraction Pattern (VCP) を検出します。
    """
    if data is None or data.empty or len(data) < 50:
        return False, None

    df = data.copy()

    # Calculate volatility and moving average volume
    df["Range"] = df["High"] - df["Low"]
    df["Volatility"] = df["Range"] / df["Close"].shift(1) * 100
    df["ATR"] = df["Range"].rolling(window=14).mean()
    df["Vol_MA"] = df["Volume"].rolling(window=10).mean()

    # 50日MAを取得してフィルターとして使用
    df["MA50"] = df["Close"].rolling(window=50).mean()

    # 最近の高値を見つける (pivot high) - order 5 to find local maxima points safely
    try:
        # Use simpler approach if scipy is not available or for robustness
        highs = df["High"].values
        pivot_idx = []
        for i in range(5, len(highs) - 5):
            if highs[i] > max(highs[i - 5 : i]) and highs[i] > max(
                highs[i + 1 : i + 6]
            ):
                pivot_idx.append(i)

        if not pivot_idx:
            # Fallback simple pivot
            pivot_idx = [df["High"].idxmax()]
            if isinstance(pivot_idx[0], (int, float)):
                pass  # it's already an index if RangeIndex
            else:
                pivot_idx = [df.index.get_loc(df["High"].idxmax())]
    except Exception:
        # Fallback simple logic
        pivot_highs = df["High"][
            (df["High"].shift(1) < df["High"]) & (df["High"].shift(-1) < df["High"])
        ]
        if pivot_highs.empty:
            return False, None
        pivot_idx = [df.index.get_loc(pivot_highs.index[-1])]

    latest_pivot_loc = pivot_idx[-1]

    # 直近の高値から十分なデータがあるか
    if len(df) - latest_pivot_loc < 5:
        return False, None

    subset = df.iloc[latest_pivot_loc:]

    # 収縮を検出
    contractions: list[dict[str, float | int | str]] = []
    current_low = subset["Low"].iloc[0]

    for i in range(1, len(subset)):
        if subset["Low"].iloc[i] > current_low:
            # 上昇開始で収縮終了かチェック
            if len(contractions) >= min_contractions:
                break
        else:
            vol = subset["Volatility"].iloc[i]
            vol_prev = contractions[-1]["vol"] if contractions else float("inf")

            # ボラ減少を確認（前の収縮に対して）
            if vol < vol_prev * vol_reduction_threshold or not contractions:
                contractions.append(
                    {
                        "index": subset.index[i],
                        "vol": vol,
                        "volume": subset["Volume"].iloc[i],
                    }
                )
            current_low = min(current_low, subset["Low"].iloc[i])

    # パターン成立条件を検証
    if min_contractions <= len(contractions) <= max_contractions:
        volumes = [c["volume"] for c in contractions]

        # 出来高が減少傾向にあるか（完全な単調減少は厳しすぎるので緩和）
        vol_decreasing = True
        for i in range(1, len(volumes)):
            if volumes[i] > volumes[i - 1] * 1.5:  # 多少のノイズは許容
                vol_decreasing = False
                break

        # 現在価格が50日移動平均線上にあるか
        current_price = df["Close"].iloc[-1]
        ma50 = df["MA50"].iloc[-1]
        price_above_ma50 = current_price >= ma50

        if vol_decreasing and price_above_ma50:
            breakout_price = df["High"].iloc[latest_pivot_loc]
            return True, {
                "contractions": len(contractions),
                "breakout_price": float(breakout_price),
                "points": contractions,
                "current_price": float(current_price),
            }

    return False, None


def analyze_stage(data: pd.DataFrame) -> MinerviniStageResult:
    """
    Minerviniのトレンドテンプレートに基づき、4つのステージを判定します。
    """
    if data is None or len(data) < 200:
        return {"stage": 0, "description": "データ不足"}

    close = data["Close"]
    ma50 = close.rolling(window=50).mean()
    ma150 = close.rolling(window=150).mean()
    ma200 = close.rolling(window=200).mean()

    # 200日MAの傾き（最低でも1ヶ月間上昇しているか）
    ma200_trend = ma200.iloc[-1] > ma200.iloc[-20]

    # 52週高値・安値
    high_52w = close.rolling(window=250).max().iloc[-1]
    low_52w = close.rolling(window=250).min().iloc[-1]

    c = close.iloc[-1]
    m50 = ma50.iloc[-1]
    m150 = ma150.iloc[-1]
    m200 = ma200.iloc[-1]

    # Stage 2 (上昇トレンド) の条件
    cond1 = c > m150 and c > m200
    cond2 = m150 > m200
    cond3 = ma200_trend
    cond4 = m50 > m150 and m50 > m200
    cond5 = c > m50
    cond6 = c > low_52w * 1.30  # 52週安値から30%以上
    cond7 = c > high_52w * 0.75  # 52週高値の25%以内にある

    if all([cond1, cond2, cond3, cond4, cond5, cond6, cond7]):
        return {"stage": 2, "description": "ステージ2 (上昇局面)"}

    # Stage 4 (下落トレンド)
    if c < m200 and m50 < m200 and not ma200_trend:
        return {"stage": 4, "description": "ステージ4 (下落局面)"}

    # Stage 1 or 3
    if c >= m200 and not ma200_trend:
        return {"stage": 1, "description": "ステージ1 (底固め局面)"}
    elif c < m50 and c < m150 and m150 > m200:
        return {"stage": 3, "description": "ステージ3 (天井圏・分布局面)"}

    return {"stage": 0, "description": "ステージ判定不能（移行期）"}


class MarketState(str, Enum):
    """市場の位相（ステート）"""

    UPTREND = "UPTREND"
    CORRECTION = "CORRECTION"
    RALLY_ATTEMPT = "RALLY_ATTEMPT"
    CONFIRMED_UPTREND = "CONFIRMED_UPTREND"


def detect_follow_through_day(data: pd.DataFrame) -> MinerviniFtdResult:
    """
    市場指数からフォロースルーデー (FTD) を検出します。
    ステートマシンアプローチを取り入れ、調整局面からの反発時のみに絞り込みます。
    """
    if data is None or len(data) < 50:
        return {"is_ftd": False, "status": "データ不足", "days_since_bottom": 0}

    df = data.copy()

    # 変化率、出来高増加、移動平均の計算
    df["Pct_Change"] = df["Close"].pct_change() * 100
    df["Vol_Increase"] = df["Volume"] > df["Volume"].shift(1)
    df["MA50"] = df["Close"].rolling(window=50).mean()
    df["MA21"] = df["Close"].rolling(window=21).mean()
    df["High50"] = df["High"].rolling(window=50).max()

    # 状態変数の初期化（過去50日時点での仮の状態）
    state = MarketState.UPTREND
    rally_day = 0
    support_low = 0.0
    days_since_bottom = 0

    # 時系列に沿って状態遷移をシミュレーションし、現在のステートを特定する
    # 少なくともMA50が計算できる50日目以降から開始
    for i in range(50, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i - 1]

        # 直近高値からの下落率（ドローダウン）
        drawdown = (current["High50"] - current["Close"]) / current["High50"] * 100

        # 調整局面の条件: 価格が50日線を下回り、かつ直近高値から5%以上下落していること（ノイズ排除）
        is_correction = current["Close"] < current["MA50"] and drawdown >= 5.0

        if state in (MarketState.UPTREND, MarketState.CONFIRMED_UPTREND):
            if is_correction:
                state = MarketState.CORRECTION

        elif state == MarketState.CORRECTION:
            # ラリー試行の開始 (Day 1): 前日の安値を下回らず、高く引けた場合
            if current["Close"] > prev["Close"] and current["Low"] >= prev["Low"]:
                state = MarketState.RALLY_ATTEMPT
                rally_day = 1
                support_low = prev["Low"]  # Day 1の安値を動的サポートとする
                days_since_bottom = 1
            # 調整を脱して直接アップトレンドへ戻るケース（V字回復）
            elif not is_correction and current["Close"] > current["MA50"]:
                state = MarketState.UPTREND

        elif state == MarketState.RALLY_ATTEMPT:
            # サポートを割ったらラリー失敗、再び調整局面へ
            if current["Low"] < support_low:
                state = MarketState.CORRECTION
                rally_day = 0
                days_since_bottom = 0
            else:
                rally_day += 1
                days_since_bottom += 1

                # FTDの判定: Day 4以降、1.5%以上の価格上昇かつ出来高増
                if (
                    rally_day >= 4
                    and current["Pct_Change"] >= 1.5
                    and current["Vol_Increase"]
                ):
                    state = MarketState.CONFIRMED_UPTREND
                # ラリーが長期間（20日以上）続き、MA50を上回っている場合は自然にアップトレンド復帰とみなす
                elif rally_day > 20 and current["Close"] > current["MA50"]:
                    state = MarketState.UPTREND

    # 最終的な状態を元に出力結果を構築
    latest = df.iloc[-1]

    if state == MarketState.CONFIRMED_UPTREND:
        return {
            "is_ftd": True,
            "status": f"強気相場入り確認（FTD点灯、ボトムから{days_since_bottom}日目）",
            "days_since_bottom": days_since_bottom,
            "pct_change": float(latest["Pct_Change"]),
        }
    elif state == MarketState.RALLY_ATTEMPT:
        return {
            "is_ftd": False,
            "status": f"ラリー試行中（Day {rally_day}）- FTDを監視中",
            "days_since_bottom": days_since_bottom,
        }
    elif state == MarketState.CORRECTION:
        return {
            "is_ftd": False,
            "status": "調整・下落局面",
            "days_since_bottom": 0,
        }
    else:
        return {
            "is_ftd": False,
            "status": "上昇トレンド継続中",
            "days_since_bottom": 0,
        }

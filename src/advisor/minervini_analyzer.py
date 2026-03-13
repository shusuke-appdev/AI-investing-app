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
    contractions = []
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


def detect_follow_through_day(data: pd.DataFrame) -> MinerviniFtdResult:
    """
    市場指数からフォロースルーデー (FTD) を検出します。
    通常、下落からの反発ラリー4日目以降に発生する、出来高増を伴う大幅高（1.5%以上）を指します。
    """
    if data is None or len(data) < 20:
        return {"is_ftd": False, "status": "データ不足"}

    df = data.copy()

    # 変化率と出来高増加の計算
    df["Pct_Change"] = df["Close"].pct_change() * 100
    df["Vol_Increase"] = df["Volume"] > df["Volume"].shift(1)

    # 直近20日の最安値（ボトム）を探す
    recent_low_idx = df["Low"].iloc[-20:].idxmin()
    recent_low_loc = df.index.get_loc(recent_low_idx)
    days_since_bottom = len(df) - 1 - recent_low_loc

    # FTDはボトムから4日目以降に発生する
    if days_since_bottom >= 4:
        # FTDの条件: 大幅な上昇(通常1.5%以上) ＆ 出来高増
        latest = df.iloc[-1]

        if latest["Pct_Change"] >= 1.5 and latest["Vol_Increase"]:
            return {
                "is_ftd": True,
                "status": f"フォロースルーデー発生確認（ボトムから{days_since_bottom}日目）",
                "days_since_bottom": days_since_bottom,
                "pct_change": latest["Pct_Change"],
            }

    # ラリー試行中かどうか（ボトムから1〜3日目）
    if 1 <= days_since_bottom <= 3:
        return {
            "is_ftd": False,
            "status": f"ラリー試行中（ボトムから{days_since_bottom}日目）- FTDを監視中",
            "days_since_bottom": days_since_bottom,
        }

    return {
        "is_ftd": False,
        "status": "下落トレンド進行中、またはすでに強気相場",
        "days_since_bottom": days_since_bottom,
    }

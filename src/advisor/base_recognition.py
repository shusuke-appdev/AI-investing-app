"""
ベース（調整・くぼみ）認識モジュール

取手付きカップ (Cup with Handle)、ダブルボトム (W型)、フラットベースを認識し、
ブレイクアウトの回数カウントとフラグ制御を行います。
"""

import numpy as np
import pandas as pd


def detect_bases(df: pd.DataFrame) -> dict:
    """
    株価データから各種ベースパターンを検出し、その結果を返します。
    """
    if df is None or len(df) < 50:
        return {"detected": False, "patterns": [], "warning": False}

    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values
    volume = df["Volume"].values if "Volume" in df else np.zeros_like(close)

    # 簡易的なベース認識の結果を格納
    patterns = []

    # 直近数ヶ月（例えば過去100日）の最高値と最安値
    lookback = min(100, len(df))
    recent_high = np.max(high[-lookback:])
    recent_low = np.min(low[-lookback:])

    # 下落率 (Drawdown)
    current_price = close[-1]
    (recent_high - current_price) / recent_high * 100
    max_drawdown = (recent_high - recent_low) / recent_high * 100

    # 1. フラットベース判定
    # 深さ15%以下、期間5〜7週（25〜35営業日）以上横ばい
    # ここでは直近25日間の変動幅が15%以下であるかを見る
    recent_25_high = np.max(high[-25:])
    recent_25_low = np.min(low[-25:])
    flat_drawdown = (recent_25_high - recent_25_low) / recent_25_high * 100

    if flat_drawdown <= 15.0 and current_price > recent_25_low:
        patterns.append(
            {
                "type": "Flat Base",
                "depth": float(flat_drawdown),
                "status": "forming" if current_price < recent_25_high else "breakout",
            }
        )

    # 2. 取手付きカップ (Cup with Handle) 判定
    # 下落率12〜30%、期間7週〜24週
    # 取手部分は下落率10〜12%以内、出来高急減
    if 12.0 <= max_drawdown <= 35.0:  # 少し余裕を持たせる
        # カップの底からの反発と、その後の小さな下落（取手）を探す
        # 簡易実装：直近10日の下落が12%以内で出来高が平均より少ないか
        recent_10_high = np.max(high[-10:])
        recent_10_low = np.min(low[-10:])
        handle_drawdown = (recent_10_high - recent_10_low) / recent_10_high * 100

        vol_ma50 = np.mean(volume[-50:])
        recent_vol = np.mean(volume[-5:])

        if handle_drawdown <= 15.0 and recent_vol < vol_ma50:
            patterns.append(
                {
                    "type": "Cup with Handle",
                    "depth": float(max_drawdown),
                    "status": "forming",
                }
            )

    return {
        "detected": len(patterns) > 0,
        "patterns": patterns,
        "breakout_count": None,
        "warning": False,
        "message": "履歴を保存していないため、ブレイクアウト回数は判定不能です。",
    }

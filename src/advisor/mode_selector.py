"""
モード判定モジュール

個別銘柄の過去の値動きや現在のテクニカル状態に基づいて、
「順張りモード（Trend Following）」と「逆張りモード（Mean Reversion）」
を判定し、スコア配分の重みを決定します。
"""

import pandas as pd


def determine_analysis_mode(
    close: pd.Series, stage: int, rsi: float, long_term_ma_deviation: float
) -> dict:
    """
    株価データと各指標から分析モードを判定します。

    Args:
        close: 終値のSeries
        stage: Minerviniのステージ（1〜4、または0）
        rsi: 現在のRSI値
        long_term_ma_deviation: 200日移動平均からの乖離率（例: -0.3 なら -30%）

    Returns:
        dict: {
            "mode": "trend_following" | "mean_reversion" | "neutral",
            "weights": {"trend": float, "mom": float, "pat": float, "flow": float, "mtf": float},
            "description": str
        }
    """
    # デフォルトの重み
    weights = {
        "trend": 0.30,
        "mom": 0.20,
        "pat": 0.20,
        "flow": 0.20,
        "mtf": 0.10,
    }
    mode = "neutral"
    description = "明確なトレンド・過熱感がなく、標準的な分析を適用"

    # 逆張りモードの判定基準:
    # 長期MAから大きく下方乖離（例: -15%以上）しているか、または強烈な売られすぎ（RSI < 25）
    # かつ ステージ2以外（主にステージ4やステージ1への移行期）
    if (long_term_ma_deviation < -0.15 or rsi < 25) and stage != 2:
        mode = "mean_reversion"
        description = "長期MAからの下方乖離や売られすぎを検知。【逆張りモード】を適用し、モメンタムとパターンのウェイトを引き上げます。"
        weights = {
            "trend": 0.10,  # トレンドは下落しているので重要度を下げる
            "mom": 0.40,    # 反発モメンタムを重視
            "pat": 0.30,    # ボトム形成パターンを重視
            "flow": 0.10,
            "mtf": 0.10,
        }

    # 順張りモードの判定基準:
    # ステージ2（上昇トレンド）にあり、長期MAより上にある場合
    elif stage == 2 and long_term_ma_deviation > 0:
        mode = "trend_following"
        description = "ステージ2の上昇トレンドを検知。【順張りモード】を適用し、トレンドと資金流入（Flow）のウェイトを引き上げます。"
        weights = {
            "trend": 0.40,  # トレンドの継続性を重視
            "mom": 0.10,
            "pat": 0.20,
            "flow": 0.20,   # 機関投資家の資金流入を重視
            "mtf": 0.10,
        }

    return {
        "mode": mode,
        "weights": weights,
        "description": description
    }

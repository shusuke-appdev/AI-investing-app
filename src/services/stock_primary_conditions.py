"""Price and growth evidence, independent of reference scores and market options."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from src.advisor.minervini_analyzer import analyze_stage, detect_vcp
from src.advisor.price_action_metrics import (
    normalize_price_frame,
    recent_pivot,
    relative_returns,
    relative_volume,
    volume_contraction,
)


def build_primary_conditions(
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    info: dict[str, Any],
    setup: dict[str, Any],
) -> dict[str, Any]:
    """Use only explicit price, volume, profile and daily setup inputs."""
    frame = normalize_price_frame(prices)
    market = normalize_price_frame(benchmark)
    rows: list[dict[str, str]] = []

    def row(label: str, passed: bool | None, value: str, reason: str) -> None:
        status = "unknown" if passed is None else "pass" if passed else "fail"
        rows.append(
            {
                "label": label,
                "status": status,
                "status_label": {
                    "pass": "成立",
                    "fail": "未成立",
                    "unknown": "判定不能",
                }[status],
                "value": value,
                "reason": reason,
            }
        )

    if len(frame) < 200:
        row("Stage 2", None, "履歴不足", "200営業日以上の株価履歴が必要です。")
    else:
        stage = analyze_stage(frame)
        for item in stage.get("conditions", []):
            status = item.get("status")
            if item.get("key") == "ma200_rising" and len(frame) < 220:
                status = "unknown"
            if (
                item.get("key") in {"above_52w_low", "near_52w_high"}
                and len(frame) < 252
            ):
                status = "unknown"
            row(
                str(item.get("label", "Stage 2")),
                True if status == "pass" else False if status == "fail" else None,
                str(item.get("value", "判定不能")),
                str(item.get("rationale", "")),
            )

    returns = (
        relative_returns(frame["Close"], market["Close"])
        if not frame.empty and not market.empty
        else {}
    )
    rs20, rs63 = _number(returns.get("20d")), _number(returns.get("63d"))
    row(
        "市場に対する相対強度",
        None if rs20 is None or rs63 is None else rs20 > 0 and rs63 > 0,
        f"20日 {_display(rs20, '%')} / 63日 {_display(rs63, '%')}",
        "両期間で市場を上回るかを確認します。",
    )
    vcp = detect_vcp(frame)[0] if len(frame) >= 50 else None
    row(
        "VCP",
        vcp,
        "検出" if vcp else "未検出" if vcp is False else "履歴不足",
        "既存のVCP検出を使用。パターン成立や将来の上昇を保証しません。",
    )
    volume = frame["Volume"] if not frame.empty else pd.Series(dtype=float)
    contraction = (
        volume_contraction(volume)
        if len(volume) >= 50 and volume.iloc[-50:-10].mean() > 0
        else None
    )
    row(
        "出来高収縮",
        contraction,
        "収縮" if contraction else "未収縮" if contraction is False else "判定不能",
        "直近10日の平均出来高が、その前40日の80%以下。",
    )
    rvol = relative_volume(volume) if len(volume) >= 51 else None
    row(
        "出来高増加",
        None if rvol is None else rvol >= 1.5,
        _display(rvol, "x"),
        "直前50日の平均に対して1.5倍以上。",
    )
    pivot = recent_pivot(frame["High"]) if len(frame) >= 50 else None
    current = _number(frame["Close"].iloc[-1]) if not frame.empty else None
    distance = (current / pivot - 1) * 100 if current is not None and pivot else None
    row(
        "ピボットとの距離",
        None,
        _display(distance, "%"),
        "直近50日高値との距離。日足Entry条件と併せて確認します。",
    )
    if distance is not None:
        rows[-1]["status"] = "reference"
        rows[-1]["status_label"] = "参考値"
    for key, label in (
        ("revenue_growth", "売上成長率"),
        ("earnings_growth", "利益成長率"),
    ):
        value = _number(info.get(key))
        row(
            label,
            None if value is None else value > 0,
            _display(value * 100 if value is not None else None, "%"),
            "取得元の成長率が正かを表示。期間・算出方法は企業データに依存し、独自の合格点は設けません。",
        )
    valid_setup = setup.get("status") in {"ready", "wait", "blocked"}
    for item in setup.get("checks", []):
        if item.get("key") not in {"ma50_extension", "breakout", "ma200_trend"}:
            continue
        status = item.get("status")
        row(
            str(item.get("label", "Entry条件")),
            True
            if valid_setup and status == "pass"
            else False
            if valid_setup and status == "fail"
            else None,
            str(item.get("value_display", "判定不能")),
            str(item.get("rationale", "")),
        )
    if not valid_setup:
        row(
            "日足Entry条件",
            None,
            "履歴・比較データ不足",
            "日足のEntry判定に必要なデータを確認してください。",
        )
    atr = _number(setup.get("atr")) if valid_setup else None
    stop = (
        current - atr * 2
        if current is not None and atr is not None and atr > 0
        else None
    )
    return {
        "conditions": rows,
        "as_of": str(frame.index[-1]) if not frame.empty else "不明",
        "benchmark_as_of": str(market.index[-1]) if not market.empty else "不明",
        "stop_reference": _display(stop),
        "invalidation": "200日線の下降、50日線から4ATR超の拡張、ブレイク失敗を確認。損切り参考値は現在値−2ATRで、注文指示ではありません。",
    }


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _display(value: float | None, suffix: str = "") -> str:
    return "判定不能" if value is None else f"{value:.2f}{suffix}"

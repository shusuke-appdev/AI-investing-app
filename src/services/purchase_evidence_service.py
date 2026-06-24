"""Confluence score for technical, adaptive fundamental, and theme evidence."""

from __future__ import annotations

from typing import Any


def evaluate_purchase_evidence(
    *,
    technical: dict[str, Any] | None,
    trade_setup: dict[str, Any] | None,
    fundamental_profile: dict[str, Any] | None,
    sector_theme: dict[str, Any] | None,
    probabilistic_signal: dict[str, Any] | None,
    fomo_regime: dict[str, Any] | None,
) -> dict[str, Any]:
    """Combine both evidence sides with a harmonic mean and explicit caps."""

    technical = technical or {}
    trade_setup = trade_setup or {}
    fundamental_profile = fundamental_profile or {}
    sector_theme = sector_theme or {}
    probabilistic_signal = probabilistic_signal or {}
    fomo_regime = fomo_regime or {}

    technical_score = _score(technical.get("overall_score"))
    entry_score = _score(trade_setup.get("score"))
    fundamental_score = _score(fundamental_profile.get("score"))
    theme_score = _theme_score(sector_theme)
    missing = []
    if technical_score is None:
        missing.append("テクニカル総合点")
    if entry_score is None:
        missing.append("Entry Framework点")
    if fundamental_score is None:
        missing.append("適応型ファンダメンタル点")
    if theme_score is None:
        missing.append("テーマ順位")
    if missing:
        return {
            "status": "unavailable",
            "score": None,
            "score_display": "算出不可",
            "label": "算出不可",
            "technical_score": None,
            "fundamental_theme_score": None,
            "missing_reasons": [f"{item}がありません。" for item in missing],
            "cap_reasons": [],
        }

    assert theme_score is not None
    technical_side = technical_score * 0.70 + entry_score * 0.30
    fundamental_theme_side = fundamental_score * 0.70 + theme_score * 0.30
    raw_score = _harmonic_mean(technical_side, fundamental_theme_side)
    cap = 100.0
    cap_reasons = []

    stage = _dict(technical.get("stage_data")).get("stage")
    action = str(probabilistic_signal.get("suggested_action") or "")
    confidence = str(probabilistic_signal.get("confidence") or "")
    risk_level = str(fomo_regime.get("risk_level") or "").lower()
    overall_signal = str(technical.get("overall_signal") or "").lower()
    if trade_setup.get("status") == "blocked":
        cap, cap_reasons = _cap(cap, 54, cap_reasons, "Entry禁止")
    if stage in (3, 4):
        cap, cap_reasons = _cap(cap, 54, cap_reasons, f"Minervini Stage {stage}")
    if (
        overall_signal in {"sell", "strong sell", "strong_sell", "bearish"}
        or technical_score < 35
    ):
        cap, cap_reasons = _cap(cap, 54, cap_reasons, "強い弱気テクニカル")
    if risk_level in {"high", "extreme"}:
        cap, cap_reasons = _cap(cap, 54, cap_reasons, "FOMO高リスク")
    if action.lower() == "avoid":
        cap, cap_reasons = _cap(cap, 54, cap_reasons, "確率シグナルAvoid")

    partial = fundamental_profile.get("status") == "partial"
    if trade_setup.get("status") != "ready":
        cap, cap_reasons = _cap(cap, 74, cap_reasons, "Entry未成立")
    if confidence.lower() == "low" or action.lower() == "watch":
        cap, cap_reasons = _cap(cap, 74, cap_reasons, "確率シグナルLow/Watch")
    if partial:
        cap, cap_reasons = _cap(cap, 74, cap_reasons, "ファンダメンタル部分評価")

    score = round(min(raw_score, cap), 1)
    label = "高" if score >= 75 else "中" if score >= 55 else "低"
    return {
        "status": "available",
        "score": score,
        "raw_score": round(raw_score, 1),
        "score_display": f"{score:.0f}/100",
        "label": label,
        "technical_score": round(technical_side, 1),
        "fundamental_theme_score": round(fundamental_theme_side, 1),
        "components": {
            "technical": technical_score,
            "entry": entry_score,
            "fundamental": fundamental_score,
            "theme": theme_score,
        },
        "cap": int(cap),
        "cap_reasons": cap_reasons,
        "missing_reasons": [],
        "method": "harmonic_mean(technical 70% + entry 30%, fundamental 70% + theme rank 30%)",
        "summary": (
            f"{label} {score:.0f}点。テクニカル側{technical_side:.0f}点、"
            f"ファンダメンタル・テーマ側{fundamental_theme_side:.0f}点。"
        ),
    }


def _theme_score(sector_theme: dict[str, Any]) -> float | None:
    rank_points = _score(sector_theme.get("best_theme_rank_points"))
    return min(100.0, rank_points * 10) if rank_points is not None else None


def _harmonic_mean(left: float, right: float) -> float:
    if left <= 0 or right <= 0:
        return 0.0
    return 2 * left * right / (left + right)


def _cap(
    current: float, requested: float, reasons: list[str], reason: str
) -> tuple[float, list[str]]:
    if reason not in reasons:
        reasons.append(reason)
    return min(current, requested), reasons


def _score(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, result))


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

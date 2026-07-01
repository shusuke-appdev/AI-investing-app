"""Trade-timing analysis built from the existing stock dashboard payload."""

from __future__ import annotations

from typing import Any


def build_stock_trade_analysis(
    stock_signal_context: dict[str, Any],
) -> dict[str, Any]:
    """Return a display-safe trade analysis without additional provider calls."""

    context = stock_signal_context or {}
    ticker = str(context.get("ticker") or "").upper()
    technical = _dict(context.get("technical_data"))
    setup = _dict(context.get("trade_setup"))
    sector_theme = _dict(context.get("sector_theme_context"))
    fomo = _dict(context.get("fomo_regime"))
    trend_follow = _dict(context.get("trend_follow_diagnostics"))
    probabilistic = _dict(context.get("probabilistic_signal"))
    stock_info = _dict(context.get("stock_info"))
    volume_profile = _dict(context.get("volume_profile"))
    purchase_evidence = _dict(context.get("purchase_evidence"))
    if not purchase_evidence:
        purchase_evidence = {
            "status": "unavailable",
            "label": "算出不可",
            "score_display": "算出不可",
            "summary": "根拠一致度は未算出です。",
        }
    purchase_evidence_health = [
        item
        for item in context.get("purchase_evidence_health", [])
        if isinstance(item, dict)
    ]
    support_zone = _dict(volume_profile.get("support_zone"))
    resistance_zone = _dict(volume_profile.get("resistance_zone"))

    current_price = _first_number(
        setup.get("current_price"),
        _dict(technical.get("stage_data")).get("current_price"),
        stock_info.get("current_price"),
    )
    support = _first_number(support_zone.get("high"), technical.get("support_price"))
    resistance = _first_number(
        resistance_zone.get("low"), technical.get("resistance_price")
    )
    ma50 = _first_number(setup.get("ma50"), technical.get("ma_50"))
    ma200 = _first_number(setup.get("ma200"), technical.get("ma_200"))
    atr = _number(setup.get("atr") or technical.get("atr"))
    atr_percent = _number(setup.get("atr_percent") or technical.get("atr_percent"))
    breakout = _first_number(
        resistance_zone.get("high"),
        setup.get("breakout_price"),
        _dict(technical.get("vcp_data")).get("breakout_price"),
        resistance,
    )
    stop_loss = _first_number(
        support_zone.get("low"),
        technical.get("stop_loss"),
        _atr_stop(current_price, atr),
    )

    stance_key = _stance_key(technical, setup, sector_theme, fomo)
    stance_label = {
        "ready": "仕掛け候補",
        "watch": "条件待ち",
        "protect": "見送り/防衛",
    }.get(stance_key, "条件待ち")
    stance_color = {
        "ready": "green",
        "watch": "orange",
        "protect": "red",
    }.get(stance_key, "orange")

    timing_rows = _timing_rows(
        setup=setup,
        technical=technical,
        sector_theme=sector_theme,
        fomo=fomo,
        trend_follow=trend_follow,
        probabilistic=probabilistic,
        current_price=current_price,
        breakout=breakout,
        support=support,
        resistance=resistance,
    )
    key_levels = _key_levels(
        current_price=current_price,
        support=support,
        resistance=resistance,
        ma50=ma50,
        ma200=ma200,
        breakout=breakout,
        stop_loss=stop_loss,
        atr_percent=atr_percent,
        technical=technical,
    )
    profile_rows = []
    if support_zone:
        profile_rows.append(
            {
                "label": "出来高支持帯",
                "value": _zone_text(support_zone),
                "note": "価格帯別出来高の現値直下の集中帯。押し目・無効化を優先評価。",
            }
        )
    if resistance_zone:
        profile_rows.append(
            {
                "label": "出来高抵抗帯",
                "value": _zone_text(resistance_zone),
                "note": "価格帯別出来高の現値直上の集中帯。ブレイク判定を優先評価。",
            }
        )
    key_levels[1:1] = profile_rows
    supply_demand = _supply_demand_rows(
        setup=setup,
        technical=technical,
        sector_theme=sector_theme,
        fomo=fomo,
        trend_follow=trend_follow,
        probabilistic=probabilistic,
    )
    invalidations = _invalidations(
        setup=setup,
        support=support,
        ma50=ma50,
        ma200=ma200,
        stop_loss=stop_loss,
        fomo=fomo,
        sector_theme=sector_theme,
    )

    return {
        "ticker": ticker,
        "stance_key": stance_key,
        "stance_label": stance_label,
        "stance_color": stance_color,
        "volume_profile_summary": str(volume_profile.get("summary") or ""),
        "purchase_evidence": purchase_evidence,
        "purchase_evidence_health": purchase_evidence_health,
        "summary": _summary(stance_key, setup, technical, sector_theme),
        "timing": _timing_plan(
            stance_key=stance_key,
            current_price=current_price,
            breakout=breakout,
            support=support,
            ma50=ma50,
            stop_loss=stop_loss,
            setup=setup,
        ),
        "key_levels": key_levels,
        "timing_checks": timing_rows,
        "supply_demand": supply_demand,
        "invalidations": invalidations,
        "risk": {
            "final_stop": _price(stop_loss),
            "atr_percent": _percent(atr_percent),
            "position_note": _position_note(current_price, stop_loss),
        },
    }


def _timing_plan(
    *,
    stance_key: str,
    current_price: float | None,
    breakout: float | None,
    support: float | None,
    ma50: float | None,
    stop_loss: float | None,
    setup: dict[str, Any],
) -> dict[str, str]:
    if stance_key == "protect":
        return {
            "primary": "新規エントリーは見送り。禁止条件の解消と支持線の再取得を待つ。",
            "pullback": "反発狙いは、50日線または直近サポート上で出来高を伴う陽線を確認してから。",
            "breakout": "ブレイク狙いは無効。先にベース再形成と相対強度の回復を確認する。",
        }

    breakout_text = _price(breakout)
    support_text = _price(support or ma50)
    stop_text = _price(stop_loss)
    if stance_key == "ready":
        primary = (
            f"{breakout_text}超えを出来高確認付きの主トリガーにし、"
            f"失敗時は{stop_text}で無効化。"
        )
    else:
        primary = (
            f"現値で追わず、{breakout_text}の明確な上抜けか"
            f"{support_text}近辺の押し目反発を待つ。"
        )
    return {
        "primary": primary,
        "pullback": f"{support_text}付近で下げ止まり、RS/RVOL改善が揃えば押し目候補。",
        "breakout": f"{breakout_text}超えとRVOL 1.5x以上が揃うまでブレイクは待機。",
    }


def _timing_rows(
    *,
    setup: dict[str, Any],
    technical: dict[str, Any],
    sector_theme: dict[str, Any],
    fomo: dict[str, Any],
    trend_follow: dict[str, Any],
    probabilistic: dict[str, Any],
    current_price: float | None,
    breakout: float | None,
    support: float | None,
    resistance: float | None,
) -> list[dict[str, str]]:
    checks = []
    for item in list(setup.get("checks") or [])[:5]:
        if not isinstance(item, dict):
            continue
        checks.append(
            {
                "label": str(item.get("label") or ""),
                "status": str(item.get("status") or "unknown"),
                "value": str(item.get("value_display") or ""),
                "rationale": str(item.get("rationale") or ""),
            }
        )

    stage = _dict(technical.get("stage_data"))
    if stage:
        checks.insert(
            0,
            {
                "label": "Minerviniステージ",
                "status": "pass" if stage.get("stage") == 2 else "fail",
                "value": str(stage.get("description") or stage.get("label") or ""),
                "rationale": "Stage 2は順張りの前提条件。Stage 1/3/4は待機または防衛寄りに扱う。",
            },
        )

    if sector_theme:
        rating = str(sector_theme.get("combined_rating") or "")
        checks.append(
            {
                "label": "セクター/テーマ",
                "status": "pass" if rating == "high" else "unknown",
                "value": str(sector_theme.get("ranking_summary") or rating or "N/A"),
                "rationale": str(sector_theme.get("rationale") or ""),
            }
        )

    risk_level = str(fomo.get("risk_level") or "")
    if risk_level:
        checks.append(
            {
                "label": "FOMO/ボラ",
                "status": "fail" if risk_level in {"high", "extreme"} else "unknown",
                "value": str(fomo.get("label") or risk_level),
                "rationale": str(
                    fomo.get("invalidation") or fomo.get("confirmation") or ""
                ),
            }
        )

    probability = _probability_text(probabilistic)
    if probability:
        checks.append(
            {
                "label": "確率シグナル",
                "status": "unknown",
                "value": probability,
                "rationale": str(probabilistic.get("rationale") or ""),
            }
        )

    if not checks:
        checks.append(
            {
                "label": "価格水準",
                "status": "unknown",
                "value": _distance_text(current_price, breakout, support, resistance),
                "rationale": "既存テクニカル水準から待機位置を確認する。",
            }
        )

    trend_summary = str(
        trend_follow.get("summary")
        or trend_follow.get("label")
        or trend_follow.get("diagnosis")
        or ""
    )
    if trend_summary:
        checks.append(
            {
                "label": "トレンド堅牢性",
                "status": "unknown",
                "value": trend_summary,
                "rationale": "トレンド継続の質を別軸で確認する。",
            }
        )

    return checks[:8]


def _key_levels(
    *,
    current_price: float | None,
    support: float | None,
    resistance: float | None,
    ma50: float | None,
    ma200: float | None,
    breakout: float | None,
    stop_loss: float | None,
    atr_percent: float | None,
    technical: dict[str, Any],
) -> list[dict[str, str]]:
    rows = [
        ("現在値", current_price, "判断の起点。現値追いよりトリガー確認を優先。"),
        ("ブレイク水準", breakout, "上抜け確認の主トリガー。"),
        ("レジスタンス", resistance, "上値抵抗。ここを明確に超えるかを確認。"),
        ("サポート", support, "押し目・無効化を分ける基準。"),
        ("50日線", ma50, "短中期トレンドの支持線。"),
        ("200日線", ma200, "長期トレンドの防衛線。"),
        ("最終ストップ", stop_loss, "想定と逆に動いた場合の撤退水準。"),
    ]
    fib = _dict(technical.get("fib_levels"))
    nearest = str(technical.get("fib_nearest_level") or "")
    if nearest and nearest in fib:
        rows.append((f"Fib {nearest}", _number(fib.get(nearest)), "最寄りのFib目安。"))
    return [
        {
            "label": label,
            "value": _price(value),
            "note": note
            if label != "最終ストップ"
            else f"{note} ATR%={_percent(atr_percent)}",
        }
        for label, value, note in rows
        if value is not None and value > 0
    ]


def _supply_demand_rows(
    *,
    setup: dict[str, Any],
    technical: dict[str, Any],
    sector_theme: dict[str, Any],
    fomo: dict[str, Any],
    trend_follow: dict[str, Any],
    probabilistic: dict[str, Any],
) -> list[dict[str, str]]:
    rows = [
        {
            "label": "RVOL",
            "value": str(setup.get("rvol_display") or "N/A"),
            "note": "直近出来高がブレイク確認に足りているか。",
        },
        {
            "label": "OBV",
            "value": str(technical.get("obv_trend") or "N/A"),
            "note": "機関投資家の蓄積proxy。",
        },
        {
            "label": "テーマフロー",
            "value": str(
                sector_theme.get("stock_flow_score_display")
                or sector_theme.get("combined_rating")
                or "N/A"
            ),
            "note": str(sector_theme.get("ranking_summary") or "テーマ資金流入proxy。"),
        },
        {
            "label": "オプションproxy",
            "value": str(
                sector_theme.get("theme_option_signal")
                or technical.get("gex_regime")
                or "N/A"
            ),
            "note": str(
                sector_theme.get("theme_option_summary")
                or "Gamma/PCRが利用可能な場合だけ補助材料にする。"
            ),
        },
    ]
    if fomo.get("label"):
        rows.append(
            {
                "label": "FOMO",
                "value": str(fomo.get("label")),
                "note": str(fomo.get("confirmation") or ""),
            }
        )
    if probabilistic.get("confidence") or probabilistic.get("label"):
        rows.append(
            {
                "label": "確率モデル",
                "value": _probability_text(probabilistic) or "N/A",
                "note": "短期需給の補助材料。単独では売買判断にしない。",
            }
        )
    if trend_follow.get("data_quality"):
        rows.append(
            {
                "label": "トレンド品質",
                "value": str(
                    _dict(trend_follow.get("data_quality")).get("status") or "N/A"
                ),
                "note": "トレンド診断のデータ品質。",
            }
        )
    return rows


def _invalidations(
    *,
    setup: dict[str, Any],
    support: float | None,
    ma50: float | None,
    ma200: float | None,
    stop_loss: float | None,
    fomo: dict[str, Any],
    sector_theme: dict[str, Any],
) -> list[dict[str, str]]:
    items = []
    for reason in setup.get("blocked_reasons") or []:
        items.append({"label": "禁止条件", "value": str(reason)})
    if stop_loss and stop_loss > 0:
        items.append({"label": "最終ストップ", "value": f"{_price(stop_loss)}割れ"})
    if support and support > 0:
        items.append({"label": "支持線", "value": f"{_price(support)}を終値で割る"})
    if ma50 and ma50 > 0:
        items.append(
            {"label": "短中期トレンド", "value": f"50日線 {_price(ma50)} の回復に失敗"}
        )
    if ma200 and ma200 > 0:
        items.append(
            {"label": "長期トレンド", "value": f"200日線 {_price(ma200)} を明確に割る"}
        )
    if fomo.get("invalidation"):
        items.append({"label": "FOMO/ボラ", "value": str(fomo.get("invalidation"))})
    proxy = str(sector_theme.get("proxy_ticker") or "")
    if proxy:
        items.append(
            {
                "label": "テーマ無効化",
                "value": f"{proxy}の50日線割れ、またはランキング低下",
            }
        )
    return items[:8]


def _stance_key(
    technical: dict[str, Any],
    setup: dict[str, Any],
    sector_theme: dict[str, Any],
    fomo: dict[str, Any],
) -> str:
    if setup.get("status") == "blocked":
        return "protect"
    stage = _dict(technical.get("stage_data")).get("stage")
    if stage in (3, 4):
        return "protect"
    risk_level = str(fomo.get("risk_level") or "")
    if risk_level in {"extreme", "high"} and setup.get("status") != "ready":
        return "protect"
    score = _number(technical.get("overall_score")) or 0.0
    sector_rating = str(sector_theme.get("combined_rating") or "")
    if setup.get("status") == "ready" and score >= 60:
        return "ready"
    if stage == 2 and score >= 55 and sector_rating in {"high", "conditional", ""}:
        return "watch"
    return "watch"


def _summary(
    stance_key: str,
    setup: dict[str, Any],
    technical: dict[str, Any],
    sector_theme: dict[str, Any],
) -> str:
    stage_desc = str(_dict(technical.get("stage_data")).get("description") or "")
    setup_summary = str(setup.get("summary") or "")
    sector_summary = str(sector_theme.get("ranking_summary") or "")
    if stance_key == "ready":
        lead = "日足Entry品質は仕掛け候補です。"
    elif stance_key == "protect":
        lead = "現時点は新規エントリーを抑える局面です。"
    else:
        lead = "現時点は条件待ちです。"
    parts = [lead, setup_summary, stage_desc, sector_summary]
    return " ".join(part for part in parts if part).strip()


def _position_note(current_price: float | None, stop_loss: float | None) -> str:
    if not current_price or not stop_loss or current_price <= stop_loss:
        return "ポジションサイズはATRと最終ストップが明確な場合だけ計算してください。"
    risk = (current_price - stop_loss) / current_price * 100
    return f"現値から最終ストップまで約{risk:.1f}%。1回の損失許容額から株数を逆算。"


def _probability_text(probabilistic: dict[str, Any]) -> str:
    label = str(probabilistic.get("label") or probabilistic.get("signal") or "")
    probability = _number(
        probabilistic.get("probability")
        or probabilistic.get("up_probability")
        or probabilistic.get("score")
    )
    confidence = str(probabilistic.get("confidence") or "")
    parts = []
    if label:
        parts.append(label)
    if probability is not None:
        parts.append(f"{probability:.1f}" if probability > 1 else f"{probability:.0%}")
    if confidence:
        parts.append(f"信頼度 {confidence}")
    return " / ".join(parts)


def _distance_text(
    current_price: float | None,
    breakout: float | None,
    support: float | None,
    resistance: float | None,
) -> str:
    parts = []
    if current_price and breakout:
        parts.append(f"ブレイクまで{(breakout / current_price - 1) * 100:+.1f}%")
    if current_price and support:
        parts.append(f"サポートまで{(support / current_price - 1) * 100:+.1f}%")
    if current_price and resistance:
        parts.append(f"抵抗まで{(resistance / current_price - 1) * 100:+.1f}%")
    return " / ".join(parts) if parts else "N/A"


def _atr_stop(current_price: float | None, atr: float | None) -> float | None:
    if not current_price or not atr:
        return None
    return current_price - atr * 2


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_number(*values: Any) -> float | None:
    for value in values:
        number = _number(value)
        if number is not None and number > 0:
            return number
    return None


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _price(value: float | None) -> str:
    return "-" if value is None else f"{value:,.2f}"


def _zone_text(zone: dict[str, Any]) -> str:
    low = _number(zone.get("low"))
    high = _number(zone.get("high"))
    if low is None or high is None:
        return "N/A"
    return f"{low:,.2f}～{high:,.2f}"


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}%"

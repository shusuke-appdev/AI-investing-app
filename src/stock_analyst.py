"""
銘柄分析AIモジュール
テクニカル分析を統合した詳細な銘柄分析を提供します。
"""

from src.advisor.technical import get_technical_summary_for_ai
from src.gemini_client import generate_content


def analyze_stock(
    ticker: str,
    stock_info: dict,
    historical_data: dict | None = None,
    news_headlines: list[str] | None = None,
    probabilistic_signal: dict | None = None,
    stock_signal_context: dict | None = None,
) -> str:
    """
    銘柄の詳細分析を生成します（テクニカル分析統合版）。

    Args:
        ticker: 銘柄コード
        stock_info: yfinanceから取得した銘柄情報
        historical_data: 過去の株価データ
        news_headlines: 関連ニュースのヘッドライン

    Returns:
        分析レポート（マークダウン形式）
    """
    # 基本情報の抽出
    company_name = stock_info.get("name", ticker)
    sector = stock_info.get("sector", "不明")
    industry = stock_info.get("industry", "不明")
    market_cap = stock_info.get("market_cap", 0)
    pe_ratio = stock_info.get("pe_ratio", "N/A")
    forward_pe = stock_info.get("forward_pe", "N/A")
    price = stock_info.get("current_price", 0)
    target_price = stock_info.get("target_price", "N/A")

    context = stock_signal_context or {}
    technical_summary = _format_technical_context(context)
    if technical_summary == "":
        technical_summary = get_technical_summary_for_ai(ticker)
    if news_headlines is None:
        news_headlines = _context_news_headlines(context)
    if probabilistic_signal is None and context:
        probabilistic_signal = context.get("probabilistic_signal")
    probabilistic_context = _format_probabilistic_context(probabilistic_signal)
    trend_follow_context = _format_trend_follow_context(context)
    trade_setup_context = _format_trade_setup_context(context)
    sector_theme_context = _format_sector_theme_context(context)
    data_quality_context = _format_data_quality_context(context)
    provenance_context = _format_provenance_context(context)
    if provenance_context:
        data_quality_context = f"{data_quality_context}\n\n{provenance_context}"

    smart_criteria_summary = _format_smart_criteria_context(context)
    if smart_criteria_summary == "":
        from src.advisor.smart_criteria import evaluate_smart_criteria

        smart_res = evaluate_smart_criteria(ticker, stock_info)
        smart_criteria_summary = _format_smart_criteria(smart_res)

    # ユーザー参照知識を取得
    from src.knowledge_storage import get_knowledge_for_ai_context

    knowledge_context = get_knowledge_for_ai_context(max_items=5)

    # プロンプト構築
    from src.prompts.analysis_prompts import STOCK_ANALYSIS_PROMPT_TEMPLATE

    market_cap_b = market_cap / 1e9 if isinstance(market_cap, (int, float)) else 0

    prompt = STOCK_ANALYSIS_PROMPT_TEMPLATE.format(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        industry=industry,
        market_cap_b=market_cap_b,
        price=price,
        pe_ratio=pe_ratio,
        forward_pe=forward_pe,
        target_price=target_price,
        technical_summary=technical_summary,
        probabilistic_context=probabilistic_context,
        trend_follow_context=trend_follow_context,
        trade_setup_context=trade_setup_context,
        sector_theme_context=sector_theme_context,
        data_quality_context=data_quality_context,
        smart_criteria_summary=smart_criteria_summary,
        news_headlines=chr(10).join(news_headlines[:5])
        if news_headlines
        else "ニュースなし",
        knowledge_context=knowledge_context if knowledge_context else "特になし",
    )

    result = generate_content(prompt)
    if result:
        return result
    return "分析エラー: Gemini APIが利用できません"


def get_quick_summary(ticker: str, stock_info: dict) -> str:
    """
    銘柄のクイックサマリーを生成します。
    """
    company_name = stock_info.get("name", ticker)
    sector = stock_info.get("sector", "不明")
    market_cap = stock_info.get("market_cap", 0)
    pe_ratio = stock_info.get("pe_ratio", "N/A")

    market_cap_b = market_cap / 1e9 if isinstance(market_cap, (int, float)) else 0

    from src.prompts.analysis_prompts import QUICK_SUMMARY_PROMPT_TEMPLATE

    prompt = QUICK_SUMMARY_PROMPT_TEMPLATE.format(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        market_cap_b=market_cap_b,
        pe_ratio=pe_ratio,
    )

    result = generate_content(prompt)
    if result:
        return result.strip()
    return f"{company_name} ({ticker}) - {sector}"


# 後方互換エイリアス: stock_state.py が参照する関数名
generate_stock_analysis_report = analyze_stock


def _format_technical_context(stock_signal_context: dict | None) -> str:
    if not stock_signal_context:
        return ""
    technical = stock_signal_context.get("technical_data") or {}
    if not isinstance(technical, dict) or not technical:
        return ""

    lines = ["【テクニカル分析】"]
    field_map = [
        ("overall_signal", "総合シグナル"),
        ("overall_score", "総合スコア"),
        ("analysis_mode", "分析モード"),
        ("entry_signal", "エントリーシグナル"),
        ("rsi", "RSI"),
        ("macd_signal", "MACD"),
        ("ma_trend", "移動平均トレンド"),
        ("ma_deviation", "MA乖離"),
        ("bb_position", "ボリンジャーバンド位置"),
        ("atr", "ATR"),
        ("support_price", "サポート"),
        ("resistance_price", "レジスタンス"),
        ("contrarian_signal", "逆張り判定"),
    ]
    for key, label in field_map:
        if key in technical and technical.get(key) not in {None, ""}:
            lines.append(f"- {label}: {technical.get(key)}")
    return "\n".join(lines)


def _format_smart_criteria_context(stock_signal_context: dict | None) -> str:
    if not stock_signal_context:
        return ""
    smart = stock_signal_context.get("smart_criteria") or {}
    if not isinstance(smart, dict) or not smart:
        return ""
    return _format_smart_criteria(smart)


def _format_smart_criteria(smart_res: dict) -> str:
    smart_lines = []
    for k in ["S", "M", "A", "R", "T"]:
        v = smart_res.get(k, {})
        mark = "✅" if v.get("met") else "❌"
        smart_lines.append(f"- {k}: {mark} {v.get('desc')} (現在: {v.get('value')})")
    return "\n".join(smart_lines)


def _context_news_headlines(stock_signal_context: dict | None) -> list[str] | None:
    if not stock_signal_context:
        return None
    headlines = stock_signal_context.get("news_headlines") or []
    if not isinstance(headlines, list):
        return None
    return [str(item) for item in headlines if str(item).strip()]


def _format_probabilistic_context(signal: dict | None) -> str:
    if not signal:
        return "Probabilistic Stock Signal: unavailable."

    risk_notes = signal.get("risk_notes") or []
    positive = signal.get("why_positive") or []
    negative = signal.get("why_negative") or []
    return f"""Probabilistic Stock Signal (local calculation; do not overwrite these numbers):
- Signal Label: {signal.get("signal_label", "Unknown")}
- Expected 5D Return: {signal.get("expected_5d_return_display", "N/A")}
- Expected 20D Excess Return: {signal.get("expected_20d_excess_return_display", "N/A")}
- Probability Up: {signal.get("probability_up_display", "N/A")}
- Risk-adjusted Signal: {signal.get("risk_adjusted_signal_display", "N/A")}
- Confidence: {signal.get("confidence", "N/A")}
- Regime Fit: {signal.get("regime_fit_display", "N/A")}
- Suggested Action: {signal.get("suggested_action", "Watch")}
- Max Allocation: {signal.get("max_allocation_display", "0%")}
- Similar Samples: {signal.get("sample_size_display", "0")}
- Walk-forward: {signal.get("walk_forward_summary", "N/A")}
- Positive Factors: {"; ".join(positive) if positive else "N/A"}
- Negative Factors: {"; ".join(negative) if negative else "N/A"}
- Risk Notes: {"; ".join(risk_notes) if risk_notes else "N/A"}
"""


def _format_data_quality_context(stock_signal_context: dict | None) -> str:
    if not stock_signal_context:
        return "Data status: unavailable."

    status_items = stock_signal_context.get("data_status") or []
    if not status_items:
        return "Data status: no explicit retrieval status was provided."

    lines = []
    for item in status_items:
        if not isinstance(item, dict):
            continue
        status = "partial" if item.get("is_partial") else "ok"
        if item.get("is_stale"):
            status = "stale"
        error = f", error={item.get('error')}" if item.get("error") else ""
        lines.append(
            "- "
            f"{item.get('name', 'data')}: {status}, "
            f"source={item.get('source', 'unknown')}{error}"
        )
    return "\n".join(lines) if lines else "Data status: unavailable."


def _format_provenance_context(stock_signal_context: dict | None) -> str:
    if not stock_signal_context:
        return ""

    provenance_items = stock_signal_context.get("provenance") or []
    if not isinstance(provenance_items, list) or not provenance_items:
        return ""

    lines = ["Data provenance:"]
    for item in provenance_items[:12]:
        if not isinstance(item, dict):
            continue
        details = [
            f"kind={item.get('kind', 'unavailable')}",
            f"source={item.get('source') or 'unknown'}",
        ]
        if item.get("as_of"):
            details.append(f"as_of={item['as_of']}")
        if item.get("method"):
            details.append(f"method={item['method']}")
        if item.get("limitation"):
            details.append(f"limitation={item['limitation']}")
        details.append(f"risk={item.get('risk_level', 'low')}")
        lines.append(
            f"- {item.get('label') or item.get('item_id', 'value')}: "
            + ", ".join(details)
        )
    return "\n".join(lines) if len(lines) > 1 else ""


def _format_trend_follow_context(stock_signal_context: dict | None) -> str:
    if not stock_signal_context:
        return "Trend-Follow Diagnostics: unavailable."

    diagnostics = stock_signal_context.get("trend_follow_diagnostics") or {}
    if not isinstance(diagnostics, dict) or not diagnostics:
        return "Trend-Follow Diagnostics: unavailable."

    warnings = diagnostics.get("warnings") or []
    return f"""Trend-Follow Diagnostics (daily local calculation; diagnostic only):
- Rating: {diagnostics.get("rating_display", diagnostics.get("diagnostic_rating", "Unavailable"))}
- Current State: {diagnostics.get("current_state_display", "N/A")}
- Strategy Return: {diagnostics.get("strategy_total_return_display", "N/A")}
- Buy & Hold Return: {diagnostics.get("buy_hold_total_return_display", "N/A")}
- OOS Alpha vs Buy & Hold: {diagnostics.get("oos_alpha_display", "N/A")}
- Top 5% Trades Removed: {diagnostics.get("top5_removed_display", "N/A")}
- Random Direction Percentile: {diagnostics.get("random_percentile_display", "N/A")}
- Max Drawdown: {diagnostics.get("strategy_max_drawdown_display", "N/A")}
- Max Time Under Water: {diagnostics.get("strategy_tuw_display", "N/A")}
- Warnings: {"; ".join(str(item) for item in warnings) if warnings else "N/A"}
"""


def _format_trade_setup_context(stock_signal_context: dict | None) -> str:
    if not stock_signal_context:
        return "Entry Framework: unavailable."

    setup = stock_signal_context.get("trade_setup") or {}
    if not isinstance(setup, dict) or not setup:
        return "Entry Framework: unavailable."

    blocked = setup.get("blocked_reasons") or []
    warnings = setup.get("warnings") or []
    return f"""Entry Framework (daily-data execution-quality gate):
- Status: {setup.get("status", "insufficient_data")}
- Grade / Score: {setup.get("grade", "D")} / {setup.get("score_display", "N/A")}
- Summary: {setup.get("summary", "N/A")}
- RVOL: {setup.get("rvol_display", "N/A")}
- ADR%: {setup.get("adr_display", "N/A")}
- VARS proxy: {setup.get("vars_display", "N/A")}
- 50MA Extension: {setup.get("ma50_extension_display", "N/A")}
- Blocked Reasons: {"; ".join(str(item) for item in blocked) if blocked else "None"}
- Limitations: {"; ".join(str(item) for item in warnings) if warnings else "N/A"}
Do not override a blocked status. Treat unknown or intraday-only rules as unverified.
"""


def _format_sector_theme_context(stock_signal_context: dict | None) -> str:
    if not stock_signal_context:
        return "Sector/Theme Context: unavailable."

    context = stock_signal_context.get("sector_theme_context") or {}
    if not isinstance(context, dict) or not context:
        return "Sector/Theme Context: unavailable."

    themes = context.get("themes") or []
    diagnostics = context.get("theme_diagnostics") or []
    diagnostic_lines = []
    for item in diagnostics[:3]:
        if not isinstance(item, dict):
            continue
        diagnostic_lines.append(
            "- "
            f"{item.get('theme')}: "
            f"fundamental={float(item.get('fundamental_score', 0.0)):.2f}, "
            f"flow={float(item.get('flow_score', 0.0)):.2f}, "
            f"class={item.get('classification', 'neutral')}"
        )
    return f"""Sector/Theme Context (qualitative base layer):
- Sector: {context.get("sector", "N/A")}
- Themes: {", ".join(str(item) for item in themes) if themes else "N/A"}
- Stock Fundamental Advantage: {context.get("fundamental_advantage", False)}
- Stock Flow Advantage: {context.get("flow_advantage", False)}
- Combined Rating: {context.get("combined_rating", "unknown")}
- Rationale: {context.get("rationale", "N/A")}
{chr(10).join(diagnostic_lines) if diagnostic_lines else "- Theme diagnostics: unavailable"}
"""

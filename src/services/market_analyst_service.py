"""
Market Analyst Service Module
Handles the orchestration of AI market analysis, aggregating data from multiple sources
and generating a comprehensive market report.
"""

from src.data_provider import DataProvider
from src.log_config import get_logger
from src.market_config import get_market_config
from src.market_data import get_stock_data
from src.news_aggregator import get_aggregated_news, merge_with_finnhub_news
from src.news_analyst import generate_market_recap
from src.option_analyst import get_major_indices_options
from src.services.analysis_context import MarketContext
from src.services.market_dashboard_service import format_market_context_for_ai
from src.services.query_generator import generate_dynamic_search_queries
from src.theme_analyst import get_ranked_themes

logger = get_logger(__name__)


def _resolve_market_context(
    market_type: str,
    *,
    market_data: dict | None,
    option_analysis: list[dict] | None,
    market_context: MarketContext | dict | None,
) -> MarketContext | None:
    if isinstance(market_context, MarketContext):
        return market_context
    if isinstance(market_context, dict):
        return MarketContext.from_mapping(market_context)
    return None


def generate_market_analysis_report(
    market_type: str = "US",
    market_data: dict | None = None,
    option_analysis: list[dict] | None = None,
    gemini_configured: bool = True,
    market_context: MarketContext | dict | None = None,
    custom_focus: str | None = None,
) -> str | None:
    """
    Generates a comprehensive AI market analysis report.

    Args:
        market_type: "US" or "JP"
        market_data: Pre-fetched market data (optional)
        option_analysis: Pre-fetched option analysis (optional)
        gemini_configured: Whether Gemini API is available

    Returns:
        Markdown string of the analysis report, or None if generation failed.
    """
    if not gemini_configured:
        return "Gemini APIが利用できません。APIキーを設定してください。"

    context = _resolve_market_context(
        market_type,
        market_data=market_data,
        option_analysis=option_analysis,
        market_context=market_context,
    )
    if context is None:
        try:
            from src.services.market_dashboard_service import build_market_context

            context = build_market_context(market_type)
        except Exception as exc:
            logger.error(f"Market context build error: {exc}")
    config = get_market_config(market_type)

    # 0. Prepare Market Data (防御的コピーで呼び出し元のdictを破壊しない)
    market_data = dict(context.market_data if context else market_data or {})

    # 1. Fetch Company News from Finnhub (using configured targets)
    target_tickers = config.get("ai_analysis_targets", [])

    # Limit to top 15 to avoid rate limits/timeouts
    limit_tickers = target_tickers[:15]

    finnhub_news = []
    seen_links = set()

    for ticker in limit_tickers:
        news_items = DataProvider.get_company_news_raw(ticker)
        for item in news_items[:2]:  # Latest 2 items per ticker
            link = item.get("url")
            if link not in seen_links:
                finnhub_news.append(item)
                seen_links.add(link)

    # 2. Fetch Macro/Sector News from Google News
    keywords = config.get("news_keywords", [])

    # Generate dynamic search queries based on current market data
    dynamic_keywords = generate_dynamic_search_queries(market_data, num_queries=3)
    if dynamic_keywords:
        logger.info(f"Generated dynamic search queries: {dynamic_keywords}")

    gnews_articles = get_aggregated_news(
        categories=["BUSINESS", "TECHNOLOGY"],
        keywords=keywords,
        dynamic_keywords=dynamic_keywords,
        max_per_source=5,
        market_type=market_type,
    )

    # 3. Merge News
    all_news = merge_with_finnhub_news(gnews_articles, finnhub_news, max_total=60)

    if context:
        theme_analysis_str = _format_theme_analysis_from_context(context)
        return generate_market_recap(
            market_data,
            all_news,
            option_analysis or context.options.items,
            theme_analysis=theme_analysis_str,
            advanced_tech_analysis=format_market_context_for_ai(context),
            custom_focus=custom_focus,
        )

    weekly_performance, trend_context = _fetch_legacy_market_trend_context()
    theme_analysis_str = _fetch_legacy_theme_analysis()
    market_data["trend_1mo"] = trend_context
    market_data["weekly_performance"] = weekly_performance

    if option_analysis is None:
        try:
            option_analysis = get_major_indices_options(market_type)
        except Exception:
            option_analysis = []

    # 8.5 Advanced Technical Analysis (Breadth & Volatility)
    advanced_tech_parts = ["【高度テクニカル＆ボラティリティ分析】"]
    try:
        from src.advisor.technical_breadth import (
            calculate_mcclellan_oscillator,
            calculate_sp_oscillator,
            fetch_breadth_data,
        )
        from src.advisor.volatility import compute_volatility
        from src.advisor.volatility import get_market_data as get_vol_data
        from src.advisor.volatility_clustering import (
            generate_signals as gen_vol_signals,
        )

        # Market Microstructure (SPY Only as base context)
        try:
            from src.market_microstructure import analyze_market_structure

            micro_data = analyze_market_structure("SPY")
            if micro_data and micro_data.get("narrative_text"):
                advanced_tech_parts.append("\n" + micro_data["narrative_text"])
        except Exception as e:
            logger.error(f"Market Microstructure fetch error: {e}")

        # Breadth
        b_df = fetch_breadth_data("1mo")
        sp_osc = calculate_sp_oscillator(b_df)
        mc_osc = calculate_mcclellan_oscillator(b_df)
        advanced_tech_parts.append(
            f"- S&Pオシレーター: {sp_osc['oscillator_percent']}% ({sp_osc['signal']})"
        )
        advanced_tech_parts.append(
            f"- McClellan Oscillator: {mc_osc['mcclellan_value']} ({mc_osc['signal']})"
        )

        # Volatility Clustering (日経平均で判断)
        v_df = get_vol_data("^N225", "2y", "1d")
        v_df = compute_volatility(v_df)
        vol_sig = gen_vol_signals(v_df, current_position=False)
        advanced_tech_parts.append(
            f"- ボラティリティクラスタリング状態: {'発生中' if vol_sig['clustering_state'] else '収束'}"
        )
        advanced_tech_parts.append(
            f"- ボラティリティAI判断: {vol_sig['signal']} - {vol_sig['explanation']}"
        )
    except Exception as e:
        logger.error(f"Advanced Tech Analysis fetch error: {e}")
        advanced_tech_parts.append("- 高度テクニカルデータ取得エラー")

    # 8.6 Market Monitor (Distribution, Climax, Spread)
    try:
        from src.advisor.market_monitor import (
            detect_market_climax,
            evaluate_yield_spread,
            track_distribution_days,
        )
        from src.stock_data_provider import get_valuation_metrics

        spy_df = get_stock_data("SPY", "6mo")
        ndx_df = get_stock_data("^NDX", "6mo")

        dist_spy = track_distribution_days(spy_df)
        dist_ndx = track_distribution_days(ndx_df)

        advanced_tech_parts.append("\n【市場監視 (Distribution Day)】")
        advanced_tech_parts.append(
            f"- S&P500: {dist_spy['count']}日 ({dist_spy['level']} - {dist_spy['status']})"
        )
        advanced_tech_parts.append(
            f"- NASDAQ: {dist_ndx['count']}日 ({dist_ndx['level']} - {dist_ndx['status']})"
        )

        # PCR (pcrフィールドはdict型: {"volume_pcr": float, ...})
        opt_pcr = 0.8
        if option_analysis and len(option_analysis) > 0:
            pcr_dict = option_analysis[0].get("pcr")
            if isinstance(pcr_dict, dict):
                opt_pcr = float(pcr_dict.get("volume_pcr", 0.8))
            elif isinstance(pcr_dict, (int, float)):
                opt_pcr = float(pcr_dict)

        climax = detect_market_climax(spy_df, ndx_df, opt_pcr)
        if climax["warnings"]:
            advanced_tech_parts.append("【市場天井警戒】")
            for w in climax["warnings"]:
                advanced_tech_parts.append(f"- {w}")

        # Yield Spread
        tnx_df = get_stock_data("^TNX", "5d")
        tnx_yield = float(tnx_df["Close"].iloc[-1]) / 10.0 if not tnx_df.empty else 4.0

        spy_info = get_valuation_metrics("SPY")
        qqq_info = get_valuation_metrics("QQQ")

        # PER取得（取れなければ固定の近似値を入れる）
        spy_pe = (
            spy_info.get("pe_ratio")
            if spy_info and isinstance(spy_info.get("pe_ratio"), (int, float))
            else 22.0
        )
        ndx_pe = (
            qqq_info.get("pe_ratio")
            if qqq_info and isinstance(qqq_info.get("pe_ratio"), (int, float))
            else 30.0
        )

        index_pe = {"SPY": float(spy_pe), "NDX": float(ndx_pe)}

        spread = evaluate_yield_spread(tnx_yield, index_pe)
        advanced_tech_parts.append(
            f"\n【イールドスプレッド (10年債利回り: {tnx_yield:.2f}%)】"
        )
        for idx, res in spread["spreads"].items():
            advanced_tech_parts.append(
                f"- {idx}: 益回り {res['earnings_yield']:.2f}% (スプレッド: {res['spread']:.2f}%) -> {res['status']}"
            )

        # market_data dictに格納してフロントエンドでも使えるようにする
        market_data["market_monitor"] = {
            "distribution_days": {"SPY": dist_spy, "NDX": dist_ndx},
            "climax": climax,
            "yield_spread": spread,
        }

    except Exception as e:
        logger.error(f"Market Monitor fetch error: {e}")
        advanced_tech_parts.append("- 市場監視データ取得エラー")

    advanced_tech_analysis_str = "\n".join(advanced_tech_parts)

    # 9. Generate Recap
    recap = generate_market_recap(
        market_data,
        all_news,
        option_analysis,
        theme_analysis=theme_analysis_str,
        advanced_tech_analysis=advanced_tech_analysis_str,
        custom_focus=custom_focus,
    )

    return recap


def _format_theme_analysis_from_context(context: MarketContext) -> str:
    """Format already-computed momentum context for the AI market recap."""

    parts = ["【テーマ別トレンド分析 (資金循環)】"]
    if not context.momentum:
        parts.append("- テーマデータはMarketContext内で未取得です")
        return "\n".join(parts)

    for category, themes in context.momentum.items():
        if not themes:
            continue
        top5 = [
            f"{item.get('theme')}({float(item.get('performance', 0.0)):+.1f}%)"
            for item in themes[:5]
        ]
        bottom5 = [
            f"{item.get('theme')}({float(item.get('performance', 0.0)):+.1f}%)"
            for item in themes[-5:]
        ]
        label = str(category)
        if top5:
            parts.append(f"- {label} Top5: {', '.join(top5)}")
        if bottom5:
            parts.append(f"- {label} Bottom5: {', '.join(bottom5)}")

    return "\n".join(parts)


def _fetch_legacy_market_trend_context() -> tuple[dict, dict]:
    """Fetch legacy weekly and monthly context when MarketContext is unavailable."""

    weekly_performance = {}
    cross_asset_tickers = {
        "S&P 500": "^GSPC",
        "Nasdaq 100": "^NDX",
        "Russell 2000": "^RUT",
        "Dow Jones": "^DJI",
        "TLT (20Y Bond)": "TLT",
        "US 10Y Yield": "^TNX",
        "Gold": "GC=F",
        "WTI Oil": "CL=F",
        "Silver": "SI=F",
        "Bitcoin": "BTC-USD",
        "Ethereum": "ETH-USD",
        "DXY (Dollar)": "DX-Y.NYB",
        "USD/JPY": "JPY=X",
    }
    try:
        for name, ticker in cross_asset_tickers.items():
            df = get_stock_data(ticker, period="5d")
            if not df.empty and len(df) >= 2:
                start_price = df["Close"].iloc[0]
                end_price = df["Close"].iloc[-1]
                change_1w = (end_price - start_price) / start_price * 100
                weekly_performance[name] = f"{change_1w:+.2f}%"
    except Exception as e:
        logger.error(f"Weekly performance fetch error: {e}")

    trend_context = {}
    try:
        indices = {"S&P 500": "^GSPC", "Nasdaq 100": "^NDX", "Russell 2000": "^RUT"}
        for name, ticker in indices.items():
            df = get_stock_data(ticker, period="1mo")
            if not df.empty and len(df) > 1:
                start_price = df["Close"].iloc[0]
                end_price = df["Close"].iloc[-1]
                change_1mo = (end_price - start_price) / start_price * 100
                trend = (
                    "上昇"
                    if change_1mo > 2
                    else "下落"
                    if change_1mo < -2
                    else "横ばい"
                )
                trend_context[name] = {
                    "change_1mo": f"{change_1mo:+.2f}%",
                    "trend": trend,
                    "start_date": df.index[0].strftime("%Y-%m-%d"),
                    "end_date": df.index[-1].strftime("%Y-%m-%d"),
                }
    except Exception as e:
        logger.error(f"Trend fetch error: {e}")

    return weekly_performance, trend_context


def _fetch_legacy_theme_analysis() -> str:
    """Fetch legacy theme rankings only when no MarketContext is available."""

    theme_str_parts = ["【テーマ別トレンド分析 (資金循環)】"]
    try:
        short_themes = get_ranked_themes("5日")
        if short_themes:
            top5_s = [
                f"{t['theme']}({t['performance']:+.1f}%)" for t in short_themes[:5]
            ]
            bot5_s = [
                f"{t['theme']}({t['performance']:+.1f}%)" for t in short_themes[-5:]
            ]
            theme_str_parts.append(f"- 短期(5日) Top5: {', '.join(top5_s)}")
            theme_str_parts.append(f"- 短期(5日) Bottom5: {', '.join(bot5_s)}")

        med_themes = get_ranked_themes("1ヶ月")
        if med_themes:
            top5_m = [f"{t['theme']}({t['performance']:+.1f}%)" for t in med_themes[:5]]
            bot5_m = [
                f"{t['theme']}({t['performance']:+.1f}%)" for t in med_themes[-5:]
            ]
            if top5_m:
                theme_str_parts.append(f"- 中期(1ヶ月) Top5: {', '.join(top5_m)}")
            if bot5_m:
                theme_str_parts.append(f"- 中期(1ヶ月) Bottom5: {', '.join(bot5_m)}")
    except Exception as e:
        logger.error(f"Theme data fetch error: {e}")
        theme_str_parts.append("- テーマデータの取得に失敗しました")

    return "\n".join(theme_str_parts)

"""
ポートフォリオアドバイザーモジュール (Facade)
Backward compatibility wrapper for src.advisor package.
"""

from .advisor import (
    PortfolioHolding,
    TechnicalScore,
    analyze_market_technicals,
    analyze_portfolio,
    analyze_technical,
    calculate_ma_deviation,
    calculate_macd_signal,
    calculate_rsi,
    generate_portfolio_advice,
    get_holdings_news,
    get_macro_context,
    get_sector_performance,
    get_theme_exposure_analysis,
    parse_csv_portfolio,
)

# Re-export everything
__all__ = [
    "PortfolioHolding",
    "TechnicalScore",
    "calculate_rsi",
    "calculate_ma_deviation",
    "calculate_macd_signal",
    "analyze_technical",
    "analyze_portfolio",
    "get_macro_context",
    "analyze_market_technicals",
    "get_sector_performance",
    "get_theme_exposure_analysis",
    "get_holdings_news",
    "generate_portfolio_advice",
    "parse_csv_portfolio",
]

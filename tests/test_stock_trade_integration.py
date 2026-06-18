from pathlib import Path


def test_trading_plan_route_and_nav_are_removed_from_normal_ui():
    frontend = Path("frontend/frontend.py").read_text(encoding="utf-8")
    sidebar = Path("frontend/components/sidebar_nav.py").read_text(encoding="utf-8")
    stock = Path("frontend/pages/stock.py").read_text(encoding="utf-8")

    assert 'route="/trading-plan"' not in frontend
    assert '"/trading-plan"' not in sidebar
    assert "Trading Plan" not in sidebar
    assert "stock_trade_analysis_panel" in stock
    assert "trade_setup_panel()" not in stock

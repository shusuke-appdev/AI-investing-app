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


def test_home_and_market_watch_use_direct_navigation_and_compact_theme_summary():
    home = Path("frontend/pages/index.py").read_text(encoding="utf-8")
    sidebar = Path("frontend/components/sidebar_nav.py").read_text(encoding="utf-8")
    frontend = Path("frontend/frontend.py").read_text(encoding="utf-8")
    market_watch = Path("frontend/pages/market_watch.py").read_text(encoding="utf-8")
    theme = Path("frontend/pages/theme.py").read_text(encoding="utf-8")
    stock = Path("frontend/pages/stock.py").read_text(encoding="utf-8")

    assert "今日の調査フロー" not in home
    assert "公開モード" not in home
    assert "更新時刻・利用可能性" in home
    assert "市場を見る" in sidebar
    assert "銘柄を探す" in sidebar
    assert "トレンド/テーマ" in sidebar
    assert "上位5テーマ" in market_watch
    assert "詳細はトレンド/テーマへ" in market_watch
    assert 'href="/theme"' in market_watch
    assert 'header="データ状態"' not in market_watch
    assert (
        "ThemeState.fetch_themes"
        not in frontend.split('route="/market-watch"')[1].split("app.add_page", 1)[0]
    )
    assert "MarketState.prepare_market_watch" in frontend
    assert 'href="/stock?ticker=" + stock.ticker' in theme
    assert "トレンド/テーマ" in theme
    assert "ランキングの読み方" in theme
    assert "代表ティッカーから開始" in stock
    assert "入力例・推奨ではありません" in stock
    assert "欠損・部分取得・取得不能は推測で補完しません" in stock

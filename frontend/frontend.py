import reflex as rx

from frontend.pages.data_quality import data_quality_page
from frontend.pages.index import index
from frontend.pages.market_watch import market_watch_page
from frontend.pages.stock import stock_page
from frontend.pages.theme import theme_page
from frontend.pages.theme_leaders import theme_leaders_page
from frontend.state.data_quality_state import DataQualityState
from frontend.state.market_state import MarketState
from frontend.state.stock_state import StockState
from frontend.state.theme_state import ThemeState
from frontend.template import template
from src.deployment_guard import require_safe_deployment

require_safe_deployment()
app = rx.App()
app.add_page(
    index,
    route="/",
    title="基本市況 | AI Investing",
    on_load=MarketState.fetch_market_summary_fast,
)
app.add_page(
    stock_page,
    route="/stock",
    title="Stock Analysis | AI Investing",
    on_load=StockState.prepare_page,
)
app.add_page(
    market_watch_page,
    route="/market-watch",
    title="基本市況・詳細 | AI Investing",
    on_load=MarketState.prepare_market_watch,
)
app.add_page(
    data_quality_page,
    route="/data-quality",
    title="データ品質 | AI Investing",
    on_load=DataQualityState.refresh_provider_statuses,
)
app.add_page(
    theme_page,
    route="/theme",
    title="トレンド/テーマ | AI Investing",
    on_load=ThemeState.fetch_themes,
)
app.add_page(
    theme_leaders_page,
    route="/theme-leaders",
    title="次期リーダー候補 | AI Investing",
    on_load=ThemeState.prepare_theme_leaders,
)


@template
def retired_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("この機能は廃止しました", as_="h1"),
            rx.text("基本市況・テーマ探索・個別銘柄分析をご利用ください。"),
            rx.link("基本市況へ", href="/"),
        ),
        min_height="80vh",
    )


for retired_route in ("/portfolio", "/knowledge", "/trading-plan"):
    app.add_page(retired_page, route=retired_route, title="廃止した機能 | AI Investing")

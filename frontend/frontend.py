import reflex as rx
from frontend.pages.index import index
from frontend.state.market_state import MarketState
from frontend.pages.stock import stock_page
from frontend.pages.theme import theme_page
from frontend.state.theme_state import ThemeState
from frontend.pages.portfolio import portfolio_page
from frontend.state.portfolio_state import PortfolioState

app = rx.App(
    theme=rx.theme(
        appearance="light",
        has_background=True,
        radius="large",
        accent_color="blue",
    )
)
app.add_page(index, route="/", title="Market Intelligence | AI Investing", on_load=MarketState.fetch_market_data)
app.add_page(stock_page, route="/stock", title="Stock Analysis | AI Investing")
app.add_page(theme_page, route="/theme", title="Thematic Trends | AI Investing", on_load=ThemeState.fetch_themes)
app.add_page(portfolio_page, route="/portfolio", title="Portfolio Advisor | AI Investing", on_load=PortfolioState.load_portfolio_list)

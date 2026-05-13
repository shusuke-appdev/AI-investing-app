import reflex as rx

from frontend.pages.index import index
from frontend.pages.knowledge import knowledge as knowledge_page
from frontend.pages.portfolio import portfolio_page
from frontend.pages.stock import stock_page
from frontend.pages.theme import theme_page
from frontend.state.knowledge_state import KnowledgeState
from frontend.state.market_state import MarketState
from frontend.state.portfolio_state import PortfolioState
from frontend.state.theme_state import ThemeState

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
app.add_page(knowledge_page, route="/knowledge", title="Knowledge DB | AI Investing", on_load=KnowledgeState.load_items)

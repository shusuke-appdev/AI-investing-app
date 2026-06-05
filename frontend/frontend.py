import reflex as rx

from frontend.pages.index import index
from frontend.pages.knowledge import knowledge as knowledge_page
from frontend.pages.market_watch import market_watch_page
from frontend.pages.portfolio import portfolio_page
from frontend.pages.stock import stock_page
from frontend.state.knowledge_state import KnowledgeState
from frontend.state.market_state import MarketState
from frontend.state.portfolio_state import PortfolioState
from frontend.state.stock_state import StockState
from frontend.state.theme_state import ThemeState

app = rx.App()
app.add_page(
    index,
    route="/",
    title="Market Intelligence | AI Investing",
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
    title="市場監視 | AI Investing",
    on_load=[MarketState.fetch_market_summary_fast, ThemeState.fetch_themes],
)
app.add_page(
    portfolio_page,
    route="/portfolio",
    title="Portfolio Advisor | AI Investing",
    on_load=PortfolioState.load_portfolio_list,
)
app.add_page(
    knowledge_page,
    route="/knowledge",
    title="Knowledge DB | AI Investing",
    on_load=KnowledgeState.load_items,
)

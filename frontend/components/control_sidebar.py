import reflex as rx
from frontend.state.dashboard_state import DashboardState

def control_sidebar() -> rx.Component:
    """サイドバーのコントロールパネル"""
    return rx.vstack(
        rx.heading("設定", size="4", margin_bottom="1rem"),
        
        rx.text("ティッカーシンボル", size="2", weight="bold", color=rx.color("gray", 11)),
        rx.input(
            placeholder="例: AAPL",
            value=DashboardState.ticker,
            on_change=DashboardState.set_ticker,
            width="100%",
        ),
        
        rx.button(
            "データを取得",
            on_click=DashboardState.fetch_financial_data,
            loading=DashboardState.is_fetching,
            width="100%",
            margin_top="1rem",
            color_scheme="blue",
        ),
        
        rx.cond(
            DashboardState.error_msg,
            rx.callout(
                DashboardState.error_msg,
                icon="triangle_alert",
                color_scheme="red",
                margin_top="1rem",
            )
        ),
        
        width="250px",
        height="100vh",
        padding="1.5rem",
        border_right=f"1px solid {rx.color('gray', 3)}",
        bg=rx.color("gray", 1),
    )

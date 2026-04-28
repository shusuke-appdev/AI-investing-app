import reflex as rx
from frontend.state.dashboard_state import DashboardState
from frontend.components.navbar import navbar
from frontend.components.control_sidebar import control_sidebar
from frontend.components.metric_card import metric_card

def index() -> rx.Component:
    """メインダッシュボード画面"""
    return rx.box(
        navbar(),
        rx.flex(
            control_sidebar(),
            rx.box(
                # メインコンテンツエリア
                rx.vstack(
                    # ヘッダー部分
                    rx.hstack(
                        rx.heading(f"{DashboardState.ticker} Overview", size="7"),
                        rx.spacer(),
                        rx.badge("Active", color_scheme="green", variant="solid"),
                        width="100%",
                        align_items="center",
                        margin_bottom="2rem",
                    ),
                    
                    # メトリックカード（グリッド表示）
                    rx.grid(
                        metric_card("Current Price", "$150.25", "+1.2%"),
                        metric_card("24h Volume", "45.2M", "-5.4%"),
                        metric_card("Market Cap", "$2.8T", "+0.5%"),
                        columns="3",
                        spacing="4",
                        width="100%",
                        margin_bottom="2rem",
                    ),
                    
                    # チャートエリア
                    rx.card(
                        rx.vstack(
                            rx.heading("Price History", size="4", margin_bottom="1rem"),
                            
                            rx.cond(
                                DashboardState.is_fetching,
                                # ローディング中
                                rx.center(
                                    rx.spinner(size="3"),
                                    height="300px",
                                    width="100%",
                                ),
                                # チャート表示
                                rx.cond(
                                    DashboardState.chart_data.length() > 0,
                                    rx.recharts.area_chart(
                                        rx.recharts.area(
                                            data_key="price",
                                            stroke=rx.color("blue", 9),
                                            fill=rx.color("blue", 4),
                                        ),
                                        rx.recharts.x_axis(data_key="name"),
                                        rx.recharts.y_axis(),
                                        rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
                                        rx.recharts.tooltip(),
                                        data=DashboardState.chart_data,
                                        height=300,
                                        width="100%",
                                    ),
                                    # データなし
                                    rx.center(
                                        rx.text("データがありません。サイドバーから取得してください。", color=rx.color("gray", 11)),
                                        height="300px",
                                        width="100%",
                                    )
                                )
                            )
                        ),
                        variant="surface",
                        width="100%",
                        padding="1.5rem",
                    ),
                    
                    width="100%",
                    padding="2rem",
                    max_width="1200px",
                    margin="0 auto",
                ),
                width="100%",
                bg=rx.color("gray", 2),
                min_height="calc(100vh - 65px)", # navbarの高さを引く
                overflow_y="auto",
            ),
            direction="row",
            width="100%",
        ),
        width="100vw",
        min_height="100vh",
    )

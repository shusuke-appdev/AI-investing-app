import reflex as rx
from frontend.state.stock_state import StockState
from frontend.template import template
from frontend.components.metric_card import metric_card
from frontend.components.technical_analysis import technical_analysis

@template
def stock_page() -> rx.Component:
    """個別銘柄分析画面 (Stock)"""
    return rx.vstack(
        # ヘッダー部分
        rx.hstack(
            rx.heading("個別銘柄分析", size="7"),
            rx.spacer(),
            width="100%",
            align_items="center",
            margin_bottom="1rem",
        ),
        
        # ティッカー入力と取得ボタン
        rx.card(
            rx.hstack(
                rx.text("銘柄コード:", weight="bold"),
                rx.input(
                    placeholder="例: AAPL",
                    value=StockState.ticker,
                    on_change=StockState.set_ticker,
                    width="200px",
                ),
                rx.button(
                    "データ取得",
                    on_click=StockState.fetch_stock_data,
                    loading=StockState.is_fetching,
                    color_scheme="blue",
                ),
                align_items="center",
                width="100%",
            ),
            width="100%",
            margin_bottom="2rem"
        ),
        
        # エラーメッセージ
        rx.cond(
            StockState.error_msg != "",
            rx.callout(
                StockState.error_msg,
                icon="triangle_alert",
                color_scheme="red",
                margin_bottom="1rem",
                width="100%",
            )
        ),
        
        # ローディングスピナー（全体）
        rx.cond(
            StockState.is_fetching,
            rx.center(
                rx.spinner(size="3"),
                rx.text("企業データを取得中...", margin_top="1rem", color="gray"),
                direction="column",
                width="100%",
                height="300px",
            ),
            # データ表示領域
            rx.cond(
                StockState.info.contains("name"),
                rx.vstack(
                    # 企業名ヘッダ
                    rx.hstack(
                        rx.heading(StockState.info["name"].to_string(), size="6"),
                        rx.badge(StockState.info.get("exchange", "").to_string(), variant="surface"),
                        rx.badge(StockState.info.get("sector", "").to_string(), color_scheme="cyan"),
                        align_items="center",
                        width="100%",
                        margin_bottom="1rem"
                    ),
                    
                    # メトリックカード（主要指標）
                    rx.grid(
                        metric_card(
                            "時価総額 (Market Cap)", 
                            rx.cond(StockState.info.contains("marketCapitalization"), rx.text(StockState.info["marketCapitalization"].to_string(), " M"), "N/A"), 
                            ""
                        ),
                        metric_card(
                            "PER (株価収益率)", 
                            rx.cond(StockState.info.contains("peRatio"), StockState.info["peRatio"].to_string(), "N/A"), 
                            ""
                        ),
                        metric_card(
                            "配当利回り", 
                            rx.cond(StockState.info.contains("dividendYield"), rx.text(StockState.info["dividendYield"].to_string(), "%"), "N/A"), 
                            ""
                        ),
                        columns="3",
                        spacing="4",
                        width="100%",
                        margin_bottom="2rem",
                    ),
                    
                    # 上段: チャート + 企業概要
                    rx.grid(
                        # チャートエリア (左 2/3)
                        rx.card(
                            rx.vstack(
                                rx.heading("株価推移 (1年)", size="4", margin_bottom="1rem"),
                                rx.cond(
                                    StockState.chart_data.length() > 0,
                                    rx.recharts.area_chart(
                                        rx.recharts.area(
                                            data_key="price",
                                            stroke=rx.color("blue", 9),
                                            fill=rx.color("blue", 4),
                                        ),
                                        rx.recharts.x_axis(data_key="name"),
                                        rx.recharts.y_axis(domain=["auto", "auto"]),
                                        rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
                                        rx.recharts.tooltip(),
                                        data=StockState.chart_data,
                                        height=300,
                                        width="100%",
                                    ),
                                    rx.center(
                                        rx.text("チャートデータがありません", color="gray"),
                                        height="300px",
                                    )
                                )
                            ),
                            width="100%"
                        ),
                        
                        # 企業概要エリア (右 1/3)
                        rx.card(
                            rx.vstack(
                                rx.heading("企業概要", size="4", margin_bottom="1rem"),
                                rx.scroll_area(
                                    rx.text(
                                        rx.cond(
                                            StockState.info.contains("summary"),
                                            StockState.info["summary"].to_string(),
                                            "概要情報がありません。"
                                        ),
                                        size="2",
                                        line_height="1.6"
                                    ),
                                    type="auto",
                                    height="300px",
                                ),
                                width="100%"
                            ),
                            width="100%"
                        ),
                        grid_template_columns="2fr 1fr",
                        spacing="4",
                        width="100%",
                        margin_bottom="2rem",
                    ),
                    
                    # テクニカル分析
                    technical_analysis(),
                    
                    # AI Recap (Gemini)
                    rx.box(
                        rx.hstack(
                            rx.heading("AI Stock Recap", size="5", margin_bottom="1rem"),
                            rx.spacer(),
                            rx.button(
                                "✨ AI銘柄分析生成",
                                on_click=StockState.generate_ai_analysis,
                                loading=StockState.is_generating_analysis,
                                color_scheme="indigo",
                            ),
                            width="100%",
                            align_items="center",
                        ),
                        rx.card(
                            rx.cond(
                                StockState.ai_analysis != "",
                                rx.markdown(StockState.ai_analysis),
                                rx.center(
                                    rx.text("AI銘柄分析レポートを生成して投資判断をサポートします。", color="gray"),
                                    height="100px"
                                )
                            ),
                            width="100%",
                            padding="1.5rem"
                        ),
                        width="100%",
                        margin_bottom="2rem"
                    ),
                    
                    # 最新ニュース
                    rx.heading("最新ニュース", size="5", margin_bottom="1rem"),
                    rx.cond(
                        StockState.news.length() > 0,
                        rx.grid(
                            rx.foreach(
                                StockState.news,
                                lambda news_item: rx.card(
                                    rx.vstack(
                                        rx.text(news_item["headline"], weight="bold", margin_bottom="0.5rem"),
                                        rx.text(news_item["summary"], size="2", color="gray", margin_bottom="1rem"),
                                        rx.link("続きを読む", href=news_item["url"], is_external=True, size="2", color="blue"),
                                        align_items="start"
                                    ),
                                    width="100%",
                                )
                            ),
                            columns="2",
                            spacing="4",
                            width="100%"
                        ),
                        rx.text("ニュースデータがありません", color="gray")
                    ),
                    
                    width="100%",
                ),
                # 初期状態またはデータなし
                rx.center(
                    rx.text("銘柄コードを入力し、データを取得してください。", color="gray"),
                    height="200px",
                    width="100%"
                )
            )
        ),
        width="100%",
        max_width="1200px",
        margin="0 auto",
    )

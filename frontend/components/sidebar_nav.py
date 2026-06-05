import reflex as rx

from frontend.state.market_state import MarketState


def nav_item(text: str, icon: str, url: str) -> rx.Component:
    """ナビゲーションアイテム"""
    active = (rx.State.router.page.path == url.lower()) | (
        (rx.State.router.page.path == "/") & (url == "/")
    )

    return rx.link(
        rx.hstack(
            rx.icon(icon, size=20),
            rx.text(text, size="3", weight="medium"),
            color=rx.cond(
                active,
                rx.color("blue", 11),
                rx.color("gray", 11),
            ),
            bg=rx.cond(
                active,
                rx.color("blue", 3),
                "transparent",
            ),
            _hover={
                "bg": rx.color("gray", 3),
                "color": rx.color("gray", 12),
            },
            padding="0.75rem 1rem",
            border_radius="0.5rem",
            width="100%",
            min_height="44px",
            align_items="center",
            spacing="3",
            transition="all 0.2s ease",
            cursor="pointer",
        ),
        href=url,
        underline="none",
        width="100%",
        display="block",
    )


def _market_button(label: str, market_value: str, emoji: str) -> rx.Component:
    """市場切り替え用の個別ボタン"""
    is_active = MarketState.market_type == market_value
    return rx.button(
        rx.text(f"{emoji} {label}", size="2", weight="medium"),
        on_click=MarketState.set_market_type(market_value),
        variant=rx.cond(is_active, "solid", "ghost"),
        color_scheme=rx.cond(is_active, "blue", "gray"),
        size="2",
        flex="1",
        cursor="pointer",
    )


def market_switcher() -> rx.Component:
    """市場切り替えセグメントコントロール"""
    return rx.box(
        rx.hstack(
            _market_button("US", "US", "🇺🇸"),
            _market_button("JP", "JP", "🇯🇵"),
            width="100%",
            spacing="2",
        ),
        width="100%",
        padding="0.5rem",
        bg=rx.color("gray", 2),
        border_radius="0.5rem",
        margin_bottom="1.5rem",
    )


def sidebar_nav() -> rx.Component:
    """左側に固定されるメインナビゲーションサイドバー"""
    return rx.vstack(
        # アプリロゴ/タイトル
        rx.hstack(
            rx.icon("activity", size=24, color=rx.color("blue", 9)),
            rx.heading("AI Investing", size="5", weight="bold"),
            align_items="center",
            spacing="2",
            margin_bottom="1rem",
            padding_x="1rem",
        ),
        # 市場切り替え
        market_switcher(),
        # ナビゲーションリンク
        rx.vstack(
            nav_item("Market", "globe", "/"),
            nav_item("市場監視", "radar", "/market-watch"),
            nav_item("Stock", "trending-up", "/stock"),
            nav_item("Portfolio", "pie-chart", "/portfolio"),
            nav_item("Knowledge", "book-open", "/knowledge"),
            width="100%",
            spacing="2",
        ),
        rx.spacer(),
        # フッター情報
        rx.vstack(
            rx.text("v2.0 (Reflex)", size="1", color=rx.color("gray", 8)),
            padding="1rem",
            width="100%",
            align_items="center",
        ),
        width="250px",
        height="100vh",
        padding="1.5rem 1rem",
        border_right=f"1px solid {rx.color('gray', 4)}",
        bg=rx.color("gray", 1),
        position="sticky",
        top="0",
    )

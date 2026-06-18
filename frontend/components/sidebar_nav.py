import reflex as rx

from frontend.state.market_state import MarketState
from src.app_mode import personal_data_enabled


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


def _market_button(label: str, market_value: str) -> rx.Component:
    """市場切り替え用の個別ボタン"""
    is_active = MarketState.market_type == market_value
    return rx.button(
        rx.text(label, size="2", weight="medium"),
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
            _market_button("米国 US", "US"),
            _market_button("日本 JP", "JP"),
            width="100%",
            spacing="2",
        ),
        width="100%",
        padding="0.5rem",
        bg=rx.color("gray", 2),
        border_radius="0.5rem",
        margin_bottom="1.5rem",
    )


def _main_navigation_items() -> list[rx.Component]:
    items = [
        nav_item("Market", "globe", "/"),
        nav_item("市場監視", "radar", "/market-watch"),
        nav_item("テーマ", "list-ordered", "/theme"),
        nav_item("Stock", "trending-up", "/stock"),
    ]
    if personal_data_enabled():
        items.extend(
            [
                nav_item("Portfolio", "pie-chart", "/portfolio"),
                nav_item("Knowledge", "book-open", "/knowledge"),
            ]
        )
    return items


def _drawer_navigation_items() -> list[rx.Component]:
    return [rx.drawer.close(item) for item in _main_navigation_items()]


def _data_quality_nav_item() -> rx.Component:
    return nav_item("データ品質", "database", "/data-quality")


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
            *_main_navigation_items(),
            width="100%",
            spacing="2",
        ),
        rx.spacer(),
        # フッター情報
        rx.vstack(
            _data_quality_nav_item(),
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
        display=rx.breakpoints(initial="none", lg="flex"),
    )


def mobile_nav() -> rx.Component:
    """Drawer navigation used when the fixed sidebar is hidden."""

    return rx.vstack(
        rx.hstack(
            rx.drawer.root(
                rx.drawer.trigger(
                    rx.button(
                        rx.icon("menu", size=18),
                        "メニュー",
                        variant="surface",
                        aria_label="メインメニューを開く",
                    )
                ),
                rx.drawer.portal(
                    rx.drawer.overlay(),
                    rx.drawer.content(
                        rx.vstack(
                            rx.hstack(
                                rx.drawer.title("AI Investing"),
                                rx.spacer(),
                                rx.drawer.close(
                                    rx.icon_button(
                                        rx.icon("x", size=18),
                                        variant="ghost",
                                        aria_label="メインメニューを閉じる",
                                    )
                                ),
                                width="100%",
                                align_items="center",
                            ),
                            rx.drawer.description(
                                "分析画面と管理画面を移動します。",
                                color=rx.color("gray", 10),
                            ),
                            rx.vstack(
                                *_drawer_navigation_items(),
                                width="100%",
                                spacing="2",
                            ),
                            rx.spacer(),
                            rx.drawer.close(_data_quality_nav_item()),
                            width="100%",
                            height="100%",
                            padding="1.25rem",
                            align_items="start",
                            spacing="3",
                            bg=rx.color("gray", 1),
                        ),
                        width="min(82vw, 320px)",
                        right="auto",
                        border_right=f"1px solid {rx.color('gray', 4)}",
                    ),
                ),
                direction="left",
            ),
            rx.text("画面ナビゲーション", size="2", color=rx.color("gray", 10)),
            rx.spacer(),
            width="100%",
            min_height="44px",
            align_items="center",
            justify="between",
        ),
        market_switcher(),
        display=rx.breakpoints(initial="flex", lg="none"),
        width="100%",
        padding="0.75rem 1rem 0",
        border_bottom=f"1px solid {rx.color('gray', 4)}",
        bg=rx.color("gray", 1),
        spacing="2",
    )

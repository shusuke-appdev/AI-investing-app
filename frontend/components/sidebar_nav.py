import reflex as rx

from frontend.state.market_state import MarketState
from frontend.state.theme_state import ThemeState


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
        border_radius="0.5rem",
        _focus_visible={
            "outline": f"3px solid {rx.color('blue', 8)}",
            "outline_offset": "2px",
        },
    )


def _market_button(label: str, market_value: str) -> rx.Component:
    """市場切り替え用の個別ボタン"""
    is_active = MarketState.market_type == market_value
    return rx.button(
        rx.text(label, size="2", weight="medium"),
        on_click=[
            MarketState.set_market_type(market_value),
            ThemeState.set_market_type(market_value),
        ],
        variant=rx.cond(is_active, "solid", "ghost"),
        color_scheme=rx.cond(is_active, "blue", "gray"),
        size="2",
        flex="1",
        min_height="44px",
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


def _nav_group(
    label: str,
    items: list[tuple[str, str, str]],
    *,
    close_drawer: bool = False,
) -> rx.Component:
    links: list[rx.Component] = []
    for text, icon, url in items:
        item = nav_item(text, icon, url)
        links.append(rx.drawer.close(item) if close_drawer else item)
    return rx.vstack(
        rx.text(
            label,
            size="1",
            weight="bold",
            color=rx.color("gray", 9),
            padding_x="1rem",
        ),
        *links,
        width="100%",
        spacing="1",
        align_items="start",
    )


def _navigation_groups(*, close_drawer: bool = False) -> list[rx.Component]:
    groups = [
        _nav_group(
            "市場を見る",
            [
                ("今日の市場", "globe", "/"),
                ("市場監視", "radar", "/market-watch"),
            ],
            close_drawer=close_drawer,
        ),
        _nav_group(
            "銘柄を探す",
            [
                ("トレンド/テーマ", "list-ordered", "/theme"),
                ("銘柄分析", "trending-up", "/stock"),
            ],
            close_drawer=close_drawer,
        ),
    ]
    groups.append(
        _nav_group(
            "自分の情報",
            [
                ("Portfolio", "pie-chart", "/portfolio"),
                ("Knowledge", "book-open", "/knowledge"),
            ],
            close_drawer=close_drawer,
        )
    )
    return groups


def _data_quality_nav_item() -> rx.Component:
    return nav_item("データ品質", "database", "/data-quality")


def sidebar_nav() -> rx.Component:
    """左側に固定されるメインナビゲーションサイドバー"""
    return rx.el.nav(
        # アプリロゴ/タイトル
        rx.hstack(
            rx.icon("activity", size=24, color=rx.color("blue", 9)),
            rx.text("AI Investing", size="5", weight="bold"),
            align_items="center",
            spacing="2",
            margin_bottom="1rem",
            padding_x="1rem",
        ),
        # 市場切り替え
        market_switcher(),
        # ナビゲーションリンク
        rx.vstack(
            *_navigation_groups(),
            width="100%",
            spacing="4",
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
        aria_label="メインナビゲーション",
    )


def mobile_nav() -> rx.Component:
    """Drawer navigation used when the fixed sidebar is hidden."""

    return rx.el.nav(
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
                                        auto_focus=True,
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
                                *_navigation_groups(close_drawer=True),
                                width="100%",
                                spacing="4",
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
                modal=True,
            ),
            rx.hstack(
                rx.icon("activity", size=18, color=rx.color("blue", 9)),
                rx.text("AI Investing", size="2", weight="bold"),
                spacing="2",
                align_items="center",
            ),
            rx.spacer(),
            rx.color_mode.button(
                aria_label="表示テーマを切り替える",
                min_width="44px",
                min_height="44px",
            ),
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
        aria_label="モバイルナビゲーション",
    )

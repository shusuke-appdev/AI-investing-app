"""
テーマモメンタム監視 UIコンポーネント
4カテゴリ×上位3テーマをカード形式で表示。
"""

import reflex as rx

from frontend.state.market_state import MarketState, MomentumCategory, MomentumTheme


def _momentum_theme_item(theme: MomentumTheme) -> rx.Component:
    """個別テーマ行の表示"""
    return rx.hstack(
        rx.text(theme.theme, font_size="0.85rem", font_weight="500", flex="1"),
        rx.text(
            theme.performance_str,
            font_size="0.85rem",
            font_weight="700",
            color=rx.cond(theme.performance >= 0, "#10b981", "#ef4444"),
        ),
        width="100%",
        justify_content="space-between",
        padding_y="0.25rem",
    )


def _momentum_category_card(category: MomentumCategory) -> rx.Component:
    """カテゴリカードの表示"""
    return rx.card(
        rx.vstack(
            rx.text(
                category.category,
                font_size="0.8rem",
                font_weight="700",
                color="var(--accent-11)",
                text_transform="uppercase",
                letter_spacing="0.05em",
            ),
            rx.divider(margin_y="0.5rem"),
            rx.cond(
                category.themes.length() > 0,  # type: ignore
                rx.foreach(category.themes, _momentum_theme_item),
                rx.text("データ取得中...", font_size="0.8rem", color="gray"),
            ),
            spacing="1",
            width="100%",
        ),
        width="100%",
        padding="1rem",
    )


def momentum_monitor_component() -> rx.Component:
    """テーマモメンタム監視セクション"""
    return rx.box(
        rx.heading("📊 テーマモメンタム監視", size="5", margin_bottom="0.75rem"),
        rx.text(
            "各カテゴリの上位3テーマを表示",
            font_size="0.85rem",
            color="gray",
            margin_bottom="1rem",
        ),
        rx.cond(
            MarketState.momentum_data.length() > 0,  # type: ignore
            rx.grid(
                rx.foreach(MarketState.momentum_data, _momentum_category_card),
                columns=rx.breakpoints(initial="2", md="4"),
                spacing="3",
                width="100%",
            ),
            rx.center(
                rx.text("モメンタムデータの取得中...", color="gray", font_size="0.85rem"),
                height="80px",
            ),
        ),
        width="100%",
    )

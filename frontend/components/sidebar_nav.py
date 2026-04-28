import reflex as rx

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
            align_items="center",
            spacing="3",
            transition="all 0.2s ease",
        ),
        href=url,
        underline="none",
        width="100%",
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
            margin_bottom="2rem",
            padding_x="1rem",
        ),
        
        # ナビゲーションリンク
        rx.vstack(
            nav_item("Market", "globe", "/"),
            nav_item("Theme", "layers", "/theme"),
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

from collections.abc import Callable

import reflex as rx

from frontend.components.navbar import navbar
from frontend.components.sidebar_nav import mobile_nav, sidebar_nav


def template(page: Callable[[], rx.Component]) -> rx.Component:
    """
    全ページ共通のレイアウトテンプレート
    左側にナビゲーション、上部にヘッダー、中央にコンテンツを配置する。
    """
    return rx.box(
        rx.el.a(
            "本文へ移動",
            href="#main-content",
            position="absolute",
            left="-10000px",
            _focus={"left": "1rem", "top": "1rem", "z_index": "1000"},
        ),
        rx.hstack(
            # サイドバー (左側固定)
            sidebar_nav(),
            # メインコンテンツエリア
            rx.vstack(
                mobile_nav(),
                # トップナビゲーションバー
                navbar(),
                # ページ固有のコンテンツ
                rx.el.main(
                    page(),
                    id="main-content",
                    width="100%",
                    padding=rx.breakpoints(
                        initial="1rem",
                        md="1.5rem",
                        xl="2rem",
                    ),
                    max_width="1400px",
                    margin="0 auto",
                ),
                width="100%",
                bg=rx.color("gray", 2),
                min_height="100vh",
                overflow_y="auto",
                min_width="0",
            ),
            width="100%",
            max_width="100%",
            min_width="0",
            min_height="100vh",
            spacing="0",
            align_items="flex-start",
        ),
    )

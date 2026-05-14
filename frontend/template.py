from collections.abc import Callable

import reflex as rx

from frontend.components.navbar import navbar
from frontend.components.sidebar_nav import sidebar_nav


def template(page: Callable[[], rx.Component]) -> rx.Component:
    """
    全ページ共通のレイアウトテンプレート
    左側にナビゲーション、上部にヘッダー、中央にコンテンツを配置する。
    """
    return rx.box(
        rx.hstack(
            # サイドバー (左側固定)
            sidebar_nav(),
            # メインコンテンツエリア
            rx.vstack(
                # トップナビゲーションバー
                navbar(),
                # ページ固有のコンテンツ
                rx.box(
                    page(),
                    width="100%",
                    padding="2rem",
                    max_width="1400px",
                    margin="0 auto",
                ),
                width="100%",
                bg=rx.color("gray", 2),
                min_height="100vh",
                overflow_y="auto",
            ),
            width="100vw",
            min_height="100vh",
            spacing="0",
            align_items="flex-start",
        )
    )

import reflex as rx

def metric_card(title: str, value: str, change: str) -> rx.Component:
    """KPIを表示するメトリックカード"""
    # 変動率がプラスかマイナスかで色を変える簡易ロジック
    is_positive = "+" in change or (change and change[0].isdigit() and float(change.replace("%", "")) > 0)
    change_color = rx.color("green", 9) if is_positive else rx.color("red", 9)
    change_icon = "trending-up" if is_positive else "trending-down"
    
    return rx.card(
        rx.vstack(
            rx.text(title, size="2", color=rx.color("gray", 11), weight="medium"),
            rx.heading(value, size="6", weight="bold"),
            rx.hstack(
                rx.icon(change_icon, size=16, color=change_color),
                rx.text(change, size="2", color=change_color, weight="bold"),
                spacing="1",
                align_items="center",
            ),
            spacing="2",
        ),
        variant="surface",
        box_shadow="0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
        border_radius="lg",
        padding="1.5rem",
        width="100%",
    )

import reflex as rx
from frontend.pages.index import index

app = rx.App(
    theme=rx.theme(
        appearance="light",
        has_background=True,
        radius="large",
        accent_color="blue",
    )
)
app.add_page(index, route="/", title="AI Investing Dashboard")


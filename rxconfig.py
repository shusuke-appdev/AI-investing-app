import reflex as rx

app_theme = rx.theme(
    appearance="light",
    has_background=True,
    radius="large",
    accent_color="blue",
)

config = rx.Config(
    app_name="frontend",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(theme=app_theme),
    ],
)

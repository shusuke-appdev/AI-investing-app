import os
from pathlib import Path

os.environ.setdefault("REFLEX_STATES_WORKDIR", ".reflex_states")

import reflex as rx


def _prefer_codex_runtime_node() -> None:
    """Prefer the runnable bundled Node over the Codex app WindowsApps shim."""

    node_dir = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "bin"
    )
    node_exe = node_dir / "node.exe"
    if not node_exe.exists():
        return

    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    node_dir_str = str(node_dir)
    if path_parts and path_parts[0].lower() == node_dir_str.lower():
        return
    os.environ["PATH"] = os.pathsep.join(
        [node_dir_str, *[part for part in path_parts if part]]
    )


_prefer_codex_runtime_node()

app_theme = rx.theme(
    appearance="inherit",
    has_background=True,
    radius="large",
    accent_color="blue",
    gray_color="slate",
    panel_background="solid",
)

config = rx.Config(
    app_name="frontend",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(theme=app_theme),
    ],
)

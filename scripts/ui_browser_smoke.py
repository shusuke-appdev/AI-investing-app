"""Browser-level responsive checks against the exported Reflex frontend."""

from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = REPO_ROOT / ".web" / "build" / "client"
ROUTES = (
    "/",
    "/market-watch",
    "/theme",
    "/theme-leaders",
    "/stock",
    "/data-quality",
    "/portfolio",
    "/knowledge",
)
ROUTE_FILES = {
    "/": "/index.html",
    "/market-watch": "/market-watch.html",
    "/theme": "/theme.html",
    "/theme-leaders": "/theme-leaders.html",
    "/stock": "/stock.html",
    "/data-quality": "/data-quality.html",
    "/portfolio": "/portfolio.html",
    "/knowledge": "/knowledge.html",
}
VIEWPORTS = (
    ("mobile", {"width": 390, "height": 844}),
    ("desktop", {"width": 1280, "height": 720}),
)


class QuietHandler(SimpleHTTPRequestHandler):
    """Serve export files without polluting release-check output."""

    def do_GET(self) -> None:
        route = self.path.split("?", maxsplit=1)[0].rstrip("/") or "/"
        if route in ROUTE_FILES:
            self.path = ROUTE_FILES[route]
        super().do_GET()

    def log_message(self, format: str, *args: object) -> None:
        return


def _layout_width(page: Page) -> tuple[int, int]:
    metrics = page.evaluate(
        """() => ({
          scrollWidth: Math.max(
            document.documentElement.scrollWidth,
            document.body ? document.body.scrollWidth : 0
          ),
          clientWidth: document.documentElement.clientWidth
        })"""
    )
    return int(metrics["scrollWidth"]), int(metrics["clientWidth"])


def _validate_mobile_drawer(page: Page, base_url: str) -> list[str]:
    errors: list[str] = []
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    trigger = page.get_by_role("button", name="メインメニューを開く")
    if trigger.count() != 1:
        return ["mobile navigation: menu trigger is missing or duplicated"]

    trigger.click()
    dialog = page.get_by_role("dialog")
    try:
        dialog.wait_for(state="visible", timeout=5_000)
    except Exception:
        return ["mobile navigation: drawer did not become visible"]

    try:
        page.wait_for_function(
            """() => {
              const dialog = document.querySelector('[role="dialog"]');
              return Boolean(dialog && dialog.contains(document.activeElement));
            }""",
            timeout=5_000,
        )
    except Exception:
        errors.append("mobile navigation: focus did not move into the drawer")

    page.keyboard.press("Escape")
    try:
        dialog.wait_for(state="hidden", timeout=5_000)
    except Exception:
        errors.append("mobile navigation: Escape did not close the drawer")
    return errors


def main() -> int:
    """Check exported routes at narrow and wide viewports."""

    if not EXPORT_DIR.exists():
        print(f"ERROR: Reflex export is missing: {EXPORT_DIR}")
        return 1

    handler = partial(QuietHandler, directory=str(EXPORT_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    errors: list[str] = []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            for viewport_name, viewport in VIEWPORTS:
                page.set_viewport_size(viewport)
                for route in ROUTES:
                    page.goto(
                        f"{base_url}{route}",
                        wait_until="domcontentloaded",
                    )
                    scroll_width, client_width = _layout_width(page)
                    if scroll_width > client_width + 1:
                        errors.append(
                            f"{route} [{viewport_name}]: horizontal overflow "
                            f"{scroll_width}px > {client_width}px"
                        )
            errors.extend(_validate_mobile_drawer(page, base_url))
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        f"Browser UI smoke passed for {len(ROUTES)} routes at "
        f"{len(VIEWPORTS)} viewports plus mobile drawer."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

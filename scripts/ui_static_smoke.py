"""Validate semantic structure in the exported Reflex routes."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = REPO_ROOT / ".web" / "build" / "client"
ROUTE_FILES = (
    "index.html",
    "market-watch.html",
    "stock.html",
    "theme.html",
    "data-quality.html",
    "portfolio.html",
    "knowledge.html",
)
PUBLIC_NAV_ROUTES = {"/", "/market-watch", "/theme", "/stock", "/data-quality"}


def validate_route(path: Path) -> list[str]:
    """Return semantic errors found in one exported route."""

    if not path.exists():
        return [f"{path.name}: export file is missing"]

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    errors: list[str] = []
    h1_values = [item.get_text(" ", strip=True) for item in soup.find_all("h1")]
    if len(h1_values) != 1:
        errors.append(f"{path.name}: expected one h1, found {len(h1_values)}")

    empty_headings = [
        item.name
        for item in soup.find_all(("h1", "h2", "h3", "h4", "h5", "h6"))
        if not item.get_text(" ", strip=True)
    ]
    if empty_headings:
        errors.append(
            f"{path.name}: empty headings found ({', '.join(empty_headings)})"
        )
    return errors


def validate_stock_form(path: Path) -> list[str]:
    """Validate the accessible ticker form contract."""

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    ticker_input = soup.find("input", id="stock-ticker")
    ticker_label = soup.find("label", attrs={"for": "stock-ticker"})
    errors = []
    if ticker_input is None:
        errors.append("stock.html: ticker input id is missing")
    if ticker_label is None:
        errors.append("stock.html: ticker label association is missing")
    ticker_form = ticker_input.find_parent("form") if ticker_input else None
    if ticker_form is None:
        errors.append("stock.html: ticker input is not inside a form")
    elif ticker_form.find("button", attrs={"type": "submit"}) is None:
        errors.append("stock.html: ticker form submit button is missing")
    return errors


def validate_navigation(path: Path) -> list[str]:
    """Validate exported public navigation and retired-route boundaries."""

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    hrefs = {str(link.get("href")) for link in soup.find_all("a", href=True)}
    missing = sorted(PUBLIC_NAV_ROUTES - hrefs)
    errors = []
    if missing:
        errors.append(f"index.html: navigation routes missing ({', '.join(missing)})")
    if "/trading-plan" in hrefs:
        errors.append("index.html: retired /trading-plan navigation is present")
    if (EXPORT_DIR / "trading-plan.html").exists() or (
        EXPORT_DIR / "trading-plan" / "index.html"
    ).exists():
        errors.append("export: retired trading-plan route was generated")
    return errors


def main() -> int:
    """Run static UI checks after a Reflex frontend export."""

    errors = [
        error
        for filename in ROUTE_FILES
        for error in validate_route(EXPORT_DIR / filename)
    ]
    stock_path = EXPORT_DIR / "stock.html"
    if stock_path.exists():
        errors.extend(validate_stock_form(stock_path))
    index_path = EXPORT_DIR / "index.html"
    if index_path.exists():
        errors.extend(validate_navigation(index_path))

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Static UI semantics passed for {len(ROUTE_FILES)} routes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

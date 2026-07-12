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

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Static UI semantics passed for {len(ROUTE_FILES)} routes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

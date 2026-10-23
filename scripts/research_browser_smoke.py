"""Rendered acceptance; Browser plugin not available, existing Python Playwright."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("dashboard", type=Path)
parser.add_argument(
    "--stock",
    type=Path,
    action="append",
    required=True,
    help="AAPL and 7203.T research snapshots for full acceptance",
)
parser.add_argument("--output", type=Path, default=Path(".states/dashboard_browser"))
args = parser.parse_args()
target = args.dashboard.resolve()
stocks = args.stock
root = args.output.resolve()
root.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: (
            errors.append(message.text) if message.type == "error" else None
        ),
    )
    for width in (320, 736, 1024, 1440):
        for mode in ("light", "dark"):
            page.set_viewport_size({"width": width, "height": 1000})
            page.emulate_media(color_scheme=mode)
            page.goto(target.as_uri())
            assert page.title() == "投資リサーチ"
            assert page.get_by_role(
                "heading", name="投資リサーチ", exact=True
            ).is_visible()
            assert page.locator("[data-comparison] svg.chart").count() == 2
            assert page.locator("[data-comparison] polyline").count() == 4
            before = page.locator(
                '[data-comparison="US"] polyline'
            ).first.get_attribute("points")
            page.get_by_label("指数期間", exact=True).select_option("1mo")
            after = page.locator('[data-comparison="US"] polyline').first.get_attribute(
                "points"
            )
            assert before != after
            for period in ("1mo", "3mo", "6mo", "1y", "2y"):
                page.get_by_label("指数期間", exact=True).select_option(period)
                assert page.locator('[data-comparison="US"] polyline').count() == 2
            page.get_by_label("指数期間", exact=True).select_option("6mo")
            page.locator('[data-market="JP"]').click()
            assert "（日本）" in page.locator("#content").inner_text()
            assert "TOPIX連動ETF・代理" in page.locator("#content").inner_text()
            page.locator('[data-market="US"]').click()
            chart = page.locator('[data-comparison="US"] svg.chart')
            chart.focus()
            chart.press("ArrowLeft")
            assert page.locator('[data-comparison="US"] .tooltip').inner_text().strip()
            assert all(
                url.startswith("https://")
                for url in page.locator("[data-comparison] a").evaluate_all(
                    "nodes=>nodes.map(n=>n.href)"
                )
            )
            page.locator('[data-market="US"]').click()
            page.screenshot(
                path=str(root / f"dashboard-overview-{width}-{mode}.png"),
                full_page=True,
            )
            page.screenshot(path=str(root / f"dashboard-viewport-{width}-{mode}.png"))
            page.locator('[data-page="theme"]').click()
            page.get_by_label("テーマを検索").fill("該当しない検索文字列")
            assert page.get_by_text(
                "一致するテーマはありません。", exact=True
            ).is_visible()
            page.get_by_label("テーマを検索").fill("")
            page.get_by_role("button", name="順位 ↕", exact=True).first.click()
            page.get_by_role("button", name="1か月 ↕", exact=True).first.click()
            returns = (
                page.locator("#content table")
                .first.locator("tbody tr td:nth-child(4)")
                .all_text_contents()
            )
            values = [
                float(value.replace("%", "").replace(",", ""))
                for value in returns
                if value != "未確認"
            ]
            assert values == sorted(values), (width, mode, values)
            for route in ("market", "stock", "policy", "health"):
                page.locator(f'[data-page="{route}"]').click()
                assert page.locator("#content").inner_text().strip()
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                ), (width, mode, route)
            invalid = {
                "schema_version": 2,
                "run_id": "invalid",
                "workflow": "stock",
                "created_at": "2026-10-06",
                "inputs": {"market": "US"},
                "sections": {"TEST": {"analysis": []}},
            }
            existing_count = page.evaluate("bundles.length")
            page.get_by_label("research.json を選択（複数可）").set_input_files(
                [
                    {
                        "name": "valid.json",
                        "mimeType": "application/json",
                        "buffer": stocks[0].read_bytes(),
                    },
                    {
                        "name": "invalid.json",
                        "mimeType": "application/json",
                        "buffer": json.dumps(invalid).encode(),
                    },
                ]
            )
            page.get_by_role("status").filter(has_text="保存形式が不正").wait_for(
                state="visible"
            )
            page.locator('[data-page="stock"]').click()
            assert page.evaluate("bundles.length") == existing_count
            page.locator('[data-page="health"]').click()
            page.get_by_label("research.json を選択（複数可）").set_input_files(
                [str(s) for s in stocks]
            )
            page.locator('[data-page="stock"]').click()
            page.get_by_label("銘柄", exact=True).select_option("AAPL")
            assert page.get_by_text("売上成長率", exact=True).first.is_visible()
            assert page.locator("svg.stock-chart").is_visible()
            assert page.locator("details[data-feature]").count() == page.evaluate(
                "Object.keys(payload.stock_features).length"
            )
            full_count = int(
                page.locator("svg.stock-chart").get_attribute("data-point-count")
            )
            page.locator("#stock-period").select_option("1mo")
            assert (
                int(page.locator("svg.stock-chart").get_attribute("data-point-count"))
                < full_count
            )
            page.locator("#stock-scale").select_option("linear")
            assert (
                page.locator("svg.stock-chart").get_attribute("data-scale") == "linear"
            )
            page.locator('input[data-series="ma10"]').uncheck()
            assert (
                page.locator('svg.stock-chart polyline[data-series="ma10"]').count()
                == 0
            )
            page.locator('input[data-series="volume"]').uncheck()
            assert (
                page.locator('svg.stock-chart rect[data-series="volume"]').count() == 0
            )
            page.locator("svg.stock-chart").focus()
            page.locator("svg.stock-chart").press("ArrowLeft")
            assert (
                "終値"
                in page.locator(
                    '[data-feature="stock_chart"] [role="status"]'
                ).inner_text()
            )
            assert (
                page.locator('[data-feature="volume_profile_view"] tbody tr').count()
                > 0
            )
            page.locator("#stock-period").select_option("1y")
            page.locator('details[data-feature="probabilistic_signal"] summary').click()
            assert (
                page.locator(
                    'details[data-feature="probabilistic_signal"]'
                ).get_attribute("open")
                is not None
            )
            page.get_by_label("銘柄", exact=True).select_option("7203.T")
            assert "7203.T" in page.locator("#content").inner_text()
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), (width, mode, "loaded stock")
            if width == 1440 and mode == "light":
                page.get_by_label("銘柄", exact=True).select_option("AAPL")
                page.evaluate("window.scrollTo(0,0)")
                page.screenshot(path=str(root / "dashboard-stock-1440-light.png"))
    # Dedicated signed/zero/null fixture, separate from real-data screenshots.
    page.goto(target.as_uri())
    rows = [
        {
            "rank": i + 1,
            "theme": name,
            "performance_1m": value,
            "performance_1w": None,
            "performance_6m": 0,
        }
        for i, (name, value) in enumerate(
            [
                ("negative10", -10),
                ("zero", 0),
                ("negative2", -2),
                ("positive20", 20),
                ("missing", None),
            ]
        )
    ]
    fixture = {
        "schema_version": 2,
        "run_id": "signed-display-fixture",
        "workflow": "theme",
        "created_at": "2026-10-06",
        "inputs": {"market": "US"},
        "sections": {"theme": {"ranking": {"items": rows}}},
    }
    page.locator('[data-page="health"]').click()
    page.get_by_label("research.json を選択（複数可）").set_input_files(
        {
            "name": "fixture.json",
            "mimeType": "application/json",
            "buffer": json.dumps(fixture).encode(),
        }
    )
    page.locator(".bar-mark.negative").first.wait_for(state="visible")
    assert page.locator(".bar-mark.negative").count() == 2
    assert (
        page.locator(".bar-mark").count() == 4
    )  # null has no mark; real zero remains.
    assert page.locator(".bar-value").all_text_contents()[:5] == [
        "-10.0%",
        "0.0%",
        "-2.0%",
        "+20.0%",
        "未確認",
    ]
    page.locator('[data-page="theme"]').click()
    page.get_by_role("button", name="1か月 ↕", exact=True).first.click()
    assert page.locator("#content table").first.locator(
        "tbody tr td:nth-child(2)"
    ).all_text_contents() == [
        "negative10",
        "negative2",
        "zero",
        "positive20",
        "missing",
    ]
    assert not errors, errors
    browser.close()
print(
    "PASS: 8 viewport/color combinations; charts, market/period, search, sorting, six pages, file import, stock selection, details, overflow, console"
)

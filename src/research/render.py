"""Purpose-built, self-contained offline views of the same research snapshot."""

from __future__ import annotations

import html
import json
from pathlib import Path

from src.research.bundle import validate_bundle
from src.research.catalog import MARKET_FEATURES, STOCK_FEATURES, feature_coverage
from src.research.comparison import comparison_views

ASSETS = Path(__file__).with_name("assets")


def render_dashboard(
    bundle: dict, attachments: list[dict] | None = None, *, embedded: bool = False
) -> str:
    validate_bundle(bundle)
    for attached in attachments or []:
        validate_bundle(attached)
    payload = {
        "embedded": embedded,
        "bundle": bundle,
        "bundles": [bundle, *(attachments or [])],
        "comparisons": comparison_views(bundle["sections"].get("comparisons", {})),
        "market_features": MARKET_FEATURES,
        "stock_features": STOCK_FEATURES,
        "coverage": feature_coverage(bundle),
    }
    encoded = html.escape(json.dumps(payload, ensure_ascii=False, allow_nan=False))
    template = (ASSETS / "dashboard.html").read_text(encoding="utf-8")
    scripts = "\n".join(
        (ASSETS / name).read_text(encoding="utf-8")
        for name in (
            "charts.js",
            "specialized.js",
            "market.js",
            "topdown.js",
            "dashboard.js",
        )
    )
    return (
        template.replace(
            "<!--STYLE-->", (ASSETS / "dashboard.css").read_text(encoding="utf-8")
        )
        .replace("<!--DATA-->", encoded)
        .replace("<!--SCRIPT-->", scripts)
    )


def markdown_summary(bundle: dict) -> str:
    summary = f"# 投資リサーチ / {bundle['workflow']}\n\n作成: {bundle['created_at']}（観測日とは別）\n\n"
    if bundle["sections"].get("market") or bundle["sections"].get("markets"):
        from src.research.brief import render_brief

        summary += render_brief(bundle) + "\n\n"
    policy = bundle["sections"].get("policy", {})
    if policy and "observations" in policy:
        summary += f"## 研究姿勢\n\n{policy['stance']}\n\n{policy['stance_reason']}\n\n"
        summary += "## 観測\n\n" + "\n".join(
            f"- {row['label']}: {row['observation']}" for row in policy["observations"]
        )
        summary += "\n\n## 反証・不足\n\n" + "\n".join(
            f"- {text}" for text in policy["counterevidence"] + policy["missing"]
        )
        for stock in policy["stocks"]:
            summary += f"\n\n## {stock['ticker']}\n\n"
            summary += "\n".join(
                f"- 未成立: {row['label']} / {row.get('value', '未確認')}"
                for row in stock["counterevidence"]
            )
            summary += f"\n\n無効化: {stock['invalidation']}\n"
        summary += "\n\n## 次の確認\n\n" + "\n".join(
            f"- {text}" for text in policy["next_checks"]
        )
    else:
        summary += "同じ入力による画面・条件・財務・資料は dashboard.html、全計算入力は research.json を参照。\n"
    for ticker, packet in bundle["sections"].items():
        if not isinstance(packet, dict) or "filings" not in packet:
            continue
        filings = packet["filings"]
        summary += f"\n\n## {ticker} / 会計・企業価値\n\n"
        audit = filings.get("accounting_audit", {})
        summary += (
            f"照合状態: {audit.get('status', '未確認')}（算定可能・投資適格とは別）\n"
        )
        for review in filings.get("accounting_reviews", []):
            summary += (
                f"\n会計: {review['accounting_basis']} / {review['ownership_basis']}\n"
                f"\n訂正・版確認: {review['amendments']}\n"
            )
            for record in review.get("reconciliations", []):
                summary += (
                    f"\n{record['metric']} {record['period_start']}–{record['period_end']}: "
                    + " + ".join(f"{k}({v:,.0f})" for k, v in record["terms"].items())
                    + f" = {record['result']:,.0f} {record['currency']} "
                    + f"[許容差{record['rounding_tolerance']:,.0f}; {record['locator']}]\n"
                )
        for r in packet.get("filing_valuations", []):
            summary += f"\n### {r['method']} / {r['status']}\n\n"
            for case in r.get("cases", []):
                summary += f"- {case['case']}: {case.get('value')} {r['currency']} / 仮定 {case.get('assumptions', {})}\n"
            summary += (
                "\n算定入力・定義・基準期間（原単位から基準通貨へ換算済）:\n\n```json\n"
            )
            summary += json.dumps(r.get("inputs", {}), ensure_ascii=False, indent=2)
            summary += "\n```\n"
            if r.get("reverse_dcf"):
                summary += (
                    f"\n逆DCF: {json.dumps(r['reverse_dcf'], ensure_ascii=False)}\n"
                )
        for derived in filings.get("derivations", []):
            summary += f"\n算定 {derived['metric']}: {derived['rationale']}\n"
            for term in derived["terms"]:
                summary += f"- {term['metric']}: {term['quantity']['value']} × {term['coefficient']} / {term['rationale']}\n"
        for source in filings.get("sources", []):
            summary += f"\n- [{source['id']} / {source['title']}]({source['url']}) / 公開 {source['published_on']} / 確認 {source['accessed_on']} / {source['locator']}\n"
    return (
        summary
        + "\n\n"
        + "\n".join(f"- {warning}" for warning in bundle.get("warnings", []))
        + "\n"
    )


def save_bundle(
    bundle: dict, directory: Path, attachments: list[dict] | None = None
) -> Path:
    validate_bundle(bundle)
    rendered = render_dashboard(bundle, attachments)
    serialized = json.dumps(
        bundle,
        ensure_ascii=False,
        indent=2 if bundle["schema_version"] < 3 else None,
        separators=None if bundle["schema_version"] < 3 else (",", ":"),
        allow_nan=False,
    )
    if len(serialized.encode("utf-8")) > 20 * 1024 * 1024:
        raise ValueError("Snapshot exceeds the dashboard's 20MB import limit")
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "research.json").write_text(
        serialized,
        encoding="utf-8",
    )
    (directory / "dashboard.html").write_text(rendered, encoding="utf-8")
    for index, attached in enumerate(attachments or [], start=1):
        (directory / f"attached_{index:02d}.json").write_text(
            json.dumps(
                attached,
                ensure_ascii=False,
                indent=2 if attached["schema_version"] < 3 else None,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
    (directory / "summary.md").write_text(markdown_summary(bundle), encoding="utf-8")
    return directory

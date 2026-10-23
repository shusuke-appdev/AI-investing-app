"""Evidence-bound research synthesis, not a trading recommendation or model call."""

from __future__ import annotations


def synthesize(sections: dict, market_type: str) -> dict:
    market = sections.get("market", {}).get("analysis", {})
    ranking = sections.get("theme", {}).get("ranking", {})
    regime = market.get("strategy_regime", {})
    observations = []
    for key, label in [
        ("ibd_regime", "市場状態（IBD代理）"),
        ("volatility_regime", "ボラ"),
        ("credit_stress", "信用"),
    ]:
        item = market.get(key, {})
        text = item.get("label") or item.get("status_label") or item.get("summary")
        observations.append(
            {
                "label": label,
                "observation": text or "未確認",
                "input_path": f"market.analysis.{key}",
            }
        )
    top = ranking.get("items", [])[:5]
    observations.append(
        {
            "label": "総合順位Top5",
            "observation": " / ".join(item["theme"] for item in top)
            or "順位を確認できません",
            "input_path": "theme.ranking.items[:5]",
        }
    )
    stocks = []
    for ticker, packet in sections.items():
        if ticker in {"market", "theme", "comparisons", "policy"}:
            continue
        conditions = packet.get("analysis", {}).get("primary_conditions", {})
        rows = conditions.get("conditions", [])
        filings = packet.get("filings", {})
        claims = filings.get("claims", [])
        stocks.append(
            {
                "ticker": ticker,
                "status": "research_only",
                "support": [row for row in rows if row.get("status") == "pass"],
                "counterevidence": [row for row in rows if row.get("status") == "fail"],
                "unconfirmed": [
                    row
                    for row in rows
                    if row.get("status") not in {"pass", "fail", "reference"}
                ],
                "filing_observations": [
                    claim for claim in claims if claim["category"] != "risk"
                ],
                "filing_risks": [
                    claim for claim in claims if claim["category"] == "risk"
                ],
                "conditional_checks": [
                    "主条件の成立と未成立を同じ基準日で再確認",
                    "業種に適した財務指標と評価仮定を原資料で照合",
                ],
                "invalidation": conditions.get("invalidation")
                or "無効化条件の入力が未確認",
                "next_checks": filings.get("missing", [])
                + (
                    []
                    if filings.get("sources")
                    else ["直近3年・最新中間の一次資料を確認"]
                ),
                "input_path": ticker,
            }
        )
    missing = list(market.get("quality_warnings", [])) + list(
        ranking.get("quality_warnings", [])
    )
    if not stocks:
        missing.append("条件を満たすリーダー候補が未確認。候補を捏造しません。")
    return {
        "status": "research_only",
        "market": market_type,
        "stance": regime.get("label") or "市場姿勢は未確認",
        "stance_reason": regime.get("rationale")
        or "市場根拠の不足を確認してください。",
        "observations": observations,
        "stocks": stocks,
        "counterevidence": [
            market.get("flow_monitor", {}).get("summary") or "資金動向は未確認"
        ],
        "invalidation": regime.get("invalidation") or "市場の無効化条件は未確認",
        "missing": missing,
        "next_checks": [
            "市場・テーマ・銘柄の観測日と取得不足を確認",
            "支持抵抗の突破／失敗を既存の条件で確認",
            "事業見通し・カタリスト・リスクを一次資料と反証で照合",
        ],
        "method": "deterministic evidence summary; no orders, no new composite stock score",
    }

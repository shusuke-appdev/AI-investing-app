"""Read-only snapshot acceptance; writes only a generated local evidence record."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.bundle import validate_bundle  # noqa: E402
from src.storage.atomic_json import write_json  # noqa: E402


def signature(value) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def audit(original: Path, updated: Path) -> dict:
    before = validate_bundle(json.loads(original.read_text(encoding="utf-8")))
    after = validate_bundle(json.loads(updated.read_text(encoding="utf-8")))
    preserved = []
    for ticker in ("AAPL", "7203.T", "JPM", "8306.T", "PLD", "8951.T"):
        old, new = before["sections"][ticker], after["sections"][ticker]
        fields = (
            "analysis",
            "filings",
            "filing_valuations",
            "filing_valuation",
            "valuation",
        )
        unchanged = all(signature(old.get(k)) == signature(new.get(k)) for k in fields)
        if not unchanged:
            raise ValueError(f"Saved issuer changed: {ticker}")
        preserved.append(
            {
                "ticker": ticker,
                "original_fields_sha256": signature({k: old.get(k) for k in fields}),
                "unchanged": unchanged,
            }
        )
    markets = []
    for market in ("US", "JP"):
        connected = after["sections"]["markets"][market]["analysis"]["connected"]
        if connected != after["sections"]["policies"][market]["connected"]:
            raise ValueError("Policy/market observations differ")
        packet = after["sections"]["themes"][market]
        ranking = packet.get("attempted_analysis", packet).get("ranking", {})
        markets.append(
            {
                "market": market,
                "qualities": {
                    q: sum(r["quality"] == q for r in connected["observations"])
                    for q in ("available", "stale", "unavailable")
                },
                "relations": [
                    {"case": r["id"], "kind": r["kind"]} for r in connected["relations"]
                ],
                "official_events": connected["events"],
                "event_sources": connected["event_sources"],
                "jpx": connected["jpx"],
                "themes": len(ranking.get("items", [])),
                "ranked_6m": sum(
                    r.get("rank_6m") is not None for r in ranking.get("items", [])
                ),
                "rate_observations": [
                    r
                    for r in connected["observations"]
                    if r["id"].startswith(("DGS", "DFII", "JP10", "credit:"))
                ],
            }
        )
    return {
        "original": str(original.resolve()),
        "original_file_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
        "updated": str(updated.resolve()),
        "updated_file_sha256": hashlib.sha256(updated.read_bytes()).hexdigest(),
        "issuer_regression": preserved,
        "markets": markets,
        "diagnostics": after["sections"]["diagnostics"],
        "execution_status": after["execution_status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("updated", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.original, args.updated)
    write_json(args.output, result)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "issuers": len(result["issuer_regression"]),
                "markets": [
                    {k: r[k] for k in ("market", "qualities", "themes", "ranked_6m")}
                    for r in result["markets"]
                ],
                "seconds": result["diagnostics"]["elapsed_seconds"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

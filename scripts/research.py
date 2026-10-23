"""Codex-facing local research CLI; no model API call is required."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.evidence import ResearchEvidence  # noqa: E402
from src.research.render import save_bundle  # noqa: E402
from src.research.runner import refresh, resume, run  # noqa: E402


def main() -> int:
    # Applies only to this CLI process, never persistent user/provider settings.
    os.environ["INVESTMENT_RESEARCH_NO_MODEL"] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workflow",
        choices=[
            "update",
            "overview",
            "market",
            "stock",
            "theme",
            "policy",
            "diagnostics",
            "screen",
            "saved",
        ],
    )
    parser.add_argument(
        "--scope",
        choices=["all", "US", "JP"],
        help="Broad update scope; default both markets",
    )
    parser.add_argument(
        "--open", action="store_true", help="Open the saved offline result"
    )
    parser.add_argument("--market", choices=["US", "JP"])
    parser.add_argument(
        "--profile",
        choices=["standard", "advanced"],
        help="New acquisition defaults to standard; saved-input workflows keep their original profile",
    )
    parser.add_argument("--ticker", default="")
    parser.add_argument(
        "--include-fundamentals",
        action="store_true",
        help="Explicit broad price and quarterly-financial update",
    )
    parser.add_argument(
        "--refresh-fundamentals",
        action="store_true",
        help="Explicit screening financial acquisition; cached issuers resume",
    )
    parser.add_argument("--evidence", type=Path)
    parser.add_argument(
        "--market-inputs",
        type=Path,
        help="Permission/source-reviewed JPX weekly amounts JSON; standard update only",
    )
    parser.add_argument(
        "--refresh", type=Path, help="Update one market stage against saved inputs"
    )
    parser.add_argument(
        "--stage",
        choices=["summary", "theme-flow", "credit-risk", "vol-sentiment", "options"],
    )
    parser.add_argument(
        "--attach",
        type=Path,
        action="append",
        default=[],
        help="Open additional saved research snapshots together without refetch",
    )
    parser.add_argument(
        "--scan-fomo", action="store_true", help="Explicit existing US-universe scan"
    )
    parser.add_argument(
        "--filings-cik",
        help="Read a matching US issuer's free SEC annual/interim catalog; SEC_USER_AGENT required",
    )
    parser.add_argument(
        "--allow-options",
        action="store_true",
        help="Explicitly authorize the existing US option provider request (may consume credits)",
    )
    parser.add_argument(
        "--replay",
        type=Path,
        help="Render a saved research.json without any data fetch",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        help="Recalculate saved inputs using --evidence without refetch",
    )
    args = parser.parse_args()
    if args.workflow == "saved":
        if any(
            (
                args.open,
                args.profile,
                args.ticker,
                args.evidence,
                args.refresh,
                args.stage,
                args.attach,
                args.scan_fomo,
                args.filings_cik,
                args.allow_options,
                args.replay,
                args.resume,
                args.market_inputs,
                args.include_fundamentals,
                args.refresh_fundamentals,
            )
        ):
            parser.error(
                "saved only reads existing inputs; use --scope/--market to select markets"
            )
        if args.scope and args.market and args.scope != args.market:
            parser.error("Conflicting --scope and --market")
        from src.research.brief import render_brief
        from src.research.workbench import saved_workspace

        scope = args.scope or args.market or "all"
        markets = ("US", "JP") if scope == "all" else (scope,)
        print(render_brief(saved_workspace(ROOT), markets), end="")
        return 0
    if (
        args.include_fundamentals
        and args.workflow != "update"
        or args.refresh_fundamentals
        and args.workflow != "screen"
    ):
        parser.error("Financial flags belong to update/screen respectively")
    if args.workflow == "screen":
        if any(
            (
                args.evidence,
                args.refresh,
                args.stage,
                args.attach,
                args.scan_fomo,
                args.filings_cik,
                args.allow_options,
                args.replay,
                args.resume,
                args.ticker,
                args.market_inputs,
                args.profile == "advanced",
            )
        ):
            parser.error(
                "screen reads saved prices and optionally refreshes quarterly data"
            )
        from copy import deepcopy
        from uuid import uuid4

        from src.research.bundle import new_bundle
        from src.research.workbench import Workbench, saved_workspace, update_lock

        if args.scope and args.market and args.scope != args.market:
            parser.error("Conflicting --scope and --market")
        scope = args.scope or args.market or "US"
        if args.refresh_fundamentals:
            workspace = Workbench(ROOT)
            output = workspace.update(scope, mode="fundamentals")
            if output is None:
                print(workspace.snapshot_status()["message"], file=sys.stderr)
                return 2
        else:
            with update_lock(ROOT / ".states" / "research_workbench" / "update.lock"):
                previous = saved_workspace(ROOT)
                markets = ("US", "JP") if scope == "all" else (scope,)
                if not any(
                    previous["sections"]
                    .get("markets", {})
                    .get(m, {})
                    .get("analysis", {})
                    .get("topdown")
                    for m in markets
                ):
                    parser.error(
                        "保存された候補入力がありません。先に update を実行してください。"
                    )
                bundle = new_bundle(
                    "screen",
                    {**previous["inputs"], "market": markets[0], "scope": scope},
                    deepcopy(previous["sections"]),
                )
                for key in ("saved_stock_origins", "saved_interpretations"):
                    if key in previous:
                        bundle[key] = deepcopy(previous[key])
                output = save_bundle(
                    bundle, ROOT / ".states" / "research_runs" / str(uuid4())
                )
        print(output)
        if args.open:
            import webbrowser

            webbrowser.open((output / "dashboard.html").as_uri())
        return 0
    if args.workflow == "update":
        market_inputs = None
        if args.market_inputs:
            from src.research.public_sources import validate_market_inputs

            if args.profile == "advanced":
                parser.error(
                    "--market-inputs requires standard and a bounded JSON file"
                )
            try:
                if args.market_inputs.stat().st_size > 1024 * 1024:
                    raise ValueError("Input too large")
                market_inputs = json.loads(
                    args.market_inputs.read_text(encoding="utf-8")
                )
                validate_market_inputs(market_inputs)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                parser.error(f"Invalid reviewed market input ({type(exc).__name__})")
        if any(
            (
                args.evidence,
                args.refresh,
                args.stage,
                args.attach,
                args.scan_fomo,
                args.filings_cik,
                args.allow_options,
                args.replay,
                args.resume,
                args.ticker,
            )
        ):
            parser.error(
                "update is a market/theme workspace update; use a separate stock/evidence/explicit optional acquisition run"
            )
        from src.research.workbench import Workbench

        if args.scope and args.market and args.scope != args.market:
            parser.error("Conflicting --scope and --market")
        workbench = Workbench(ROOT)
        output = workbench.update(
            args.scope or args.market or "all",
            profile=args.profile or "standard",
            **({"mode": "all"} if args.include_fundamentals else {}),
            **({"market_inputs": market_inputs} if market_inputs is not None else {}),
        )
        if output is None:
            print(workbench.snapshot_status()["message"], file=sys.stderr)
            return 2
        print(output)
        if args.open:
            import webbrowser

            webbrowser.open((output / "dashboard.html").as_uri())
        return 0
    if args.scope or args.open:
        parser.error("--scope/--open belong to update")
    if args.market_inputs:
        parser.error("--market-inputs belongs to standard update")
    args.market = args.market or "US"
    if sum(bool(x) for x in (args.replay, args.resume, args.refresh)) > 1:
        parser.error("--replay, --resume and --refresh are mutually exclusive")
    if bool(args.stage) != bool(args.refresh):
        parser.error("--stage requires --refresh and vice versa")
    if args.refresh and (
        args.workflow not in {"market", "overview", "policy"}
        or args.evidence
        or args.scan_fomo
        or args.filings_cik
    ):
        parser.error("Stage refresh only updates saved market acquisitions")
    if (args.resume or args.replay) and (args.allow_options or args.scan_fomo):
        parser.error("Saved-input workflows do not allow network requests")
    if (args.resume or args.replay) and args.profile:
        parser.error("Saved-input workflows preserve the original acquisition profile")
    if args.refresh and args.profile == "standard":
        parser.error("Stage refresh is an explicit legacy/advanced update")
    if args.profile and args.workflow in {"stock", "diagnostics"}:
        parser.error("--profile belongs to market/theme/policy/overview/update")
    if args.resume and not args.evidence:
        parser.error(
            "--resume requires --evidence and does not allow network/option requests"
        )
    if args.filings_cik and (
        args.workflow != "stock" or args.market != "US" or args.resume or args.replay
    ):
        parser.error("--filings-cik is only valid for a new US stock run")
    if args.filings_cik and not re.fullmatch(r"\d{1,10}", args.filings_cik):
        parser.error("CIK must contain 1 to 10 digits")
    try:
        if args.replay:
            bundle = json.loads(args.replay.read_text(encoding="utf-8"))
            # Preserve the original run id, inputs, evidence and timestamps on replay.
        elif args.refresh:
            bundle = refresh(
                json.loads(args.refresh.read_text(encoding="utf-8")),
                args.stage,
                market_type=args.market,
                allow_options=args.allow_options,
            )
        else:
            evidence = (
                ResearchEvidence.model_validate_json(
                    args.evidence.read_text(encoding="utf-8")
                )
                if args.evidence
                else ResearchEvidence()
            )
            if evidence.interpretations and not args.resume:
                raise ValueError(
                    "Interpretations require --resume and original run references"
                )
            bundle = (
                resume(json.loads(args.resume.read_text(encoding="utf-8")), evidence)
                if args.resume
                else run(
                    args.workflow,
                    market_type=args.market,
                    ticker=args.ticker,
                    allow_options=args.allow_options,
                    scan_fomo=args.scan_fomo,
                    evidence=evidence,
                    profile=args.profile or "standard",
                )
            )
        if args.filings_cik:
            from src.research.filing_catalog import fetch_sec_catalog

            bundle["sections"][args.ticker.strip().upper()]["filing_catalog"] = (
                fetch_sec_catalog(
                    args.ticker.strip().upper(),
                    args.filings_cik,
                    os.environ.get("SEC_USER_AGENT", ""),
                )
            )
        from uuid import uuid4

        if len(args.attach) > 20 or any(
            path.stat().st_size > 20 * 1024 * 1024 for path in args.attach
        ):
            raise ValueError("Up to 20 attachments, each at most 20MB")
        attached = [
            json.loads(path.read_text(encoding="utf-8")) for path in args.attach
        ]
        output = save_bundle(
            bundle, ROOT / ".states" / "research_runs" / str(uuid4()), attached
        )
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(
            f"Research failed: {type(exc).__name__}; check arguments/evidence schema.",
            file=sys.stderr,
        )
        return 2
    print(output)
    return 1 if bundle.get("execution_status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

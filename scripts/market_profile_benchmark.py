"""Opt-in free live benchmark. No options/FOMO/models/filing review/publication."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from collections import Counter
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.runner import run  # noqa: E402
from src.storage.atomic_json import write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--profile", choices=["standard", "advanced"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ["INVESTMENT_RESEARCH_NO_MODEL"] = "1"
    import requests
    from curl_cffi.requests import Session

    counts = Counter()
    lock = threading.Lock()
    originals = []
    for cls in (requests.sessions.Session, Session):
        original = cls.request
        originals.append((cls, original))

        def counted(self, method, url, *a, _original=original, **kw):
            with lock:
                counts[urlsplit(str(url)).hostname or "unknown"] += 1
            return _original(self, method, url, *a, **kw)

        cls.request = counted
    results = []
    try:
        for state in ("new_process_existing_persistent_cache", "same_process_warm"):
            with lock:
                counts.clear()
            start = perf_counter()
            bundle = run("overview", profile=args.profile)
            elapsed = perf_counter() - start
            with lock:
                requests_by_host = dict(counts)
            result = {
                "profile": args.profile,
                "cache_condition": state,
                "elapsed_seconds": round(elapsed, 3),
                "http_calls_observed_by_host": requests_by_host,
                "http_calls": sum(requests_by_host.values()),
                "input_diagnostics": bundle["sections"].get("diagnostics", {}),
                "limits": "No cache deletion. First run is process-cold, not guaranteed storage-cold. Hosts only; no URLs/headers/credentials logged. Background legacy requests may continue after stage timeout.",
            }
            results.append(result)
            write_json(args.output, {"runs": results})
            print(
                json.dumps(
                    {
                        k: result[k]
                        for k in (
                            "profile",
                            "cache_condition",
                            "elapsed_seconds",
                            "http_calls",
                        )
                    }
                ),
                flush=True,
            )
    finally:
        for cls, original in originals:
            cls.request = original
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

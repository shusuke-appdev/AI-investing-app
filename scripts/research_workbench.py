"""Start the local research entry point, without fetching or starting model APIs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.local_server import create_server  # noqa: E402


def main() -> int:
    os.environ["INVESTMENT_RESEARCH_NO_MODEL"] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Invalid local port")
    url = f"http://127.0.0.1:{args.port}/"
    try:
        server = create_server(ROOT, args.port)
    except OSError:
        try:
            with urlopen(url + "api/status", timeout=3) as response:
                existing = json.load(response)
            if existing.get("app") != "investment-research-workbench-v1":
                raise ValueError("Unrelated service")
        except (OSError, ValueError):
            if sys.stderr:
                print(
                    "Local port is in use by another service; use --port.",
                    file=sys.stderr,
                )
            return 2
        if args.open:
            webbrowser.open(url)
        return 0
    if args.open:
        webbrowser.open(url)
    if sys.stdout:
        print(url, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

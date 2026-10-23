"""Loopback-only, explicit-action research entry point; never serves repo files."""

from __future__ import annotations

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from src.research.workbench import Workbench

ASSET = Path(__file__).with_name("assets") / "workbench.html"


def create_server(root: Path, port: int = 8768) -> ThreadingHTTPServer:
    workbench = Workbench(root)
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, format, *args):
            pass  # No request text/secrets in logs.

        def allowed_host(self) -> bool:
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def respond(self, code: int, body: str, content_type: str = "application/json"):
            raw = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "frame-ancestors 'self'")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self.allowed_host():
                self.respond(403, "{}")
                return
            path = urlsplit(self.path).path
            if path == "/":
                body = ASSET.read_text(encoding="utf-8").replace("<!--TOKEN-->", token)
                self.respond(200, body, "text/html")
            elif path == "/api/status":
                status = workbench.snapshot_status()
                status["app"] = "investment-research-workbench-v1"
                self.respond(200, json.dumps(status, ensure_ascii=False))
            elif path == "/dashboard":
                self.respond(
                    200,
                    workbench.dashboard(
                        reload_saved="view=" in urlsplit(self.path).query
                    ),
                    "text/html",
                )
            elif path == "/favicon.ico":
                self.respond(204, "")
            else:
                self.respond(404, "{}")

        def do_POST(self):
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if (
                not self.allowed_host()
                or self.headers.get("Origin") != origin
                or not secrets.compare_digest(
                    self.headers.get("X-Research-Token", ""), token
                )
                or self.headers.get_content_type() != "application/json"
            ):
                self.respond(403, "{}")
                return
            if self.path != "/api/update":
                self.respond(404, "{}")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024 or self.headers.get("Transfer-Encoding"):
                    raise ValueError("Invalid body size")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or set(payload) not in (
                    {"scope"},
                    {"scope", "profile"},
                    {"scope", "profile", "mode"},
                ):
                    raise ValueError("Invalid action")
                accepted = workbench.begin(
                    payload["scope"],
                    payload.get("profile", "standard"),
                    **({"mode": payload["mode"]} if "mode" in payload else {}),
                )
            except (ValueError, TypeError):
                self.respond(400, "{}")
                return
            self.respond(202 if accepted else 409, json.dumps({"accepted": accepted}))

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server

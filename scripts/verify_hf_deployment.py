"""Verify that the intended private Hugging Face Space revision is healthy."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener


class VerificationError(RuntimeError):
    """Raised when the Space cannot be safely accepted as deployed."""


@dataclass(frozen=True)
class FetchResult:
    """A JSON HTTP response without credential-adjacent request details."""

    status: int
    payload: Any = None


@dataclass(frozen=True)
class VerificationResult:
    """The revision and health evidence accepted by the verifier."""

    expected_sha: str
    observed_sha: str
    runtime_stage: str
    health_status: int


FetchJson = Callable[[str, str], FetchResult]
Emit = Callable[[str], None]

_ASSIGNMENT_SECRET = re.compile(
    r"(?i)\b(authorization|token|secret|password|api[_-]?key)\s*[:=]\s*\S+"
)
_BEARER_SECRET = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+")
_KNOWN_SECRET = re.compile(
    r"(?i)\b(?:hf|sb_secret)_[A-Za-z0-9._~+/-]{6,}|\beyJ[A-Za-z0-9._~-]{12,}"
)


def sanitize_message(
    value: object,
    *,
    sensitive_values: Sequence[str] = (),
    limit: int = 800,
) -> str:
    """Return a single-line diagnostic with likely credentials removed."""

    message = " ".join(str(value).split())
    for sensitive in sensitive_values:
        if sensitive:
            message = message.replace(sensitive, "[REDACTED]")
    message = _BEARER_SECRET.sub("Bearer [REDACTED]", message)
    message = _ASSIGNMENT_SECRET.sub(r"\1=[REDACTED]", message)
    message = _KNOWN_SECRET.sub("[REDACTED]", message)
    return (message or "unavailable")[:limit]


def _decode_json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def fetch_json(url: str, token: str) -> FetchResult:
    """Fetch JSON with the token only in the Authorization header."""

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "ai-investing-app-deploy-verifier/1",
        },
    )
    try:
        opener = build_opener(_RejectRedirects)
        with opener.open(request, timeout=10) as response:  # noqa: S310
            return FetchResult(int(response.status), _decode_json(response.read()))
    except HTTPError as exc:
        try:
            payload = _decode_json(exc.read())
        except OSError:
            payload = None
        return FetchResult(int(exc.code), payload)
    except (OSError, TimeoutError):
        return FetchResult(0, None)


def _require_token(token: str) -> None:
    if not token:
        raise VerificationError("HF_TOKEN is not configured")


def _space_api_url(space: str) -> str:
    parts = space.split("/")
    if len(parts) != 2 or not all(parts):
        raise VerificationError("Space must use the owner/name format")
    encoded = "/".join(quote(part, safe="") for part in parts)
    return f"https://huggingface.co/api/spaces/{encoded}"


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return None


def _space_health_url(space: str) -> str:
    parts = space.split("/")
    if len(parts) != 2 or not all(parts):
        raise VerificationError("Space must use the owner/name format")
    host = "-".join(parts).lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", host):
        raise VerificationError(
            "Space name cannot be converted to a safe health origin"
        )
    return f"https://{host}.hf.space/_health"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _runtime_stage(space_info: Mapping[str, Any]) -> str:
    runtime = _mapping(space_info.get("runtime"))
    return str(runtime.get("stage") or space_info.get("stage") or "UNKNOWN")


def _runtime_error(
    space_info: Mapping[str, Any], *, sensitive_values: Sequence[str]
) -> str:
    runtime = _mapping(space_info.get("runtime"))
    for key in ("errorMessage", "error", "message"):
        if runtime.get(key):
            return sanitize_message(runtime[key], sensitive_values=sensitive_values)
    return "No runtime error detail was returned by the Hub API."


def _short_sha(value: object) -> str:
    text = str(value or "none")
    return text[:12]


def preflight_space(
    *,
    space: str,
    token: str,
    require_private: bool,
    fetch_space: FetchJson = fetch_json,
) -> Mapping[str, Any]:
    """Fail before a push if authentication or privacy is not ready."""

    _require_token(token)
    response = fetch_space(_space_api_url(space), token)
    if response.status != 200 or not isinstance(response.payload, Mapping):
        raise VerificationError(
            f"Space preflight failed via Hub API (HTTP {response.status})"
        )
    info = response.payload
    if require_private and info.get("private") is not True:
        raise VerificationError("Space preflight failed: Space is not private")
    return info


def verify_deployment(
    *,
    space: str,
    expected_sha: str,
    health_url: str | None,
    token: str,
    require_private: bool,
    timeout_seconds: float,
    poll_interval_seconds: float = 10,
    fetch_space: FetchJson = fetch_json,
    fetch_health: FetchJson = fetch_json,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    emit: Emit = print,
    force_staging_health_failure: bool = False,
    staging_failure_authorized: bool = False,
) -> VerificationResult:
    """Wait for the intended revision, then verify its authenticated health."""

    _require_token(token)
    if force_staging_health_failure and not staging_failure_authorized:
        raise VerificationError("Forced health failure lacks staging authorization")
    if not expected_sha:
        raise VerificationError("Expected Hugging Face revision is missing")
    derived_health_url = _space_health_url(space)
    if health_url and health_url != derived_health_url:
        raise VerificationError("Health URL must match the Space-derived HTTPS origin")
    health_url = derived_health_url
    if timeout_seconds < 0:
        raise VerificationError("Timeout must be zero or greater")
    if poll_interval_seconds <= 0:
        raise VerificationError("Poll interval must be greater than zero")

    deadline = monotonic() + timeout_seconds
    last_sha = "none"
    last_stage = "UNKNOWN"
    last_health = 0
    api_url = _space_api_url(space)

    while True:
        hub_response = fetch_space(api_url, token)
        info = _mapping(hub_response.payload)
        if hub_response.status == 200 and info:
            if require_private and info.get("private") is not True:
                raise VerificationError("Deployment rejected: Space is not private")

            last_sha = str(info.get("sha") or "none")
            last_stage = _runtime_stage(info)
            if last_sha == expected_sha:
                if last_stage == "RUNTIME_ERROR":
                    detail = _runtime_error(info, sensitive_values=(token,))
                    raise VerificationError(
                        f"Target revision entered RUNTIME_ERROR: {detail}"
                    )
                if last_stage == "RUNNING":
                    health_response = fetch_health(health_url, token)
                    last_health = health_response.status
                    health = _mapping(health_response.payload)
                    if last_health == 200 and health.get("status") is True:
                        if force_staging_health_failure:
                            raise VerificationError(
                                "Intentional staging health acceptance failure after "
                                "HTTP 200 status=true"
                            )
                        return VerificationResult(
                            expected_sha=expected_sha,
                            observed_sha=last_sha,
                            runtime_stage=last_stage,
                            health_status=last_health,
                        )
                    emit(
                        "Target revision is RUNNING but health is not ready "
                        f"(HTTP {last_health})."
                    )
                else:
                    emit(f"Target revision stage is {last_stage}; waiting.")
            else:
                emit(
                    "Waiting for target revision "
                    f"{_short_sha(expected_sha)}; Hub has {_short_sha(last_sha)}."
                )
        else:
            last_stage = f"HUB_HTTP_{hub_response.status}"
            emit(f"Hub API is not ready (HTTP {hub_response.status}); waiting.")

        now = monotonic()
        if now >= deadline:
            raise VerificationError(
                "Deployment verification timed out: "
                f"expected={_short_sha(expected_sha)}, "
                f"observed={_short_sha(last_sha)}, stage={last_stage}, "
                f"health_http={last_health}"
            )
        sleep(min(poll_interval_seconds, deadline - now))


def require_staging_failure_authorization(
    space: str, environment: Mapping[str, str]
) -> None:
    """Allow forced health failure only for an explicitly isolated staging Space."""

    staging_space = environment.get("HF_STAGING_SPACE_REPO", "")
    production_space = environment.get("HF_PRODUCTION_SPACE_REPO", "")
    if environment.get("HF_STAGING_ACCEPTANCE_ACK") != "1":
        raise VerificationError("Staging acceptance acknowledgement is missing")
    if not staging_space or not production_space:
        raise VerificationError(
            "Staging and production Space declarations are required"
        )
    if staging_space == production_space:
        raise VerificationError("Staging and production Spaces must be different")
    if space != staging_space:
        raise VerificationError("Forced health failure is limited to the staging Space")


def append_metadata(path: Path, values: Mapping[str, object]) -> None:
    """Append non-secret deployment evidence to the workflow artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for key, value in values.items():
            handle.write(f"{key}={sanitize_message(value)}\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space", required=True, help="Hugging Face owner/name")
    parser.add_argument("--expected-sha")
    parser.add_argument("--health-url")
    parser.add_argument("--require-private", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-interval-seconds", type=float, default=10)
    parser.add_argument("--metadata-path", type=Path)
    parser.add_argument(
        "--staging-force-health-failure",
        action="store_true",
        help="Fail after real health succeeds; requires staging-only environment guards.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Run the command-line verifier without accepting a token argument."""

    parser = _parser()
    args = parser.parse_args(argv)
    environment = os.environ if environ is None else environ
    token = environment.get(
        "HF_TOKEN" if args.preflight_only else "HF_SPACE_READ_TOKEN", ""
    )

    try:
        if args.staging_force_health_failure:
            if args.preflight_only:
                raise VerificationError(
                    "Forced staging health failure cannot be used for preflight"
                )
            require_staging_failure_authorization(args.space, environment)
        if args.preflight_only:
            info = preflight_space(
                space=args.space,
                token=token,
                require_private=args.require_private,
            )
            print(
                "Space preflight passed: "
                f"private={str(info.get('private') is True).lower()}."
            )
            return 0

        if not args.expected_sha:
            parser.error("--expected-sha is required after push")
        result = verify_deployment(
            space=args.space,
            expected_sha=args.expected_sha,
            health_url=args.health_url,
            token=token,
            require_private=args.require_private,
            timeout_seconds=args.timeout_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
            force_staging_health_failure=args.staging_force_health_failure,
            staging_failure_authorized=args.staging_force_health_failure,
        )
        if args.metadata_path:
            append_metadata(
                args.metadata_path,
                {
                    "observed_hf_commit": result.observed_sha,
                    "runtime_stage": result.runtime_stage,
                    "health_status": result.health_status,
                },
            )
        print(
            "Space deployment verified: "
            f"revision={_short_sha(result.observed_sha)}, "
            f"stage={result.runtime_stage}, health=200."
        )
        return 0
    except VerificationError as exc:
        safe_error = sanitize_message(exc, sensitive_values=(token,))
        if args.metadata_path:
            append_metadata(
                args.metadata_path,
                {"verification_result": "failed", "verification_error": safe_error},
            )
        print(f"ERROR: {safe_error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

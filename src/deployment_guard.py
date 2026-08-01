"""Fail closed when the personal application is started on an unapproved host."""

from __future__ import annotations

import os

PRIVATE_DEPLOYMENT_ACK = "PRIVATE_DEPLOYMENT_ACK"


def hosted_environment_detected() -> bool:
    """Return whether a known hosted runtime is active."""

    return bool(os.getenv("SPACE_ID", "").strip())


def private_deployment_acknowledged() -> bool:
    """Return whether external access control was explicitly acknowledged."""

    return os.getenv(PRIVATE_DEPLOYMENT_ACK, "").strip() == "1"


def require_safe_deployment() -> None:
    """Allow local runs and reject hosted runs without an access-control ack."""

    if hosted_environment_detected() and not private_deployment_acknowledged():
        raise RuntimeError(
            "Hosted personal deployment requires PRIVATE_DEPLOYMENT_ACK=1 after "
            "external access control has been verified."
        )

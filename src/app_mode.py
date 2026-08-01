"""Compatibility helpers for the single personal application mode."""

from __future__ import annotations

from typing import Literal

from src.deployment_guard import (
    hosted_environment_detected,
    private_deployment_acknowledged,
    require_safe_deployment,
)

AppMode = Literal["personal"]


def get_app_mode() -> AppMode:
    require_safe_deployment()
    return "personal"


def app_capability_summary() -> dict[str, str | bool]:
    """Return a non-secret summary of the active deployment policy."""

    mode = get_app_mode()
    return {
        "mode": mode,
        "personal_data": True,
        "ai_generation": True,
        "external_content_fetch": True,
        "hosted_environment": hosted_environment_detected(),
        "private_deployment_acknowledged": private_deployment_acknowledged(),
    }


def writes_enabled() -> bool:
    require_safe_deployment()
    return True


def personal_data_enabled() -> bool:
    """Return whether personal portfolio, plan, and knowledge data may be read."""

    require_safe_deployment()
    return True


def ai_generation_enabled() -> bool:
    """Return whether server-funded AI generation may be invoked."""

    require_safe_deployment()
    return True


def external_content_fetch_enabled() -> bool:
    """Return whether users may ask the server to fetch arbitrary external content."""

    require_safe_deployment()
    return True


def require_writes_enabled() -> None:
    require_safe_deployment()


def require_personal_data_enabled() -> None:
    require_safe_deployment()


def require_ai_generation_enabled() -> None:
    require_safe_deployment()


def require_external_content_fetch_enabled() -> None:
    require_safe_deployment()

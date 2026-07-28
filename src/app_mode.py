"""Deployment-mode policy for personal data and write operations."""

from __future__ import annotations

import os
from typing import Literal, cast

AppMode = Literal["private", "public_readonly"]
PRIVATE_DEPLOYMENT_ACK = "PRIVATE_DEPLOYMENT_ACK"


def hosted_environment_detected() -> bool:
    """Return whether the app is running inside a known hosted runtime."""

    return bool(os.getenv("SPACE_ID", "").strip())


def private_deployment_acknowledged() -> bool:
    """Return whether hosted private mode was explicitly approved."""

    return os.getenv(PRIVATE_DEPLOYMENT_ACK, "").strip() == "1"


def get_app_mode() -> AppMode:
    # Missing deployment configuration must never expose personal data or
    # server-funded features. Local/private use remains an explicit opt-in.
    value = os.getenv("APP_MODE", "public_readonly").strip().lower()
    if value not in {"private", "public_readonly"}:
        raise ValueError("APP_MODE must be 'private' or 'public_readonly'.")
    if (
        value == "private"
        and hosted_environment_detected()
        and not private_deployment_acknowledged()
    ):
        raise RuntimeError(
            "Hosted APP_MODE=private requires PRIVATE_DEPLOYMENT_ACK=1 and "
            "external access control."
        )
    return cast(AppMode, value)


def app_capability_summary() -> dict[str, str | bool]:
    """Return a non-secret summary of the active deployment policy."""

    mode = get_app_mode()
    enabled = mode == "private"
    return {
        "mode": mode,
        "explicitly_configured": bool(os.getenv("APP_MODE", "").strip()),
        "personal_data": enabled,
        "ai_generation": enabled,
        "external_content_fetch": enabled,
        "hosted_environment": hosted_environment_detected(),
        "private_deployment_acknowledged": private_deployment_acknowledged(),
    }


def writes_enabled() -> bool:
    return get_app_mode() == "private"


def personal_data_enabled() -> bool:
    """Return whether personal portfolio, plan, and knowledge data may be read."""

    return get_app_mode() == "private"


def ai_generation_enabled() -> bool:
    """Return whether server-funded AI generation may be invoked."""

    return get_app_mode() == "private"


def external_content_fetch_enabled() -> bool:
    """Return whether users may ask the server to fetch arbitrary external content."""

    return get_app_mode() == "private"


def require_writes_enabled() -> None:
    if not writes_enabled():
        raise PermissionError(
            "公開読み取り専用モードでは個人データの保存・更新・削除はできません。"
        )


def require_personal_data_enabled() -> None:
    if not personal_data_enabled():
        raise PermissionError(
            "公開読み取り専用モードでは個人データを読み込むことはできません。"
        )


def require_ai_generation_enabled() -> None:
    if not ai_generation_enabled():
        raise PermissionError("公開読み取り専用モードではAI生成を利用できません。")


def require_external_content_fetch_enabled() -> None:
    if not external_content_fetch_enabled():
        raise PermissionError(
            "公開読み取り専用モードではURL・YouTubeコンテンツを取得できません。"
        )

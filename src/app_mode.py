"""Deployment-mode policy for personal data and write operations."""

from __future__ import annotations

import os
from typing import Literal, cast

AppMode = Literal["private", "public_readonly"]


def get_app_mode() -> AppMode:
    value = os.getenv("APP_MODE", "private").strip().lower()
    if value not in {"private", "public_readonly"}:
        raise ValueError("APP_MODE must be 'private' or 'public_readonly'.")
    return cast(AppMode, value)


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

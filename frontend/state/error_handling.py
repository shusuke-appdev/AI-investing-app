"""Safe user-facing error messages for Reflex state handlers."""

from __future__ import annotations

import logging
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserFacingError:
    """Stable error metadata safe to expose in the UI."""

    code: str
    message: str
    retryable: bool


def user_facing_error(action: str, exc: Exception) -> UserFacingError:
    """Classify an exception without exposing provider or credential details."""

    if isinstance(exc, TimeoutError):
        return UserFacingError(
            code="timeout",
            message=f"{action}が時間内に完了しませんでした。時間をおいて再試行してください。",
            retryable=True,
        )
    if isinstance(exc, PermissionError):
        return UserFacingError(
            code="permission_denied",
            message=f"{action}に必要な権限を確認できませんでした。設定を確認してください。",
            retryable=False,
        )
    if isinstance(exc, (ConnectionError, OSError)):
        return UserFacingError(
            code="connection_error",
            message=f"{action}で接続エラーが発生しました。時間をおいて再試行してください。",
            retryable=True,
        )
    if isinstance(exc, ValueError):
        return UserFacingError(
            code="invalid_response",
            message=f"{action}で利用できる形式のデータを確認できませんでした。",
            retryable=True,
        )
    return UserFacingError(
        code="unexpected_error",
        message=f"{action}に失敗しました。時間をおいて再試行してください。",
        retryable=True,
    )


def log_state_exception(
    logger: logging.Logger,
    operation: str,
    exc: Exception,
) -> UserFacingError:
    """Log full diagnostics server-side and return the safe UI representation."""

    error = user_facing_error(operation, exc)
    logger.exception("%s failed [error_code=%s]", operation, error.code)
    return error

"""
ログ設定モジュール
アプリケーション全体の統一ログ設定を提供します。
"""
import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """
    名前付きロガーを取得します。

    Args:
        name: ロガー名（通常は ``__name__``）

    Returns:
        設定済み logging.Logger インスタンス
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

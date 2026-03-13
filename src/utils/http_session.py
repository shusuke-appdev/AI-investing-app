"""
HTTPセッションユーティリティ
yfinance用の一貫したセッションを提供します。
"""

import requests


def get_yf_session():
    """yfinance用の共通セッション（User-Agent指定でStreamlit CloudでのIPブロックを回避）"""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
    )
    return session

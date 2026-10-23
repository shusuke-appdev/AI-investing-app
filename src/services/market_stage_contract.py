"""Shared orchestration values; imports no facade, workflow or UI module."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

MARKET_CONTEXT_CACHE_NAMESPACE = "market_context_cache"
MARKET_STAGE_TASK_TIMEOUT_SECONDS = 10.0
MARKET_STAGE_TOTAL_TIMEOUT_SECONDS = 20.0
MARKET_STAGE_EXECUTORS = {
    workers: ThreadPoolExecutor(
        max_workers=workers, thread_name_prefix=f"market-stage-{workers}"
    )
    for workers in (2, 7)
}
DETAIL_STAGE_ORDER = (
    "core",
    "theme_flow",
    "volatility_sentiment",
    "credit_distortion",
    "options",
)
DETAIL_STAGE_DEFAULTS = {
    "core": {
        "label": "Core: 市場概要/キャッシュ",
        "difficulty": "低",
        "target": "主要指数、設定、前回成功キャッシュ",
        "summary": "主要指数と前回成功した監視結果を先に表示します。",
    },
    "theme_flow": {
        "label": "Theme/Flow: 市場状態/資金流入",
        "difficulty": "中",
        "target": "IBD式市場状態、モメンタム、統合トレンド、セクター/テーマ資金流入",
        "summary": "IBD式市場状態、モメンタム、ETF proxy、セクター資金流入を更新します。",
    },
    "volatility_sentiment": {
        "label": "Vol/Sentiment: ボラ/センチメント",
        "difficulty": "中",
        "target": "ボラティリティ、1/5/20日短期予測、複合センチメント、時間軸別方向感",
        "summary": "ボラティリティ、検証付き短期予測、複合センチメントを更新します。",
    },
    "credit_distortion": {
        "label": "Credit/Risk: 信用/歪み/天井警戒",
        "difficulty": "高",
        "target": "FRED信用ストレス、市場の歪み検知、天井警戒サインポスト",
        "summary": "FRED信用ストレス、市場の歪み検知、天井警戒サインポストを更新します。",
    },
    "options": {
        "label": "高: オプション",
        "difficulty": "高",
        "target": "SPY/QQQ/IWMと上位テーマETF proxyのPCR、IV、Greeks、GEX可否",
        "summary": "主要ETFのオプション分析を更新します。",
    },
}


@dataclass(frozen=True)
class StageTaskResult:
    value: Any = None
    status: str = "ok"
    error: str = ""
    timed_out: bool = False

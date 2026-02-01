from dataclasses import dataclass
from typing import Optional

@dataclass
class PortfolioHolding:
    """ポートフォリオ保有銘柄"""
    ticker: str
    shares: float
    avg_cost: Optional[float] = None


@dataclass
class TechnicalScore:
    """テクニカル分析スコア"""
    rsi: float  # 0-100
    rsi_signal: str  # 買われすぎ/売られすぎ/中立
    ma_deviation: float  # 移動平均乖離率
    ma_signal: str  # 上方乖離/下方乖離/中立
    macd_signal: str  # 強気/弱気/中立
    overall_score: int  # -100 to 100
    overall_signal: str  # 強気/弱気/中立

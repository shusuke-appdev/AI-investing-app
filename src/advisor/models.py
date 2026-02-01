from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PortfolioHolding:
    """ポートフォリオ保有銘柄"""
    ticker: str
    shares: float
    avg_cost: Optional[float] = None


@dataclass
class TechnicalScore:
    """テクニカル分析スコア（拡張版）"""
    # RSI
    rsi: float  # 0-100
    rsi_signal: str  # 買われすぎ/売られすぎ/中立
    
    # 移動平均
    ma_deviation: float  # 50日MA乖離率
    ma_signal: str  # 上方乖離/下方乖離/中立
    ma_trend: str  # 上昇/下降/横ばい (20>50>200なら上昇)
    
    # MACD
    macd_signal: str  # 強気/弱気/中立
    
    # ボリンジャーバンド
    bb_position: str  # 上限突破/下限突破/中間
    bb_width: float  # バンド幅（ボラティリティ指標）
    
    # ATR（ボラティリティ）
    atr: float  # ATR値
    atr_percent: float  # ATR / 現在価格 (%)
    
    # サポート/レジスタンス
    support_price: float  # 直近サポート価格
    resistance_price: float  # 直近レジスタンス価格
    
    # 総合判断
    overall_score: int  # -100 to 100
    overall_signal: str  # 強気/弱気/中立
    
    # 逆張り買いゾーン
    contrarian_buy_zone: tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))  # (下限, 上限)
    contrarian_signal: str = ""  # "買い検討ゾーン" / "様子見" / "過熱警戒"


@dataclass
class TechnicalAnalysis:
    """AI用テクニカル分析サマリー"""
    ticker: str
    score: TechnicalScore
    summary: str  # AI生成サマリー
    recommendation: str  # 買い/売り/ホールド
    target_buy_price: Optional[float] = None  # 推奨買い価格
    stop_loss_price: Optional[float] = None  # 損切りライン

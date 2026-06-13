from dataclasses import dataclass, field
from typing import Any, TypedDict


class MinerviniStageResult(TypedDict):
    stage: int
    description: str


class MinerviniVcpResult(TypedDict, total=False):
    is_vcp: bool
    contractions: int
    breakout_price: float
    points: list[dict[str, Any]]
    current_price: float


class MinerviniFtdResult(TypedDict, total=False):
    is_ftd: bool
    status: str
    days_since_bottom: int
    pct_change: float


class MeanReversionParabolicState(TypedDict, total=False):
    is_parabolic: bool
    description: str
    deviation_10ma: float | None
    deviation_20ma: float | None
    target_reversion_price: float | None


class MeanReversionReboundState(TypedDict, total=False):
    is_dip_buyable: bool
    is_perfect_order: bool
    description: str
    near_support: str


class MeanReversionResult(TypedDict, total=False):
    ticker: str
    current_price: float
    parabolic_state: MeanReversionParabolicState
    rebound_state: MeanReversionReboundState
    ma_10: float | None
    ma_20: float | None
    ma_50: float | None
    error: str


@dataclass
class PortfolioHolding:
    """ポートフォリオ保有銘柄"""

    ticker: str
    shares: float
    avg_cost: float | None = None


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
    overall_score: int  # 0 to 100
    overall_signal: str  # 強気/弱気/中立

    # 逆張り買いゾーン
    contrarian_buy_zone: tuple[float, float] = field(
        default_factory=lambda: (0.0, 0.0)
    )  # (下限, 上限)
    contrarian_signal: str = ""  # "買い検討ゾーン" / "様子見" / "過熱警戒"

    # === 拡張指標 ===

    # OBV (On Balance Volume)
    obv_trend: str = ""  # 上昇/下降/横ばい
    obv_divergence: str = ""  # bullish/bearish/none

    # ADX (Average Directional Index)
    adx: float = 0.0  # 0-100, >25でトレンド強い
    adx_signal: str = ""  # 強トレンド/弱トレンド/レンジ

    # Stochastic RSI
    stoch_rsi: float = 50.0  # 0-100
    stoch_rsi_signal: str = ""  # 買われすぎ/売られすぎ/中立

    # フィボナッチ・リトレースメント
    fib_levels: dict = field(default_factory=dict)  # {0.236: price, 0.382: price, ...}
    fib_nearest_level: str = ""  # 最寄りのフィボナッチレベル

    # 複数タイムフレーム分析
    mtf_alignment: str = ""  # aligned_bullish/aligned_bearish/mixed
    mtf_details: dict = field(
        default_factory=dict
    )  # {daily: signal, weekly: signal, monthly: signal}

    # モメンタムダイバージェンス
    divergence_rsi: str = ""  # bullish/bearish/none
    divergence_macd: str = ""  # bullish/bearish/none

    # === Phase 1 拡張 ===

    # MACD高度化
    macd_hist_slope: str = ""  # rising/falling/bottoming/topping
    macd_zero_filter: str = ""  # above_zero/below_zero

    # 動的RSI (レジーム別閾値)
    rsi_regime: str = ""  # bullish_regime/bearish_regime
    rsi_dynamic_signal: str = ""  # 動的閾値での判定結果

    # BBスクイズ
    bb_squeeze: bool = False  # スクイズ状態か否か
    bb_squeeze_signal: str = ""  # squeeze/expansion/normal

    # 一目均衡表
    ichimoku_regime: str = ""  # above_cloud/below_cloud/in_cloud
    ichimoku_sannyaku: bool = False  # 三役好転
    ichimoku_signal: str = ""  # 強気/弱気/中立

    # === Phase 2 拡張 ===

    # Anchored VWAP
    avwap_ytd: float = 0.0  # 年初来AVWAP
    avwap_deviation: float = 0.0  # AVWAP乖離率(%)

    # GEX環境
    # GEX環境
    gex_regime: str = ""  # positive_gamma/negative_gamma/unknown
    gex_positive_wall: float = 0.0  # 上値抵抗(Gamma Wall)
    gex_negative_wall: float = 0.0  # 下値支持(Gamma Wall)

    # オプション需給
    pcr_ratio: float = 0.0  # Put/Call Ratio (Open Interest)
    pcr_signal: str = ""  # 強気/弱気/中立
    atm_iv: float = 0.0  # ATM Implied Volatility
    max_pain: float = 0.0  # Max Pain Price
    option_data_available: bool = False

    # === Phase 3 拡張 ===

    # 極値検出
    recent_peaks: list = field(default_factory=list)  # [(index, price), ...]
    recent_valleys: list = field(default_factory=list)  # [(index, price), ...]
    peak_valley_signal: str = ""  # higher_highs/lower_lows/range/unknown

    # ローソク足パターン
    candlestick_patterns: list = field(
        default_factory=list
    )  # [{"name": str, "signal": int}, ...]
    candlestick_summary: str = ""  # bullish/bearish/neutral

    # === Minervini Extension ===
    stage_data: MinerviniStageResult = field(
        default_factory=lambda: {"stage": 0, "description": ""}
    )
    vcp_data: MinerviniVcpResult = field(default_factory=dict)

    # === Option Skew & Mean Reversion Extension ===
    skew: float | None = None
    dte: float | None = None
    price_range: tuple[float, float] | None = None

    mr_parabolic_state: MeanReversionParabolicState = field(
        default_factory=lambda: MeanReversionParabolicState()
    )
    mr_rebound_state: MeanReversionReboundState = field(
        default_factory=lambda: MeanReversionReboundState()
    )

    # === Extended Technical Breakdown (Dip Buy & Climax) ===
    pinbar_data: dict = field(default_factory=dict)
    volume_climax_bleed_data: dict = field(default_factory=dict)
    advanced_patterns_data: dict = field(default_factory=dict)
    ma_long_term_data: dict = field(default_factory=dict)

    # === Analysis Mode & New Indicators ===
    analysis_mode: str = ""
    ma_10: float | None = None
    ma_20: float | None = None
    ma_50: float | None = None
    ma_200: float | None = None
    base_recognition_data: dict = field(default_factory=dict)
    entry_signal: str = ""
    stop_loss: float | None = None
    profit_line: float | None = None


@dataclass
class TechnicalAnalysis:
    """AI用テクニカル分析サマリー"""

    ticker: str
    score: TechnicalScore
    summary: str  # AI生成サマリー
    recommendation: str  # 買い/売り/ホールド
    target_buy_price: float | None = None  # 推奨買い価格
    stop_loss_price: float | None = None  # 損切りライン

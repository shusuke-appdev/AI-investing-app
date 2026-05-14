import asyncio
from typing import Any

import reflex as rx
from pydantic import BaseModel

from src.advisor.market_environment import evaluate_market_environment
from src.advisor.market_monitor import (
    detect_market_climax,
    evaluate_yield_spread,
    track_distribution_days,
)
from src.market_config import get_market_config
from src.market_data import get_market_indices, get_stock_data, get_stock_info
from src.market_microstructure import analyze_market_structure
from src.momentum_monitor import get_momentum_themes
from src.option_analyst import get_major_indices_options
from src.services.market_analyst_service import generate_market_analysis_report


class MarketSignal(BaseModel):
    name: str = ""
    score: float = 0.0
    weight: float = 0.0
    rationale: str = ""
    category: str = "neutral"  # "bullish" / "neutral" / "bearish"


class OptionSummary(BaseModel):
    ticker: str = ""
    sentiment: str = "中立"
    current_price: float = 0.0
    pcr_vol: float = 0.0
    pcr_vol_str: str = ""
    net_gex: float = 0.0
    net_gex_str: str = ""
    iv: str = "-"
    max_pain: str = "-"
    analysis: list[str] = []


class MicrostructureData(BaseModel):
    """マイクロストラクチャー分析データ"""

    unwind_score: int = 0
    unwind_level: str = ""
    vrp: str = "-"
    cta_score: int = 0
    cta_extremity: str = ""
    liquidity_status: str = ""
    narrative: str = ""


class MomentumTheme(BaseModel):
    """モメンタムテーマデータ"""

    theme: str = ""
    performance: float = 0.0
    performance_str: str = ""


class MomentumCategory(BaseModel):
    """モメンタムカテゴリデータ"""

    category: str = ""
    period: str = ""
    themes: list[MomentumTheme] = []


class DistributionData(BaseModel):
    count: int = 0
    status: str = ""
    level: str = "normal"


class ClimaxData(BaseModel):
    is_climax: bool = False
    warnings: list[str] = []
    level: str = "normal"


class SpreadItem(BaseModel):
    earnings_yield: float = 0.0
    spread: float = 0.0
    status: str = "neutral"


class Spreads(BaseModel):
    SPY: SpreadItem = SpreadItem()
    NDX: SpreadItem = SpreadItem()


class YieldSpreadData(BaseModel):
    yield_10y: float = 0.0
    spreads: Spreads = Spreads()
    overall_status: str = "neutral"
    warnings: list[str] = []


class MarketMonitorData(BaseModel):
    """市場監視データ"""

    distribution_spy: DistributionData = DistributionData()
    distribution_ndx: DistributionData = DistributionData()
    climax: ClimaxData = ClimaxData()
    yield_spread: YieldSpreadData = YieldSpreadData()


class MarketState(rx.State):
    """マーケット（市況）ページ用の状態管理クラス"""

    market_type: str = "US"
    is_fetching: bool = False
    error_msg: str = ""
    option_error_msg: str = ""  # オプション専用エラー

    # UI表示用の整形済みデータリスト
    indices_data: list[dict[str, Any]] = []
    sectors_data: list[dict[str, Any]] = []
    others_data: list[dict[str, Any]] = []

    # 市場環境の評価結果
    evaluation: dict[str, Any] = {}
    market_signals: list[MarketSignal] = []

    # マイクロストラクチャー分析
    microstructure: MicrostructureData = MicrostructureData()

    # オプション分析データ
    option_analysis: list[OptionSummary] = []

    # テーマモメンタム監視
    momentum_data: list[MomentumCategory] = []

    # 市場監視機能 (Phase 3)
    market_monitor: MarketMonitorData = MarketMonitorData()

    # AIレポート関連
    ai_recap: str = ""
    is_generating_recap: bool = False

    def set_market_type(self, m_type: str):
        """対象市場の切り替え（US / JP）"""
        self.market_type = m_type
        # 切り替えたら即座に再取得
        return MarketState.fetch_market_data

    async def fetch_market_data(self):
        """外部APIから市場データを取得する"""
        self.is_fetching = True
        self.error_msg = ""
        self.option_error_msg = ""
        yield

        try:
            # 同期ブロッキング関数をバックグラウンドスレッドで実行
            raw_data_task = asyncio.to_thread(get_market_indices, self.market_type)
            config_task = asyncio.to_thread(get_market_config, self.market_type)

            # オプションデータは分離して取得（失敗しても他に影響しない）
            option_data_task = asyncio.to_thread(
                get_major_indices_options, self.market_type
            )

            # 指数・設定は必須、オプションは失敗許容
            raw_data, config = await asyncio.gather(raw_data_task, config_task)

            # オプションデータは個別にエラーハンドリング
            option_data = None
            try:
                option_data = await option_data_task
            except Exception as opt_e:
                self.option_error_msg = f"オプションデータの取得に失敗しました: {opt_e}"

            # Format option data for UI
            opt_list = []
            if option_data:
                for opt in option_data:
                    iv_val = opt.get("iv")
                    mp_val = opt.get("max_pain")
                    pcr_dict = opt.get("pcr") or {}
                    gex_dict = opt.get("gex") or {}
                    pcr_val = float(pcr_dict.get("volume_pcr", 0.0))
                    gex_val = float(gex_dict.get("nearby_net_gex", 0.0))
                    opt_list.append(
                        OptionSummary(
                            ticker=opt.get("ticker", ""),
                            sentiment=opt.get("sentiment", "中立"),
                            current_price=opt.get("current_price", 0.0),
                            pcr_vol=pcr_val,
                            pcr_vol_str=f"{pcr_val:.2f}",
                            net_gex=gex_val,
                            net_gex_str=f"{gex_val / 1e6:+.0f}M",
                            iv=f"{iv_val * 100:.1f}%" if iv_val is not None else "-",
                            max_pain=f"${mp_val:.0f}" if mp_val is not None else "-",
                            analysis=opt.get("analysis", []),
                        )
                    )
            elif not self.option_error_msg:
                self.option_error_msg = (
                    "市場閉場中のため最新のオプションデータがありません"
                )

            self.option_analysis = opt_list

            # 残りの重い分析タスクを並行実行
            eval_task = asyncio.to_thread(
                evaluate_market_environment, self.market_type, option_data
            )
            micro_task = asyncio.to_thread(self._fetch_microstructure)
            momentum_task = asyncio.to_thread(self._fetch_momentum)
            monitor_task = asyncio.to_thread(self._fetch_market_monitor, option_data)

            eval_res, micro_res, momentum_res, monitor_res = await asyncio.gather(
                eval_task,
                micro_task,
                momentum_task,
                monitor_task,
                return_exceptions=True,
            )

            # 評価データの反映
            if not isinstance(eval_res, Exception) and eval_res:
                eval_data = eval_res
            else:
                eval_data = {}

            # マイクロストラクチャーの反映
            if not isinstance(micro_res, Exception) and micro_res:
                self.microstructure = MicrostructureData(**micro_res)

            # モメンタムの反映
            if not isinstance(momentum_res, Exception) and momentum_res:
                self.momentum_data = momentum_res

            # 市場監視の反映
            if not isinstance(monitor_res, Exception) and monitor_res:
                self.market_monitor = MarketMonitorData(**monitor_res)

            # データをカテゴライズしてリスト化
            indices_list = []
            sectors_list = []
            commodities_list = []
            forex_list = []
            crypto_list = []

            idx_tickers = set(config["indices"].values())
            sec_tickers = set(config.get("sectors", {}).values())
            commodity_tickers = set(config.get("commodities", {}).values())
            crypto_tickers = set(config.get("crypto", {}).values())
            forex_tickers = set(config.get("forex", {}).values())

            # 日本市場の特別対応
            if self.market_type == "JP":
                jp_names = ["日経平均", "TOPIX"]
                for name in jp_names:
                    if name in raw_data:
                        d = raw_data[name]
                        change_rounded = round(float(d.get("change", 0.0)), 1)
                        indices_list.append(
                            {
                                "name": name,
                                "price": f"¥{d.get('price', 0):,.0f}",
                                "change": change_rounded,
                            }
                        )

            for name, data in raw_data.items():
                if name in ("trend_1mo", "weekly_performance"):
                    continue
                ticker = data.get("ticker", "")
                price = data.get("price", 0.0)
                change = data.get("change", 0.0)
                change_rounded = round(float(change), 1)

                item = {"name": name, "change": change_rounded}

                if ticker in idx_tickers and self.market_type != "JP":
                    if "VIX" in name:
                        item["price"] = f"{price:.2f}"
                    elif "Yield" in name:
                        item["price"] = f"{price:.2f}%"
                    else:
                        item["price"] = f"{price:,.0f}"
                    indices_list.append(item)
                elif ticker in sec_tickers:
                    item["price"] = f"${price:.2f}"
                    sectors_list.append(item)
                elif ticker in commodity_tickers:
                    if "Gold" in name:
                        item["price"] = f"${price:,.0f}"
                    elif "Silver" in name:
                        item["price"] = f"${price:,.2f}"
                    else:
                        item["price"] = f"${price:.2f}"
                    commodities_list.append(item)
                elif ticker in forex_tickers:
                    if "JPY" in name:
                        item["price"] = f"¥{price:.2f}"
                    else:
                        item["price"] = f"${price:.4f}"
                    forex_list.append(item)
                elif ticker in crypto_tickers:
                    item["price"] = f"${price / 1000:.1f}K"
                    crypto_list.append(item)

            # others_data: Commodity → FX → Crypto の順序
            self.indices_data = indices_list
            self.sectors_data = sectors_list
            self.others_data = commodities_list + forex_list + crypto_list
            self.evaluation = eval_data

            # シグナルにカテゴリを付与して抽出
            if "signals" in eval_data:
                self.market_signals = [
                    MarketSignal(
                        name=s.get("name", ""),
                        score=float(s.get("score", 0.0)),
                        weight=float(s.get("weight", 0.0)),
                        rationale=s.get("rationale", ""),
                        category="bullish"
                        if float(s.get("score", 0.0)) >= 0.3
                        else "bearish"
                        if float(s.get("score", 0.0)) <= -0.3
                        else "neutral",
                    )
                    for s in eval_data["signals"]
                ]
            else:
                self.market_signals = []

        except Exception as e:
            self.error_msg = f"データの取得に失敗しました: {str(e)}"
            self.indices_data = []
            self.sectors_data = []
            self.others_data = []
            self.option_analysis = []
            self.market_signals = []
        finally:
            self.is_fetching = False
            yield

    def _fetch_microstructure(self) -> dict | None:
        """マイクロストラクチャー分析データを取得"""
        try:
            data = analyze_market_structure("SPY")
            if not data:
                return None

            cta = data.get("cta_proxy") or {}
            liq = data.get("liquidity") or {}
            vrp_val = data.get("vrp")

            return {
                "unwind_score": data.get("unwind_score", 0),
                "unwind_level": data.get("unwind_level", ""),
                "vrp": f"{vrp_val:.2%}" if vrp_val is not None else "-",
                "cta_score": cta.get("score", 0),
                "cta_extremity": cta.get("extremity", ""),
                "liquidity_status": liq.get("status", ""),
                "narrative": data.get("narrative_text", ""),
            }
        except Exception:
            return None

    def _fetch_momentum(self) -> list[MomentumCategory]:
        """テーマモメンタムデータを取得"""
        try:
            raw = get_momentum_themes(self.market_type)
            result = []
            for cat_name, themes in raw.items():
                theme_list = []
                for t in themes:
                    perf = float(t.get("performance", 0.0))
                    theme_list.append(
                        MomentumTheme(
                            theme=t.get("theme", ""),
                            performance=perf,
                            performance_str=f"{perf:+.1f}%",
                        )
                    )
                period_str = themes[-1].get("period", "") if themes else ""
                result.append(
                    MomentumCategory(
                        category=cat_name, period=period_str, themes=theme_list
                    )
                )
            return result
        except Exception:
            return []

    def _fetch_market_monitor(self, option_data: list[dict] | None) -> dict | None:
        """市場監視データを取得"""
        try:
            spy_df = get_stock_data("SPY", "6mo")
            ndx_df = get_stock_data("^NDX", "6mo")

            dist_spy = track_distribution_days(spy_df)
            dist_ndx = track_distribution_days(ndx_df)

            opt_pcr = 0.8
            if option_data and len(option_data) > 0:
                pcr_dict = option_data[0].get("pcr", {})
                if pcr_dict:
                    opt_pcr = float(pcr_dict.get("volume_pcr", 0.8))

            climax = detect_market_climax(spy_df, ndx_df, opt_pcr)

            tnx_df = get_stock_data("^TNX", "5d")
            tnx_yield = (
                float(tnx_df["Close"].iloc[-1]) / 10.0 if not tnx_df.empty else 4.0
            )

            spy_info = get_stock_info("SPY")
            qqq_info = get_stock_info("QQQ")
            spy_pe = (
                spy_info.get("pe_ratio")
                if spy_info and isinstance(spy_info.get("pe_ratio"), (int, float))
                else 22.0
            )
            ndx_pe = (
                qqq_info.get("pe_ratio")
                if qqq_info and isinstance(qqq_info.get("pe_ratio"), (int, float))
                else 30.0
            )
            index_pe = {"SPY": float(spy_pe), "NDX": float(ndx_pe)}

            spread = evaluate_yield_spread(tnx_yield, index_pe)

            return {
                "distribution_spy": dist_spy,
                "distribution_ndx": dist_ndx,
                "climax": climax,
                "yield_spread": spread,
            }
        except Exception:
            return None

    async def generate_ai_recap(self):
        """GeminiによるAI市況レポート生成"""
        self.is_generating_recap = True
        yield

        try:
            recap = await asyncio.to_thread(
                generate_market_analysis_report, self.market_type
            )

            if recap:
                self.ai_recap = recap
            else:
                self.error_msg = "レポートの生成に失敗しました。"
        except Exception as e:
            self.error_msg = f"AI Recap 生成エラー: {e}"
        finally:
            self.is_generating_recap = False
            yield

import asyncio
from typing import Any

import reflex as rx
from pydantic import BaseModel

from src.services.market_analyst_service import generate_market_analysis_report
from src.services.market_dashboard_service import build_market_context


class MarketSignal(BaseModel):
    name: str = ""
    score: float = 0.0
    weight: float = 0.0
    rationale: str = ""
    category: str = "neutral"


class OptionSummary(BaseModel):
    ticker: str = ""
    sentiment: str = "Neutral"
    current_price: float = 0.0
    current_price_str: str = ""
    pcr_vol: float = 0.0
    pcr_vol_str: str = ""
    net_gex: float = 0.0
    net_gex_str: str = ""
    iv: str = "-"
    max_pain: str = "-"
    analysis: list[str] = []


class MicrostructureData(BaseModel):
    unwind_score: int = 0
    unwind_level: str = ""
    vrp: str = "-"
    cta_score: int = 0
    cta_extremity: str = ""
    liquidity_status: str = ""
    narrative: str = ""


class MomentumTheme(BaseModel):
    theme: str = ""
    performance: float = 0.0
    performance_str: str = ""


class MomentumCategory(BaseModel):
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
    level: str = "neutral"


class Spreads(BaseModel):
    SPY: SpreadItem = SpreadItem()
    NDX: SpreadItem = SpreadItem()


class YieldSpreadData(BaseModel):
    yield_10y: float = 0.0
    spreads: Spreads = Spreads()
    overall_status: str = "neutral"
    warnings: list[str] = []


class MarketMonitorData(BaseModel):
    distribution_spy: DistributionData = DistributionData()
    distribution_ndx: DistributionData = DistributionData()
    climax: ClimaxData = ClimaxData()
    yield_spread: YieldSpreadData = YieldSpreadData()


class MarketState(rx.State):
    """State for the Market Intelligence page."""

    market_type: str = "US"
    is_fetching: bool = False
    error_msg: str = ""
    option_error_msg: str = ""
    option_status: str = "unavailable"
    option_failed_tickers: list[str] = []

    indices_data: list[dict[str, Any]] = []
    sectors_data: list[dict[str, Any]] = []
    others_data: list[dict[str, Any]] = []

    evaluation: dict[str, Any] = {}
    market_signals: list[MarketSignal] = []
    microstructure: MicrostructureData = MicrostructureData()
    option_analysis: list[OptionSummary] = []
    momentum_data: list[MomentumCategory] = []
    market_monitor: MarketMonitorData = MarketMonitorData()

    ai_recap: str = ""
    is_generating_recap: bool = False
    market_context: dict[str, Any] = {}

    def set_market_type(self, m_type: str):
        self.market_type = m_type
        return MarketState.fetch_market_data

    async def fetch_market_data(self):
        self.is_fetching = True
        self.error_msg = ""
        self.option_error_msg = ""
        yield

        try:
            context = await asyncio.to_thread(build_market_context, self.market_type)
            self.market_context = context.to_dict()

            if context.options.error_message:
                self.option_error_msg = context.options.error_message
            self.option_status = context.options.status
            self.option_failed_tickers = list(context.options.failed_tickers)

            self.option_analysis = self._format_options(context.options.items)
            if not self.option_analysis and not self.option_error_msg:
                self.option_error_msg = "Option data is currently unavailable."

            self.evaluation = context.evaluation
            self.market_signals = self._format_signals(context.evaluation)

            micro = self._format_microstructure(context.microstructure)
            if micro:
                self.microstructure = MicrostructureData(**micro)

            self.momentum_data = self._format_momentum(context.momentum)

            if context.monitor:
                self.market_monitor = MarketMonitorData(**context.monitor)

            self._set_market_lists(context.market_data, context.market_config)
        except Exception as exc:
            self.error_msg = f"Failed to fetch market data: {exc}"
            self.indices_data = []
            self.sectors_data = []
            self.others_data = []
            self.option_analysis = []
            self.option_status = "failed"
            self.option_failed_tickers = []
            self.market_signals = []
        finally:
            self.is_fetching = False
            yield

    def _format_options(self, option_data: list[dict[str, Any]]) -> list[OptionSummary]:
        formatted = []
        for opt in option_data:
            pcr = opt.get("pcr") or {}
            gex = opt.get("gex") or {}
            pcr_val = float(pcr.get("volume_pcr", 0.0))
            gex_val = float(gex.get("nearby_net_gex", 0.0))
            current_price = float(opt.get("current_price") or 0.0)
            iv_val = opt.get("iv")
            max_pain = opt.get("max_pain")
            formatted.append(
                OptionSummary(
                    ticker=opt.get("ticker", ""),
                    sentiment=opt.get("sentiment", "Neutral"),
                    current_price=current_price,
                    current_price_str=f"${current_price:,.2f}"
                    if current_price > 0
                    else "",
                    pcr_vol=pcr_val,
                    pcr_vol_str=f"{pcr_val:.2f}",
                    net_gex=gex_val,
                    net_gex_str=f"{gex_val / 1e6:+.0f}M",
                    iv=f"{iv_val * 100:.1f}%" if iv_val is not None else "-",
                    max_pain=f"${max_pain:.0f}" if max_pain is not None else "-",
                    analysis=opt.get("analysis", []),
                )
            )
        return formatted

    def _format_signals(self, evaluation: dict[str, Any]) -> list[MarketSignal]:
        signals = []
        for signal in evaluation.get("signals", []):
            score = float(signal.get("score", 0.0))
            signals.append(
                MarketSignal(
                    name=signal.get("name", ""),
                    score=score,
                    weight=float(signal.get("weight", 0.0)),
                    rationale=signal.get("rationale", ""),
                    category="bullish"
                    if score >= 0.3
                    else "bearish"
                    if score <= -0.3
                    else "neutral",
                )
            )
        return signals

    def _format_microstructure(self, data: dict[str, Any]) -> dict[str, Any]:
        if not data:
            return {}
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

    def _format_momentum(
        self, raw: dict[str, list[dict[str, Any]]]
    ) -> list[MomentumCategory]:
        result = []
        for category, themes in raw.items():
            theme_list = []
            for item in themes:
                perf = float(item.get("performance", 0.0))
                theme_list.append(
                    MomentumTheme(
                        theme=item.get("theme", ""),
                        performance=perf,
                        performance_str=f"{perf:+.1f}%",
                    )
                )
            result.append(
                MomentumCategory(
                    category=category,
                    period=themes[-1].get("period", "") if themes else "",
                    themes=theme_list,
                )
            )
        return result

    def _set_market_lists(
        self, raw_data: dict[str, Any], config: dict[str, Any]
    ) -> None:
        indices_tickers = set(config.get("indices", {}).values())
        sector_tickers = set(config.get("sectors", {}).values())
        commodity_tickers = set(config.get("commodities", {}).values())
        crypto_tickers = set(config.get("crypto", {}).values())
        forex_tickers = set(config.get("forex", {}).values())

        indices = []
        sectors = []
        others = []
        for name, data in raw_data.items():
            if name in {"trend_1mo", "weekly_performance"}:
                continue
            item = self._market_item(name, data)
            ticker = data.get("ticker", "")
            if ticker in indices_tickers:
                indices.append(item)
            elif ticker in sector_tickers:
                sectors.append(item)
            elif (
                ticker in commodity_tickers
                or ticker in forex_tickers
                or ticker in crypto_tickers
            ):
                others.append(item)

        self.indices_data = indices
        self.sectors_data = sectors
        self.others_data = others

    def _market_item(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        price = float(data.get("price", 0.0))
        change = round(float(data.get("change", 0.0)), 1)
        ticker = data.get("ticker", "")
        if "Yield" in name:
            price_text = f"{price:.2f}%"
        elif "JPY" in ticker:
            price_text = f"¥{price:.2f}"
        elif "BTC" in ticker or "ETH" in ticker:
            price_text = f"${price / 1000:.1f}K"
        elif price >= 1000:
            price_text = f"{price:,.0f}"
        else:
            price_text = f"${price:.2f}"
        return {"name": name, "price": price_text, "change": change}

    async def generate_ai_recap(self):
        self.is_generating_recap = True
        yield

        try:
            recap = await asyncio.to_thread(
                generate_market_analysis_report,
                self.market_type,
                market_context=self.market_context or None,
            )
            if recap:
                self.ai_recap = recap
            else:
                self.error_msg = "Failed to generate market recap."
        except Exception as exc:
            self.error_msg = f"AI recap generation error: {exc}"
        finally:
            self.is_generating_recap = False
            yield

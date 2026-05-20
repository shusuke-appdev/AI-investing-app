import asyncio
import dataclasses
from collections.abc import Mapping
from typing import Any

import reflex as rx
from pydantic import BaseModel


class SmartItem(BaseModel):
    met: bool = False
    desc: str = ""
    value: str = ""


class SmartCriteria(BaseModel):
    all_met: bool = False
    S: SmartItem = SmartItem()
    M: SmartItem = SmartItem()
    A: SmartItem = SmartItem()
    R: SmartItem = SmartItem()
    T: SmartItem = SmartItem()


def plain_state_value(value: Any) -> Any:
    """Return Reflex mutable proxy values as plain Python containers."""

    if hasattr(value, "__wrapped__"):
        return plain_state_value(value.__wrapped__)
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Mapping):
        return {str(key): plain_state_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain_state_value(item) for item in value]
    if isinstance(value, tuple):
        return [plain_state_value(item) for item in value]
    return value


def smart_criteria_from_mapping(value: Mapping[str, Any] | None) -> SmartCriteria:
    """Normalize SMART criteria payloads into the Reflex state model."""

    if not value:
        return SmartCriteria()
    return SmartCriteria(**plain_state_value(value))


def _normalize_news_item(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or item.get("headline") or "")
    link = str(item.get("link") or item.get("url") or "")
    return {
        "title": title,
        "headline": title,
        "publisher": str(item.get("publisher") or item.get("source") or ""),
        "source": str(item.get("source") or item.get("publisher") or ""),
        "link": link,
        "url": link,
        "published": str(item.get("published") or ""),
        "summary": str(item.get("summary") or ""),
    }


class StockState(rx.State):
    """State for the individual stock analysis page."""

    ticker: str = ""
    is_fetching: bool = False
    error_msg: str = ""

    info: dict[str, Any] = {}
    chart_data: list[dict[str, Any]] = []
    news: list[dict[str, Any]] = []
    news_source_status: str = ""
    news_error_reason: str = ""
    technical_data: dict[str, Any] = {}
    smart_criteria: SmartCriteria = SmartCriteria()
    earnings: list[dict[str, Any]] = []
    financials: list[dict[str, Any]] = []
    ai_analysis: str = ""
    is_generating_analysis: bool = False
    probabilistic_signal: dict[str, Any] = {}
    stock_signal_context: dict[str, Any] = {}

    def set_ticker(self, value: str):
        self.ticker = value.upper()

    async def fetch_stock_data(self):
        """Fetch individual stock data without invoking Gemini/AI generation."""

        if not self.ticker:
            self.error_msg = "ティッカーシンボルを入力してください。"
            return

        self.is_fetching = True
        self.error_msg = ""
        yield

        try:
            from src.advisor.probabilistic_signal import (
                generate_probabilistic_stock_signal,
                signal_to_dict,
            )
            from src.advisor.smart_criteria import evaluate_smart_criteria
            from src.advisor.technical import analyze_technical
            from src.market_data import (
                get_stock_data,
                get_stock_info,
                get_stock_news_with_status,
            )

            info_data = await asyncio.to_thread(
                get_stock_info, self.ticker, translate_summary=False
            )
            history_df = await asyncio.to_thread(get_stock_data, self.ticker, "1y")
            news_result = await asyncio.to_thread(
                get_stock_news_with_status, self.ticker, 5
            )
            tech_data = await asyncio.to_thread(analyze_technical, self.ticker, "1y")

            smart_res = await asyncio.to_thread(
                evaluate_smart_criteria,
                self.ticker,
                dict(info_data) if info_data else {},
                "Unknown",
            )

            chart_list = []
            if history_df is not None and not history_df.empty:
                import pandas as pd

                history_view = history_df.copy()
                history_view["MA10"] = history_view["Close"].rolling(10).mean()
                history_view["MA20"] = history_view["Close"].rolling(20).mean()
                history_view["MA50"] = history_view["Close"].rolling(50).mean()
                history_view["MA200"] = history_view["Close"].rolling(200).mean()

                for date, row in history_view.iterrows():
                    chart_list.append(
                        {
                            "name": date.strftime("%Y-%m-%d"),
                            "price": float(row["Close"]),
                            "volume": float(row["Volume"])
                            if "Volume" in history_view.columns
                            else 0.0,
                            "ma10": float(row["MA10"])
                            if not pd.isna(row["MA10"])
                            else None,
                            "ma20": float(row["MA20"])
                            if not pd.isna(row["MA20"])
                            else None,
                            "ma50": float(row["MA50"])
                            if not pd.isna(row["MA50"])
                            else None,
                            "ma200": float(row["MA200"])
                            if not pd.isna(row["MA200"])
                            else None,
                        }
                    )

            news_items = (
                news_result.get("items", []) if isinstance(news_result, dict) else []
            )
            news_list = [_normalize_news_item(dict(item)) for item in news_items]

            info_dict = plain_state_value(info_data) if info_data else {}
            self.info = info_dict
            self.chart_data = chart_list
            self.news = news_list
            self.news_source_status = (
                str(news_result.get("source_status", ""))
                if isinstance(news_result, dict)
                else ""
            )
            self.news_error_reason = (
                str(news_result.get("error_reason", ""))
                if isinstance(news_result, dict)
                else ""
            )
            self.smart_criteria = smart_criteria_from_mapping(smart_res)

            if tech_data:
                tech_dict = (
                    dataclasses.asdict(tech_data)
                    if dataclasses.is_dataclass(tech_data)
                    else dict(tech_data)
                )
                for key in ("contrarian_buy_zone", "price_range"):
                    if key in tech_dict and isinstance(tech_dict[key], tuple):
                        tech_dict[key] = list(tech_dict[key])
                self.technical_data = plain_state_value(tech_dict)
            else:
                self.technical_data = {}

            stock_info = plain_state_value(self.info)
            technical_data = plain_state_value(self.technical_data)
            probabilistic = await asyncio.to_thread(
                generate_probabilistic_stock_signal,
                self.ticker,
                "5y",
                "SPY",
                stock_info,
                technical_data,
            )
            self.probabilistic_signal = plain_state_value(signal_to_dict(probabilistic))
            probabilistic_signal = plain_state_value(self.probabilistic_signal)

            from src.services.analysis_context import StockSignalContext

            self.stock_signal_context = StockSignalContext(
                ticker=self.ticker,
                stock_info=stock_info,
                technical_data=technical_data,
                probabilistic_signal=probabilistic_signal,
                news_source_status=self.news_source_status,
                news_error_reason=self.news_error_reason,
            ).to_dict()

            if self.info.get("summary") == "N/A" and self.info.get("sector") == "N/A":
                self.error_msg = "企業情報を取得できませんでした。価格データやプロバイダー設定を確認してください。"
        except Exception as exc:
            self.error_msg = f"データの取得に失敗しました: {exc}"
            self.info = {}
            self.chart_data = []
            self.news = []
            self.news_source_status = ""
            self.news_error_reason = ""
            self.technical_data = {}
            self.probabilistic_signal = {}
            self.stock_signal_context = {}
            self.smart_criteria = SmartCriteria()
        finally:
            self.is_fetching = False
            yield

    async def generate_ai_analysis(self):
        """Generate the Gemini-backed stock recap only when explicitly requested."""

        if not self.ticker or not self.info:
            return
        self.is_generating_analysis = True
        yield

        try:
            from src.stock_analyst import generate_stock_analysis_report

            recap = await asyncio.to_thread(
                generate_stock_analysis_report,
                self.ticker,
                plain_state_value(self.info),
                None,
                None,
                plain_state_value(self.probabilistic_signal),
            )

            if recap:
                self.ai_analysis = recap
            else:
                self.error_msg = "分析レポートの生成に失敗しました。"
        except Exception as exc:
            self.error_msg = f"AI分析エラー: {exc}"
        finally:
            self.is_generating_analysis = False
            yield

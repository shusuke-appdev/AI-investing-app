import asyncio
import dataclasses
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

class StockState(rx.State):
    """個別銘柄（Stock）ページ用の状態管理クラス"""

    ticker: str = ""
    is_fetching: bool = False
    error_msg: str = ""

    # 基本情報
    info: dict[str, Any] = {}

    # チャート用データ
    chart_data: list[dict[str, Any]] = []

    # ニュースデータ
    news: list[dict[str, Any]] = []

    # テクニカル分析データ
    technical_data: dict[str, Any] = {}

    # SMART基準
    smart_criteria: SmartCriteria = SmartCriteria()

    # 決算・財務データ
    earnings: list[dict[str, Any]] = []
    financials: list[dict[str, Any]] = []

    # テクニカル分析・AI分析結果
    ai_analysis: str = ""
    is_generating_analysis: bool = False

    def set_ticker(self, value: str):
        self.ticker = value.upper()

    async def fetch_stock_data(self):
        """外部APIから個別銘柄データを取得する"""
        if not self.ticker:
            self.error_msg = "ティッカーシンボルを入力してください。"
            return

        self.is_fetching = True
        self.error_msg = ""
        yield

        try:
            from src.advisor.technical import analyze_technical
            from src.market_data import get_stock_data, get_stock_info, get_stock_news

            # APIコールのブロッキングを回避してデータ取得
            info_data = await asyncio.to_thread(get_stock_info, self.ticker)
            history_df = await asyncio.to_thread(get_stock_data, self.ticker, "1y")
            news_data = await asyncio.to_thread(get_stock_news, self.ticker, 5)
            tech_data = await asyncio.to_thread(analyze_technical, self.ticker, "1y")

            # SMART基準を評価
            from src.advisor.smart_criteria import evaluate_smart_criteria
            smart_res = await asyncio.to_thread(evaluate_smart_criteria, self.ticker, dict(info_data) if info_data else {}, "不明")

            # Recharts用の形式に変換
            chart_list = []
            if history_df is not None and not history_df.empty:
                import pandas as pd
                history_df["MA10"] = history_df["Close"].rolling(10).mean()
                history_df["MA20"] = history_df["Close"].rolling(20).mean()
                history_df["MA50"] = history_df["Close"].rolling(50).mean()
                history_df["MA200"] = history_df["Close"].rolling(200).mean()

                # pandas DataFrame を dict のリストに変換
                for date, row in history_df.iterrows():
                    chart_list.append({
                        "name": date.strftime("%Y-%m-%d"),
                        "price": float(row["Close"]),
                        "volume": float(row["Volume"]) if "Volume" in history_df.columns else 0.0,
                        "ma10": float(row["MA10"]) if not pd.isna(row["MA10"]) else None,
                        "ma20": float(row["MA20"]) if not pd.isna(row["MA20"]) else None,
                        "ma50": float(row["MA50"]) if not pd.isna(row["MA50"]) else None,
                        "ma200": float(row["MA200"]) if not pd.isna(row["MA200"]) else None,
                    })

            # NewsItem を dict に変換
            news_list = [dict(n) for n in news_data] if news_data else []

            self.info = dict(info_data) if info_data else {}
            self.chart_data = chart_list
            self.news = news_list
            self.smart_criteria = smart_res

            # Technical Data
            if tech_data:
                # asdictで辞書化。タプルなどを適切に処理
                tech_dict = dataclasses.asdict(tech_data)
                # listやtupleを含む場合、Reflexのstateでうまく扱えるように変換
                if "contrarian_buy_zone" in tech_dict and isinstance(tech_dict["contrarian_buy_zone"], tuple):
                    tech_dict["contrarian_buy_zone"] = list(tech_dict["contrarian_buy_zone"])
                if "price_range" in tech_dict and isinstance(tech_dict["price_range"], tuple):
                    tech_dict["price_range"] = list(tech_dict["price_range"])
                self.technical_data = tech_dict
            else:
                self.technical_data = {}

            # APIキーが未設定等の場合のエラーハンドリング
            if self.info.get("summary") == "情報なし" and self.info.get("sector") == "N/A":
                self.error_msg = "企業情報を取得できませんでした。Finnhub APIキーが正しく設定されているか確認してください。"

        except Exception as e:
            self.error_msg = f"データの取得に失敗しました: {str(e)}"
            self.info = {}
            self.chart_data = []
            self.news = []
            self.technical_data = {}
            self.smart_criteria = {}
        finally:
            self.is_fetching = False
            yield

    async def generate_ai_analysis(self):
        """Geminiによる個別銘柄のAI分析レポート生成"""
        if not self.ticker or not self.info:
            return
        self.is_generating_analysis = True
        yield

        try:
            from src.stock_analyst import generate_stock_analysis_report
            # info をディクショナリとして渡す
            recap = await asyncio.to_thread(generate_stock_analysis_report, self.ticker, self.info)

            if recap:
                self.ai_analysis = recap
            else:
                self.error_msg = "分析レポートの生成に失敗しました。"
        except Exception as e:
            self.error_msg = f"AI分析エラー: {e}"
        finally:
            self.is_generating_analysis = False
            yield

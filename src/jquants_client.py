"""
J-Quants API Client
日本取引所グループ提供のJ-Quants API (v2) を使用して、高信頼な株価・財務データを取得します。
"""

from datetime import datetime, timedelta

import pandas as pd
import requests

from src.cache import ttl_cache
from src.constants import CACHE_TTL_DAILY, CACHE_TTL_SHORT
from src.log_config import get_logger
from src.settings_storage import get_jquants_api_key

logger = get_logger(__name__)

# V2 API Base URL
BASE_URL = "https://api.jquants.com/v2"


def is_configured() -> bool:
    """J-Quants API Keyが設定されているかどうかを返す"""
    return bool(get_jquants_api_key())


def _get_headers() -> dict:
    """APIリクエスト用のヘッダーを生成する"""
    api_key = get_jquants_api_key()
    if not api_key:
        return {}
    return {
        "x-api-key": api_key
    }


@ttl_cache(ttl=CACHE_TTL_SHORT)
def get_daily_quotes(ticker: str, period: str = "1mo") -> pd.DataFrame:
    """
    指定したティッカーの過去データ(日足)を取得する。
    period は "1mo", "3mo", "6mo", "1y", "max" などをサポート。
    """
    headers = _get_headers()
    if not headers:
        return pd.DataFrame()

    code = "".join(filter(str.isdigit, str(ticker)))
    if len(code) != 4:
        return pd.DataFrame()

    try:
        # 日付範囲の計算
        period_map = {
            "1d": timedelta(days=5), # 休日を考慮して少し長めに
            "5d": timedelta(days=10),
            "1mo": timedelta(days=35),
            "3mo": timedelta(days=100),
            "6mo": timedelta(days=190),
            "1y": timedelta(days=380),
            "max": timedelta(days=1825), # 約5年
        }
        days = period_map.get(period, timedelta(days=35))
        # J-Quants Freeプラン制限: データは約12週間遅延で提供される
        to_dt = datetime.now() - timedelta(days=92)
        from_date = (to_dt - days).strftime("%Y%m%d")
        to_date = to_dt.strftime("%Y%m%d")

        url = f"{BASE_URL}/prices/daily_quotes"
        params = {
            "code": f"{code}0",  # J-Quantsは5桁コード(末尾0)
            "from": from_date,
            "to": to_date
        }

        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json().get("daily_quotes", [])

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        # カラム名の変換(yfinance互換へ)
        df.rename(
            columns={
                "Date": "Date",
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close",
                "Volume": "Volume",
                "AdjustmentOpen": "Adj Open",
                "AdjustmentHigh": "Adj High",
                "AdjustmentLow": "Adj Low",
                "AdjustmentClose": "Adj Close",
                "AdjustmentVolume": "Adj Volume"
            },
            inplace=True,
        )
        # yfinance の挙動に合わせる: Open/High/Low/Close は分割調整済みの値を使う方が安全
        if "Adj Close" in df.columns:
             df["Open"] = df["Adj Open"]
             df["High"] = df["Adj High"]
             df["Low"] = df["Adj Low"]
             df["Close"] = df["Adj Close"]
             df["Volume"] = df["Adj Volume"]

        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df.set_index("Date", inplace=True)

        return df

    except Exception as e:
        logger.warning(f"J-Quants: Failed to get historical data for {ticker}: {e}")
        return pd.DataFrame()


@ttl_cache(ttl=CACHE_TTL_SHORT)
def get_current_price(ticker: str) -> float:
    """最新の終値を取得する"""
    df = get_daily_quotes(ticker, period="1d")
    if not df.empty and "Close" in df.columns:
        return float(df["Close"].iloc[-1])
    return 0.0


@ttl_cache(ttl=CACHE_TTL_DAILY)
def get_fins_statements(ticker: str) -> dict | None:
    """財務情報(直近の決算)を取得する"""
    headers = _get_headers()
    if not headers:
        return None

    code = "".join(filter(str.isdigit, str(ticker)))
    if len(code) != 4:
        return None

    try:
        url = f"{BASE_URL}/fins/statements"
        params = {
            "code": f"{code}0",
        }

        days = timedelta(days=400)
        from_date = (datetime.now() - days).strftime("%Y%m%d")
        params["date"] = from_date

        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        statements = response.json().get("statements", [])

        if not statements:
            return None

        # 最新のものを取得(文字列の日付でソート)
        statements.sort(key=lambda x: x.get("DiscloseDate", ""), reverse=True)
        latest = statements[0]

        def _parse_num(val):
            if val is None or val == "":
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        return {
            "net_sales": _parse_num(latest.get("NetSales")),
            "operating_income": _parse_num(latest.get("OperatingProfit")),
            "ordinary_income": _parse_num(latest.get("OrdinaryProfit")),
            "net_income": _parse_num(latest.get("Profit")),
            "eps": _parse_num(latest.get("EarningsPerShare")),
            "bps": _parse_num(latest.get("BookValuePerShare")),
            "total_assets": _parse_num(latest.get("TotalAssets")),
            "equity": _parse_num(latest.get("Equity")),
            "disclose_date": latest.get("DiscloseDate"),
            "type": latest.get("TypeOfDocument"),
            "company_name": latest.get("CompanyName")
        }

    except Exception as e:
        logger.warning(f"J-Quants: Failed to get statements for {ticker}: {e}")
        return None


@ttl_cache(ttl=CACHE_TTL_DAILY)
def get_company_info(ticker: str) -> dict | None:
    """基本銘柄情報(業種等)を取得する"""
    headers = _get_headers()
    if not headers:
        return None

    code = "".join(filter(str.isdigit, str(ticker)))
    if len(code) != 4:
        return None

    try:
        url = f"{BASE_URL}/listed/info"
        params = {"code": f"{code}0"}

        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        info_list = response.json().get("info", [])

        if not info_list:
            return None

        info = info_list[0]
        return {
            "company_name": info.get("CompanyName"),
            "company_name_en": info.get("CompanyNameEnglish"),
            "sector_name": info.get("Sector33CodeName"),
            "industry_name": info.get("Sector17CodeName"),
            "market_code_name": info.get("MarketCodeName"),
            "margin_code_name": info.get("MarginCodeName")
        }
    except Exception as e:
        logger.warning(f"J-Quants: Failed to get company info for {ticker}: {e}")
        return None

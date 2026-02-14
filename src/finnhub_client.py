"""
Finnhub APIクライアントモジュール
レート制限ハンドリング・リトライ・キャッシュ内蔵。
"""
import json
import time
import threading
import pandas as pd
# import streamlit as st  # Removed UI dependency
from datetime import datetime, timedelta
from typing import Optional, Tuple
import finnhub
from src.settings_storage import get_finnhub_api_key

# --- Custom Exceptions ---
class FinnhubError(Exception):
    """Base exception for Finnhub client errors."""
    pass

class FinnhubConfigError(FinnhubError):
    """Raised when API key is missing or invalid."""
    pass

class FinnhubRateLimitError(FinnhubError):
    """Raised when rate limit is exceeded."""
    pass

class FinnhubNetworkError(FinnhubError):
    """Raised when network issues occur."""
    pass

# --- クライアント初期化 ---

def _get_api_key() -> str:
    """APIキーを取得（Streamlit依存を最小限に）"""
    # 1. Session State (if available)
    try:
        import streamlit as st
        if hasattr(st, "session_state"):
            key = st.session_state.get("finnhub_api_key")
            if key: return key
    except ImportError:
        pass

    # 2. Environment Variable
    import os
    key = os.environ.get("FINNHUB_API_KEY")
    if key: return key

    # 3. Settings Storage
    return get_finnhub_api_key()

def _get_client() -> Optional[finnhub.Client]:
    """Finnhubクライアントを取得"""
    api_key = _get_api_key()
    if not api_key:
        return None
    return finnhub.Client(api_key=api_key)


def is_configured() -> bool:
    """Finnhub APIが設定済みか確認"""
    return _get_api_key() != ""


# --- レート制限 & リトライ ---

_last_call_time = 0.0
_MIN_INTERVAL = 1.1  # 秒
_rate_lock = threading.Lock()

def _rate_limited_call(func, *args, max_retries: int = 3, **kwargs):
    """
    レート制限付きAPI呼び出し。
    UI依存(st.toast)を排除し、例外を送出する。
    """
    global _last_call_time

    for attempt in range(max_retries):
        with _rate_lock:
            elapsed = time.time() - _last_call_time
            if elapsed < _MIN_INTERVAL:
                time.sleep(_MIN_INTERVAL - elapsed)
            _last_call_time = time.time()

        try:
            return func(*args, **kwargs)
        except finnhub.FinnhubAPIException as e:
            if e.status_code == 429:
                wait = 2 ** attempt
                print(f"[FINNHUB_WARN] Rate Limit (429). Retrying in {wait}s...")
                time.sleep(wait)
            elif e.status_code == 401 or e.status_code == 403:
                print(f"[FINNHUB_ERROR] Permission Denied ({e.status_code})")
                raise FinnhubConfigError(f"Invalid API Key or Permission Denied: {e}")
            else:
                print(f"[FINNHUB_ERROR] API Error: {e}")
                raise FinnhubError(f"API Error: {e}")
        except finnhub.FinnhubRequestException as e:
            print(f"[FINNHUB_WARN] Network Exception: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                raise FinnhubNetworkError(f"Network Error: {e}")
    
    print(f"[FINNHUB_ERROR] Max retries exceeded.")
    raise FinnhubRateLimitError("Max retries exceeded")


# --- 株価データ ---

def get_quote(symbol: str) -> Optional[dict]:
    """
    リアルタイム株価クォートを取得。

    Args:
        symbol: ティッカーシンボル (e.g. "AAPL")

    Returns:
        {"c": 現在価格, "h": 高値, "l": 安値, "o": 始値, "pc": 前日終値, "d": 変化, "dp": 変化率%}
    """
    client = _get_client()
    if not client:
        return None
    try:
        data = _rate_limited_call(client.quote, symbol)
        if not data or data.get("c") == 0:
             print(f"[FINNHUB_WARN] Quote for {symbol} is empty or zero: {data}")
        return data
    except Exception as e:
        print(f"[FINNHUB_ERROR] Quote error ({symbol}): {e}")
        return None


def get_candles(
    symbol: str,
    resolution: str = "D",
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    period_days: int = 30
) -> pd.DataFrame:
    """
    OHLCVローソク足データを取得しDataFrameで返す。

    Args:
        symbol: ティッカーシンボル
        resolution: "1", "5", "15", "30", "60", "D", "W", "M"
        from_date: 開始日時
        to_date: 終了日時
        period_days: from_date未指定時の日数

    Returns:
        DataFrame (columns: Open, High, Low, Close, Volume, index: datetime)
    """
    client = _get_client()
    if not client:
        return pd.DataFrame()

    if to_date is None:
        to_date = datetime.now()
    if from_date is None:
        from_date = to_date - timedelta(days=period_days)

    from_ts = int(from_date.timestamp())
    to_ts = int(to_date.timestamp())

    try:
        data = _rate_limited_call(client.stock_candles, symbol, resolution, from_ts, to_ts)
    except Exception as e:
        print(f"[FINNHUB_ERROR] Candles error ({symbol}): {e}")
        return pd.DataFrame()

    if not data or data.get("s") != "ok":
        print(f"[FINNHUB_WARN] No candle data for {symbol} (status: {data.get('s') if data else 'None'})")
        # DEBUG
        print(f"[DEBUG_RAW] data={data}")
        return pd.DataFrame()

    df = pd.DataFrame({
        "Open": data["o"],
        "High": data["h"],
        "Low": data["l"],
        "Close": data["c"],
        "Volume": data["v"],
    }, index=pd.to_datetime(data["t"], unit="s"))
    df.index.name = "Date"
    df.sort_index(inplace=True)
    return df


# --- オプションデータ ---

def get_option_chain(
    symbol: str,
    max_expirations: int = 4
) -> Optional[Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Finnhubからオプションチェーンデータを取得。

    Args:
        symbol: ティッカーシンボル (e.g. "SPY")
        max_expirations: 取得する満期日の最大数

    Returns:
        (calls_df, puts_df) のタプル。各DataFrameには以下のカラムを含む:
        strike, lastPrice, bid, ask, volume, openInterest,
        impliedVolatility, delta, gamma, theta, vega, rho,
        expiration, contractName
        取得失敗時はNoneを返す。
    """
    client = _get_client()
    if not client:
        return None

    try:
        raw = _rate_limited_call(client.option_chain, symbol=symbol)
    except Exception as e:
        print(f"[FINNHUB_ERROR] Option chain error ({symbol}): {e}")
        return None

    # Finnhubクライアントは文字列(JSON)を返す場合がある
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[FINNHUB_ERROR] Option chain JSON parse error ({symbol}): {e}")
            return None

    if not raw or not isinstance(raw, dict) or "data" not in raw:
        print(f"[FINNHUB_WARN] No option data for {symbol}")
        return None

    all_calls: list[dict] = []
    all_puts: list[dict] = []

    expirations = raw["data"][:max_expirations]

    for exp_data in expirations:
        expiration_date = exp_data.get("expirationDate", "")
        options = exp_data.get("options", {})

        for contract in options.get("CALL", []):
            all_calls.append(_normalize_option_contract(contract, expiration_date))

        for contract in options.get("PUT", []):
            all_puts.append(_normalize_option_contract(contract, expiration_date))

    if not all_calls and not all_puts:
        print(f"[FINNHUB_WARN] Option data empty for {symbol}")
        return None

    calls_df = pd.DataFrame(all_calls) if all_calls else pd.DataFrame()
    puts_df = pd.DataFrame(all_puts) if all_puts else pd.DataFrame()

    return calls_df, puts_df


def _normalize_option_contract(contract: dict, expiration_date: str) -> dict:
    """
    Finnhubのオプション契約データを統一フォーマットに変換する。

    Args:
        contract: Finnhub APIからの個別契約データ
        expiration_date: 満期日文字列 (YYYY-MM-DD)

    Returns:
        正規化された辞書
    """
    return {
        "contractName": contract.get("contractName", ""),
        "strike": contract.get("strike", 0),
        "lastPrice": contract.get("lastPrice", 0),
        "bid": contract.get("bid", 0),
        "ask": contract.get("ask", 0),
        "change": contract.get("change", 0),
        "changePercent": contract.get("changePercent", 0),
        "volume": contract.get("volume", 0),
        "openInterest": contract.get("openInterest", 0),
        "impliedVolatility": contract.get("impliedVolatility", 0),
        "delta": contract.get("delta", 0),
        "gamma": contract.get("gamma", 0),
        "theta": contract.get("theta", 0),
        "vega": contract.get("vega", 0),
        "rho": contract.get("rho", 0),
        "inTheMoney": contract.get("inTheMoney", ""),
        "intrinsicValue": contract.get("intrinsicValue", 0),
        "timeValue": contract.get("timeValue", 0),
        "expiration": expiration_date,
    }


# --- 企業情報 ---

def get_company_profile(symbol: str) -> Optional[dict]:
    """
    企業プロフィールを取得。

    Args:
        symbol: ティッカーシンボル

    Returns:
        {"name", "ticker", "exchange", "industry", "logo", "weburl",
         "marketCapitalization", "shareOutstanding", "ipo", ...}
    """
    client = _get_client()
    if not client:
        return None
    try:
        result = _rate_limited_call(client.company_profile2, symbol=symbol)
        return result if result else None
    except Exception as e:
        print(f"Finnhub profile error ({symbol}): {e}")
        return None


def get_basic_financials(symbol: str) -> Optional[dict]:
    """
    基本的な財務指標を取得。

    Args:
        symbol: ティッカーシンボル

    Returns:
        {"metric": {"peBasicExclExtraTTM", "epsBasicExclExtraItemsTTM", ...}, "series": {...}}
    """
    client = _get_client()
    if not client:
        return None
    try:
        return _rate_limited_call(client.company_basic_financials, symbol, 'all')
    except Exception as e:
        print(f"Finnhub financials error ({symbol}): {e}")
        return None


# --- ニュース ---

def get_company_news(
    symbol: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
) -> list[dict]:
    """
    銘柄関連ニュースを取得。

    Args:
        symbol: ティッカーシンボル
        from_date: "YYYY-MM-DD"
        to_date: "YYYY-MM-DD"

    Returns:
        [{"headline", "summary", "source", "url", "datetime", "category", "related"}, ...]
    """
    client = _get_client()
    if not client:
        return []

    if to_date is None:
        to_date = datetime.now().strftime("%Y-%m-%d")
    if from_date is None:
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    try:
        return _rate_limited_call(client.company_news, symbol, _from=from_date, to=to_date) or []
    except Exception as e:
        print(f"Finnhub news error ({symbol}): {e}")
        return []


def get_market_news(category: str = "general") -> list[dict]:
    """
    マーケット全般ニュースを取得。

    Args:
        category: "general", "forex", "crypto", "merger"

    Returns:
        [{"headline", "summary", "source", "url", "datetime", "category"}, ...]
    """
    client = _get_client()
    if not client:
        return []
    try:
        return _rate_limited_call(client.general_news, category, min_id=0) or []
    except Exception as e:
        print(f"Finnhub market news error: {e}")
        return []


# --- 決算データ ---

def get_earnings_surprises(symbol: str, limit: int = 4) -> list[dict]:
    """
    EPSサプライズデータを取得。

    Args:
        symbol: ティッカーシンボル
        limit: 取得する四半期数

    Returns:
        [{"actual", "estimate", "period", "quarter", "surprise", "surprisePercent", "symbol"}, ...]
    """
    client = _get_client()
    if not client:
        return []
    try:
        return _rate_limited_call(client.company_earnings, symbol, limit=limit) or []
    except Exception as e:
        print(f"Finnhub earnings error ({symbol}): {e}")
        return []


def get_earnings_calendar(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
) -> list[dict]:
    """
    決算カレンダーを取得。

    Args:
        from_date: "YYYY-MM-DD"
        to_date: "YYYY-MM-DD"

    Returns:
        [{"date", "epsActual", "epsEstimate", "hour", "quarter", "revenueActual",
          "revenueEstimate", "symbol", "year"}, ...]
    """
    client = _get_client()
    if not client:
        return []

    if to_date is None:
        to_date = datetime.now().strftime("%Y-%m-%d")
    if from_date is None:
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    try:
        result = _rate_limited_call(client.earnings_calendar, _from=from_date, to=to_date, symbol="")
        return result.get("earningsCalendar", []) if result else []
    except Exception as e:
        print(f"Finnhub earnings calendar error: {e}")
        return []


# --- 財務諸表 ---

def get_financials_reported(symbol: str, freq: str = "quarterly") -> list[dict]:
    """
    報告済み財務諸表を取得。

    Args:
        symbol: ティッカーシンボル
        freq: "annual" | "quarterly"

    Returns:
        [{"accessNumber", "symbol", "cik", "year", "quarter", "form",
          "startDate", "endDate", "filedDate", "report": {...}}, ...]
    """
    client = _get_client()
    if not client:
        return []
    try:
        result = _rate_limited_call(client.financials_reported, symbol=symbol, freq=freq)
        return result.get("data", []) if result else []
    except Exception as e:
        print(f"Finnhub financials reported error ({symbol}): {e}")
        return []

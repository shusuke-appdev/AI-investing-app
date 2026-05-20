import logging
import os
import time

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from src.yfinance_runtime import configure_yfinance_cache

logger = logging.getLogger(__name__)
configure_yfinance_cache()


def get_market_data(
    asset: str = "^N225", period: str = "2y", interval: str = "1d"
) -> pd.DataFrame:
    """
    Step 1: ボラティリティ観測用の市場データ取得
    yfinance または Polygon APIを利用してデータを取得する。
    """
    configure_yfinance_cache()
    polygon_api_key = os.getenv("POLYGON_API_KEY")

    # リトライ共通処理
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 1. 優先: Polygon API (APIキーが存在し、対応可能であれば。ここでは日足の簡易フォールバックを想定)
            # 実際には ^N225 はPolygonではプレフィックスが異なるため、個別株や他インデックス対応用
            if polygon_api_key and not asset.startswith("^"):
                from datetime import datetime, timedelta

                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=365 * 2)).strftime(
                    "%Y-%m-%d"
                )
                url = f"https://api.polygon.io/v2/aggs/ticker/{asset}/range/1/day/{start_date}/{end_date}?apiKey={polygon_api_key}"
                res = requests.get(url, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    if "results" in data and len(data["results"]) > 0:
                        df = pd.DataFrame(data["results"])
                        df["datetime"] = pd.to_datetime(df["t"], unit="ms")
                        df.set_index("datetime", inplace=True)
                        df.rename(
                            columns={
                                "o": "open",
                                "h": "high",
                                "l": "low",
                                "c": "close",
                                "v": "volume",
                            },
                            inplace=True,
                        )

                        # 対数リターンの事前計算処理へ
                        return _prepare_vol_df(df)

            # 2. フォールバック: yfinance
            df = yf.download(asset, period=period, interval=interval, progress=False)
            if df.empty:
                raise ValueError(f"データが空です: {asset}")

            # multi-index columns対応 (yfinance recent version)
            if isinstance(df.columns, pd.MultiIndex):
                # asset名のレベルを落とす
                df.columns = df.columns.droplevel(1)

            df.columns = [c.lower() for c in df.columns]
            return _prepare_vol_df(df)

        except Exception as e:
            logger.warning(
                f"データ取得エラー (attempt {attempt + 1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                # 指数バックオフ
                time.sleep(2**attempt)
            else:
                logger.error(f"{asset}のデータ取得に失敗しました。")
                return pd.DataFrame()


def _prepare_vol_df(df: pd.DataFrame) -> pd.DataFrame:
    """基本のカラム整備と対数リターン計算"""
    if "close" not in df.columns:
        return df
    # 対数リターン: ln(C_t / C_{t-1})
    df["log_return"] = np.log(df["close"] / df["close"].shift(1))
    return df


def compute_volatility(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    Step 2: ボラティリティ観測・計算モジュール
    """
    if df is None or df.empty or "log_return" not in df.columns:
        return df

    df = df.copy()

    # 実現ボラティリティ: 20日ローリング標準偏差 * √(252)
    # NaN処理: 前方埋め (ffill) なしでもrolling().std()は一定データ揃えば算出されるが要件指示通りに
    df["log_return"].ffill(inplace=True)

    df["vol"] = df["log_return"].rolling(window=window).std() * np.sqrt(252)

    # ボラの不安定度 (vol_of_vol): ボラティリティ自体の20日ローリング標準偏差
    df["vol_of_vol"] = df["vol"].rolling(window=window).std()

    # 平方リターン系列: r_t^2
    df["sq_returns"] = df["log_return"] ** 2

    return df

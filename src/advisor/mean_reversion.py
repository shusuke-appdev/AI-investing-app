"""
Mean Reversion Analyzer モジュール
日足ベースの価格データから、Parabolicな過熱感や平均回帰によるサポート水準を判定します。
デイトレードのシグナルではなく、AIベースのテクニカル分析へのコンテキスト提供を目的とします。
"""

import pandas as pd


class MeanReversionAnalyzer:
    """
    Qullamägiのパラボリックセットアップにインスパイアされた、
    日足ベースのテクニカル過熱感・回帰水準分析クラス。
    """

    def __init__(self, ticker: str):
        self.ticker = ticker

    def analyze(self, df_daily: pd.DataFrame) -> dict:
        """
        日足データからMean Reversionの観点で状態を評価する。

        Args:
            df_daily: 過去数十日分以上を含む日足DataFrame (Close, Open, High, Low 列が必要)

        Returns:
            評価結果の辞書
        """
        if df_daily is None or df_daily.empty or len(df_daily) < 50:
            return {"error": "Insufficient data"}

        df = df_daily.copy()

        # 移動平均線の計算
        df = self._calculate_ma(df)

        # 最新のデータを取得
        latest = df.iloc[-1]

        # Parabolic（過熱感）状態の判定
        parabolic_result = self._check_parabolic_extension(df)

        # リバウンド（反発）/Dip Buy セットアップの判定
        rebound_result = self._check_rebound_setup(df)

        return {
            "ticker": self.ticker,
            "current_price": latest["Close"],
            "parabolic_state": parabolic_result,
            "rebound_state": rebound_result,
            "ma_10": float(latest["SMA_10"]) if not pd.isna(latest["SMA_10"]) else None,
            "ma_20": float(latest["SMA_20"]) if not pd.isna(latest["SMA_20"]) else None,
            "ma_50": float(latest["SMA_50"]) if not pd.isna(latest["SMA_50"]) else None,
        }

    def _calculate_ma(self, df: pd.DataFrame) -> pd.DataFrame:
        """SMA10, 20, 50 を計算"""
        df["SMA_10"] = df["Close"].rolling(window=10).mean()
        df["SMA_20"] = df["Close"].rolling(window=20).mean()
        df["SMA_50"] = df["Close"].rolling(window=50).mean()
        return df

    def _check_parabolic_extension(self, df: pd.DataFrame) -> dict:
        """
        急激な上昇によるParabolicな状態（過熱感）を検知。
        10MA/20MAからの大きな乖離、および連続する大陽線などで判定。
        """
        latest = df.iloc[-1]

        price = latest["Close"]
        sma10 = latest["SMA_10"]
        sma20 = latest["SMA_20"]

        if pd.isna(sma10) or pd.isna(sma20):
            return {"is_parabolic": False, "description": "MA計算不足"}

        # 10MA、20MAからの乖離率
        dev_10 = (price - sma10) / sma10
        dev_20 = (price - sma20) / sma20

        is_parabolic = False
        description = "正常な範囲内"
        target_reversion = None

        # 簡易的な過熱感判定（+10%以上乖離で過熱とみなす。ボラティリティにより調整可能）
        if dev_10 > 0.10 or dev_20 > 0.15:
            is_parabolic = True
            description = (
                f"強い過熱感 (10MAから {dev_10:.1%} 乖離)。平均回帰のリスクあり。"
            )
            target_reversion = float(sma10)  # 最初のターゲットは10MA

        elif dev_10 < -0.10 or dev_20 < -0.15:
            is_parabolic = True
            description = f"極端な売られすぎ (10MAから {dev_10:.1%} 乖離)。ショートカバー反発の可能性。"
            target_reversion = float(sma10)

        # 連続陽線のチェック（例えば過去5日間で4日以上陽線など）
        recent_5 = df.tail(5)
        # Open列が存在しない場合はCloseの差分等で代用できるが、通常はOHLCVがある
        if "Open" in recent_5.columns:
            green_candles = len(recent_5[recent_5["Close"] > recent_5["Open"]])
            if green_candles >= 4 and dev_10 > 0.05:
                if not is_parabolic:
                    is_parabolic = True
                    description = (
                        f"短期的な上昇トレンド過熱 (直近5日で{green_candles}本の陽線)。"
                    )
                    target_reversion = float(sma10)

        return {
            "is_parabolic": bool(is_parabolic),
            "description": description,
            "deviation_10ma": float(round(dev_10, 3)) if not pd.isna(dev_10) else None,
            "deviation_20ma": float(round(dev_20, 3)) if not pd.isna(dev_20) else None,
            "target_reversion_price": target_reversion,
        }

    def _check_rebound_setup(self, df: pd.DataFrame) -> dict:
        """
        サポートライン（主にMA）付近からの反発可能性や、Dip Buyの適性を確認する。
        """
        latest = df.iloc[-1]

        price = latest["Close"]
        sma10 = latest["SMA_10"]
        sma20 = latest["SMA_20"]
        sma50 = latest["SMA_50"]

        if pd.isna(sma10) or pd.isna(sma20) or pd.isna(sma50):
            return {"is_dip_buyable": False, "description": "MA計算不足"}

        # パーフェクトオーダーの確認 (短期 > 中期 > 長期 が全て上向き)
        # 上向きチェックは簡単のため現在値の大小関係のみで判定 (10 > 20 > 50)
        is_perfect_order = (sma10 > sma20) and (sma20 > sma50)

        # サポート接近の確認（10MAまたは20MAに価格が近いか。±2%以内）
        near_10ma = abs(price - sma10) / sma10 < 0.02
        near_20ma = abs(price - sma20) / sma20 < 0.02
        near_50ma = abs(price - sma50) / sma50 < 0.02

        description = "特筆すべきセットアップなし"
        is_dip_buyable = False

        if is_perfect_order:
            if near_10ma or near_20ma:
                is_dip_buyable = bool(True)
                description = "上昇トレンド継続中 (パーフェクトオーダー)。10/20MA付近での押し目買い(Dip Buy)の好機に近い水準です。"
            else:
                description = "強い上昇トレンド(パーフェクトオーダー)ですが、現在サポートからはやや離れています。"
        else:
            if sma10 < sma20 and sma20 < sma50:
                description = "下落トレンド(逆パーフェクトオーダー)。Falling Knife(落ちるナイフ)を買い向かうのは避けるべき状態です。"

            elif near_50ma:
                description = (
                    "50MA付近に位置。中長期的なサポートとして機能するかが焦点です。"
                )

        return {
            "is_dip_buyable": bool(is_dip_buyable),
            "is_perfect_order": bool(is_perfect_order),
            "description": description,
            "near_support": "10MA/20MA"
            if (near_10ma or near_20ma)
            else "50MA"
            if near_50ma
            else "None",
        }

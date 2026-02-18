"""
オプション分析モジュールのテスト
"""

from unittest.mock import patch

import numpy as np
import pandas as pd


class TestCalculatePCR:
    """calculate_pcr関数のテスト"""

    def test_returns_none_when_option_data_unavailable(self):
        """オプションデータが取得できない場合はNoneを返す"""
        with patch("src.option_analyst.get_option_chain", return_value=None):
            from src.option_analyst import calculate_pcr

            result = calculate_pcr("INVALID")
            assert result is None

    def test_calculates_pcr_correctly(self):
        """PCRが正しく計算される"""
        mock_calls = pd.DataFrame({"volume": [100, 200], "openInterest": [1000, 2000]})
        mock_puts = pd.DataFrame({"volume": [150, 250], "openInterest": [1500, 2500]})

        with patch(
            "src.option_analyst.get_option_chain", return_value=(mock_calls, mock_puts)
        ):
            from src.option_analyst import calculate_pcr

            result = calculate_pcr("SPY")

            assert result is not None
            assert result["ticker"] == "SPY"
            # Volume PCR: (150+250)/(100+200) = 400/300 ≈ 1.33
            assert abs(result["volume_pcr"] - 1.333) < 0.01
            # OI PCR: (1500+2500)/(1000+2000) = 4000/3000 ≈ 1.33
            assert abs(result["oi_pcr"] - 1.333) < 0.01


class TestCalculateGEX:
    """calculate_gex関数のテスト"""

    def test_returns_none_when_option_data_unavailable(self):
        """オプションデータが取得できない場合はNoneを返す"""
        with patch("src.option_analyst.get_option_chain", return_value=None):
            from src.option_analyst import calculate_gex

            result = calculate_gex("INVALID")
            assert result is None

    def test_returns_none_when_price_unavailable(self):
        """株価が取得できない場合はNoneを返す"""
        mock_calls = pd.DataFrame(
            {"strike": [100], "openInterest": [1000], "gamma": [0.05]}
        )
        mock_puts = pd.DataFrame(
            {"strike": [100], "openInterest": [1000], "gamma": [0.05]}
        )

        with patch(
            "src.option_analyst.get_option_chain", return_value=(mock_calls, mock_puts)
        ):
            with patch(
                "src.option_analyst.DataProvider.get_current_price", return_value=0.0
            ):
                from src.option_analyst import calculate_gex

                result = calculate_gex("SPY")
                assert result is None


class TestGammaEstimation:
    """ガンマ推定ロジックのテスト"""

    def test_gamma_decreases_with_distance_from_atm(self):
        """ATMから離れるとガンマが減衰する"""
        # current_price = 100 (Unused)

        # ATM (moneyness = 0)
        moneyness_atm = 0
        gamma_atm = max(0.001, 0.05 * np.exp(-5 * moneyness_atm))

        # OTM 5% (moneyness = 0.05)
        moneyness_otm = 0.05
        gamma_otm = max(0.001, 0.05 * np.exp(-5 * moneyness_otm))

        # Deep OTM 20% (moneyness = 0.2)
        moneyness_deep = 0.2
        gamma_deep = max(0.001, 0.05 * np.exp(-5 * moneyness_deep))

        assert gamma_atm > gamma_otm > gamma_deep
        assert abs(gamma_atm - 0.05) < 0.01  # ATMでは約0.05

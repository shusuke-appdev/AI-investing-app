from unittest.mock import patch

import pandas as pd
import pytest

from src.option_analyst import (
    analyze_option_sentiment,
    assess_option_data_quality,
    calculate_atm_iv,
    calculate_gex,
    calculate_pcr,
)


class TestOptionAnalyst:
    @pytest.fixture
    def mock_option_data(self):
        # Create sample Calls
        calls_data = {
            "strike": [100, 105, 110],
            "volume": [100, 50, 10],
            "openInterest": [1000, 500, 100],
            "gamma": [0.05, 0.04, 0.02],
            "impliedVolatility": [0.2, 0.18, 0.15],
        }
        calls = pd.DataFrame(calls_data)

        # Create sample Puts
        puts_data = {
            "strike": [90, 95, 100],
            "volume": [20, 30, 80],
            "openInterest": [200, 300, 800],
            "gamma": [0.03, 0.04, 0.05],
            "impliedVolatility": [0.22, 0.20, 0.18],
        }
        puts = pd.DataFrame(puts_data)
        return calls, puts

    @patch("src.option_analyst.get_option_chain")
    def test_calculate_pcr(self, mock_get_chain, mock_option_data):
        """Test Put/Call Ratio calculation."""
        mock_get_chain.return_value = mock_option_data

        pcr = calculate_pcr("TEST")

        assert pcr is not None
        assert pcr["ticker"] == "TEST"

        # Call Vol: 100+50+10 = 160
        # Put Vol: 20+30+80 = 130
        expected_vol_pcr = 130 / 160
        assert pcr["volume_pcr"] == pytest.approx(expected_vol_pcr)

        # Call OI: 1000+500+100 = 1600
        # Put OI: 200+300+800 = 1300
        expected_oi_pcr = 1300 / 1600
        assert pcr["oi_pcr"] == pytest.approx(expected_oi_pcr)

    @patch("src.option_analyst.DataProvider.get_current_price")
    @patch("src.option_analyst.get_option_chain")
    def test_calculate_gex(self, mock_get_chain, mock_get_price, mock_option_data):
        """Test Gamma Exposure calculation."""
        mock_get_chain.return_value = mock_option_data
        mock_get_price.return_value = 100.0  # Current Price = 100

        gex = calculate_gex("TEST")

        assert gex is not None
        assert gex["current_price"] == 100.0

        # Check specific GEX logic
        # Call GEX (Strike 100): gamma(0.05) * oi(1000) * 100 * price(100) = 500,000
        # Put GEX (Strike 100): -gamma(0.05) * oi(800) * 100 * price(100) = -400,000
        # Net GEX at Strike 100 should be 500k - 400k = 100k

        strike_100 = next(
            (item for item in gex["strike_gex"] if item["strike"] == 100), None
        )
        assert strike_100 is not None
        assert strike_100["gex"] == pytest.approx(100000.0)

        # Total GEX check
        # Call GEX Total: 100(500k) + 105(0.04*500*100*100=200k) + 110(0.02*100*100*100=20k) = 720k
        # Put GEX Total: 90(-0.03*200*100*100=-60k) + 95(-0.04*300*100*100=-120k) + 100(-400k) = -580k
        # Net Total = 720k - 580k = 140k
        assert gex["total_gex"] == pytest.approx(140000.0)

    @patch("src.option_analyst.get_option_chain")
    def test_none_data(self, mock_get_chain):
        """Test handling of missing data."""
        mock_get_chain.return_value = None
        assert calculate_pcr("TEST") is None
        assert calculate_gex("TEST") is None

    @patch("src.option_analyst.DataProvider.get_current_price", return_value=0.0)
    @patch("src.option_analyst.get_option_chain")
    def test_gex_is_unavailable_without_current_price(
        self, mock_get_chain, _mock_price, mock_option_data
    ):
        mock_get_chain.return_value = mock_option_data

        assert calculate_gex("TEST") is None

    def test_estimated_gamma_decreases_away_from_atm(self):
        calls = pd.DataFrame(
            {
                "strike": [100, 120],
                "volume": [1, 1],
                "openInterest": [100, 100],
                "impliedVolatility": [0.2, 0.2],
                "gamma": [0.05, None],
            }
        )
        puts = pd.DataFrame(columns=calls.columns)

        result = calculate_gex(
            "TEST",
            calls=calls,
            puts=puts,
            current_price=100.0,
            allow_gamma_estimation=True,
        )

        assert result is not None
        by_strike = {item["strike"]: item["gex"] for item in result["strike_gex"]}
        assert by_strike[100] > by_strike[120] > 0
        assert result["is_estimated"] is True

    def test_gex_hidden_when_gamma_missing(self, mock_option_data):
        calls, puts = mock_option_data
        calls = calls.drop(columns=["gamma"])
        puts = puts.drop(columns=["gamma"])

        gex = calculate_gex("TEST", calls=calls, puts=puts, current_price=100.0)

        assert gex is None

    def test_marketdata_gex_excludes_missing_gamma_without_estimation(
        self, mock_option_data
    ):
        calls, puts = mock_option_data
        calls.loc[0, "gamma"] = None

        gex = calculate_gex(
            "TEST",
            calls=calls,
            puts=puts,
            current_price=100.0,
            allow_gamma_estimation=False,
        )

        assert gex is not None
        assert gex["is_estimated"] is False
        assert gex["is_partial"] is True
        assert gex["missing_gamma_count"] == 1

    @patch("src.option_analyst.DataProvider.get_current_price", return_value=100.0)
    @patch("src.option_analyst.get_option_chain_metadata", return_value={})
    @patch("src.option_analyst.get_option_chain")
    def test_analyze_option_sentiment_marks_missing_gamma_partial(
        self, mock_get_chain, _mock_metadata, _mock_price, mock_option_data
    ):
        calls, puts = mock_option_data
        mock_get_chain.return_value = (
            calls.drop(columns=["gamma"]),
            puts.drop(columns=["gamma"]),
        )

        result = analyze_option_sentiment("TEST")

        assert result is not None
        assert result["gex"] is None
        assert result["data_quality"] == "partial"
        assert any("GEX is hidden" in w for w in result["quality_warnings"])

    @patch("src.option_analyst.DataProvider.get_current_price", return_value=100.0)
    @patch(
        "src.option_analyst.get_option_chain_metadata",
        return_value={
            "source": "yfinance",
            "provider_active": False,
            "fallback_reason": "MarketData.app token unavailable; yfinance fallback active.",
        },
    )
    @patch("src.option_analyst.get_option_chain")
    def test_analyze_option_sentiment_hides_gex_without_marketdata_direct_greeks(
        self, mock_get_chain, _mock_metadata, _mock_price, mock_option_data
    ):
        mock_get_chain.return_value = mock_option_data

        result = analyze_option_sentiment("TEST")

        assert result is not None
        assert result["gex"] is None
        assert result["provider_active"] is False
        assert result["gamma_coverage"] == pytest.approx(1.0)
        assert result["complete_status"] == "fallback"
        assert any("yfinance fallback" in w for w in result["quality_warnings"])

    @patch("src.option_analyst.DataProvider.get_current_price", return_value=100.0)
    @patch(
        "src.option_analyst.get_option_chain_metadata",
        return_value={"source": "marketdata.app", "provider_active": True},
    )
    @patch("src.option_analyst.get_option_chain")
    def test_analyze_option_sentiment_marks_complete_for_marketdata_direct_greeks(
        self, mock_get_chain, _mock_metadata, _mock_price, mock_option_data
    ):
        calls, puts = (frame.copy() for frame in mock_option_data)
        calls["delta"] = [0.50, 0.35, 0.25]
        puts["delta"] = [-0.25, -0.35, -0.50]
        for frame in (calls, puts):
            frame["bid"] = 1.0
            frame["ask"] = 1.2
            frame["mid"] = 1.1
        mock_get_chain.return_value = calls, puts

        result = analyze_option_sentiment("TEST")

        assert result is not None
        assert result["gex"] is not None
        assert result["provider_active"] is True
        assert result["gamma_coverage"] == pytest.approx(1.0)
        assert result["complete_status"] == "complete"

    def test_assess_option_data_quality_flags_zero_oi(self):
        calls = pd.DataFrame(
            {
                "strike": [100],
                "volume": [0],
                "openInterest": [0],
                "impliedVolatility": [0],
            }
        )
        puts = pd.DataFrame(
            {
                "strike": [100],
                "volume": [0],
                "openInterest": [0],
                "impliedVolatility": [0],
            }
        )

        quality = assess_option_data_quality(calls, puts)

        assert quality["data_quality"] == "unreliable"
        assert any("Open interest" in w for w in quality["quality_warnings"])

    @patch("src.option_analyst.DataProvider.get_current_price", return_value=100.0)
    @patch("src.option_analyst.get_option_chain")
    def test_calculate_atm_iv_fetch_path_unpacks_metadata(
        self, mock_get_chain, _mock_get_price, mock_option_data
    ):
        """The public ticker path should work when _fetch_option_data returns metadata."""
        mock_get_chain.return_value = mock_option_data

        iv = calculate_atm_iv("TEST")

        assert iv == pytest.approx(0.19)

    @patch("src.option_analyst.DataProvider.get_current_price", return_value=100.0)
    @patch("src.option_analyst.get_option_chain_metadata")
    @patch("src.option_analyst.get_option_chain")
    def test_analyze_option_sentiment_adds_horizon_structure(
        self, mock_get_chain, mock_metadata, _mock_price, mock_option_data
    ):
        calls, puts = mock_option_data

        def chain(_ticker, **kwargs):
            target_dte = kwargs.get("target_dte")
            calls_copy = calls.copy()
            puts_copy = puts.copy()
            dte = 1 if target_dte is None else target_dte
            calls_copy["dte"] = dte
            puts_copy["dte"] = dte
            calls_copy["underlyingPrice"] = 100.0
            puts_copy["underlyingPrice"] = 100.0
            return calls_copy, puts_copy

        def metadata(_ticker, *, target_dte=None):
            return {
                "source": "marketdata.app",
                "provider_active": True,
                "resolved_dte": 1 if target_dte is None else target_dte,
                "resolved_expiration": f"2026-07-{1 if target_dte is None else target_dte:02d}",
            }

        mock_get_chain.side_effect = chain
        mock_metadata.side_effect = metadata

        result = analyze_option_sentiment("TEST", allow_marketdata=True)

        assert result is not None
        assert [item["key"] for item in result["horizons"]] == [
            "current",
            "one_week",
            "one_month",
        ]
        assert result["iv"] == pytest.approx(result["horizons"][0]["iv"])
        assert result["term_structure"]["one_week_iv"] is not None
        assert result["horizons"][1]["target_dte"] == 7
        assert result["horizons"][2]["target_dte"] == 30

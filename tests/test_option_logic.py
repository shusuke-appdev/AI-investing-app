import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from src.option_analyst import calculate_pcr, calculate_gex

class TestOptionAnalyst:
    
    @pytest.fixture
    def mock_option_data(self):
        # Create sample Calls
        calls_data = {
            "strike": [100, 105, 110],
            "volume": [100, 50, 10],
            "openInterest": [1000, 500, 100],
            "gamma": [0.05, 0.04, 0.02],
            "impliedVolatility": [0.2, 0.18, 0.15]
        }
        calls = pd.DataFrame(calls_data)
        
        # Create sample Puts
        puts_data = {
            "strike": [90, 95, 100],
            "volume": [20, 30, 80],
            "openInterest": [200, 300, 800],
            "gamma": [0.03, 0.04, 0.05],
            "impliedVolatility": [0.22, 0.20, 0.18]
        }
        puts = pd.DataFrame(puts_data)
        return calls, puts

    @patch('src.option_analyst.get_option_chain')
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

    @patch('src.option_analyst.get_quote')
    @patch('src.option_analyst.get_option_chain')
    def test_calculate_gex(self, mock_get_chain, mock_quote, mock_option_data):
        """Test Gamma Exposure calculation."""
        mock_get_chain.return_value = mock_option_data
        mock_quote.return_value = {"c": 100.0} # Current Price = 100
        
        gex = calculate_gex("TEST")
        
        assert gex is not None
        assert gex["current_price"] == 100.0
        
        # Check specific GEX logic
        # Call GEX (Strike 100): gamma(0.05) * oi(1000) * 100 * price(100) = 500,000
        # Put GEX (Strike 100): -gamma(0.05) * oi(800) * 100 * price(100) = -400,000
        # Net GEX at Strike 100 should be 500k - 400k = 100k
        
        strike_100 = next((item for item in gex["strike_gex"] if item["strike"] == 100), None)
        assert strike_100 is not None
        assert strike_100["gex"] == pytest.approx(100000.0)
        
        # Total GEX check
        # Call GEX Total: 100(500k) + 105(0.04*500*100*100=200k) + 110(0.02*100*100*100=20k) = 720k
        # Put GEX Total: 90(-0.03*200*100*100=-60k) + 95(-0.04*300*100*100=-120k) + 100(-400k) = -580k
        # Net Total = 720k - 580k = 140k
        assert gex["total_gex"] == pytest.approx(140000.0)

    @patch('src.option_analyst.get_option_chain')
    def test_none_data(self, mock_get_chain):
        """Test handling of missing data."""
        mock_get_chain.return_value = None
        assert calculate_pcr("TEST") is None
        assert calculate_gex("TEST") is None

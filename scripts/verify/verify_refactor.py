import os
import sys

sys.path.append(os.getcwd())
from unittest.mock import MagicMock

# Mock streamlit before importing the service
mock_st = MagicMock()
mock_st.session_state = {"gemini_configured": True}
sys.modules["streamlit"] = mock_st

# Mock other dependencies to avoid API calls
sys.modules["src.finnhub_client"] = MagicMock()
sys.modules["src.market_data"] = MagicMock()
sys.modules["src.theme_analyst"] = MagicMock()
sys.modules["src.news_aggregator"] = MagicMock()
sys.modules["src.news_analyst"] = MagicMock()
sys.modules["src.option_analyst"] = MagicMock()

# Setup return values for mocks

sys.modules["src.finnhub_client"].get_company_news.return_value = []
sys.modules["src.news_aggregator"].get_aggregated_news.return_value = []
sys.modules["src.news_aggregator"].merge_with_finnhub_news.return_value = []
sys.modules["src.market_data"].get_stock_data.return_value = MagicMock(empty=True)
sys.modules[
    "src.news_analyst"
].generate_market_recap.return_value = "Mock Recap Generated Successfully"

# Now import the service
from src.services.market_analyst_service import (  # noqa: E402
    generate_market_analysis_report,
)


def run_verification():
    print("Starting verification of market_analyst_service...")
    try:
        recap = generate_market_analysis_report("US")
        if recap == "Mock Recap Generated Successfully":
            print("SUCCESS: Service generated report correctly using mocks.")
        else:
            print(f"FAILURE: Unexpected return value: {recap}")
    except Exception as e:
        print(f"FAILURE: Service raised exception: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    run_verification()

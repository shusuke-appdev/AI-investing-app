import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# We will mock get_financials_reported availability or output
from src.market_data import get_stock_data


def verify_stock_data():
    print("--- Verifying Stock Data (MA Calculation) ---")
    ticker = "AAPL"

    print(f"Fetching 1y data for {ticker}...")
    df = get_stock_data(ticker, "1y")

    if df.empty:
        print("Dataset is empty. Skipping MA verification.")
        return

    print(f"Data shape: {df.shape}")

    # Calculate SMAs
    df["SMA200"] = df["Close"].rolling(window=200).mean()

    last_row = df.iloc[-1]

    if pd.notna(last_row["SMA200"]):
        print("[OK] SMA200 calculation successful.")
        print(f"SMA200: {last_row['SMA200']}")
    else:
        print("[WARN] SMA200 is NaN (insufficient data?).")


def test_financials_logic():
    print("\n--- Verifying Operating Income Logic (Mock) ---")

    # Mock data structure resembling Finnhub response
    mock_reports = [
        {
            "year": 2024,
            "quarter": 1,
            "filedDate": "2024-04-01",
            "report": {
                "ic": [
                    {"concept": "Revenues", "value": 1000},
                    {"concept": "OperatingIncomeLoss", "value": 200},
                    {"concept": "NetIncomeLoss", "value": 150},
                ]
            },
        }
    ]

    print("Testing extraction logic with mock data...")
    financials_data = []

    for item in mock_reports:
        # year = item.get("year") (Unused)
        # quarter = item.get("quarter") (Unused)
        report = item.get("report", {})
        ic = report.get("ic", [])

        revenue = 0
        operating_income = 0
        net_income = 0

        for entry in ic:
            concept = entry.get("concept", "")
            value = entry.get("value", 0)

            if concept in [
                "Revenues",
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "SalesRevenueNet",
                "SalesRevenueGoodsNet",
            ]:
                if revenue == 0:
                    revenue = value

            if concept in ["OperatingIncomeLoss", "OperatingIncome"]:
                if operating_income == 0:
                    operating_income = value

            if concept in ["NetIncomeLoss", "ProfitLoss"]:
                if net_income == 0:
                    net_income = value

        financials_data.append(
            {
                "revenue": revenue,
                "operating_income": operating_income,
                "net_income": net_income,
            }
        )

    res = financials_data[0]
    print(f"Result: {res}")

    if res["operating_income"] == 200:
        print("[OK] Operating Income extracted correctly.")
    else:
        print(
            f"[FAIL] Operating Income extraction failed. Got {res['operating_income']}"
        )


if __name__ == "__main__":
    try:
        verify_stock_data()
        test_financials_logic()
    except Exception as e:
        print(f"Verification failed: {e}")

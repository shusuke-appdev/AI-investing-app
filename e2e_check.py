import os
import sys

# プロジェクトルートにパスを追加
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.advisor.technical import get_technical_summary_for_ai


def main():
    ticker = "TSLA"
    print(f"Running E2E verification for {ticker}...")

    summary = get_technical_summary_for_ai(ticker)

    print("\n--- Technical Summary ---")
    print(summary)
    print("-------------------------\n")

    assert "TSLA" in summary
    assert "総合" in summary
    assert "平均回帰・過熱感" in summary
    print("✅ E2E Verification Passed!")


if __name__ == "__main__":
    main()

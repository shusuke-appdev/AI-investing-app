import logging
import os
import sys

# 将来的に相対インポート解決のためパスを通す
sys.path.append(os.getcwd())

from src.data_provider import DataProvider

# ロガー設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_translation():
    print("=== Translation Verification Start ===")

    # 1. Company Summary Verification (AAPL)
    print("\n[1] Verifying Company Summary Translation (AAPL)...")
    try:
        # Note: Cache might prevent re-fetching if TTL hasn't expired.
        # Ideally clear cache or use a different ticker if possible, but let's try AAPL first.
        # If it returns English, we might need to clear Streamlit cache.
        # However, DataProvider.get_stock_info is st.cache_data wrapped.
        # Running this script outside streamlit run doesn't use the cache persistence usually
        # unless configured.

        info = DataProvider.get_stock_info("AAPL")
        summary = info.get("summary", "")

        # Check if Japanese characters exist
        has_japanese = any(
            "\u3040" <= char <= "\u309f"
            or "\u30a0" <= char <= "\u30ff"
            or "\u4e00" <= char <= "\u9fff"
            for char in summary
        )

        if summary and summary != "情報なし":
            if has_japanese:
                print("[OK] Success: Summary contains Japanese characters.")
                print(f"Sample (first 50 chars): {summary[:50]}...")
            else:
                print("[WARN] Warning: Summary seems to be English only.")
                print(f"Sample: {summary[:50]}...")
        else:
            print("[WARN] Warning: Summary is empty or '情報なし'.")

    except Exception as e:
        print(f"[ERROR]Verification failed: {e}")

    print("\n=== Verification End ===")


if __name__ == "__main__":
    verify_translation()

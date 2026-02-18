
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

print("Checking critical imports...")

try:
    from src.data_provider import DataProvider
    print(f"[OK] imported DataProvider: {DataProvider}")
    
    # Check if critical methods exist
    assert hasattr(DataProvider, "get_stock_info")
    assert hasattr(DataProvider, "get_stock_news")
    assert hasattr(DataProvider, "get_option_chain")
    print("[OK] DataProvider methods verified")

except ImportError as e:
    print(f"[FAIL] ImportError: {e}")
    sys.exit(1)
except AttributeError as e:
    print(f"[FAIL] AttributeError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[FAIL] Unexpected error: {e}")
    sys.exit(1)

print("Integrity check passed.")

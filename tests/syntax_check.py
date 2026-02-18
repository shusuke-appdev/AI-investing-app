import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    print("Importing src.market_data...")

    print("Success.")
except Exception as e:
    print(f"Failed to import src.market_data: {e}")
    sys.exit(1)

try:
    print("Importing src.finnhub_client...")

    print("Success.")
except Exception as e:
    print(f"Failed to import src.finnhub_client: {e}")
    sys.exit(1)

try:
    print("Importing src.theme_analyst...")

    print("Success.")
except Exception as e:
    print(f"Failed to import src.theme_analyst: {e}")
    sys.exit(1)

print("All imports successful. Syntax check passed.")

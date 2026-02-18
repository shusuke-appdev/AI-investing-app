import importlib
import os
import sys

import streamlit as st

# Required external packages (install name -> import name)
REQUIRED_PACKAGES = {
    "streamlit": "streamlit",
    "pandas": "pandas",
    "numpy": "numpy",
    "yfinance": "yfinance",
    "finnhub-python": "finnhub",  # pip name vs import name
    "requests": "requests",
    "plotly": "plotly",
    "google-generativeai": "google.generativeai",
}

# Required internal modules
REQUIRED_MODULES = [
    "src.market_data",
    "src.finnhub_client",
    "src.news_analyst",
    "src.option_analyst",
    "src.ui.market_tab",
    "src.ui.stock_tab",
    "src.ui.portfolio_tab",
    "src.ui.theme_tab",
]


def check_package(pip_name, import_name):
    try:
        if "." in import_name:
            # Handle nested imports logic if needed, but import_module handles dots
            importlib.import_module(import_name)
        else:
            importlib.import_module(import_name)
        print(f"[OK] Package '{pip_name}' (import: {import_name})")
        return True
    except ImportError as e:
        print(f"[FAIL] Package '{pip_name}' not found: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected error checking '{pip_name}': {e}")
        return False


def check_local_module(module_name):
    try:
        importlib.import_module(module_name)
        print(f"[OK] Module '{module_name}'")
        return True
    except ImportError as e:
        print(f"[FAIL] Module '{module_name}' failed to import: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Module '{module_name}' raised compilation/execution error: {e}")
        return False


def check_env_vars():
    # Only verify critical API keys if we want to be strict,
    # but for "app startup" we might just warn.
    keys = ["FINNHUB_API_KEY", "GEMINI_API_KEY"]
    all_present = True
    print("\n[Checking Environment Variables]")

    # Try loading from .env first if dotenv exists
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    # Check secrets safely
    secrets_present = False
    try:
        # Just accessing st.secrets might raise FileNotFoundError if no file exists
        if st.secrets:
            secrets_present = True
    except FileNotFoundError:
        print("[INFO] No secrets.toml found (expected in local dev if not using .env)")
    except Exception:
        pass

    for key in keys:
        if secrets_present and key in st.secrets:
            print(f"[OK] {key} found in st.secrets")
        elif key in os.environ:
            print(f"[OK] {key} found in os.environ")
        else:
            print(f"[WARN] {key} missing. Some features will be disabled.")
            # Not a critical failure for app startup, but good to know
    return all_present


def main():
    print("==========================================")
    print("   AI Investing App - Deployment Check    ")
    print("==========================================")

    # Ensure current directory is in path for src imports
    sys.path.insert(0, os.getcwd())

    # 1. Check External Packages
    print("\n--- 1. External Dependencies ---")
    pkg_results = [check_package(p, i) for p, i in REQUIRED_PACKAGES.items()]

    # 2. Check Local Modules
    print("\n--- 2. Internal Modules ---")
    mod_results = [check_local_module(m) for m in REQUIRED_MODULES]

    # 3. Env Vars
    check_env_vars()

    if all(pkg_results) and all(mod_results):
        print("\n[PASS] SYSTEM CHECK PASSED: Ready for Deployment")
        sys.exit(0)
    else:
        print("\n[FAIL] SYSTEM CHECK FAILED: Fix errors before deploying")
        sys.exit(1)


if __name__ == "__main__":
    main()

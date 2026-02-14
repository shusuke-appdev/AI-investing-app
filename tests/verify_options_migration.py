"""
Verification script for Finnhub options migration.
Tests the new DataProvider.get_option_chain and option_analyst functions.
"""
import sys
import os
sys.path.insert(0, os.getcwd())

LOG_FILE = "verify_options_migration.log"

def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def main():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=== Options Migration Verification ===\n")

    # 1. Test DataProvider.get_option_chain
    log("\n--- Test 1: DataProvider.get_option_chain ---")
    from src.data_provider import DataProvider
    
    result = DataProvider.get_option_chain("SPY")
    if result is None:
        log("[FAIL] get_option_chain returned None")
        return
    
    calls, puts = result
    log(f"[OK] Calls: {len(calls)} rows, Puts: {len(puts)} rows")
    log(f"  Calls columns: {list(calls.columns)}")
    
    # Check Greeks are present
    greeks = ["delta", "gamma", "theta", "vega", "rho"]
    missing = [g for g in greeks if g not in calls.columns]
    if missing:
        log(f"[WARN] Missing Greeks in calls: {missing}")
    else:
        log(f"[OK] All Greeks present: {greeks}")
    
    # Show sample ATM call
    if "strike" in calls.columns and len(calls) > 0:
        mid_idx = len(calls) // 2
        sample = calls.iloc[mid_idx]
        log(f"  Sample Call (strike={sample.get('strike')}):")
        for g in greeks:
            log(f"    {g}: {sample.get(g, 'N/A')}")
    
    # 2. Test option_analyst functions
    log("\n--- Test 2: calculate_pcr ---")
    from src.option_analyst import calculate_pcr
    pcr = calculate_pcr("SPY")
    if pcr:
        log(f"[OK] Volume PCR: {pcr['volume_pcr']:.4f}, OI PCR: {pcr['oi_pcr']:.4f}")
        log(f"  Call Vol: {pcr['total_call_volume']}, Put Vol: {pcr['total_put_volume']}")
        log(f"  Call OI: {pcr['total_call_oi']}, Put OI: {pcr['total_put_oi']}")
    else:
        log("[FAIL] calculate_pcr returned None")
    
    log("\n--- Test 3: calculate_gex ---")
    from src.option_analyst import calculate_gex
    gex = calculate_gex("SPY")
    if gex:
        log(f"[OK] Total GEX: {gex['total_gex']:.2f}")
        log(f"  Current Price: {gex['current_price']}")
        log(f"  Nearby Net GEX: {gex['nearby_net_gex']:.2f}")
        if gex['positive_wall']:
            log(f"  +Wall: ${gex['positive_wall']['strike']:.0f}")
        if gex['negative_wall']:
            log(f"  -Wall: ${gex['negative_wall']['strike']:.0f}")
    else:
        log("[FAIL] calculate_gex returned None")
    
    log("\n--- Test 4: calculate_max_pain ---")
    from src.option_analyst import calculate_max_pain
    mp = calculate_max_pain("SPY")
    if mp:
        log(f"[OK] Max Pain: ${mp:.0f}")
    else:
        log("[FAIL] calculate_max_pain returned None")
    
    log("\n--- Test 5: calculate_atm_iv ---")
    from src.option_analyst import calculate_atm_iv
    iv = calculate_atm_iv("SPY")
    if iv:
        log(f"[OK] ATM IV: {iv:.1%}")
    else:
        log("[FAIL] calculate_atm_iv returned None (may be expected for deep OTM)")
    
    log("\n--- Test 6: analyze_option_sentiment ---")
    from src.option_analyst import analyze_option_sentiment
    sentiment = analyze_option_sentiment("SPY")
    if sentiment:
        log(f"[OK] Sentiment: {sentiment['sentiment']}")
        for a in sentiment.get('analysis', []):
            log(f"  - {a}")
    else:
        log("[FAIL] analyze_option_sentiment returned None")
    
    log("\n=== Verification Complete ===")

if __name__ == "__main__":
    main()

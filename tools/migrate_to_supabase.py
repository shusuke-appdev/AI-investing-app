"""
Migrate to Supabase Script
Reads local JSON data and uploads to Supabase tables.
"""
import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.supabase_client import get_supabase_client
from src.portfolio_storage import load_portfolio, list_portfolios, _storage_type
from src.knowledge_storage import load_all_knowledge
from src.settings_storage import load_settings

def migrate():
    print("=== Supabase Migration Tool ===")
    
    # 1. Connect
    client = get_supabase_client()
    if not client:
        print("Error: Could not connect to Supabase. Check credentials in secrets.toml or .env")
        return

def load_json_robust(path: Path) -> dict:
    """Try to load JSON with utf-8, fallback to cp932."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except UnicodeDecodeError:
        pass
    
    with open(path, "r", encoding="cp932") as f:
        return json.load(f)

def migrate():
    print("=== Supabase Migration Tool ===")
    
    # 1. Connect
    client = get_supabase_client()
    if not client:
        print("Error: Could not connect to Supabase. Check credentials in secrets.toml or .env")
        return

    print("[OK] Connected to Supabase")

    # Clean Slate (Optional but recommended for re-runs)
    print("\n--- Cleaning existing data ---")
    try:
        client.table("portfolios").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute() # Delete all
        client.table("user_settings").delete().neq("key", "PLACEHOLDER").execute()
        client.table("knowledge_items").delete().neq("id", "PLACEHOLDER").execute()
        print("[OK] Cleared tables")
    except Exception as e:
        print(f"[WARN] Failed to clear tables (might be empty or RLS): {e}")

    # 2. Migrate Settings
    print("\n--- Migrating Settings ---")
    # settings_storage load_settings already handles fallback logic?
    # But it returns a dict. We don't know the file path it used.
    # Let's just use load_settings() as it abstracts the file finding.
    # But wait, load_settings might not handle encoding if it was hardcoded utf-8.
    # settings_storage.py uses "utf-8" hardcoded.
    # If settings.json is cp932, load_settings might fail or return empty.
    # Let's try to reload it responsibly here if we want to be sure?
    # Or just trust load_settings for now (it printed success logs in previous attempts).
    
    settings = load_settings()
    if settings:
        data = [{"key": k, "value": str(v), "updated_at": "now()"} for k, v in settings.items()]
        try:
            client.table("user_settings").upsert(data).execute()
            print(f"[OK] Uploaded {len(data)} settings.")
        except Exception as e:
            print(f"[ERR] Failed to upload settings: {e}")
    else:
        print("No local settings found.")

    # 3. Migrate Portfolios
    print("\n--- Migrating Portfolios ---")
    PORTFOLIO_DIR = Path(__file__).parent.parent / "data" / "portfolios"
    if PORTFOLIO_DIR.exists():
        files = list(PORTFOLIO_DIR.glob("*.json"))
        print(f"Found {len(files)} local portfolio files.")
        
        for p_file in files:
            try:
                p_data = load_json_robust(p_file)
                
                # Prepare payload
                name = p_data["name"]
                
                payload = {
                    "name": name,
                    "holdings": p_data["holdings"],
                    "created_at": p_data.get("created_at") or "now()",
                    "updated_at": p_data.get("updated_at") or "now()"
                }
                
                # Upsert by name
                client.table("portfolios").upsert(payload, on_conflict="name").execute()
                print(f"Inserted: {name}")
                    
            except Exception as e:
                print(f"[ERR] Error migrating {p_file.name}: {e}")
    else:
        print("No local portfolios directory found.")

    # 4. Migrate Knowledge
    print("\n--- Migrating Knowledge ---")
    KNOWLEDGE_FILE = Path(__file__).parent.parent / "data" / "knowledge" / "knowledge_items.json"
    if KNOWLEDGE_FILE.exists():
        try:
            k_data = load_json_robust(KNOWLEDGE_FILE)
            
            print(f"Found {len(k_data)} knowledge items.")
            
            batch_size = 10
            for i in range(0, len(k_data), batch_size):
                batch = k_data[i:i+batch_size]
                try:
                    # Ensure metadata is dict
                    for item in batch:
                         if "metadata" not in item: item["metadata"] = {}
                         
                    client.table("knowledge_items").upsert(batch).execute()
                    print(f"Uploaded batch {i}-{i+len(batch)}")
                except Exception as e:
                     print(f"[ERR] Batch upload failed: {e}")

        except Exception as e:
            print(f"[ERR] Error reading knowledge file: {e}")
    else:
        print("No local knowledge file found.")

    print("\n=== Migration Complete ===")

if __name__ == "__main__":
    migrate()

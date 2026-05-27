"""
Supabase Client Module
Provides a singleton instance of the Supabase client.
"""

import os

from src.log_config import get_logger
from supabase import Client, create_client

logger = get_logger(__name__)

_supabase_client: Client | None = None


def get_supabase_client() -> Client | None:
    """
    Get or create the Supabase client singleton.
    Reads credentials from environment variables.
    """
    global _supabase_client

    if _supabase_client:
        return _supabase_client

    try:
        url = os.getenv("SUPABASE_URL")
        key = (
            os.getenv("SUPABASE_SECRET_KEY")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_KEY")
        )

        if not url or not key:
            return None

        _supabase_client = create_client(url, key)
        return _supabase_client

    except Exception as e:
        logger.info(f"Failed to initialize Supabase client: {e}")
        return None

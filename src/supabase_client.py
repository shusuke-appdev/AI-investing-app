"""
Supabase Client Module
Provides a singleton instance of the Supabase client.
"""

import os
from typing import Optional

import streamlit as st
from supabase import Client, create_client

from src.log_config import get_logger

logger = get_logger(__name__)

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """
    Get or create the Supabase client singleton.
    Reads credentials from Streamlit secrets or environment variables.
    """
    global _supabase_client

    if _supabase_client:
        return _supabase_client

    try:
        url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")

        if not url or not key:
            return None

        _supabase_client = create_client(url, key)
        return _supabase_client

    except Exception as e:
        logger.info(f"Failed to initialize Supabase client: {e}")
        return None

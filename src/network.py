"""
Centralized Networking Module
Provides a shared session with User-Agent, timeouts, and optional caching.
"""

import requests
import streamlit as st

from src.log_config import get_logger

logger = get_logger(__name__)

# Constants
DEFAULT_TIMEOUT = 10  # seconds
CACHE_EXPIRE_SECONDS = 3600  # 1 hour
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@st.cache_resource
def get_session(
    cache_name: str = "app_cache", expire_after: int = CACHE_EXPIRE_SECONDS
) -> requests.Session:
    """
    Returns a configured requests session.
    Uses requests-cache if available, otherwise falls back to standard requests.Session.
    """
    session = None

    try:
        import requests_cache

        session = requests_cache.CachedSession(cache_name, expire_after=expire_after)
    except ImportError:
        logger.info(
            "[NETWORK_WARN] requests_cache not found. Using standard session without caching."
        )
        session = requests.Session()
    except Exception as e:
        logger.error(f"Failed to initialize cache: {e}. Using standard session.")
        session = requests.Session()

    session.headers.update({"User-Agent": USER_AGENT})
    return session


def get_retry_session() -> requests.Session:
    """
    Returns a session configured for retries (if needed in future).
    Currently just wraps get_session.
    """
    return get_session()


def safe_request(
    url: str, params: dict = None, timeout: int = DEFAULT_TIMEOUT
) -> requests.Response:
    """
    Wrapper for safe HTTP GET requests with error handling.
    """
    session = get_session()
    try:
        response = session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")
        raise e

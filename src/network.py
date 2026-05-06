"""
Centralized Networking Module
Provides a shared session with User-Agent, timeouts, and optional caching.
"""

import functools

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.log_config import get_logger

logger = get_logger(__name__)

# Constants
DEFAULT_TIMEOUT = 10  # seconds
CACHE_EXPIRE_SECONDS = 3600  # 1 hour
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Retry Configuration
RETRY_TOTAL = 3
RETRY_BACKOFF_FACTOR = 0.5
RETRY_STATUS_FORCELIST = [429, 500, 502, 503, 504]

# シングルトンのセッションを保持
_session: requests.Session | None = None


def get_session(
    cache_name: str = "app_cache", expire_after: int = CACHE_EXPIRE_SECONDS
) -> requests.Session:
    """
    Returns a configured requests session with automatic retries and exponential backoff.
    Uses requests-cache if available, otherwise falls back to standard requests.Session.
    """
    global _session
    if _session is not None:
        return _session

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

    # Configure Retries
    retry_strategy = Retry(
        total=RETRY_TOTAL,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_FORCELIST,
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    _session = session
    return _session


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

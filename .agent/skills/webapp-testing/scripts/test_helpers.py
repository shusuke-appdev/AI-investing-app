"""
Helper utilities for web application testing with Playwright (Python)
"""
import time
import datetime
from typing import Callable, Any, List, Dict
from playwright.sync_api import Page

def wait_for_condition(condition: Callable[[], bool], timeout: float = 5.0, interval: float = 0.1) -> bool:
    """
    Wait for a condition to be true with timeout
    
    Args:
        condition: Function that returns boolean
        timeout: Timeout in seconds
        interval: Check interval in seconds
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition():
            return True
        time.sleep(interval)
    raise TimeoutError('Condition not met within timeout')

def capture_console_logs(page: Page) -> List[Dict[str, Any]]:
    """
    Capture browser console logs
    
    Args:
        page: Playwright page object
    
    Returns:
        List of console messages
    """
    logs = []
    def handler(msg):
        logs.append({
            "type": msg.type,
            "text": msg.text,
            "timestamp": datetime.datetime.now().isoformat()
        })
    
    page.on("console", handler)
    return logs

def capture_screenshot(page: Page, name: str) -> str:
    """
    Take screenshot with automatic naming
    
    Args:
        page: Playwright page object
        name: Base name for screenshot
    
    Returns:
        Filename of the saved screenshot
    """
    timestamp = datetime.datetime.now().isoformat().replace(":", "-").replace(".", "-")
    filename = f"{name}-{timestamp}.png"
    page.screenshot(path=filename, full_page=True)
    print(f"Screenshot saved: {filename}")
    return filename

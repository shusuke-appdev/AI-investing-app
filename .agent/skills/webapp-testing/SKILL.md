---
name: webapp-testing
description: Toolkit for interacting with and testing local web applications using Playwright for Python. Supports verifying frontend functionality, debugging UI behavior, capturing browser screenshots, and viewing browser logs.
---

# Web Application Testing (Python)

This skill enables comprehensive testing and debugging of local web applications using Playwright for Python.

## When to Use This Skill

Use this skill when you need to:
- Test frontend functionality in a real browser
- Verify UI behavior and interactions
- Debug web application issues
- Capture screenshots for documentation or debugging
- Inspect browser console logs
- Validate form submissions and user flows
- Check responsive design across viewports

## Prerequisites

- Python installed on the system
- `pytest-playwright` installed (`pip install pytest-playwright`)
- Playwright browsers installed (`playwright install`)

## Core Capabilities

### 1. Browser Automation
- Navigate to URLs
- Click buttons and links
- Fill form fields
- Select dropdowns
- Handle dialogs and alerts

### 2. Verification
- Assert element presence
- Verify text content
- Check element visibility
- Validate URLs
- Test responsive behavior

### 3. Debugging
- Capture screenshots
- View console logs
- Inspect network requests
- Debug failed tests

## Usage Examples

### Example 1: Basic Navigation Test
```python
import re
from playwright.sync_api import Page, expect

def test_basic_navigation(page: Page):
    # Navigate to a page and verify title
    page.goto("http://localhost:8501")
    expect(page).to_have_title(re.compile("Streamlit"))
```

### Example 2: Form Interaction
```python
from playwright.sync_api import Page, expect

def test_form_interaction(page: Page):
    # Fill out and submit a form
    page.get_by_label("Username").fill("testuser")
    page.get_by_label("Password").fill("password123")
    page.get_by_role("button", name="Log in").click()
    
    # Verify navigation
    expect(page).to_have_url(re.compile(".*/dashboard"))
```

### Example 3: Screenshot Capture
```python
from playwright.sync_api import Page

def test_take_screenshot(page: Page):
    # Capture a screenshot for debugging
    page.screenshot(path="debug.png", full_page=True)
```

## Guidelines

1. **Always verify the app is running** - Check that the local server is accessible before running tests
2. **Use explicit assertions** - Use `expect` for waiting assertions (e.g., `expect(locator).to_be_visible()`)
3. **Capture screenshots on failure** - Configure pytest to take screenshots on failure
4. **Clean up resources** - Pytest fixtures normally handle cleanup, but be mindful of external state
5. **Handle timeouts gracefully** - Set reasonable timeouts for slow operations
6. **Test incrementally** - Start with simple interactions before complex flows
7. **Use selectors wisely** - Prefer user-facing locators like `get_by_role`, `get_by_text` over CSS classes

## Common Patterns

### Pattern: Wait for Element
```python
# Playwright auto-waits for actionability, but you can assert visibility
expect(page.locator("#element-id")).to_be_visible()
```

### Pattern: Check if Element Exists
```python
if page.locator("#element-id").count() > 0:
    print("Element exists")
```

### Pattern: Get Console Logs
```python
# In your test setup or fixture
page.on("console", lambda msg: print(f"Browser log: {msg.text}"))
```

### Pattern: Handle Errors
```python
try:
    page.click("#button")
except Exception as e:
    page.screenshot(path="error.png")
    raise e
```

## Limitations

- Requires `pytest` runner for best experience
- Cannot test native mobile apps
- May have issues with complex authentication flows (use `auth.json` storage state)

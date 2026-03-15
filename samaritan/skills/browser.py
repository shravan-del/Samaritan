"""
browser.py - Browser automation skill for Veritas using Playwright.

URL allowlist: localhost and LAN IP ranges only (security constraint).
Actions: navigate, extract_text, click, fill_form.

Install: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Only allow localhost and RFC-1918 private LAN addresses
ALLOWED_HOSTS = re.compile(
    r"^(localhost|127\.\d+\.\d+\.\d+|10\.\d+\.\d+\.\d+|"
    r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+)$"
)


def _is_allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return bool(ALLOWED_HOSTS.match(host))
    except Exception:
        return False


class BrowserSkill:
    """
    Browser automation via Playwright (LAN/localhost only).
    """

    description = (
        "Automate a web browser to interact with local/LAN web applications. "
        "Navigate pages, extract text, click elements, or fill forms. "
        "Only works with localhost and LAN URLs (e.g., http://localhost:8080). "
        "NOT for internet URLs."
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action: navigate, extract_text, click, fill_form.",
                "enum": ["navigate", "extract_text", "click", "fill_form"],
            },
            "url": {
                "type": "string",
                "description": "Target URL (localhost/LAN only).",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector for click/fill_form.",
            },
            "value": {
                "type": "string",
                "description": "Value to fill in a form field.",
            },
        },
        "required": ["action", "url"],
    }

    def __init__(self, guardian=None):
        self.guardian = guardian

    def execute(self, params: dict, session=None) -> str:
        action   = params.get("action", "navigate")
        url      = params.get("url", "")
        selector = params.get("selector", "")
        value    = params.get("value", "")

        if not _is_allowed_url(url):
            return (
                f"URL blocked: '{url}' is not a localhost or LAN address. "
                "Browser automation is restricted to local network URLs."
            )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return (
                "Playwright not installed. "
                "Install with: pip install playwright && playwright install chromium"
            )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=15000)

                if action == "navigate":
                    title = page.title()
                    browser.close()
                    return f"Navigated to: {url}\nPage title: {title}"

                elif action == "extract_text":
                    text = page.inner_text("body")
                    browser.close()
                    return text[:3000] + ("..." if len(text) > 3000 else "")

                elif action == "click":
                    if not selector:
                        browser.close()
                        return "Error: selector required for click."
                    page.click(selector)
                    browser.close()
                    return f"Clicked: {selector}"

                elif action == "fill_form":
                    if not selector or not value:
                        browser.close()
                        return "Error: selector and value required for fill_form."
                    page.fill(selector, value)
                    browser.close()
                    return f"Filled '{selector}'."

                browser.close()
        except Exception as e:
            logger.error("Browser action failed: %s", e)
            return f"Browser error: {str(e)}"

        return "Done."

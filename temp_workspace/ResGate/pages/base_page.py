"""Shared Page Object base — canonical scaffolding copied into every project's
pages/ folder by the harness. DO NOT regenerate per project; fixes belong in
core/templates/base_page.py. All Playwright calls live in the POM layer.

Selectors are the single source of truth in mcp-selectors/locators.json, resolved
relative to this file so the copy works inside any project's pages/ folder.
"""

import json
from pathlib import Path

from playwright.sync_api import expect

_LOCATORS_PATH = Path(__file__).parent.parent / "mcp-selectors" / "locators.json"


def load_locators():
    """Load the MCP-discovered selectors (the only source of truth for selectors)."""
    with _LOCATORS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


class BasePage:
    def __init__(self, page, base_url=None):
        self.page = page
        self.base_url = base_url
        self.loc = load_locators()

    def goto(self, url, timeout=30000):
        # Never networkidle — domcontentloaded + finite timeout, then wait on elements.
        self.page.goto(url, wait_until="domcontentloaded", timeout=timeout)

    def wait_visible(self, selector, timeout=30000):
        el = self.page.locator(selector).first
        expect(el).to_be_visible(timeout=timeout)
        return el

    def is_visible(self, selector, timeout=10000):
        try:
            expect(self.page.locator(selector).first).to_be_visible(timeout=timeout)
            return True
        except Exception:
            return False

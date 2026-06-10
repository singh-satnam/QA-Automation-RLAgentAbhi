from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from playwright.sync_api import Locator, Page, expect


class BasePage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self._locators = self._read_locators()

    def _read_locators(self) -> dict:
        locator_path = Path(__file__).resolve().parents[1] / "mcp-selectors" / "locators.json"
        try:
            data = json.loads(locator_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def selectors(self, page_key: str, key: str) -> list[str]:
        page_map = self._locators.get(page_key) or {}
        value = page_map.get(key, [])
        return value if isinstance(value, list) else [value]

    def first_visible(self, selectors: Iterable[str], timeout: int = 10000) -> Locator:
        for selector in selectors:
            locator = self.page.locator(selector).first
            try:
                expect(locator).to_be_visible(timeout=timeout)
                return locator
            except Exception:
                continue
        raise AssertionError(f"No visible selector found in {list(selectors)}")

    def click_any(self, selectors: Iterable[str], timeout: int = 10000, force: bool = False) -> None:
        locator = self.first_visible(selectors, timeout=timeout)
        locator.click(timeout=timeout, force=force)

    def fill_any(self, selectors: Iterable[str], value: str, timeout: int = 10000) -> None:
        locator = self.first_visible(selectors, timeout=timeout)
        locator.fill(value, timeout=timeout)

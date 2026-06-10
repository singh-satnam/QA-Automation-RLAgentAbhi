from __future__ import annotations

import pytest
from playwright.sync_api import BrowserContext, Page

# Step-def modules are registered via `pytest_plugins` in the root conftest.py
# (one entry per feature). No imports needed here.


class DialogRecorder:
    """Auto-accepts every JS alert/confirm/prompt and records the message text
    so step defs can assert on it."""

    def __init__(self) -> None:
        self.last: str | None = None
        self.messages: list[str] = []

    def __call__(self, dialog) -> None:
        try:
            self.last = dialog.message
            self.messages.append(dialog.message)
        except Exception:
            pass
        try:
            dialog.accept()
        except Exception:
            pass


@pytest.fixture()
def dialog_recorder(page: Page) -> DialogRecorder:
    rec = DialogRecorder()
    page.on("dialog", rec)
    return rec


@pytest.fixture(autouse=True)
def _ensure_clean_state(page: Page, context: BrowserContext, dialog_recorder: DialogRecorder):
    """Each scenario starts from a logged-out, cookie-clean context so the
    login step always lands on the login page."""
    try:
        page.context.clear_cookies()
    except Exception:
        pass
    try:
        page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
        page.evaluate(
            "() => { try { localStorage.clear(); sessionStorage.clear(); } catch (e) {} }"
        )
    except Exception:
        pass
    yield

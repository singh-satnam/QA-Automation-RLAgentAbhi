from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

pytest_plugins = ()

# Captured-values log: a per-session record of every value the test extracted,
# every assertion expected-vs-actual, every aggregate-sum check. The Auditor
# reads this AFTER pytest finishes to build the human-readable HTML report.
# Cleared at session start; appended throughout the run.
_CAPTURED_VALUES_PATH = Path("reports") / "captured_values.json"

# Per-step visual trace: one entry per Gherkin step (Given/When/Then), each with
# a Playwright screenshot of the page right after that step ran and a pass/fail
# status. The inline coverage report reads this to render a step-by-step gallery
# so a failure shows EXACTLY which step broke, with a picture. Reset each run.
_STEP_TRACE_PATH = Path("reports") / "step_trace.json"
_STEP_SCREENSHOT_DIR = Path("reports") / "screenshots"


def pytest_sessionstart(session: pytest.Session) -> None:
    """Reset the captured-values log + step trace + screenshots at the start of
    every pytest invocation so each run's report reflects only this run."""
    try:
        _CAPTURED_VALUES_PATH.parent.mkdir(parents=True, exist_ok=True)
        if _CAPTURED_VALUES_PATH.exists():
            _CAPTURED_VALUES_PATH.unlink()
    except OSError:
        pass
    try:
        if _STEP_TRACE_PATH.exists():
            _STEP_TRACE_PATH.unlink()
    except OSError:
        pass
    # Clear stale per-step screenshots so a shorter run can't leave higher-index
    # frames from a previous, longer run lying around.
    import shutil as _shutil
    try:
        if _STEP_SCREENSHOT_DIR.exists():
            _shutil.rmtree(_STEP_SCREENSHOT_DIR, ignore_errors=True)
        _STEP_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def _to_num(value):
    """Best-effort: parse $1,234.56 / 48.99 / '13%' / 100 → float. None if not parseable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).replace(",", "").replace("$", "").replace("%", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _product(xs):
    if not xs:
        return None
    result = 1.0
    for x in xs:
        result *= x
    return result


def _median(xs):
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


# Phrases that mean the application REJECTED a state-changing action
# (create / add / submit / save / update / register). When the backend says any
# of these — e.g. a toast reading "user already exists" — the action did NOT
# complete, so the test must FAIL there. Used by CaptureLog.assert_action_succeeded
# and mirrored by the report's verdict safety-net in agent_ui.py.
BACKEND_ERROR_MARKERS = (
    "already exists", "already in use", "already registered", "already taken",
    "exist", "exists",   # also catches "name exist" / "name already exist"
    "duplicate", "error:", "could not", "couldn't", "cannot ", "can't ",
    "unable to", "failed to", "failure", "was rejected", "rejected",
    "not created", "not saved", "not added", "invalid", "denied",
    "forbidden", "something went wrong", "please try again",
)


def looks_like_backend_error(text: str) -> bool:
    """True if `text` (a toast / server message captured right after an action)
    reads like the backend rejected that action. Callers typically pass an
    error-toast string, where any content already signals trouble — the marker
    list just makes the intent explicit and catches generic messages too."""
    if not text:
        return False
    low = " " + str(text).strip().lower() + " "
    return any(m in low for m in BACKEND_ERROR_MARKERS)


class CaptureLog:
    """Generic value-capture helper used by step defs.

    Universal usage (works for ANY website / story):
        cap.add("Manager name on toggle", actual_name)
        cap.assert_match("Manager name on toggle", expected="Nitin Kumar", actual=actual_name)
        cap.add_component("Sales revenue", "125000", group="dept_revenues")
        cap.assert_sum("Total revenue on super-admin dashboard",
                       group="dept_revenues", actual=displayed_total)

    Every call persists to reports/captured_values.json so even on failure
    the data the test gathered is in the Auditor's report."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.entries: list[dict] = []
        if path.exists():
            try:
                self.entries = json.loads(path.read_text(encoding="utf-8")).get("captures", [])
            except (OSError, ValueError):
                self.entries = []

    def add(self, label: str, value, **meta) -> None:
        """Record a value the test extracted (no assertion). E.g. price, name."""
        entry = {
            "label": str(label),
            "value": "" if value is None else str(value),
            "ts": datetime.now().strftime("%H:%M:%S"),
            "kind": meta.pop("kind", "value"),
        }
        entry.update(meta)
        self.entries.append(entry)
        self._persist()

    def assert_match(self, label: str, expected, actual, **meta) -> bool:
        """Record an expected-vs-actual check. Returns True if they match."""
        e, a = str(expected).strip(), "" if actual is None else str(actual).strip()
        passed = e == a or e.lower() == a.lower()
        entry = {
            "label": str(label),
            "kind": meta.pop("kind", "assertion"),
            "expected": e,
            "actual": a,
            "passed": passed,
            "ts": datetime.now().strftime("%H:%M:%S"),
        }
        entry.update(meta)
        self.entries.append(entry)
        self._persist()
        return passed

    def add_component(self, label: str, value, *, group: str, **meta) -> None:
        """Add a value that contributes to an aggregate (e.g. one dept revenue
        that will later be summed)."""
        try:
            num = float(str(value).replace(",", "").replace("$", "").strip())
        except (ValueError, TypeError):
            num = None
        entry = {
            "label": str(label),
            "kind": "component",
            "group": str(group),
            "value": "" if value is None else str(value),
            "numeric": num,
            "ts": datetime.now().strftime("%H:%M:%S"),
        }
        entry.update(meta)
        self.entries.append(entry)
        self._persist()

    # ---- Math aggregates ------------------------------------------------
    # `assert_aggregate` is the generic one. `assert_sum / avg / min / max /
    # count / product / range / median` are thin wrappers for ergonomic use.

    _OPS = {
        "sum":     lambda xs: sum(xs),
        "avg":     lambda xs: sum(xs) / len(xs) if xs else None,
        "mean":    lambda xs: sum(xs) / len(xs) if xs else None,
        "average": lambda xs: sum(xs) / len(xs) if xs else None,
        "min":     lambda xs: min(xs) if xs else None,
        "max":     lambda xs: max(xs) if xs else None,
        "count":   lambda xs: float(len(xs)),
        "product": lambda xs: _product(xs),
        "range":   lambda xs: (max(xs) - min(xs)) if xs else None,
        "median":  lambda xs: _median(xs),
    }

    def assert_aggregate(self, label: str, *, group: str, op: str, actual,
                         tolerance: float = 0.01) -> bool:
        """Generic aggregate assertion. `op` is one of:
        sum, avg/mean/average, min, max, count, product, range, median.
        Compares the computed value over every component in `group` to `actual`."""
        components = [e for e in self.entries
                      if e.get("kind") == "component" and e.get("group") == group]
        numerics = [e["numeric"] for e in components if isinstance(e.get("numeric"), (int, float))]
        op_key = (op or "sum").lower().strip()
        op_fn = self._OPS.get(op_key)
        if op_fn is None:
            raise ValueError(
                f"Unknown aggregate op '{op}'. Valid: {sorted(self._OPS)}"
            )
        computed = op_fn(numerics) if numerics or op_key == "count" else None
        try:
            actual_num = float(str(actual).replace(",", "").replace("$", "").replace("%", "").strip())
        except (ValueError, TypeError):
            actual_num = None
        passed = (
            computed is not None and actual_num is not None
            and abs(computed - actual_num) <= tolerance
        )
        self.entries.append({
            "label": str(label),
            "kind": "aggregate_assertion",
            "op": op_key,
            "group": str(group),
            "components": [{"label": c["label"], "value": c["value"]} for c in components],
            f"computed_{op_key}": computed,
            "actual": "" if actual is None else str(actual),
            "actual_numeric": actual_num,
            "tolerance": tolerance,
            "passed": passed,
            "ts": datetime.now().strftime("%H:%M:%S"),
        })
        self._persist()
        return passed

    def assert_sum(self, label, *, group, actual, tolerance=0.01):
        return self.assert_aggregate(label, group=group, op="sum",
                                     actual=actual, tolerance=tolerance)

    def assert_avg(self, label, *, group, actual, tolerance=0.01):
        return self.assert_aggregate(label, group=group, op="avg",
                                     actual=actual, tolerance=tolerance)

    def assert_min(self, label, *, group, actual, tolerance=0.01):
        return self.assert_aggregate(label, group=group, op="min",
                                     actual=actual, tolerance=tolerance)

    def assert_max(self, label, *, group, actual, tolerance=0.01):
        return self.assert_aggregate(label, group=group, op="max",
                                     actual=actual, tolerance=tolerance)

    def assert_count(self, label, *, group, actual):
        return self.assert_aggregate(label, group=group, op="count",
                                     actual=actual, tolerance=0.0001)

    def assert_product(self, label, *, group, actual, tolerance=0.01):
        return self.assert_aggregate(label, group=group, op="product",
                                     actual=actual, tolerance=tolerance)

    def assert_range(self, label, *, group, actual, tolerance=0.01):
        return self.assert_aggregate(label, group=group, op="range",
                                     actual=actual, tolerance=tolerance)

    def assert_median(self, label, *, group, actual, tolerance=0.01):
        return self.assert_aggregate(label, group=group, op="median",
                                     actual=actual, tolerance=tolerance)

    # ---- Cross-value arithmetic (no group needed) -----------------------

    def assert_difference(self, label: str, *, larger, smaller, expected_diff,
                          tolerance: float = 0.01) -> bool:
        """Check that `larger - smaller == expected_diff` within tolerance.
        Useful for things like 'discount = full_price - sale_price'."""
        a, b, e = _to_num(larger), _to_num(smaller), _to_num(expected_diff)
        computed = (a - b) if (a is not None and b is not None) else None
        passed = (
            computed is not None and e is not None
            and abs(computed - e) <= tolerance
        )
        self.entries.append({
            "label": str(label),
            "kind": "diff_assertion",
            "larger": str(larger), "larger_numeric": a,
            "smaller": str(smaller), "smaller_numeric": b,
            "computed_diff": computed,
            "expected_diff": str(expected_diff), "expected_numeric": e,
            "tolerance": tolerance,
            "passed": passed,
            "ts": datetime.now().strftime("%H:%M:%S"),
        })
        self._persist()
        return passed

    def assert_percentage(self, label: str, *, part, whole, expected_pct,
                          tolerance: float = 0.5) -> bool:
        """Check that `part / whole * 100 == expected_pct` within tolerance.
        Useful for HST=13%, achievement_pct=125%, etc."""
        a, b, e = _to_num(part), _to_num(whole), _to_num(expected_pct)
        computed = (a / b * 100) if (a is not None and b not in (None, 0)) else None
        passed = (
            computed is not None and e is not None
            and abs(computed - e) <= tolerance
        )
        self.entries.append({
            "label": str(label),
            "kind": "percentage_assertion",
            "part": str(part), "part_numeric": a,
            "whole": str(whole), "whole_numeric": b,
            "computed_percentage": computed,
            "expected_percentage": str(expected_pct), "expected_numeric": e,
            "tolerance": tolerance,
            "passed": passed,
            "ts": datetime.now().strftime("%H:%M:%S"),
        })
        self._persist()
        return passed

    def assert_ratio(self, label: str, *, numerator, denominator, expected_ratio,
                     tolerance: float = 0.01) -> bool:
        """Check that `numerator / denominator == expected_ratio` within tolerance."""
        a, b, e = _to_num(numerator), _to_num(denominator), _to_num(expected_ratio)
        computed = (a / b) if (a is not None and b not in (None, 0)) else None
        passed = (
            computed is not None and e is not None
            and abs(computed - e) <= tolerance
        )
        self.entries.append({
            "label": str(label),
            "kind": "ratio_assertion",
            "numerator": str(numerator), "numerator_numeric": a,
            "denominator": str(denominator), "denominator_numeric": b,
            "computed_ratio": computed,
            "expected_ratio": str(expected_ratio), "expected_numeric": e,
            "tolerance": tolerance,
            "passed": passed,
            "ts": datetime.now().strftime("%H:%M:%S"),
        })
        self._persist()
        return passed

    # ---- Negative path / missing data ----------------------------------
    # Two patterns the Auditor renders distinctly:
    #
    #   record_missing       — "we looked for X but it wasn't there".
    #                          Does NOT raise. Test continues with the next
    #                          item in the loop. Used when the story has
    #                          multiple independent targets (search A AND B,
    #                          delete X AND Y) and the absence of one doesn't
    #                          invalidate the whole flow.
    #
    #   assert_prerequisite  — "we couldn't even start". Raises AssertionError.
    #                          Halts the scenario immediately with a clear
    #                          reason (e.g. login failed, page didn't load).
    #                          Used when every subsequent step depends on
    #                          this one succeeding.

    def record_missing(self, label: str, *, target, reason: str = "") -> bool:
        """Record that a specific item could NOT be found, without raising.
        Returns False so the step def can `if not cap.record_missing(...): continue`.

        Use this for per-item loops where the story expects multiple things
        and one of them is absent — the test should continue with the others.

        Example (story: 'search "ice cream" and "chocolate", add each to cart'):
            for product in test_data["products"]:
                if not search_page.has_results_for(product):
                    cap.record_missing("Product search",
                                       target=product,
                                       reason="0 results on search page")
                    continue
                cap.add("Product found", product)
                cart.add(product)
        """
        entry = {
            "label": str(label),
            "kind": "missing",
            "target": "" if target is None else str(target),
            "reason": str(reason or "not found"),
            "ts": datetime.now().strftime("%H:%M:%S"),
        }
        self.entries.append(entry)
        self._persist()
        return False

    def assert_prerequisite(self, label: str, *, condition: bool,
                            reason: str = "", evidence: str = "") -> None:
        """Halt the scenario immediately when a blocking precondition fails.
        Records a structured 'prerequisite' entry with the cause, then raises
        AssertionError so pytest stops the scenario right here.

        Use this for steps every later step depends on (login, opening a
        page, having a session). Don't use this in per-item loops.

        Example (story: 'log in as manager 503, then …'):
            cap.assert_prerequisite(
                "Manager login",
                condition=login_page.is_logged_in(),
                reason="invalid credentials — manager_id=499 was rejected",
                evidence=login_page.last_error_text(),
            )
        """
        passed = bool(condition)
        entry = {
            "label": str(label),
            "kind": "prerequisite",
            "passed": passed,
            "reason": "" if passed else (reason or "blocking prerequisite failed"),
            "evidence": str(evidence or ""),
            "ts": datetime.now().strftime("%H:%M:%S"),
        }
        self.entries.append(entry)
        self._persist()
        if not passed:
            msg = f"PREREQUISITE FAILED — {label}: {reason or 'no reason given'}"
            if evidence:
                msg += f" | evidence: {evidence}"
            raise AssertionError(msg)

    def assert_action_succeeded(self, label: str, *, error_text: str = "",
                                positive_signal=None, reason: str = "",
                                evidence: str = "") -> None:
        """Verify a state-changing action (create / add / submit / save /
        update / register) ACTUALLY succeeded on THIS run — the report-is-truth
        rule applied to actions. Use this after any step that submits a form or
        triggers a mutation.

        error_text:      the backend's error toast / message captured right
                         after the action (empty string if none appeared). ANY
                         error-looking content here means the action was
                         REJECTED → failure. Detection via looks_like_backend_error.
        positive_signal: optional explicit proof the action happened on THIS run
                         (e.g. the list count incremented, a success toast
                         appeared). If you pass it, it must be truthy.

        A pre-existing matching row is NOT proof of success — pass the
        count-incremented / success-toast signal as `positive_signal` instead.

        Records a blocking outcome (via assert_prerequisite) and RAISES on
        failure so the scenario halts at the broken action."""
        err = (error_text or "").strip()
        # Many sites reuse ONE toast component for BOTH success and error
        # messages, so a non-empty toast is NOT automatically a failure. Classify
        # by content: only fail when the text actually reads like a rejection
        # ("already exists" / "name exist" / "could not" / "failed" …). A success
        # toast such as "created successfully" must NOT be treated as an error.
        is_error = looks_like_backend_error(err)
        ok = (not is_error) and (positive_signal is not False)
        if is_error:
            cause = f"backend rejected the action — {err!r}; it did not complete on this run"
        elif positive_signal is False:
            cause = reason or "no confirmation the action completed on this run"
        else:
            cause = ""
        self.assert_prerequisite(
            label, condition=ok, reason=cause, evidence=(evidence or err),
        )

    def assert_in_range(self, label: str, *, actual, low, high) -> bool:
        """Check `low <= actual <= high`. Useful for bounded values."""
        a, lo, hi = _to_num(actual), _to_num(low), _to_num(high)
        passed = (
            a is not None and lo is not None and hi is not None
            and lo <= a <= hi
        )
        self.entries.append({
            "label": str(label),
            "kind": "range_assertion",
            "actual": str(actual), "actual_numeric": a,
            "low": str(low), "low_numeric": lo,
            "high": str(high), "high_numeric": hi,
            "passed": passed,
            "ts": datetime.now().strftime("%H:%M:%S"),
        })
        self._persist()
        return passed

    def _persist(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps({"captures": self.entries}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass


@pytest.fixture()
def captured_values() -> CaptureLog:
    """Per-test handle to the session-level capture log.

    Step defs use this to record EVERYTHING the test sees — names, prices,
    counts, individual component values, then aggregate sums. The Auditor
    reads `reports/captured_values.json` after pytest to build the HTML
    report so the user can see exactly what the test verified."""
    return CaptureLog(_CAPTURED_VALUES_PATH)


# ============================================================
# Multi-tab / new-window support
# ============================================================

class TabRegistry:
    """Track named tabs/windows opened during the test. Generic API any step
    def can use without site-specific code.

    Typical patterns (works for any website):
        # The user clicks a link that opens a new tab:
        with tabs.expect_new("Order Detail") as new:
            page.locator("a:has-text('View Order')").click()
        # `new.page` is now the new tab; tabs.active() is also pointing at it.

        # Later, switch back:
        tabs.switch("main")     # the original tab
        tabs.switch("Order Detail")   # the tab we just opened by label
        # or by URL substring:
        tabs.switch_by_url("/orders/")

        # Assertions across tabs:
        cap.assert_match("Detail page header",
                         expected="Order #12345",
                         actual=tabs.named("Order Detail").locator("h1").inner_text())
    """

    def __init__(self, context: BrowserContext) -> None:
        self.context = context
        self._named: dict[str, Page] = {}
        # The first page (the one pytest-bdd uses via `page`) is "main"
        if context.pages:
            self._named["main"] = context.pages[0]
        self._active: Page | None = context.pages[0] if context.pages else None

    def expect_new(self, label: str | None = None,
                   *, wait_until: str = "domcontentloaded",
                   timeout_ms: int = 15000) -> "_NewTabContext":
        """Context manager. Inside the `with` block, perform the click that
        opens a new tab. The new tab is captured, registered under `label`
        (or auto-numbered), and becomes the active tab on exit."""
        return _NewTabContext(self, label, wait_until, timeout_ms)

    def register(self, label: str, page: Page) -> None:
        self._named[label] = page
        self._active = page

    def named(self, label: str) -> Page:
        if label in self._named:
            return self._named[label]
        raise AssertionError(
            f"No tab named {label!r}. Known: {list(self._named.keys())}"
        )

    def switch(self, label: str) -> Page:
        page = self.named(label)
        try:
            page.bring_to_front()
        except Exception:
            pass
        self._active = page
        return page

    def switch_by_url(self, url_fragment: str) -> Page:
        for n, p in list(self._named.items()):
            if url_fragment.lower() in (p.url or "").lower():
                return self.switch(n)
        # Fallback: scan all pages in the context
        for p in self.context.pages:
            if url_fragment.lower() in (p.url or "").lower():
                label = f"tab_{len(self._named) + 1}"
                self._named[label] = p
                return self.switch(label)
        raise AssertionError(f"No tab whose URL contains {url_fragment!r}")

    def switch_by_title(self, title_fragment: str) -> Page:
        for n, p in list(self._named.items()):
            try:
                if title_fragment.lower() in (p.title() or "").lower():
                    return self.switch(n)
            except Exception:
                continue
        for p in self.context.pages:
            try:
                if title_fragment.lower() in (p.title() or "").lower():
                    label = f"tab_{len(self._named) + 1}"
                    self._named[label] = p
                    return self.switch(label)
            except Exception:
                continue
        raise AssertionError(f"No tab whose title contains {title_fragment!r}")

    def active(self) -> Page | None:
        return self._active

    def close(self, label: str) -> None:
        if label in self._named:
            try:
                self._named[label].close()
            except Exception:
                pass
            del self._named[label]
            if self._active is None or self._active.is_closed():
                self._active = next(iter(self._named.values()), None)

    def all_labels(self) -> list[str]:
        return list(self._named.keys())


class _NewTabContext:
    def __init__(self, registry: TabRegistry, label: str | None,
                 wait_until: str, timeout_ms: int) -> None:
        self.registry = registry
        self.label = label
        self.wait_until = wait_until
        self.timeout_ms = timeout_ms
        self._cm = None
        self.page: Page | None = None

    def __enter__(self) -> "_NewTabContext":
        self._cm = self.registry.context.expect_page(timeout=self.timeout_ms)
        self._cm.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        result = self._cm.__exit__(exc_type, exc_val, exc_tb)
        # If the action raised, don't try to register anything
        if exc_type is None:
            try:
                new_page = self._cm.value
                try:
                    new_page.wait_for_load_state(self.wait_until,
                                                 timeout=self.timeout_ms)
                except Exception:
                    pass
                label = self.label or f"tab_{len(self.registry.all_labels()) + 1}"
                self.registry.register(label, new_page)
                self.page = new_page
            except Exception:
                pass
        return result


@pytest.fixture()
def tabs(context: BrowserContext) -> TabRegistry:
    """Generic multi-tab handle. Story-friendly idioms:

        # "clicks the link which opens a new tab" →
        with tabs.expect_new("Detail") as t:
            page.locator("a.detail").click()
        # t.page is the new tab; tabs.active() is now Detail.

        # "switches back to the main dashboard" →
        tabs.switch("main")

        # "in the new tab, verifies X is Y" →
        actual = tabs.active().locator("h1").inner_text()
    """
    return TabRegistry(context)

# Storage-state cache: after a successful run we save cookies + localStorage so
# the next run can skip the cookie banner + login. Cookie consent and session
# cookies typically expire within a day, so we invalidate after 30 minutes to
# stay safely fresh.
_STORAGE_STATE_PATH = Path("reports") / ".storage_state.json"
_STORAGE_STATE_TTL_SECS = 1800  # 30 minutes


def _load_storage_state() -> str | None:
    """Return the path to a cached storage_state file if it's fresh, else None.
    Stale or missing files are treated as no-cache."""
    try:
        if not _STORAGE_STATE_PATH.exists():
            return None
        age = time.time() - _STORAGE_STATE_PATH.stat().st_mtime
        if age > _STORAGE_STATE_TTL_SECS:
            return None
        return str(_STORAGE_STATE_PATH)
    except OSError:
        return None


def _invalidate_storage_state() -> None:
    try:
        if _STORAGE_STATE_PATH.exists():
            _STORAGE_STATE_PATH.unlink()
    except OSError:
        pass


def pytest_addoption(parser: pytest.Parser) -> None:
    try:
        parser.addoption("--headed", action="store_true", default=False, help="Run browser in headed mode")
    except Exception:
        pass  # pytest-playwright already registered --headed
    try:
        parser.addini("base_url", help="Base URL for the application under test", default="")
    except Exception:
        pass  # already registered


@pytest.fixture(scope="session")
def base_url(pytestconfig: pytest.Config) -> str:
    return pytestconfig.getini("base_url")


@pytest.fixture(scope="session")
def playwright_instance() -> Playwright:
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright, pytestconfig: pytest.Config) -> Browser:
    is_headed = bool(pytestconfig.getoption("headed", default=False))
    # Demo-friendly slow_mo when headed: every Playwright action (click / fill /
    # hover / select) pauses for this many ms so the audience can actually see
    # what's happening. Override either:
    #   PLAYWRIGHT_SLOW_MO=300   → faster demo
    #   PLAYWRIGHT_SLOW_MO=0     → instant (headless behavior)
    #   PLAYWRIGHT_SLOW_MO=1000  → very slow / very visible
    # Default in headed mode is 500ms; default in headless is 0.
    import os as _os
    default_slow_mo = 500 if is_headed else 0
    try:
        slow_mo_ms = int(_os.environ.get("PLAYWRIGHT_SLOW_MO", default_slow_mo))
    except ValueError:
        slow_mo_ms = default_slow_mo

    # Intentionally NOT setting `downloads_path` on the browser launch. If we
    # did, Playwright would save the raw download to that directory under a
    # UUID name (e.g. b363213f-80ff-...) AND then `download.save_as(...)` in
    # the step def would write a SECOND file with the proper name alongside —
    # so the user ended up with two files, one UUID-named, one properly named.
    # By leaving downloads_path unset, Playwright stashes the raw download in
    # an internal temp dir (auto-cleaned), and `download.save_as()` becomes
    # the SOLE writer to ~/Downloads. The user sees exactly one file with the
    # server-suggested name.
    browser = playwright_instance.chromium.launch(
        headless=not is_headed,
        slow_mo=slow_mo_ms,
        args=["--start-maximized"],
    )
    yield browser
    browser.close()


# ============================================================
# Per-step visual trace (screenshots for the report)
# ============================================================

def _resolve_step_page(step_func_args, request):
    """Best-effort handle to the Page the step acted on. Prefer the step's own
    `page` arg; fall back to the already-created `page` fixture. Never raises."""
    page = None
    if isinstance(step_func_args, dict):
        page = step_func_args.get("page")
    if page is None:
        try:
            page = request.getfixturevalue("page")
        except Exception:
            page = None
    return page if isinstance(page, Page) else None


def _next_step_index() -> int:
    try:
        if _STEP_TRACE_PATH.exists():
            existing = json.loads(
                _STEP_TRACE_PATH.read_text(encoding="utf-8")
            ).get("steps", [])
            return len(existing) + 1
    except (OSError, ValueError):
        pass
    return 1


def _append_step_trace(entry: dict) -> None:
    try:
        _STEP_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {"steps": []}
        if _STEP_TRACE_PATH.exists():
            try:
                data = json.loads(_STEP_TRACE_PATH.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {"steps": []}
        data.setdefault("steps", []).append(entry)
        _STEP_TRACE_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def _capture_step(step, step_func_args, request, *, status: str,
                  error: str = "") -> None:
    """Record one step into the trace and snap a viewport screenshot of the
    page in its post-step state. Viewport (not full_page) keeps frames a clean,
    uniform size for the report gallery. Entirely best-effort — a screenshot
    failure must never break the test run."""
    idx = _next_step_index()
    keyword = (getattr(step, "keyword", "") or "").strip()
    name = (getattr(step, "name", "") or "").strip()
    page = _resolve_step_page(step_func_args, request)
    shot_rel = ""
    if page is not None:
        try:
            _STEP_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            safe_kw = (keyword or "step").lower().replace(" ", "_")
            fname = f"step_{idx:02d}_{safe_kw}_{status}.png"
            page.screenshot(path=str(_STEP_SCREENSHOT_DIR / fname),
                            full_page=False)
            shot_rel = f"screenshots/{fname}"
        except Exception:
            shot_rel = ""
    _append_step_trace({
        "index": idx,
        "keyword": keyword,
        "name": name,
        "status": status,
        "error": str(error or ""),
        "screenshot": shot_rel,
        "ts": datetime.now().strftime("%H:%M:%S"),
    })


# Per-BDD-step delay (only when headed). The audience sees each Given/When/Then
# fully complete before the next starts — gives time to read the step name in
# the trace + watch the page settle. Override via STEP_DELAY_SEC env var.
#   STEP_DELAY_SEC=0     → no per-step delay
#   STEP_DELAY_SEC=2.5   → 2.5 second pause after each step
# Default in headed mode is 1.5s; default in headless is 0.
def pytest_bdd_after_step(
    request, feature, scenario, step, step_func, step_func_args
) -> None:
    # Only successful steps reach `after_step`; the failing one goes to
    # `pytest_bdd_step_error` below. So this records every PASSED step.
    _capture_step(step, step_func_args, request, status="passed")

    is_headed = bool(request.config.getoption("headed", default=False))
    default_delay = 1.5 if is_headed else 0.0
    import os as _os
    try:
        delay = float(_os.environ.get("STEP_DELAY_SEC", default_delay))
    except ValueError:
        delay = default_delay
    if delay > 0:
        time.sleep(delay)


def pytest_bdd_step_error(
    request, feature, scenario, step, step_func, step_func_args, exception
) -> None:
    """The step that raised. Snap it and mark it FAILED so the report can point
    straight at the breaking step with a screenshot of the page at that moment."""
    _capture_step(step, step_func_args, request, status="failed",
                  error=exception)


@pytest.fixture()
def context(browser: Browser) -> BrowserContext:
    # If we have a fresh cached storage_state from a previous run, replay it so
    # cookie consent + login carry over. The Background steps stay defensive
    # (`accept_cookies_if_present` checks visibility; `expect_logged_in` handles
    # the already-logged-in case), so reusing state is safe.
    cached_state = _load_storage_state()
    context = browser.new_context(
        no_viewport=True,
        http_credentials={"username": "storefront", "password": "storefront"},
        ignore_https_errors=True,
        storage_state=cached_state,
    )
    yield context
    try:
        _STORAGE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(_STORAGE_STATE_PATH))
    except Exception:
        # Saving is best-effort; don't fail the test for it.
        pass
    context.close()


def _resolve_downloads_dir() -> Path:
    """Where Chromium should drop downloaded files. Defaults to the user's
    real `~/Downloads`. Override with PLAYWRIGHT_DOWNLOADS_DIR for CI."""
    import os
    return Path(
        os.environ.get(
            "PLAYWRIGHT_DOWNLOADS_DIR",
            str(Path.home() / "Downloads"),
        )
    )


def _enable_native_downloads(context: BrowserContext, page: Page) -> bool:
    """Tell Chromium (via CDP) to save downloads NATIVELY into ~/Downloads,
    using the server's suggested filename — exactly as if the user clicked the
    download link in a regular browser session.

    With this in place:
      * Playwright does NOT intercept the download into a UUID temp path.
      * Chromium's own download tray shows the proper filename.
      * The file appears in File Explorer at ~/Downloads immediately.
      * No `download.save_as(...)` call is needed in the step def — the file
        is already in the right place by the time `page.expect_download()`
        returns.

    Returns True on success, False if CDP isn't available (non-Chromium)."""
    download_dir = _resolve_downloads_dir()
    try:
        download_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    try:
        cdp = context.new_cdp_session(page)
        # `Browser.setDownloadBehavior` is browser-scope and is the supported
        # way to override download routing in modern Chromium. `behavior:
        # "allow"` (vs the GUID-producing `allowAndName`) means Chromium uses
        # the server's `Content-Disposition` filename.
        cdp.send(
            "Browser.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_dir)},
        )
        return True
    except Exception:
        # Firefox/WebKit, or a very old Chromium without the command. The
        # fallback handler below will copy the file post-download instead.
        return False


def _fallback_save_download(download) -> None:
    """Used only when native download routing couldn't be enabled (e.g.
    non-Chromium browser). Copies the intercepted file to ~/Downloads with
    the server-suggested filename."""
    target_dir = _resolve_downloads_dir()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    suggested = download.suggested_filename or "download.bin"
    target = target_dir / suggested
    try:
        download.save_as(str(target))
    except Exception:
        pass


@pytest.fixture()
def page(context: BrowserContext) -> Page:
    page = context.new_page()
    native_ok = _enable_native_downloads(context, page)
    if not native_ok:
        # Non-Chromium fallback: copy intercepted downloads into ~/Downloads.
        page.on("download", _fallback_save_download)
    yield page
    page.close()


@pytest.fixture()
def story_context() -> dict[str, str]:
    return {}


# Universal data fixture. If the user provided a `user_data.json` alongside
# their story, its contents are exposed here. Step defs treat this as the
# source-of-truth for both inputs (e.g. productid to type) and expected
# values (e.g. Subtotal to assert). The fixture re-reads on every test, so
# changing user_data.json between runs takes effect immediately — no
# regeneration needed.
@pytest.fixture()
def test_data() -> "dict | list":
    import json as _json
    p = Path("user_data.json")
    if not p.exists():
        return {}
    try:
        return _json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[object]) -> None:
    if call.when != "call" or call.excinfo is None:
        return
    # On any test failure, drop the cached storage_state so the next run starts
    # from a clean session. Otherwise a corrupt/expired session would keep
    # poisoning every run until the TTL ticks over.
    _invalidate_storage_state()
    page_obj = item.funcargs.get("page")
    if not isinstance(page_obj, Page):
        return
    screenshot_dir = Path("reports/screenshots")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = screenshot_dir / f"{item.name}_{ts}.png"
    page_obj.screenshot(path=str(screenshot_path), full_page=True)

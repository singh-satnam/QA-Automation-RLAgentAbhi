"""Root conftest — canonical scaffolding copied into every project by the harness.

DO NOT hand-edit per project and DO NOT have the LLM regenerate this. Fixes belong
in core/templates/conftest.py so every project inherits them. Provides:
  * Playwright browser/context/page fixtures (headless unless --headed).
  * base_url (from pytest.ini), test_data (user_data.json at runtime).
  * captured_values  -> records every value/assertion into report/captured_values.json
  * tabs (TabRegistry) -> generic multi-tab/new-window handling.
  * pytest-bdd step hooks -> report/step_trace.json (per-step pass/fail/skip + failure shots).

`pytest_plugins` is left empty here; the harness (sync_pytest_plugins) fills it from
the step-def modules actually present on disk after generation.
"""
from __future__ import annotations

import json
import os
import re
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

# --- per-feature step modules (filled by the harness, not by hand) -----------
pytest_plugins = ('step_defs.common_steps', 'step_defs.admin_login_steps', 'step_defs.logout_via_signout_steps', 'step_defs.pi_add_budget_to_project_steps', 'step_defs.pi_admin_user_cannot_be_added_to_project_steps', 'step_defs.pi_login_steps', 'step_defs.pi_project_creation_steps', 'step_defs.pi_project_details_active_project_steps', 'step_defs.researcher_login_steps')

# --- project paths -----------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
REPORT_DIR = PROJECT_ROOT / "report"
SHOTS_DIR = REPORT_DIR / "screenshots"
DOWNLOADS_DIR = Path.home() / "Downloads"

# --- in-memory accumulators flushed in pytest_sessionfinish ------------------
_CAPTURES: list[dict] = []
_STEP_TRACE: list[dict] = []


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


# --- global test data (test_data/.env) --------------------------------------
TEST_DATA_DIR = PROJECT_ROOT / "test_data"
_URL_KEYS = ("URL", "BASE_URL")


def _parse_env(path: Path) -> dict:
    out = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("\"", "'"):
            val = val[1:-1].replace('\\n', "\n").replace('\\"', '"').replace("\\\\", "\\")
        out[key] = val
    return out


def _resolve_story_file(slug: str):
    if not TEST_DATA_DIR.exists():
        return None
    candidates = [p for p in sorted(TEST_DATA_DIR.glob("*.json"))
                  if p.name != "global_project_data.json"]
    for p in candidates:
        if p.stem == slug:
            return p
    for p in candidates:
        if slug and (slug in p.stem or p.stem in slug):
            return p
    return None


# ============================================================================
# Captured values — persisted into report/captured_values.json in the exact
# schema the coverage renderer (core/agent_ui.py) expects (one dict per entry,
# keyed by `kind`).
# ============================================================================
class CapturedValues:
    def __init__(self, sink: list[dict]):
        self._sink = sink

    # ---- plain values -------------------------------------------------------
    def add(self, label, value, path=None):
        e = {"kind": "value", "label": label, "value": value, "ts": _now()}
        if path:
            e["path"] = path
        self._sink.append(e)
        return value

    def add_component(self, label, value, group):
        self._sink.append({
            "kind": "component", "label": label, "value": value,
            "group": group, "ts": _now(),
        })
        return value

    # ---- direct assertion ---------------------------------------------------
    def assert_match(self, label, expected, actual):
        passed = str(expected).strip() == str(actual).strip()
        self._sink.append({
            "kind": "assertion", "label": label,
            "expected": expected, "actual": actual,
            "passed": passed, "ts": _now(),
        })
        return passed

    # ---- action-succeeded (create/add/submit) — blocking on failure --------
    def assert_action_succeeded(self, label, error_text, positive_signal,
                                reason="", evidence=""):
        err = (error_text or "").strip()
        passed = (not err) and bool(positive_signal)
        self._sink.append({
            "kind": "assertion", "label": label,
            "expected": "action succeeded (no error toast + positive signal)",
            "actual": f"error_toast={err or '<none>'}; "
                      f"positive_signal={bool(positive_signal)}",
            "passed": passed, "reason": reason, "evidence": evidence,
            "ts": _now(),
        })
        if not passed:
            raise AssertionError(
                f"{label} NOT confirmed: {reason or 'no positive signal'} | "
                f"evidence={evidence} | server_response={err or '<none>'}"
            )
        return passed

    # ---- blocking prerequisite ---------------------------------------------
    def assert_prerequisite(self, label, condition, reason="", evidence=""):
        passed = bool(condition)
        self._sink.append({
            "kind": "prerequisite", "label": label, "passed": passed,
            "reason": reason, "evidence": evidence, "ts": _now(),
        })
        if not passed:
            raise AssertionError(f"BLOCKED — {label} failed: {reason} | {evidence}")
        return passed

    # ---- per-item missing (does NOT raise) ---------------------------------
    def record_missing(self, label, target, reason=""):
        self._sink.append({
            "kind": "missing", "label": label, "target": target,
            "reason": reason, "ts": _now(),
        })
        return False

    # ---- aggregates over a component group ---------------------------------
    def _components(self, group):
        return [e for e in self._sink
                if e.get("kind") == "component" and e.get("group") == group]

    @staticmethod
    def _agg(op, vals):
        if not vals and op not in ("count",):
            return 0
        if op == "sum":
            return sum(vals)
        if op == "avg":
            return sum(vals) / len(vals) if vals else 0
        if op == "min":
            return min(vals)
        if op == "max":
            return max(vals)
        if op == "count":
            return len(vals)
        if op == "product":
            out = 1
            for v in vals:
                out *= v
            return out
        if op == "range":
            return max(vals) - min(vals)
        if op == "median":
            s = sorted(vals)
            n = len(s)
            mid = n // 2
            return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2
        raise ValueError(f"unknown op {op}")

    @staticmethod
    def _num_eq(a, b, tol=1e-6):
        try:
            return abs(float(a) - float(b)) <= tol
        except (TypeError, ValueError):
            return str(a).strip() == str(b).strip()

    def assert_aggregate(self, label, group, op, actual):
        vals = [float(c["value"]) for c in self._components(group)]
        computed = self._agg(op, vals)
        passed = self._num_eq(computed, actual)
        self._sink.append({
            "kind": "aggregate_assertion", "label": label, "op": op,
            "components": [{"label": c["label"], "value": c["value"]}
                           for c in self._components(group)],
            f"computed_{op}": computed, "computed": computed,
            "actual": actual, "passed": passed, "ts": _now(),
        })
        return passed

    def assert_sum(self, label, group, actual):
        return self.assert_aggregate(label, group, "sum", actual)

    def assert_avg(self, label, group, actual):
        return self.assert_aggregate(label, group, "avg", actual)

    def assert_min(self, label, group, actual):
        return self.assert_aggregate(label, group, "min", actual)

    def assert_max(self, label, group, actual):
        return self.assert_aggregate(label, group, "max", actual)

    def assert_count(self, label, group, actual):
        return self.assert_aggregate(label, group, "count", actual)

    def assert_product(self, label, group, actual):
        return self.assert_aggregate(label, group, "product", actual)

    def assert_range(self, label, group, actual):
        return self.assert_aggregate(label, group, "range", actual)

    def assert_median(self, label, group, actual):
        return self.assert_aggregate(label, group, "median", actual)

    # ---- cross-value arithmetic --------------------------------------------
    def assert_difference(self, label, larger, smaller, expected_diff):
        computed = float(larger) - float(smaller)
        passed = self._num_eq(computed, expected_diff)
        self._sink.append({
            "kind": "diff_assertion", "label": label,
            "larger": larger, "smaller": smaller,
            "computed_diff": computed, "expected_diff": expected_diff,
            "passed": passed, "ts": _now(),
        })
        return passed

    def assert_percentage(self, label, part, whole, expected_pct):
        computed = (float(part) / float(whole) * 100) if float(whole) else 0
        passed = self._num_eq(computed, expected_pct)
        self._sink.append({
            "kind": "percentage_assertion", "label": label,
            "part": part, "whole": whole,
            "computed_percentage": computed, "expected_percentage": expected_pct,
            "passed": passed, "ts": _now(),
        })
        return passed

    def assert_ratio(self, label, numerator, denominator, expected_ratio):
        computed = (float(numerator) / float(denominator)) if float(denominator) else 0
        passed = self._num_eq(computed, expected_ratio)
        self._sink.append({
            "kind": "ratio_assertion", "label": label,
            "numerator": numerator, "denominator": denominator,
            "computed_ratio": computed, "expected_ratio": expected_ratio,
            "passed": passed, "ts": _now(),
        })
        return passed

    def assert_in_range(self, label, actual, low, high):
        passed = float(low) <= float(actual) <= float(high)
        self._sink.append({
            "kind": "range_assertion", "label": label,
            "actual": actual, "low": low, "high": high,
            "passed": passed, "ts": _now(),
        })
        return passed


# ============================================================================
# Generic multi-tab / new-window registry.
# ============================================================================
class TabRegistry:
    def __init__(self, page, context):
        self._context = context
        self._tabs = {"main": page}
        self._active = page

    def active(self):
        return self._active

    @contextmanager
    def expect_new(self, label):
        holder = type("_TabHolder", (), {"page": None})()
        with self._context.expect_page() as info:
            yield holder
        new_page = info.value
        new_page.wait_for_load_state("domcontentloaded")
        self._tabs[label] = new_page
        self._active = new_page
        holder.page = new_page

    def switch(self, label):
        self._active = self._tabs[label]
        self._active.bring_to_front()
        return self._active

    def switch_by_url(self, substring):
        for pg in self._context.pages:
            if substring in pg.url:
                self._active = pg
                pg.bring_to_front()
                return pg
        raise AssertionError(f"No open tab with URL containing {substring!r}")

    def switch_by_title(self, substring):
        for pg in self._context.pages:
            if substring in (pg.title() or ""):
                self._active = pg
                pg.bring_to_front()
                return pg
        raise AssertionError(f"No open tab with title containing {substring!r}")


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture(scope="session")
def _playwright():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(_playwright, pytestconfig):
    browser = _playwright.chromium.launch(
        headless=not pytestconfig.getoption("--headed"),
        downloads_path=str(DOWNLOADS_DIR),
    )
    yield browser
    browser.close()


@pytest.fixture
def context(browser):
    ctx = browser.new_context(accept_downloads=True)
    ctx.set_default_timeout(30000)
    yield ctx
    ctx.close()


@pytest.fixture
def page(context):
    pg = context.new_page()
    yield pg


@pytest.fixture(scope="session")
def base_url(pytestconfig, global_data):
    # Global test_data/.env URL wins; then pytest.ini base_url; then empty.
    for key in _URL_KEYS:
        if global_data.get(key):
            return global_data[key]
    for getter in ("getoption", "getini"):
        try:
            val = getattr(pytestconfig, getter)("base_url")
            if val:
                return val
        except Exception:
            continue
    return ""


@pytest.fixture(scope="session")
def global_data():
    """Global project data from test_data/.env (URL, credentials, shared values).
    Also exported to os.environ (without clobbering already-set vars)."""
    env_path = TEST_DATA_DIR / ".env"
    data = _parse_env(env_path) if env_path.exists() else {}
    for k, v in data.items():
        os.environ.setdefault(k, v)
    return data


@pytest.fixture
def test_data(request, global_data):
    """Merged test data for the running test: global .env values overlaid with the
    per-story test_data/<slug>.json (per-story wins, except the URL key). Falls
    back to legacy project-root user_data.json when no test_data/ files exist.
    NEVER hardcode values from it — step defs read this fixture live."""
    slug = request.module.__name__.rsplit(".", 1)[-1]
    if slug.startswith("test_"):
        slug = slug[len("test_"):]
    story = _resolve_story_file(slug)

    if not (TEST_DATA_DIR / ".env").exists() and story is None:
        legacy = PROJECT_ROOT / "user_data.json"
        if legacy.exists():
            try:
                return json.loads(legacy.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {}

    data = dict(global_data)
    if story is not None:
        try:
            extra = json.loads(story.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            extra = None
        if isinstance(extra, dict):
            for k, v in extra.items():
                if k.upper() in _URL_KEYS and k in data:
                    continue  # global URL is the single source
                data[k] = v
        elif isinstance(extra, list):
            data["rows"] = extra  # parameterised rows exposed under 'rows'
    return data


@pytest.fixture(scope="session")
def captured_values():
    return CapturedValues(_CAPTURES)


@pytest.fixture
def scenario_context():
    """Per-scenario scratch dict to pass values between step defs."""
    return {}


@pytest.fixture
def tabs(page, context):
    return TabRegistry(page, context)


# ============================================================================
# pytest-bdd step hooks -> report/step_trace.json
# ============================================================================
def _step_index(scenario, step):
    try:
        return list(scenario.steps).index(step)
    except (ValueError, TypeError):
        return len(_STEP_TRACE)


def pytest_bdd_after_step(request, feature, scenario, step, step_func, step_func_args):
    _STEP_TRACE.append({
        "test": scenario.name,
        "feature": feature.name,
        "index": _step_index(scenario, step),
        "keyword": step.keyword,
        "name": step.name,
        "status": "passed",
    })


def pytest_bdd_step_error(request, feature, scenario, step, step_func,
                          step_func_args, exception):
    idx = _step_index(scenario, step)
    shot_rel = ""
    try:
        page = request.getfixturevalue("page")
        SHOTS_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_",
                      f"{scenario.name}_{idx}_{step.name}")[:80]
        fp = SHOTS_DIR / f"{safe}.png"
        page.screenshot(path=str(fp))
        shot_rel = f"screenshots/{fp.name}"
    except Exception:
        shot_rel = ""

    err_lines = "".join(
        traceback.format_exception_only(type(exception), exception)
    ).strip().splitlines()
    err = "\n".join(err_lines[:5])

    _STEP_TRACE.append({
        "test": scenario.name,
        "feature": feature.name,
        "index": idx,
        "keyword": step.keyword,
        "name": step.name,
        "status": "failed",
        "error": err,
        "screenshot": shot_rel,
    })

    # Every later step in this scenario is skipped.
    steps = list(scenario.steps)
    try:
        pos = steps.index(step)
    except ValueError:
        pos = idx
    for j, s in enumerate(steps):
        if j > pos:
            _STEP_TRACE.append({
                "test": scenario.name,
                "feature": feature.name,
                "index": j,
                "keyword": getattr(s, "keyword", ""),
                "name": getattr(s, "name", ""),
                "status": "skipped",
            })


def pytest_sessionfinish(session, exitstatus):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        (REPORT_DIR / "captured_values.json").write_text(
            json.dumps(_CAPTURES, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass
    try:
        (REPORT_DIR / "step_trace.json").write_text(
            json.dumps(_STEP_TRACE, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass

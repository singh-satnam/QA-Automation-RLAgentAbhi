# Test Results Step-Level Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Test results tab show a per-step pass/fail/skip table with an aggregated summary and a failure gallery (screenshot + top-5 error lines), aggregated across all tests in a run.

**Architecture:** A new dependency-free `core/step_report.py` renders the report HTML from a list of step records (pure, unit-tested). `core/agent_ui.py` loads `step_trace.json` and delegates rendering to it inside `build_inline_coverage_report`. The generated `conftest.py` gains pytest-bdd step hooks that produce the richer `step_trace.json`. The framework prompts are updated so future projects include the hooks.

**Tech Stack:** Python, pytest-bdd 8.1.0, Streamlit (report embedded via `components.html`), self-contained HTML/CSS/JS.

Spec: `docs/superpowers/specs/2026-06-14-test-results-step-report-design.md`

---

## File Structure

- **Create** `core/step_report.py` — pure rendering: `step_summary(steps)`, `render_step_report(steps, img_resolver)`, `STEP_REPORT_CSS`. No Streamlit import, so it is unit-testable in isolation (same pattern as `core/workspace.py`).
- **Create** `tests/test_step_report.py` — unit tests for the above.
- **Modify** `core/agent_ui.py` — import `step_report`; in `build_inline_coverage_report` replace the `_render_step_timeline(...)` section with `step_report.render_step_report(...)` as the headline section; include `STEP_REPORT_CSS` in the `<style>` block. Retire `_render_step_timeline`/`_render_step_card` (leave `_load_step_trace`/`_img_data_uri` — still used).
- **Modify** `workspace/ResGate/conftest.py` — add `pytest_bdd_after_step`, `pytest_bdd_step_error`, `pytest_sessionfinish` hooks + accumulator; stop `CapturedValues.flush()` from writing `step_trace.json` (it keeps writing `captured_values.json`).
- **Modify** `core/prompts/framework_prompt.md` and `core/prompts/framework_delta_prompt.md` — document the step hooks and the new `step_trace.json` schema so future generations include them.

Status colors: pass `#16a34a` `✓` · fail `#dc2626` `✗` · skip `#1e3a8a` `⊘`.

---

## Task 1: `step_summary` (pure counts)

**Files:**
- Create: `core/step_report.py`
- Test: `tests/test_step_report.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_step_report.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
import step_report  # noqa: E402

SAMPLE = [
    {"test": "test_a", "feature": "a.feature", "index": 1, "keyword": "Given",
     "name": "login", "status": "passed"},
    {"test": "test_a", "feature": "a.feature", "index": 2, "keyword": "Then",
     "name": "created", "status": "failed",
     "error": "AssertionError: boom\nline2\nline3", "screenshot": "screenshots/x.png"},
    {"test": "test_a", "feature": "a.feature", "index": 3, "keyword": "And",
     "name": "appears", "status": "skipped"},
    {"test": "test_b", "feature": "b.feature", "index": 1, "keyword": "Given",
     "name": "open", "status": "passed"},
]


def test_step_summary_counts_and_distinct_tests():
    s = step_report.step_summary(SAMPLE)
    assert s["tests"] == 2
    assert s["passed"] == 2
    assert s["failed"] == 1
    assert s["skipped"] == 1
    assert s["total_steps"] == 4


def test_step_summary_empty():
    s = step_report.step_summary([])
    assert s == {"tests": 0, "passed": 0, "failed": 0, "skipped": 0, "total_steps": 0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_step_report.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'step_report'`.

- [ ] **Step 3: Write minimal implementation**

Create `core/step_report.py`:

```python
"""Pure rendering of the per-step Test-results report (no Streamlit).

Consumes a list of step records (the new step_trace.json schema) produced by the
generated conftest's pytest-bdd hooks. Kept dependency-free so it is unit-testable
in isolation, mirroring core/workspace.py.
"""

from __future__ import annotations

import html as _html


def _esc(value) -> str:
    return _html.escape("" if value is None else str(value), quote=True)


def step_summary(steps: list[dict]) -> dict:
    """Aggregate counts across every step in the run."""
    tests = {s.get("test") for s in steps if s.get("test")}
    return {
        "tests": len(tests),
        "passed": sum(1 for s in steps if s.get("status") == "passed"),
        "failed": sum(1 for s in steps if s.get("status") == "failed"),
        "skipped": sum(1 for s in steps if s.get("status") == "skipped"),
        "total_steps": len(steps),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_step_report.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/step_report.py tests/test_step_report.py
git commit -m "feat(report): step_summary aggregates per-step counts"
```

---

## Task 2: `render_step_report` + `STEP_REPORT_CSS`

**Files:**
- Modify: `core/step_report.py`
- Test: `tests/test_step_report.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_step_report.py`:

```python
def test_render_empty_returns_empty_string():
    assert step_report.render_step_report([]) == ""


def test_render_includes_summary_table_and_failure_gallery():
    html = step_report.render_step_report(
        SAMPLE, img_resolver=lambda p: "data:image/png;base64,Zm9v" if p else "")
    assert "Tests ran" in html and "Passed steps" in html
    assert html.count('class="sr-row') == 4          # one row per step
    assert "Failures (1)" in html                    # one failed step
    assert "AssertionError: boom" in html            # error text shown
    assert 'data-f="failed"' in html                 # filter button present
    assert "stp-fail" in html and "stp-skip" in html # status classes


def test_render_failed_step_without_screenshot_shows_placeholder():
    html = step_report.render_step_report(SAMPLE, img_resolver=lambda p: "")
    assert "(no screenshot)" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_step_report.py -q`
Expected: FAIL — `AttributeError: module 'step_report' has no attribute 'render_step_report'`.

- [ ] **Step 3: Write minimal implementation**

Append to `core/step_report.py`:

```python
# status -> (marker, css class, label)
_STATUS_META = {
    "passed":  ("✓", "stp-pass", "PASS"),   # green tick
    "failed":  ("✗", "stp-fail", "FAIL"),   # red cross
    "skipped": ("⊘", "stp-skip", "SKIP"),   # dark-blue circle-slash
}

STEP_REPORT_CSS = """
.sr-section{margin-top:1.5rem}
.sr-cards{display:flex;gap:0.75rem;flex-wrap:wrap;margin:0.5rem 0 1rem}
.sr-card{flex:1;min-width:120px;border:1px solid #e2e8f0;border-radius:10px;
  padding:0.75rem 1rem;background:#f8fafc;text-align:center}
.sr-card .sr-num{font-size:1.6rem;font-weight:700;color:#0f172a}
.sr-card .sr-lbl{font-size:0.8rem;color:#475569}
.sr-card.sr-pass .sr-num{color:#16a34a}
.sr-card.sr-fail .sr-num{color:#dc2626}
.sr-card.sr-skip .sr-num{color:#1e3a8a}
.sr-filters{margin:0.5rem 0}
.sr-fbtn{border:1px solid #cbd5e1;background:#fff;border-radius:6px;
  padding:0.25rem 0.7rem;margin-right:0.4rem;cursor:pointer;font-size:0.85rem}
.sr-fbtn.active{background:#0f172a;color:#fff;border-color:#0f172a}
.sr-table{width:100%;border-collapse:collapse;font-size:0.9rem}
.sr-table th,.sr-table td{border-bottom:1px solid #eef2f7;padding:0.4rem 0.6rem;
  text-align:left;vertical-align:top}
.sr-table .sr-i{color:#94a3b8;width:2rem}
.sr-table .sr-kw{font-weight:600;color:#334155;white-space:nowrap}
.sr-pill{display:inline-block;border-radius:999px;padding:0.1rem 0.55rem;
  font-size:0.78rem;font-weight:700;white-space:nowrap}
.sr-pill.stp-pass{background:#dcfce7;color:#16a34a}
.sr-pill.stp-fail{background:#fee2e2;color:#dc2626}
.sr-pill.stp-skip{background:#dbeafe;color:#1e3a8a}
.sr-gtitle{margin-top:1.25rem;font-size:1rem;color:#dc2626}
.sr-gallery{display:flex;flex-direction:column;gap:0.75rem}
.sr-fcard{border:1px solid #fecaca;border-radius:10px;overflow:hidden}
.sr-fhead{background:#fef2f2;color:#991b1b;font-weight:600;padding:0.5rem 0.75rem}
.sr-fbody{display:flex;gap:0.75rem;padding:0.75rem;align-items:flex-start}
.sr-shot{max-width:360px;border:1px solid #e2e8f0;border-radius:6px}
.sr-noshot{color:#94a3b8;font-style:italic;padding:1rem;border:1px dashed #e2e8f0;
  border-radius:6px}
.sr-err{flex:1;margin:0;background:#0f172a;color:#e2e8f0;border-radius:6px;
  padding:0.6rem;font-size:0.8rem;white-space:pre-wrap;overflow:auto}
"""

_FILTER_SCRIPT = (
    "<script>function srFilter(b){"
    "var f=b.getAttribute('data-f');"
    "var btns=b.parentNode.querySelectorAll('.sr-fbtn');"
    "btns.forEach(function(x){x.classList.remove('active')});"
    "b.classList.add('active');"
    "document.querySelectorAll('.sr-row').forEach(function(r){"
    "var show=(f=='all')||r.classList.contains('stp-'+f.slice(0,4));"
    "r.style.display=show?'':'none';});}</script>"
)


def render_step_report(steps: list[dict], img_resolver=None) -> str:
    """Return the Template-C report section (summary cards + filterable status
    table + failure gallery). `img_resolver(rel_path) -> data-uri-or-empty` inlines
    failure screenshots; pass None to skip image embedding."""
    if not steps:
        return ""
    summ = step_summary(steps)

    cards = (
        '<div class="sr-cards">'
        f'<div class="sr-card"><div class="sr-num">{summ["tests"]}</div>'
        '<div class="sr-lbl">Tests ran</div></div>'
        f'<div class="sr-card sr-pass"><div class="sr-num">{summ["passed"]}</div>'
        '<div class="sr-lbl">Passed steps</div></div>'
        f'<div class="sr-card sr-fail"><div class="sr-num">{summ["failed"]}</div>'
        '<div class="sr-lbl">Failed steps</div></div>'
        f'<div class="sr-card sr-skip"><div class="sr-num">{summ["skipped"]}</div>'
        '<div class="sr-lbl">Skipped steps</div></div>'
        '</div>'
    )

    rows = []
    for i, s in enumerate(steps, start=1):
        mark, cls, lbl = _STATUS_META.get(s.get("status", ""), ("—", "", ""))
        rows.append(
            f'<tr class="sr-row {cls}">'
            f'<td class="sr-i">{i}</td>'
            f'<td class="sr-test">{_esc(s.get("test", ""))}</td>'
            f'<td class="sr-kw">{_esc(s.get("keyword", ""))}</td>'
            f'<td>{_esc(s.get("name", ""))}</td>'
            f'<td><span class="sr-pill {cls}">{mark} {lbl}</span></td>'
            '</tr>'
        )
    table = (
        '<div class="sr-filters">'
        '<button class="sr-fbtn active" data-f="all" onclick="srFilter(this)">All</button>'
        '<button class="sr-fbtn" data-f="failed" onclick="srFilter(this)">Failed</button>'
        '<button class="sr-fbtn" data-f="skipped" onclick="srFilter(this)">Skipped</button>'
        '</div>'
        '<table class="sr-table"><thead><tr>'
        '<th>#</th><th>Test</th><th>Keyword</th><th>Step</th><th>Status</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table>'
    )

    failures = [s for s in steps if s.get("status") == "failed"]
    gallery = ""
    if failures:
        fcards = []
        for s in failures:
            uri = img_resolver(s.get("screenshot", "")) if img_resolver else ""
            shot = (
                f'<a href="{uri}" target="_blank">'
                f'<img class="sr-shot" src="{uri}" alt="failure screenshot"></a>'
                if uri else '<div class="sr-noshot">(no screenshot)</div>'
            )
            err = _esc(s.get("error", "")) or "(no error captured)"
            fcards.append(
                '<div class="sr-fcard">'
                f'<div class="sr-fhead">✗ {_esc(s.get("test", ""))} · '
                f'{_esc(s.get("keyword", ""))} {_esc(s.get("name", ""))}</div>'
                f'<div class="sr-fbody">{shot}<pre class="sr-err">{err}</pre></div>'
                '</div>'
            )
        gallery = (
            f'<h3 class="sr-gtitle">Failures ({len(failures)})</h3>'
            f'<div class="sr-gallery">{"".join(fcards)}</div>'
        )

    return (
        '<section class="sr-section"><h2>Step-by-step results</h2>'
        f'{cards}{table}{gallery}{_FILTER_SCRIPT}</section>'
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_step_report.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add core/step_report.py tests/test_step_report.py
git commit -m "feat(report): render_step_report (Template C) with summary, table, failure gallery"
```

---

## Task 3: Wire renderer into `agent_ui.build_inline_coverage_report`

**Files:**
- Modify: `core/agent_ui.py` (import near line 22; section build near line 963-967; `<style>` near line 1053)

- [ ] **Step 1: Add the import**

After `import workspace as ws` (line 22) add:

```python
import step_report
```

- [ ] **Step 2: Replace the step-timeline section with the new renderer**

Find (around lines 963-967):

```python
    # Step-by-step visual timeline (screenshots) — the headline visual: shows
    # every step's pass/fail with a picture and points at the failing step.
    step_timeline = _render_step_timeline(_load_step_trace())
    if step_timeline:
        sections_html.append(step_timeline)
```

Replace with (note: insert at the FRONT of sections_html so it is the headline):

```python
    # Step-by-step results (summary cards + filterable status table + failure
    # gallery). Headline section, rendered first.
    step_section = step_report.render_step_report(_load_step_trace(), _img_data_uri)
    if step_section:
        sections_html.insert(0, step_section)
```

- [ ] **Step 3: Include the report CSS**

Find (around line 1053):

```python
<style>{_coverage_css()}</style></head>
```

Replace with:

```python
<style>{_coverage_css()}{step_report.STEP_REPORT_CSS}</style></head>
```

- [ ] **Step 4: Verify compile + existing tests still pass**

Run: `python -m py_compile core/agent_ui.py && python -m pytest tests/ -q`
Expected: COMPILE OK; all tests pass.

- [ ] **Step 5: Smoke-render against the existing ResGate trace**

The current `workspace/ResGate/report/step_trace.json` is still the OLD shape
(`type/name` entries). Confirm the renderer degrades gracefully (no status =>
0 counts, rows still render, no crash):

Run:
```bash
python -c "import sys; sys.path.insert(0,'core'); import json, step_report; \
steps=json.load(open('workspace/ResGate/report/step_trace.json')); \
print('html len', len(step_report.render_step_report(steps)))"
```
Expected: prints a positive length, no exception.

- [ ] **Step 6: Commit**

```bash
git add core/agent_ui.py
git commit -m "feat(report): use Template C step report as headline of coverage report"
```

---

## Task 4: pytest-bdd step hooks in ResGate `conftest.py`

**Files:**
- Modify: `workspace/ResGate/conftest.py` (add hooks at end of file; edit `CapturedValues.flush`)

- [ ] **Step 1: Stop `flush()` writing the old step_trace.json**

Find in `CapturedValues.flush` (around lines 261-264):

```python
        (self.report_dir / "captured_values.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8")
        (self.report_dir / "step_trace.json").write_text(
            json.dumps(self.trace, indent=2, default=str), encoding="utf-8")
```

Replace with (step_trace.json is now owned by the hooks below):

```python
        (self.report_dir / "captured_values.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8")
```

- [ ] **Step 2: Add the step hooks at the end of `conftest.py`**

Append after the existing `pytest_runtest_makereport` hook (end of file):

```python
# --------------------------------------------------------------------------- #
# Step-level trace for the Test-results report. pytest-bdd fires these hooks per
# step; we record status and, on failure, the top-5 error lines + a screenshot.
# Steps after a failure never fire a hook, so we mark them skipped. The list
# accumulates across ALL tests in the run and is written once at session end.
# --------------------------------------------------------------------------- #
_STEP_TRACE = []


def _feature_name(feature):
    try:
        return Path(feature.filename).name
    except Exception:
        return ""


def _step_index(scenario, step):
    try:
        return list(scenario.steps).index(step) + 1
    except ValueError:
        return 0


def _top_error_lines(exc, n=5):
    lines = [ln for ln in str(exc).strip().splitlines() if ln.strip()]
    return "\n".join(lines[:n])


def pytest_bdd_after_step(request, feature, scenario, step, step_func, step_func_args):
    _STEP_TRACE.append({
        "test": request.node.name,
        "feature": _feature_name(feature),
        "index": _step_index(scenario, step),
        "keyword": getattr(step, "keyword", ""),
        "name": step.name,
        "status": "passed",
    })


def pytest_bdd_step_error(request, feature, scenario, step, step_func,
                          step_func_args, exception):
    failed_idx = _step_index(scenario, step)
    shot_rel = ""
    try:
        page = request.getfixturevalue("page")
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", f"FAIL_{request.node.name}_{step.name}")[:80]
        shot_path = SCREENSHOTS_DIR / f"{int(time.time() * 1000)}_{safe}.png"
        page.screenshot(path=str(shot_path))
        shot_rel = f"screenshots/{shot_path.name}"
    except Exception:
        shot_rel = ""
    _STEP_TRACE.append({
        "test": request.node.name,
        "feature": _feature_name(feature),
        "index": failed_idx,
        "keyword": getattr(step, "keyword", ""),
        "name": step.name,
        "status": "failed",
        "error": _top_error_lines(exception, 5),
        "screenshot": shot_rel,
    })
    for s in scenario.steps:
        if _step_index(scenario, s) > failed_idx:
            _STEP_TRACE.append({
                "test": request.node.name,
                "feature": _feature_name(feature),
                "index": _step_index(scenario, s),
                "keyword": getattr(s, "keyword", ""),
                "name": s.name,
                "status": "skipped",
            })


def pytest_sessionfinish(session, exitstatus):
    if not _STEP_TRACE:
        return
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "step_trace.json").write_text(
        json.dumps(_STEP_TRACE, indent=2, default=str), encoding="utf-8")
```

- [ ] **Step 3: Verify conftest imports are present**

`Path`, `re`, `time`, `json` are already imported at the top of
`workspace/ResGate/conftest.py` (lines 14-18). No new imports needed. Confirm by
reading the top of the file; if any are missing, add them.

- [ ] **Step 4: Run the ResGate suite to produce a real trace**

Run (from the project dir):
```bash
cd workspace/ResGate && python -m pytest -q ; cd ../..
```
Expected: the suite runs (it currently FAILS on the duplicate-org assertion — that
is fine for this task). Then verify the trace shape:

```bash
python -c "import json; t=json.load(open('workspace/ResGate/report/step_trace.json')); \
print(len(t), 'records'); print(set(s['status'] for s in t)); \
print([s for s in t if s['status']=='failed'][:1])"
```
Expected: a list of records; statuses include `passed` and `failed` (and
`skipped` if steps follow the failing one); the failed record has `error` and a
`screenshot` path.

- [ ] **Step 5: Commit**

```bash
git add workspace/ResGate/conftest.py
git commit -m "feat(report): conftest pytest-bdd hooks emit per-step status trace"
```

---

## Task 5: Update framework prompts for future projects

**Files:**
- Modify: `core/prompts/framework_prompt.md`
- Modify: `core/prompts/framework_delta_prompt.md`

- [ ] **Step 1: Document the schema + hooks in `framework_prompt.md`**

Find the REPORT ARTIFACT PATHS line (line 7) and append a paragraph after it:

```markdown
STEP TRACE (per-step report): the generated `conftest.py` MUST register pytest-bdd
step hooks that write `report/step_trace.json` as a JSON array — one object per
step, accumulated across all tests in the run and flushed in `pytest_sessionfinish`.
Each object: `{"test","feature","index","keyword","name","status"}` where status is
`"passed"|"failed"|"skipped"`. For a `failed` step also include `"error"` (top 5
lines of the exception) and `"screenshot"` (path relative to `report/`, captured
via the live `page` fixture). On a step error, mark every later step in
`scenario.steps` as `"skipped"`. Do NOT write `step_trace.json` from the
`captured_values` flush; the hooks own it. Use hooks `pytest_bdd_after_step`
(passed) and `pytest_bdd_step_error` (failed).
```

- [ ] **Step 2: Cross-reference from `framework_delta_prompt.md`**

Find the FIDELITY rules line (line 51) and append to it:

```markdown
The `step_trace.json` step-hook contract from FRAMEWORK_PROMPT still applies: keep
the `pytest_bdd_after_step`/`pytest_bdd_step_error`/`pytest_sessionfinish` hooks and
the per-step `{test,feature,index,keyword,name,status[,error,screenshot]}` schema.
```

- [ ] **Step 3: Verify no broken references**

Run: `python -m pytest tests/ -q`
Expected: PASS (prompts are text; this just confirms nothing else broke).

- [ ] **Step 4: Commit**

```bash
git add core/prompts/framework_prompt.md core/prompts/framework_delta_prompt.md
git commit -m "docs(prompt): require per-step step_trace.json hooks in generated conftest"
```

---

## Task 6: End-to-end verification in the UI

**Files:** none (manual verification)

- [ ] **Step 1: Launch the app**

Run: `streamlit run core/agent_ui.py`

- [ ] **Step 2: Run the ResGate test from the Run Tests tab**

Select the ResGate project, go to **Run Tests**, run the test. Wait for completion.

- [ ] **Step 3: Verify the report in Test results**

Open **Test results**. Confirm:
- Summary cards show Tests ran / Passed steps / Failed steps / Skipped steps with correct numbers.
- The status table lists every step with green ✓ / red ✗ / dark-blue ⊘ markers.
- The All / Failed / Skipped filter buttons toggle rows.
- The Failures gallery shows the failed step with a screenshot and ≤5 error lines.

- [ ] **Step 4: Final commit (docs/plan checkbox updates if tracked)**

```bash
git add -A
git commit -m "chore: mark step-report plan complete"
```

---

## Self-Review Notes

- **Spec coverage:** colored markers (Task 2 `_STATUS_META`/CSS), mandatory failure screenshot + top-5 error (Task 4 `pytest_bdd_step_error` + Task 2 gallery), summary counts (Task 1/2), multi-test aggregation (Task 1 distinct tests + Task 4 module-level accumulator), Template C table+gallery (Task 2), ResGate now (Tasks 3-4), future prompts (Task 5). All covered.
- **Skip marker:** dark-blue `⊘` (`⊘`, `#1e3a8a`) consistently in `_STATUS_META` and CSS.
- **Type consistency:** status string values `passed|failed|skipped` and record keys `test/feature/index/keyword/name/status/error/screenshot` identical in conftest (producer) and step_report (consumer).
- **Known unknown resolved:** pytest-bdd 8.1.0 confirmed; `step.keyword`/`step.name`/`scenario.steps` verified; hooks `pytest_bdd_after_step`/`pytest_bdd_step_error` exist.

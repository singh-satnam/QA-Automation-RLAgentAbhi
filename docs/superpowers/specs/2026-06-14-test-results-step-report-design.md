# Test Results Step-Level Report — Design

_Date: 2026-06-14 · Status: approved design, pending implementation_

## Goal

Upgrade the **Test results** tab so the report shows, for every test run, a
per-step pass/fail/skip breakdown, mandatory failure evidence (screenshot +
error log), and an aggregated summary across all tests in the run.

Requirements (from the user):

- Each step shows its status with a colored marker:
  - **Pass** → green tick (`✓`, `#16a34a`)
  - **Fail** → red cross (`✗`, `#dc2626`)
  - **Skip** → dark-blue circle-slash (`⊘`, `#1e3a8a`)
- Every **failed** step MUST have a screenshot and the **top 5 lines** of the
  error log.
- A **summary** with: Total tests ran, Passed steps, Failed steps, Skipped steps.
- When multiple tests run in one go, data is **aggregated across all tests**.
- Chosen layout: **Template C — filterable status table + failure gallery**.

## Key finding (why this is two parts, not just a template)

The data needed (per-step status, per-step error, per-step screenshot) is **not
captured today**:

- `step_trace.json` is built from `CapturedValues.step()` in the generated
  `conftest.py`, which records only `{type, name, ts}` — no status, keyword,
  error, or per-step screenshot.
- The existing renderer `_render_step_timeline()` (core/agent_ui.py) already
  reads `status`/`keyword`/`index`/`error`, but the generated conftest has **no
  pytest-bdd step hooks** to populate them. So every step currently renders as a
  tick regardless of the real outcome; failure only surfaces as one `FAILURE_*`
  screenshot.

Therefore the work has two halves: **instrumentation** (produce the data) and
**renderer** (display it).

## 1. Data contract — new `step_trace.json`

The new hooks own `step_trace.json`. One record per step, accumulated across all
tests in a single pytest run:

```json
{
  "test": "test_successfully_create_a_new_organization",
  "feature": "create_organization.feature",
  "index": 5,
  "keyword": "Then",
  "name": "a new organization should be created successfully",
  "status": "failed",
  "error": "AssertionError: ...\n(up to 5 lines)",
  "screenshot": "screenshots/FAIL_....png"
}
```

- `status` ∈ `passed` | `failed` | `skipped`.
- `error` and `screenshot` are present only for `failed` records.
- `screenshot` path is relative to the project's `report/` directory.
- `index` is 1-based within the test (position in `scenario.steps`).

`captured_values.json` is unchanged — it remains the assertion/value audit trail.
Only `step_trace.json` becomes richer, and it is now produced by the hooks rather
than by `cap.step()`/`cap.snap()`.

## 2. Instrumentation — `conftest.py` (generated per project)

Add a session-level accumulator and three pytest-bdd hooks:

- `pytest_bdd_after_step(request, feature, scenario, step, step_func, step_func_args)`
  — fires when a step **passes**. Append a `passed` record (test name, feature,
  index, keyword, step text). No screenshot.
- `pytest_bdd_step_error(request, feature, scenario, step, step_func,
  step_func_args, exception)` — fires when a step **fails**. Append a `failed`
  record with the top-5 lines of `exception` and a screenshot captured via the
  live `page` fixture (`request.getfixturevalue("page")`). Then enumerate
  `scenario.steps`; every step positioned after the failed one is appended as a
  `skipped` record (those hooks never fire after a failure).
- `pytest_sessionfinish(session, exitstatus)` — write the accumulated list to
  `report/step_trace.json`. A run of N tests yields one aggregated trace.

Helpers:

- `_step_index(scenario, step)` → `list(scenario.steps).index(step) + 1`.
- `_top_lines(exception, 5)` → first 5 lines of `str(exception)`.
- Screenshot file naming reuses the existing `screenshots/` dir and timestamp
  pattern; the failure screenshot from `pytest_runtest_makereport` is retained
  for backwards compatibility but the per-step screenshot is what the gallery
  uses.

The old per-step writing into `step_trace.json` via `cap.flush()` is retired (the
flush keeps writing `captured_values.json` only).

Note on hook names/signatures: `pytest_bdd_after_step` and
`pytest_bdd_step_error` are stable across pytest-bdd versions; the exact arg list
is verified during implementation against the installed pytest-bdd.

## 3. Renderer — Template C (`build_inline_coverage_report`)

Replace `_render_step_timeline()` with a new `_render_step_report(steps)` that
emits three blocks into the self-contained `story_coverage.html` (still embedded
and downloadable in the Test results tab):

**a. Summary cards** — `Total tests ran`, `Passed steps`, `Failed steps`,
`Skipped steps`, aggregated across every test. `Total tests ran` = count of
distinct `test` values in the trace.

**b. Status table** — columns `# | Test | Keyword | Step | Status`, one row per
step across all tests, status rendered as a colored pill. Three filter buttons
(**All / Failed / Skipped**) implemented with a small inline `<script>` that
toggles row visibility by CSS class (works inside the `components.html` iframe).

**c. Failures gallery** — only failed steps: `test · step text`, the screenshot
inlined as a base64 data URI (`_img_data_uri`), and the top-5 error lines in a
monospace block.

Colors: pass `#16a34a` (`✓`), fail `#dc2626` (`✗`), skip `#1e3a8a` (`⊘`).

This section becomes the headline, rendered directly under the verdict banner.
Existing sections (assertions, values, prerequisites) remain below it.

## 4. Scope

- **ResGate now:** edit `workspace/ResGate/conftest.py` and the renderer so the
  current project produces the new report end-to-end.
- **Future projects:** update `core/prompts/framework_prompt.md` (and the
  report-artifact contract / `framework_delta_prompt.md` as needed) so newly
  generated projects include the step hooks and the new `step_trace.json` schema.
  Otherwise the next regeneration would silently drop the instrumentation.

## Out of scope

- The Run Tests tab (no changes — explicitly deferred by the user).
- Checkbox multi-select run feature (deferred).
- Allure/pytest-html report changes (the raw artifacts stay as secondary).

## Testing

- Unit-test the renderer helper with a synthetic `step_trace` list covering all
  three statuses and a multi-test aggregate; assert counts, row count, pill
  classes, and that each failed step yields a gallery entry with a screenshot
  reference and ≤5 error lines.
- Integration: run the ResGate test (currently failing on the duplicate-org
  issue) and confirm `step_trace.json` contains passed→failed→skipped records and
  the report renders the table + failure gallery + correct summary counts.

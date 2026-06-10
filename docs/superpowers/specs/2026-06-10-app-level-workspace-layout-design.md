# App-Level Workspace Layout & Direct-to-Project Execution

Date: 2026-06-10
Status: Approved (design phase) — ready for implementation planning

## 1. Problem statement

The QA-Automation engine currently organizes generated artifacts (Gherkin
features, Page Objects, step defs, tests, reports) **per story**, with a
separate `_shared/` folder per app holding reusable POMs/step defs/selectors.
Concretely, for app `ra_demo_rlcatalyst_com`:

```
workspace/projects/ra_demo_rlcatalyst_com/
  _shared/{pages, step_defs, mcp-selectors, flow_index.json}
  _suite_runs/<timestamp>/suite_report.html
  feature_add_a_new_user__3834495b/
    .story_id, user_story.txt, process_log.txt, README.md
    features/, pages/, step_defs/, tests/, mcp-selectors/, reports/
  feature_delete_an_existing_user__f26ca53f/
    (same shape)
```

Problems with this:
- Per-story duplication of `pages/`/`step_defs/`/`mcp-selectors/` (also
  duplicated again in `_shared/`), with last-write-wins copying between them
  (`promote_to_shared` / `restore_from_shared`).
- File-name collisions are latent: both existing stories independently named
  their first feature/step-def/test file `story_1_*`.
- Reports/screenshots/logs are generated in `core/reports/` (the engine's
  scratch dir) during a run and only copied into the project folder
  afterward via `archive_artifacts()` — not "live" in the project, and a
  source of path bugs (e.g. the recent `ValueError` on `relative_to`).
- All of this works against the stated goal: **one application = one
  project = one coherent, browsable folder** that a user can open and
  understand directly.

## 2. Goal

Each application (`app_id`, derived from the story's URL — see
`AGENT_FLOW.md`) gets exactly **one** folder tree under
`workspace/projects/<app_id>/` containing exactly six artifact folders
(`features/`, `pages/`, `step_defs/`, `tests/`, `mcp-selectors/`,
`reports/`), shared across every story for that app. The Claude agent and
pytest write **directly** into this tree — no `core/` scratch copies, no
post-run archive/promote/restore step.

## 3. New directory layout

```
workspace/projects/<app_id>/
  stories.json              # manifest: one entry per story
  flow_index.json           # POM method -> file index (kept, unchanged purpose)

  features/
    <slug>.feature                    # one per story, e.g. add_a_new_user.feature

  pages/
    __init__.py
    base_page.py
    page_<name>.py                    # POMs, shared/extended across stories

  step_defs/
    __init__.py
    <slug>_steps.py                   # one per story's feature file

  tests/
    __init__.py
    conftest.py                       # small per-app fixtures (dialog_recorder, clean-state)
    test_<slug>.py                    # one per story

  mcp-selectors/
    locators.json                     # discovered selectors, shared across stories

  reports/
    report.html
    allure-results/
    screenshots/
    captured_values.json
    step_trace.json
    story_coverage.html
    story_coverage.json
    story_coverage.md
    .storage_state.json
    runs/
      <YYYY-MM-DD_HH-MM-SS>/           # snapshot of the above, one per run
        report.html
        allure-results/
        screenshots/
        captured_values.json
        step_trace.json
        story_coverage.*
        process_log.txt
```

Removed entirely: `_shared/`, `_suite_runs/`, per-story
`feature_<slug>__<digest>/` folders, `.story_id` sidecars, per-story
`user_story.txt` / `process_log.txt` / `README.md`.

## 4. File naming — drop the "story_N" prefix

Files are named by the story's descriptive **slug** (already computed by
`_story_slug()`), not a numeric `story_N` prefix:

- `features/add_a_new_user.feature` (was `story_1_add_new_user.feature`)
- `step_defs/add_a_new_user_steps.py`
- `tests/test_add_a_new_user.py`

Rationale: slugs are derived from story content and are effectively unique
per app; `story_N` numbering was a latent collision (`story_1` chosen
independently by two different stories). This requires updating the prompt
templates in `core/prompts/` (gherkin, framework, framework-delta) to use
`<slug>`-based filenames instead of `story_N_<slug>`.

## 5. `stories.json` manifest

Replaces `.story_id` sidecars + per-story `user_story.txt`. One entry per
story, keyed by content digest (same digest algorithm as today's
`_content_digest()`):

```json
{
  "stories": [
    {
      "slug": "add_a_new_user",
      "digest": "3834495b",
      "story_text": "As an admin, I want to add a new user...",
      "feature_file": "features/add_a_new_user.feature",
      "step_defs_file": "step_defs/add_a_new_user_steps.py",
      "test_file": "tests/test_add_a_new_user.py",
      "created": "2026-06-10T07:08:11"
    }
  ]
}
```

`compute_story_id()`'s re-binding logic (re-pasting an unchanged story
serves cached files) becomes a digest lookup against `stories.json` instead
of scanning `.story_id` sidecars across folders.

## 6. Reports — live + history

- During a run, pytest/conftest write **directly** to
  `workspace/projects/<app_id>/reports/...` (report.html, allure-results/,
  screenshots/, captured_values.json, step_trace.json). These files are
  overwritten on each run — always reflecting the latest run.
- `write_inline_coverage_report()` writes `story_coverage.{html,json,md}`
  into the same `reports/` folder, also overwritten each run.
- Immediately after, the full set of `reports/*` files (excluding `runs/`
  itself) is copied into `reports/runs/<timestamp>/` as a historical
  snapshot. The per-run `process_log.txt` (agent activity log, currently
  written per-story) also goes into this snapshot folder.
- The "Run All Stories" suite report (`_suite_runs/.../suite_report.html`)
  becomes `reports/runs/<timestamp>/suite_report.html` — same history
  mechanism, no separate top-level folder.

## 7. Execution model — root conftest shim

Today: `core/conftest.py` + `core/pytest.ini` live in `core/`; pytest runs
with `cwd=core/`; relative `Path("reports")` resolves to `core/reports/`.

Problem: pytest discovers `conftest.py` by walking from the test path's
directory up to a common ancestor with `rootdir`. `workspace/` and `core/`
are siblings, so a test run rooted in `workspace/projects/<app_id>/tests/`
would never see `core/conftest.py`.

**Solution**: a thin `conftest.py` at the **repo root** (parent of `core/`
and `workspace/`) re-exports everything from `core/conftest.py`:

```python
# /conftest.py (repo root)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from core.conftest import *  # noqa: F401,F403
from core.conftest import (
    pytest_sessionstart, pytest_addoption, pytest_bdd_after_step,
    pytest_bdd_step_error, pytest_runtest_makereport,
)

# pytest_plugins = (...)  -- maintained by sync_pytest_plugins(), appended below
```

`core/conftest.py` no longer defines `pytest_plugins` itself (it has no
fixed set of step-def modules to register — that varies per app).
`sync_pytest_plugins()` rewrites the trailing `pytest_plugins = (...)` line
in the root shim file directly.

- `pytest.ini` moves from `core/pytest.ini` to the repo root (still
  maintained by `_write_pytest_ini`, just a different path).
- `core/conftest.py` keeps all real fixture/hook implementations, but path
  constants (`_CAPTURED_VALUES_PATH`, `_STEP_TRACE_PATH`,
  `_STEP_SCREENSHOT_DIR`, `_STORAGE_STATE_PATH`) are resolved from a
  `QA_PROJECT_DIR` environment variable (set by `agent_ui.py` to
  `workspace/projects/<app_id>`) instead of the relative `Path("reports")`.
- `agent_ui.py` invokes pytest with:
  - `cwd=<repo root>`
  - test path argument = `workspace/projects/<app_id>/tests`
  - `--html=workspace/projects/<app_id>/reports/report.html`
  - `--alluredir=workspace/projects/<app_id>/reports/allure-results`
  - env `QA_PROJECT_DIR=workspace/projects/<app_id>`
- `sync_pytest_plugins()` is retargeted to write the `pytest_plugins` tuple
  into the **root conftest shim** (not `core/conftest.py`), scanning
  `workspace/projects/<app_id>/step_defs/*.py`. The shim's `sys.path`
  insertion of `QA_PROJECT_DIR` makes `step_defs.<slug>_steps` importable.

## 8. Functions removed

- `archive_artifacts()` — nothing to archive; files are written in place.
- `promote_to_shared()`, `restore_from_shared()`, `_app_shared_dir()`,
  `app_shared_has_work()`, `_rebuild_flow_index()`'s `_shared`-specific
  paths (re-pointed at app-level `pages/` instead) — no more shared/story
  duplication to reconcile.
- `_migrate_legacy_folders()` — superseded by the one-time migration in
  Section 9 (which can supersede/absorb this function).

`ARTIFACT_DIRS` keeps its role as the list of the 6 app-level folder names
to ensure-exist, but is no longer used for copy operations.

## 9. Migration of existing `ra_demo_rlcatalyst_com` data

One-time migration, run automatically the next time this app's data is
touched:

1. Create the 6 app-level folders under
   `workspace/projects/ra_demo_rlcatalyst_com/`.
2. Move `_shared/pages/*` → `pages/`, `_shared/step_defs/*` → `step_defs/`,
   `_shared/mcp-selectors/*` → `mcp-selectors/`, `_shared/flow_index.json` →
   app root (these already contain the union of both stories' POMs/steps).
3. For each of the 2 existing story folders:
   - Copy `features/story_1_*.feature` → `features/<slug>.feature`
     (rename, dropping the `story_1_` prefix).
   - Copy `step_defs/story_1_*_steps.py` → `step_defs/<slug>_steps.py`
     (dedupe against files already moved from `_shared/`).
   - Copy `tests/test_story_1_*.py` → `tests/test_<slug>.py`.
   - Copy `tests/conftest.py` once (the two copies are near-identical).
4. Build `stories.json` from each story folder's `.story_id` (digest) +
   `user_story.txt` (story text) + the renamed file paths.
5. The more recently modified story's `reports/` becomes the new
   `reports/`; both stories' old `reports/` (plus `_suite_runs/*`) are
   archived under `reports/runs/<timestamp-from-mtime>/`.
6. Delete the old per-story folders, `_shared/`, `_suite_runs/`.

## 10. Current-state reference points (for implementation planning)

All in `core/agent_ui.py` unless noted:

- Path constants: `REPORTS_DIR`/`ALLURE_RESULTS`/`HTML_REPORT`/`SCREENSHOT_DIR`
  (lines 44-47), `PYTEST_HEADED_CMD_BASE` (86-92), `pytest_headed_cmd()` (95)
- Story identity: `_content_digest` (332), `_story_slug` (344),
  `_folder_name_for` (352), `_extract_app_id` (389), `compute_story_id` (738),
  `project_dir` (780)
- Shared/archive machinery to remove: `_app_dir`/`_app_shared_dir` (439-444),
  `app_shared_has_work` (455), `promote_to_shared` (471),
  `_rebuild_flow_index` (537), `restore_from_shared` (565),
  `_is_app_folder` (607), `_migrate_legacy_folders` (623),
  `archive_artifacts` (1123), `_NON_APP_TOP_DIRS` (386)
- pytest plugin sync: `sync_pytest_plugins` (1317)
- Report loading/writing: `_CAPTURED_VALUES_FILE`/`_load_captured_values`
  (1389-1404), `_load_step_trace` (1406), `write_inline_coverage_report`
  (2053)
- Call sites of removed functions: lines ~4317, 4320, 4569, 4620, 4740,
  4745, 4787, 4800, 4819, 4824, 4870, 4879, 4915-4916
- `core/conftest.py`: `pytest_plugins` (11), `_CAPTURED_VALUES_PATH` (17),
  `_STEP_TRACE_PATH`/`_STEP_SCREENSHOT_DIR` (23-24), `_STORAGE_STATE_PATH`
  (661), `pytest_addoption`'s `base_url` ini registration (687); also a
  hardcoded `Path("reports/screenshots")` in `pytest_runtest_makereport`
  (~line 989) needs to use `_STEP_SCREENSHOT_DIR` instead
- `core/pytest.ini` → moves to repo root
- Prompt templates needing slug-only filename updates:
  `core/prompts/gherkin_prompt.md`, `framework_prompt.md`,
  `framework_delta_prompt.md`

## 11. Out of scope

- Changing the URL → `app_id` derivation (`_extract_app_id`) — unchanged.
- Changing the LLM prompts' *content* beyond the file-naming convention.
- Multi-app suite running, CI integration — unchanged.

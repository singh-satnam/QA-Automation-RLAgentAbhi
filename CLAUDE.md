# CLAUDE.md — QE Agent Project Conventions

## What This Project Is

QE Agent is a Streamlit-based UI that converts plain-English user stories into self-healing pytest-bdd + Playwright test suites. The pipeline has three steps:

1. **Generate Gherkin** — Claude CLI reads a user story, writes `.feature` files
2. **Generate Framework** — Claude CLI + Playwright MCP discovers selectors, writes Page Object Models, step definitions, and test files
3. **Run Tests** — `pytest --headed` with Playwright executes the tests, generates HTML/Allure reports

All generated files go through a **staging workspace** (`temp_workspace/<Project>/`) first. After tests pass, the user promotes files to `workspace/<Project>/` via a confirmation dialog (additive merge — never overwrites).

## Project Structure

```
core/
  agent_ui.py        # Streamlit UI + pipeline orchestration (~3231 lines)
  workspace.py       # All path resolution, project/story CRUD, staging/promotion
  step_report.py     # Pure HTML rendering of per-step test results
  prompts/           # LLM prompt templates (.md files, loaded at import time)
  templates/         # conftest.py + base_page.py scaffolding copied to each project
  .streamlit/        # Streamlit theme + server config
tests/
  test_workspace.py  # 29 unit tests for workspace.py
  test_step_report.py
workspace/<Project>/ # Promoted (production) test projects — flat per-project layout
temp_workspace/<Project>/ # Staging area (gitignored)
docs/superpowers/    # Design specs and implementation plans
SYSTEM_GUIDE.md      # Single source of truth for current architecture (supersedes ARCHITECTURE.md)
```

## Tech Stack

- **Python 3.14**, **Streamlit 1.58**, **pytest 9.0**, **pytest-bdd**, **Playwright**
- Claude Code CLI for LLM calls (piped via stdin, stream-json mode)
- Playwright MCP tools for selector discovery during framework generation
- JRE 21 for Allure report generation

## Key Architectural Patterns

### Dual-Path Resolution (Staging)

`workspace.py` functions accept `staging: bool = False`. All path resolution goes through `project_dir(project, staging)` which returns `temp_workspace/<Project>/` or `workspace/<Project>/`.

In `agent_ui.py`, the single choke point `proj_path(*parts)` reads `st.session_state.staging_active` and resolves all ~30 call sites automatically.

### Project Layout

Every project (staging or workspace) has these canonical subdirectories:
`user_story/`, `feature/`, `step_defs/`, `pages/`, `test/`, `mcp-selectors/`, `report/`

### Reuse Index

`reuse_index.json` in each project maps discovered page methods, step defs, and selectors so the LLM can reuse existing code when generating for new stories.

### Prompt Templates

Prompts live in `core/prompts/*.md` and are loaded once at module import via `_load_prompt()`. Edit the `.md` files to change LLM behavior — no code changes needed.

## Running the App

```bash
cd core
streamlit run agent_ui.py
```

Server runs on port 8501 (headless mode, configured in `.streamlit/config.toml`).

## Running Tests

```bash
pytest tests/ -v
```

Tests use `tmp_path` fixtures — no real workspace/temp_workspace is touched. All 29 workspace tests + step_report tests should pass.

## Development Rules

### File Organization

- `core/` contains ONLY agent logic, workspace operations, and prompt files
- `workspace/<Project>/` holds the full generated project structure (feature files, POMs, step defs, tests, reports)
- Never put generated test artifacts in `core/`

### workspace.py Conventions

- Every path function takes `staging: bool = False` — always pass it explicitly in new code
- `promote_to_workspace()` uses additive merge: copy only if dest doesn't exist, never overwrite
- `list_projects()` and `list_stories()` scan BOTH roots (workspace + temp_workspace)
- `PROJECT_SUBDIRS` is the single source of truth for subfolder names (singular: `user_story`, not `user_stories`)
- `derive_project_name(filename)` extracts the project name from the **filename prefix before the first underscore** — `RLRG_login.txt` → project `RLRG`. All path resolution flows from this. Files without an underscore raise `ProjectNameError`.
- Env vars `QA_WORKSPACE_DIR` and `QA_TEMP_WORKSPACE_DIR` override the default workspace roots at runtime (used to point at a per-client path without touching code)

### agent_ui.py Conventions

- Use `proj_path(*parts)` for all project-relative paths — it handles staging automatically
- Use `current_project()` for the active project name, never read `st.session_state.project` directly
- Session state is wiped on page refresh via `initialize_session()` — staging state is recovered from disk via `ws.is_staged()`
- Pipeline buttons (`gen_clicked`, `fw_clicked`, `run_clicked`) are captured by `render_stepper()` and handled in `main()`
- Long-running commands go through `stream_command()` which streams output to the activity panel

### LLM Prompts

- Prompt files are in `core/prompts/` as Markdown
- `gherkin_prompt.md` — Gherkin generation from user stories
- `framework_prompt.md` — Full framework generation (POMs, step defs, tests)
- `framework_delta_prompt.md` — Incremental framework for additional stories
- Use `{{TOKEN}}` placeholders in prompts, replaced at call time in `agent_ui.py`

Scout prompts (opt-in, defined inline in `agent_ui.py`) produce JSON artefacts the framework prompt can ingest:
- `SCOUT_SITEMAP_PROMPT` → `mcp-selectors/sitemap.json`
- `SCOUT_INVENTORY_PROMPT` → `mcp-selectors/scout_inventory.json` (confirmed-clickable selectors per page)
- `SCOUT_FLOW_PROMPT` → `mcp-selectors/scout_flow.json` (end-to-end story replay with selectors per step)
- `SCOUT_EDGE_PROMPT` → `mcp-selectors/scout_edge.json` (overlays: cookie banners, modals, iframes)

### Testing

- Unit tests go in `tests/`
- Tests for `workspace.py` use `tmp_path` and monkeypatch `WORKSPACE_DIR` / `TEMP_WORKSPACE_DIR`
- `step_report.py` is pure (no Streamlit dependency) and tested independently
- `agent_ui.py` is not unit-tested — verify UI changes by running the Streamlit app

### Git

- Branch: `feature/Version5` for active development
- Commit style: `feat(scope):`, `fix(scope):`, `chore:`, `docs:`
- `temp_workspace/` is gitignored
- `workspace/*/report/` and `workspace/**/report/` are gitignored (run artefacts accumulate without bound)

### captured_values Contract

Every generated step definition receives a `captured_values` fixture (a `CapturedValues` instance from `core/templates/conftest.py`). It accumulates every observation into memory and flushes to `report/captured_values.json` at session end. The coverage report is built **entirely** from that JSON — if a step def calls no `cap.*` method, that step shows as "not exercised" even if the test passes green.

**Rule: every `Then` step (any Verify/Check/Validate step) must call exactly one `cap.*` method.**

| Method | Raises? | Use when |
|---|---|---|
| `cap.add(label, value)` | No | Recording an observed value with no pass/fail |
| `cap.assert_match(label, expected, actual)` | No | Verifying a displayed value matches expected |
| `cap.record_missing(label, target, reason)` | No | An item in a loop was not found — loop continues |
| `cap.assert_prerequisite(label, condition, reason)` | Yes (halts scenario) | Login/navigation — if this fails, the rest can't run |
| `cap.assert_action_succeeded(label, error_text, positive_signal)` | Yes on failure | Confirming a create/submit action completed |
| `cap.add_component(label, value, group)` + `cap.assert_sum/avg/min/max/count(...)` | No / No | Multi-row aggregates (totals, averages across a table) |

**Verdict hierarchy** (written into `story_coverage.html` by the deterministic Python builder in `agent_ui.py`):

| Verdict | Condition |
|---|---|
| 🚫 BLOCKED | An `assert_prerequisite` call returned false |
| ❌ FAIL | At least one `assert_match` failed, or pytest exited nonzero |
| ⚠ PARTIAL | At least one `record_missing` entry, remaining assertions passed |
| ✓ PASS | All recorded assertions passed and pytest exited 0 |

## What NOT to Change

- `PROJECT_SUBDIRS` tuple order/naming — downstream code depends on these exact names
- `proj_path()` signature — it's the single routing point for staging vs workspace
- Scaffolding files (`core/templates/conftest.py`, `core/templates/base_page.py`) — `copy_scaffolding()` **overwrites the copy in every existing project** on each call, not just new ones; a change here propagates immediately to all projects
- `_PYTEST_INI_TEMPLATE` format — pytest reads this at test runtime

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
  agent_ui.py        # Streamlit UI + pipeline orchestration (~3000 lines)
  workspace.py       # All path resolution, project/story CRUD, staging/promotion
  step_report.py     # Pure HTML rendering of per-step test results
  prompts/           # LLM prompt templates (.md files, loaded at import time)
  templates/         # conftest.py + base_page.py scaffolding copied to each project
  .streamlit/        # Streamlit theme + server config
tests/
  test_workspace.py  # 29 unit tests for workspace.py
  test_step_report.py
workspace/<Project>/ # Promoted (production) test projects
temp_workspace/<Project>/ # Staging area (gitignored)
docs/superpowers/    # Design specs and implementation plans
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

### Testing

- Unit tests go in `tests/`
- Tests for `workspace.py` use `tmp_path` and monkeypatch `WORKSPACE_DIR` / `TEMP_WORKSPACE_DIR`
- `step_report.py` is pure (no Streamlit dependency) and tested independently
- `agent_ui.py` is not unit-tested — verify UI changes by running the Streamlit app

### Git

- Branch: `feature/version4` for active development
- Commit style: `feat(scope):`, `fix(scope):`, `chore:`, `docs:`
- `temp_workspace/` is gitignored
- `workspace/projects/*/*/reports/runs/` is gitignored (accumulates without bound)

## What NOT to Change

- `PROJECT_SUBDIRS` tuple order/naming — downstream code depends on these exact names
- `proj_path()` signature — it's the single routing point for staging vs workspace
- Scaffolding files (`core/templates/conftest.py`, `core/templates/base_page.py`) — these are copied verbatim to every project; changes here affect all future projects
- `_PYTEST_INI_TEMPLATE` format — pytest reads this at test runtime

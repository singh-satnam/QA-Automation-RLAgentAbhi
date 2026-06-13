# Project-Scoped Workspace Layout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-shape the QE Agent so a "project" is derived from the uploaded story filename, all artifacts live in one flat `workspace/<project>/` tree, `core/` holds only agent code, and reuse across stories is driven by a maintained `reuse_index.json` instead of a `_shared/` folder.

**Architecture:** Extract all project/path/reuse logic into a new pure module `core/workspace.py` (unit-tested). Rewire `core/agent_ui.py` to use it: derive the project from the upload/paste, generate directly into `workspace/<project>/` (agent subprocess `cwd` = the project dir), and remove the per-story archive / `_shared` / fork / demo-stash / legacy-migration machinery. Update the prompt `.md` files for the new folder names and create-only rules.

**Tech Stack:** Python 3, Streamlit, pytest + pytest-bdd, Playwright MCP, Claude Code CLI.

**Spec:** `docs/superpowers/specs/2026-06-13-project-scoped-workspace-layout-design.md`

---

## File structure

| File | Responsibility | Action |
|---|---|---|
| `core/workspace.py` | Pure logic: project-name derivation, path building, folder creation, duplicate check, base_url/pytest.ini, report run dirs, reuse index. No Streamlit. | Create |
| `tests/test_workspace.py` | Unit tests for `core/workspace.py`. | Create |
| `core/agent_ui.py` | Streamlit UI + orchestration. Rewired to `workspace.py`; old machinery removed. | Modify |
| `core/prompts/*.md` | LLM prompts. Folder names + create-only + story-file reading. | Modify |
| `workspace/` | Reset to clean slate. | Delete contents |
| stray `core/` artifacts | `user_story.txt`, `user_data.json`, `features/`, `pages/`, `step_defs/`, `tests/`, `conftest.py`, `pytest.ini`, `mcp-selectors/`, `reports/`, `generation_log.txt`, `.playwright-mcp/`, `.pytest_cache/` | Delete |

**Note for the executor:** `core/agent_ui.py` is ~4900 lines and tightly coupled. Tasks that modify it name the exact function/region and give the replacement code; you must open the file and read the surrounding code before each edit. Verify imports still resolve after each removal by running `python -c "import ast; ast.parse(open('core/agent_ui.py',encoding='utf-8').read())"`.

---

## Stage 0 — Filesystem cleanup

### Task 0: Reset workspace and purge stray artifacts from core

**Files:**
- Delete: `workspace/projects/` (and any other content under `workspace/`)
- Delete: stray data dirs/files inside `core/`

- [ ] **Step 1: Confirm what's tracked vs untracked**

Run: `git status --porcelain`
Expected: `workspace/` is untracked (`??`); some `core/` files show as deleted/modified already.

- [ ] **Step 2: Remove old workspace data and stray core artifacts**

```bash
rm -rf workspace/projects
rm -rf "core/.playwright-mcp" "core/.pytest_cache"
rm -f  core/user_story.txt core/user_data.json core/user_data.* core/generation_log.txt
rm -rf core/features core/pages core/step_defs core/tests core/mcp-selectors core/reports
rm -f  core/conftest.py core/pytest.ini
```

(If any path does not exist, that's fine — it was already gone.)

- [ ] **Step 3: Verify core is down to agent code only**

Run: `ls core`
Expected: only `agent_ui.py`, `prompts`, `requirements.txt`, `.streamlit` (plus `.gitignore`/`README` if present). No `features`/`tests`/`reports`/`pytest.ini`/`conftest.py`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: reset workspace and purge client artifacts from core"
```

---

## Stage 1 — `core/workspace.py` (pure logic, TDD)

### Task 1: Project-name derivation + filename sanitisation

**Files:**
- Create: `core/workspace.py`
- Test: `tests/test_workspace.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workspace.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
import workspace  # noqa: E402
import pytest  # noqa: E402


def test_derive_project_name_takes_prefix_before_first_underscore():
    assert workspace.derive_project_name("RLRG_login.txt") == "RLRG"
    assert workspace.derive_project_name("saucedemo_checkout_flow.txt") == "saucedemo"
    assert workspace.derive_project_name("caedu_a_b_c.txt") == "caedu"  # only first '_'


def test_derive_project_name_rejects_missing_prefix():
    with pytest.raises(workspace.ProjectNameError):
        workspace.derive_project_name("login.txt")


def test_sanitize_filename_forces_txt_and_strips_unsafe_chars():
    assert workspace.sanitize_filename("RLRG login flow") == "RLRG_login_flow.txt"
    assert workspace.sanitize_filename("RLRG_login.txt") == "RLRG_login.txt"
    with pytest.raises(workspace.ProjectNameError):
        workspace.sanitize_filename("   ")
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_workspace.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'workspace'` (module not created yet).

- [ ] **Step 3: Create `core/workspace.py` with these functions**

```python
# core/workspace.py
from __future__ import annotations

import datetime as _dt
import json
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACE_DIR = Path(os.environ.get("QA_WORKSPACE_DIR", PROJECT_ROOT.parent / "workspace"))

# Canonical subfolders of a project, per the design diagram (singular names).
PROJECT_SUBDIRS = (
    "user_story", "feature", "step_defs", "pages", "test", "mcp-selectors", "report",
)

REUSE_INDEX_NAME = "reuse_index.json"

_PROJECT_NAME_RE = re.compile(r"^([A-Za-z0-9]+)_")
_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


class ProjectNameError(ValueError):
    """Raised when a project name / story filename cannot be derived."""


def derive_project_name(filename: str) -> str:
    """Project name = text before the FIRST underscore in the filename.
    'RLRG_login.txt' -> 'RLRG'. Raises ProjectNameError if there is no '_'."""
    stem = Path(filename).name
    m = _PROJECT_NAME_RE.match(stem)
    if not m:
        raise ProjectNameError(
            "Filename must be '<project>_<name>.txt' so the project can be "
            f"identified — got '{stem}'."
        )
    return m.group(1)


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safe story filename ending in '.txt'."""
    base = Path(name).name.strip()
    if not base:
        raise ProjectNameError("Story filename must not be empty.")
    base = _UNSAFE_RE.sub("_", base).strip("_")
    if not base:
        raise ProjectNameError("Story filename has no usable characters.")
    if not base.lower().endswith(".txt"):
        base += ".txt"
    return base
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_workspace.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add core/workspace.py tests/test_workspace.py
git commit -m "feat(workspace): project-name derivation + filename sanitise"
```

### Task 2: Path helpers + folder creation + duplicate check

**Files:**
- Modify: `core/workspace.py`
- Test: `tests/test_workspace.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_ensure_project_dirs_creates_all_canonical_subfolders(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    pd = workspace.ensure_project_dirs("RLRG")
    assert pd == tmp_path / "RLRG"
    for sub in workspace.PROJECT_SUBDIRS:
        assert (pd / sub).is_dir()


def test_ensure_project_dirs_is_idempotent_and_non_destructive(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    keep = tmp_path / "RLRG" / "feature" / "keep.feature"
    keep.write_text("Feature: keep", encoding="utf-8")
    workspace.ensure_project_dirs("RLRG")  # second call must not wipe
    assert keep.exists()


def test_add_story_writes_new_and_refuses_duplicate(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    created, path = workspace.add_story("RLRG", "RLRG_login.txt", "story body")
    assert created is True
    assert path.read_text(encoding="utf-8") == "story body"
    assert workspace.story_exists("RLRG", "RLRG_login.txt") is True
    # Re-adding the same filename must NOT overwrite and must report not-created.
    created2, path2 = workspace.add_story("RLRG", "RLRG_login.txt", "DIFFERENT")
    assert created2 is False
    assert path2.read_text(encoding="utf-8") == "story body"


def test_list_projects_and_stories(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.add_story("RLRG", "RLRG_a.txt", "a")
    workspace.add_story("RLRG", "RLRG_b.txt", "b")
    workspace.add_story("saucedemo", "saucedemo_x.txt", "x")
    assert workspace.list_projects() == ["RLRG", "saucedemo"]
    names = [p.name for p in workspace.list_stories("RLRG")]
    assert names == ["RLRG_a.txt", "RLRG_b.txt"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_workspace.py -q`
Expected: FAIL — `AttributeError: module 'workspace' has no attribute 'ensure_project_dirs'`.

- [ ] **Step 3: Add the helpers to `core/workspace.py`**

```python
def project_dir(project: str) -> Path:
    return WORKSPACE_DIR / project


def subdir(project: str, name: str) -> Path:
    return project_dir(project) / name


def ensure_project_dirs(project: str) -> Path:
    """Create only the missing canonical subfolders. Idempotent; never clears
    an existing folder. Returns the project dir."""
    pd = project_dir(project)
    for sub in PROJECT_SUBDIRS:
        (pd / sub).mkdir(parents=True, exist_ok=True)
    return pd


def story_exists(project: str, filename: str) -> bool:
    """Duplicate check: True if a story with this filename already exists."""
    return (subdir(project, "user_story") / filename).exists()


def add_story(project: str, filename: str, content: str) -> tuple[bool, Path]:
    """Write a NEW story file. Returns (created, path). If the file already
    exists it is left untouched and (False, path) is returned."""
    ensure_project_dirs(project)
    path = subdir(project, "user_story") / filename
    if path.exists():
        return False, path
    path.write_text(content, encoding="utf-8")
    return True, path


def list_projects() -> list[str]:
    if not WORKSPACE_DIR.exists():
        return []
    return sorted(
        p.name for p in WORKSPACE_DIR.iterdir()
        if p.is_dir() and not p.name.startswith((".", "_"))
    )


def list_stories(project: str) -> list[Path]:
    us = subdir(project, "user_story")
    return sorted(us.glob("*.txt")) if us.exists() else []
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_workspace.py -q`
Expected: PASS (7 tests total).

- [ ] **Step 5: Commit**

```bash
git add core/workspace.py tests/test_workspace.py
git commit -m "feat(workspace): paths, folder creation, duplicate check"
```

### Task 3: base_url extraction + per-project pytest.ini

**Files:**
- Modify: `core/workspace.py`
- Test: `tests/test_workspace.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_extract_base_url():
    assert workspace.extract_base_url("go to https://saucedemo.com/login now") == "https://saucedemo.com/login"
    assert workspace.extract_base_url("no url here") == ""


def test_write_pytest_ini_sets_base_url_and_testpaths(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    ini = workspace.write_pytest_ini("RLRG", "https://saucedemo.com")
    text = ini.read_text(encoding="utf-8")
    assert "base_url = https://saucedemo.com" in text
    assert "testpaths = test" in text
    # Rewriting with a new url updates in place, doesn't duplicate the key.
    workspace.write_pytest_ini("RLRG", "https://other.com")
    text2 = ini.read_text(encoding="utf-8")
    assert text2.count("base_url =") == 1
    assert "https://other.com" in text2
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_workspace.py -q`
Expected: FAIL — `AttributeError: ... 'extract_base_url'`.

- [ ] **Step 3: Add to `core/workspace.py`**

```python
_URL_RE = re.compile(r"https?://[^/\s\"'>)]+", re.IGNORECASE)

_PYTEST_INI_TEMPLATE = """[pytest]
base_url = {base_url}
testpaths = test
addopts = -ra
markers =
"""


def extract_base_url(text: str) -> str:
    """First http(s) URL in the text (scheme+host+port), or '' if none."""
    if not text:
        return ""
    m = _URL_RE.search(text)
    return m.group(0) if m else ""


def write_pytest_ini(project: str, base_url: str) -> Path:
    """Ensure workspace/<project>/pytest.ini exists with base_url + testpaths=test.
    Updates base_url in place if the file already exists; never duplicates keys."""
    ini = project_dir(project) / "pytest.ini"
    if ini.exists():
        text = ini.read_text(encoding="utf-8")
        new_text, n = re.subn(r"(?m)^base_url\s*=.*$", f"base_url = {base_url}", text, count=1)
        if n == 0:
            new_text = re.sub(r"(?m)^\[pytest\]\s*$", f"[pytest]\nbase_url = {base_url}", text, count=1)
        if new_text != text:
            ini.write_text(new_text, encoding="utf-8")
    else:
        ini.write_text(_PYTEST_INI_TEMPLATE.format(base_url=base_url), encoding="utf-8")
    return ini
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_workspace.py -q`
Expected: PASS (9 tests total).

- [ ] **Step 5: Commit**

```bash
git add core/workspace.py tests/test_workspace.py
git commit -m "feat(workspace): base_url extraction + per-project pytest.ini"
```

### Task 4: Timestamped report run dirs + history

**Files:**
- Modify: `core/workspace.py`
- Test: `tests/test_workspace.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_new_report_run_dir_is_unique_and_listed_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    d1 = workspace.new_report_run_dir("RLRG", run_id="2026-06-13_10-00-00")
    d2 = workspace.new_report_run_dir("RLRG", run_id="2026-06-13_11-00-00")
    assert d1.is_dir() and d2.is_dir()
    runs = workspace.report_runs("RLRG")
    assert [r.name for r in runs] == ["2026-06-13_11-00-00", "2026-06-13_10-00-00"]


def test_report_runs_empty_when_none(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    assert workspace.report_runs("RLRG") == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_workspace.py -q`
Expected: FAIL — missing `new_report_run_dir`.

- [ ] **Step 3: Add to `core/workspace.py`**

```python
def new_report_run_dir(project: str, run_id: str | None = None) -> Path:
    """Create and return report/<timestamp>/ for a fresh run.
    run_id is overridable for deterministic tests."""
    stamp = run_id or _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    d = subdir(project, "report") / stamp
    d.mkdir(parents=True, exist_ok=True)
    return d


def report_runs(project: str) -> list[Path]:
    """All report run folders for the project, newest first."""
    rep = subdir(project, "report")
    if not rep.exists():
        return []
    return sorted((d for d in rep.iterdir() if d.is_dir()),
                  key=lambda p: p.name, reverse=True)
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_workspace.py -q`
Expected: PASS (11 tests total).

- [ ] **Step 5: Commit**

```bash
git add core/workspace.py tests/test_workspace.py
git commit -m "feat(workspace): timestamped report run dirs + history listing"
```

### Task 5: Reuse index

**Files:**
- Modify: `core/workspace.py`
- Test: `tests/test_workspace.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rebuild_reuse_index_maps_page_methods_steps_and_selectors(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    pd = tmp_path / "RLRG"
    (pd / "pages" / "page_login.py").write_text(
        "class LoginPage:\n"
        "    def open(self): ...\n"
        "    def submit_credentials(self): ...\n"
        "    def _private(self): ...\n",
        encoding="utf-8",
    )
    (pd / "step_defs" / "login_steps.py").write_text(
        "def given_user_on_login(): ...\n", encoding="utf-8",
    )
    (pd / "mcp-selectors" / "locators.json").write_text(
        '{"login_button": "#login", "username": "#user"}', encoding="utf-8",
    )
    idx = workspace.rebuild_reuse_index("RLRG")
    assert idx["page_methods"]["open"] == "page_login.py"
    assert idx["page_methods"]["submit_credentials"] == "page_login.py"
    assert "_private" not in idx["page_methods"]
    assert idx["step_defs"]["given_user_on_login"] == "login_steps.py"
    assert idx["selectors"]["login_button"] == "locators.json"
    # Persisted to disk and reloadable.
    loaded = workspace.load_reuse_index("RLRG")
    assert loaded == idx


def test_load_reuse_index_default_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    idx = workspace.load_reuse_index("RLRG")
    assert idx == {"page_methods": {}, "step_defs": {}, "selectors": {}, "flows": {}}
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_workspace.py -q`
Expected: FAIL — missing `rebuild_reuse_index`.

- [ ] **Step 3: Add to `core/workspace.py`**

```python
_DEF_RE = re.compile(r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", re.MULTILINE)


def reuse_index_path(project: str) -> Path:
    return project_dir(project) / REUSE_INDEX_NAME


def _empty_reuse_index() -> dict:
    return {"page_methods": {}, "step_defs": {}, "selectors": {}, "flows": {}}


def load_reuse_index(project: str) -> dict:
    p = reuse_index_path(project)
    if not p.exists():
        return _empty_reuse_index()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        base = _empty_reuse_index()
        base.update({k: v for k, v in data.items() if k in base})
        return base
    except (OSError, json.JSONDecodeError):
        return _empty_reuse_index()


def rebuild_reuse_index(project: str) -> dict:
    """Scan pages/, step_defs/, mcp-selectors/ and write reuse_index.json.
    Best-effort and tolerant of parse errors. Existing files always win on
    first-seen so the index is stable across rebuilds."""
    pd = project_dir(project)
    index = _empty_reuse_index()

    pages = pd / "pages"
    if pages.exists():
        for f in sorted(pages.glob("page_*.py")):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for name in _DEF_RE.findall(text):
                if name.startswith("_") or name == "__init__":
                    continue
                index["page_methods"].setdefault(name, f.name)

    steps = pd / "step_defs"
    if steps.exists():
        for f in sorted(steps.glob("*_steps.py")):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for name in _DEF_RE.findall(text):
                if name.startswith("_"):
                    continue
                index["step_defs"].setdefault(name, f.name)

    sel = pd / "mcp-selectors"
    if sel.exists():
        for f in sorted(sel.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                for key in data:
                    index["selectors"].setdefault(str(key), f.name)

    reuse_index_path(project).write_text(
        json.dumps(index, indent=2, sort_keys=True), encoding="utf-8"
    )
    return index
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_workspace.py -q`
Expected: PASS (13 tests total).

- [ ] **Step 5: Commit**

```bash
git add core/workspace.py tests/test_workspace.py
git commit -m "feat(workspace): maintained reuse_index.json"
```

---

## Stage 2 — Strip old machinery from `agent_ui.py`

### Task 6: Remove the per-story / _shared / fork / migration functions

**Files:**
- Modify: `core/agent_ui.py`

Delete the following functions and their module-level helpers entirely (search by name; they were all part of the per-story-archive + `_shared` model that the new layout replaces):

- `_extract_app_id`, `_app_dir`, `_app_shared_dir`, `app_id_for_story_id`,
  `app_shared_has_work`, `promote_to_shared`, `_rebuild_flow_index`,
  `restore_from_shared`, `_is_app_folder`, `_migrate_legacy_folders`
- `find_similar_projects`, `_extract_flow_signals`, `_score_similarity`,
  `fork_project_into_workspace`, and the `_FLOW_KEYWORDS` constant
- `compute_story_id`, `_content_digest`, `_story_slug`, `_folder_name_for`
  (story-id-by-digest scheme — replaced by filename-based project routing)
- `archive_artifacts`, `restore_artifacts`, `_safe_copytree`,
  `_archive_user_data`, `_restore_user_data` (the flat-workspace↔archive copy cycle)
- The `_NON_APP_TOP_DIRS` constant and `PROJECTS_DIR` constant.

- [ ] **Step 1: Delete the functions/constants listed above.** Use Grep to find each definition and every call site. Leave call sites referenced by later tasks (they will be rewired in Stage 4); for now, comment out or delete call sites that are inside functions also being deleted.

Run (to find call sites before editing each): `grep -n "compute_story_id\|archive_artifacts\|restore_artifacts\|promote_to_shared\|fork_project_into_workspace\|find_similar_projects\|PROJECTS_DIR\|_migrate_legacy_folders" core/agent_ui.py`

- [ ] **Step 2: Verify the file still parses**

Run: `python -c "import ast,io; ast.parse(open('core/agent_ui.py',encoding='utf-8').read())"`
Expected: no output (parse OK). If `NameError`-prone call sites remain, they will be resolved in Stage 4 — but the file must still PARSE now.

- [ ] **Step 3: Commit**

```bash
git add core/agent_ui.py
git commit -m "refactor(agent): remove per-story archive, _shared, fork, migration machinery"
```

### Task 7: Replace module-level path constants with project-relative resolution

**Files:**
- Modify: `core/agent_ui.py:21-56` (the constants block) — see current lines `USER_STORY_PATH … ARTIFACT_DIRS`.

The old constants pointed every artifact dir into `core/` (`PROJECT_ROOT`). Replace them with helpers that resolve against the **current project** stored in session state.

- [ ] **Step 1: Add the workspace import and project-session helpers near the top of `agent_ui.py` (after `import streamlit as st`).**

```python
import workspace as ws

def current_project() -> str:
    """The active project name (from the most recent upload/paste), or ''."""
    return st.session_state.get("project", "")

def proj_path(*parts: str) -> Path:
    """Resolve a path inside the active project's folder."""
    return ws.project_dir(current_project()).joinpath(*parts)
```

- [ ] **Step 2: Replace the artifact-dir constants** (`FEATURES_DIR`, `PAGES_DIR`, `STEP_DEFS_DIR`, `TESTS_DIR`, `CONFTEST_PATH`, `LOCATORS_PATH`, `DISCOVERY_META_PATH`, `REPORTS_DIR`, `ALLURE_RESULTS`, `HTML_REPORT`, `SCREENSHOT_DIR`, `USER_STORY_PATH`, `USER_DATA_PATH`, `WORKSPACE_DIR`, `PROJECTS_DIR`, `GENERATION_LOG_PATH`) with calls to `proj_path(...)`/`ws.subdir(...)` at the point of use. Folder names change to singular: `feature`, `test`, `report`, `mcp-selectors`.

There is no single drop-in here — each former constant becomes a call. Use Grep to find every usage and replace it:

Run: `grep -n "FEATURES_DIR\|PAGES_DIR\|STEP_DEFS_DIR\|TESTS_DIR\|REPORTS_DIR\|ALLURE_RESULTS\|HTML_REPORT\|SCREENSHOT_DIR\|USER_STORY_PATH\|USER_DATA_PATH\|LOCATORS_PATH\|CONFTEST_PATH" core/agent_ui.py`

Replacement mapping (apply at each call site):

| Old | New |
|---|---|
| `FEATURES_DIR` | `proj_path("feature")` |
| `PAGES_DIR` | `proj_path("pages")` |
| `STEP_DEFS_DIR` | `proj_path("step_defs")` |
| `TESTS_DIR` | `proj_path("test")` |
| `REPORTS_DIR` | `proj_path("report")` |
| `LOCATORS_PATH` | `proj_path("mcp-selectors", "locators.json")` |
| `USER_STORY_PATH` | (replaced — see Stage 3; story now selected from `user_story/`) |
| `USER_DATA_PATH` | `proj_path("user_data.json")` |

- [ ] **Step 3: Verify parse + import**

Run: `python -c "import sys; sys.path.insert(0,'core'); import ast; ast.parse(open('core/agent_ui.py',encoding='utf-8').read()); print('parse ok')"`
Expected: `parse ok`.

- [ ] **Step 4: Commit**

```bash
git add core/agent_ui.py
git commit -m "refactor(agent): resolve artifact paths against active project folder"
```

---

## Stage 3 — Upload / paste / duplicate UI

### Task 8: Rewire the upload + paste handlers to derive the project and dedupe

**Files:**
- Modify: `core/agent_ui.py` — the sidebar story section (`render_sidebar`, currently around lines 3696-3740).

Replace the current upload handler (which wrote to a fixed `core/user_story.txt`) with project-aware handling.

- [ ] **Step 1: Replace the `st.file_uploader` block** so it derives the project from `uploaded.name`, rejects a missing prefix, and dedupes by filename:

```python
uploaded = st.file_uploader(
    "Upload .txt", type=["txt"], label_visibility="collapsed",
    key=f"upload_{st.session_state.get('upload_nonce', 0)}",
)
if uploaded is not None:
    raw = uploaded.read().decode("utf-8")
    content = normalize_story_text(raw)
    try:
        project = ws.derive_project_name(uploaded.name)
    except ws.ProjectNameError as exc:
        st.error(str(exc))
    else:
        filename = ws.sanitize_filename(uploaded.name)
        if ws.story_exists(project, filename):
            st.error("same user story exists. Proceed to execute the test")
            st.session_state.project = project
            st.session_state.active_story = filename
        else:
            ws.add_story(project, filename, content)
            ws.write_pytest_ini(project, ws.extract_base_url(content))
            st.session_state.project = project
            st.session_state.active_story = filename
            st.session_state.log = []
            st.session_state.last_run = "never"
            st.session_state.last_upload_info = (
                f"**{uploaded.name}** → project `{project}` · {len(raw)} chars"
            )
            st.session_state.upload_nonce = st.session_state.get("upload_nonce", 0) + 1
            st.rerun()
```

- [ ] **Step 2: Replace the paste textarea block** with a project-name field + story-filename field + save button:

```python
st.markdown('<div class="section-heading">Or paste a story</div>', unsafe_allow_html=True)
paste_project = st.text_input("Project name", key="paste_project",
                              placeholder="e.g. RLRG")
paste_filename = st.text_input("Story file name (.txt)", key="paste_filename",
                               placeholder="e.g. RLRG_login.txt")
paste_body = st.text_area("Story content", key="paste_body", height=180,
                          placeholder="Paste your user story here.")
if st.button("Save story", disabled=not (paste_project.strip()
                                         and paste_filename.strip()
                                         and paste_body.strip())):
    project = re.sub(r"[^A-Za-z0-9]+", "", paste_project.strip())
    if not project:
        st.error("Project name must contain letters or digits.")
    else:
        filename = ws.sanitize_filename(paste_filename)
        content = normalize_story_text(paste_body)
        if ws.story_exists(project, filename):
            st.error("same user story exists. Proceed to execute the test")
            st.session_state.project = project
            st.session_state.active_story = filename
        else:
            ws.add_story(project, filename, content)
            ws.write_pytest_ini(project, ws.extract_base_url(content))
            st.session_state.project = project
            st.session_state.active_story = filename
            st.rerun()
```

- [ ] **Step 3: Add a project/story selector** so the user can switch between existing stories in a project. Place it above the upload widget:

```python
projects = ws.list_projects()
if projects:
    sel_proj = st.selectbox("Project", projects,
                            index=(projects.index(current_project())
                                   if current_project() in projects else 0))
    st.session_state.project = sel_proj
    stories = ws.list_stories(sel_proj)
    if stories:
        names = [p.name for p in stories]
        sel_story = st.selectbox(
            "Story", names,
            index=(names.index(st.session_state.get("active_story"))
                   if st.session_state.get("active_story") in names else 0))
        st.session_state.active_story = sel_story
```

- [ ] **Step 4: Manual verification**

Run: `cd core && python -m streamlit run agent_ui.py` (open the local URL).
Verify:
- Uploading `login.txt` (no prefix) shows the rejection error and creates nothing.
- Uploading `RLRG_login.txt` creates `workspace/RLRG/user_story/RLRG_login.txt` and the six sibling folders + `pytest.ini`.
- Uploading the same `RLRG_login.txt` again shows *"same user story exists. Proceed to execute the test"* and does not overwrite.
- Pasting with project `RLRG` + filename `RLRG_search.txt` adds a second story under the same `RLRG` project (no new project folder).

Confirm on disk:
Run: `find workspace -maxdepth 3 -type d | sort`
Expected: `workspace/RLRG`, `workspace/RLRG/user_story`, `feature`, `pages`, `step_defs`, `test`, `mcp-selectors`, `report`.

- [ ] **Step 5: Commit**

```bash
git add core/agent_ui.py
git commit -m "feat(agent): filename-derived project, paste fields, duplicate detection"
```

---

## Stage 4 — Generation into the project folder

### Task 9: Run the agent subprocess with cwd = project dir; remove archive/fork/demo-stash

**Files:**
- Modify: `core/agent_ui.py` — `claude_command` callers, `stream_command` (around 2588-2680), the scout subprocess (around 2856-2870), `run_multi_agent_framework` (around 3012), and the `gen_clicked` / `fw_clicked` handlers (around 4505-4766).

- [ ] **Step 1: Make `stream_command` and the scout/framework subprocesses run in the project dir.** Change `cwd=str(PROJECT_ROOT)` to the active project dir. Add a `cwd` parameter to `stream_command` (default to the active project):

In `stream_command` (definition around line 2588): add `cwd: Path | None = None` to the signature and use:
```python
proc_cwd = str(cwd or ws.project_dir(current_project()))
process = subprocess.Popen(
    cmd,
    cwd=proc_cwd,
    ...
)
```
Do the same for the scout `subprocess.Popen` (around line 2859) and any other `cwd=str(PROJECT_ROOT)` in the generation paths.

Run: `grep -n "cwd=str(PROJECT_ROOT)" core/agent_ui.py`
Expected: replace each generation-related occurrence with the project dir.

- [ ] **Step 2: Simplify the `gen_clicked` (Gherkin) handler.** Remove the demo-stash branch (`_has_demo_stash`/`_replay_stash`/`_fake_claude_stream`), the fork-mode branch, and the archive/restore calls. The new handler writes the active story into the gherkin prompt context and runs the agent in the project dir. Replace the whole `if gen_clicked:` block with:

```python
if gen_clicked:
    log_event("Step ① clicked — Generate Gherkin")
    project = current_project()
    ws.ensure_project_dirs(project)
    story_file = st.session_state.get("active_story", "")
    append_process_log(project, f"Generate Gherkin clicked for {story_file}")
    with st.status("Generating Gherkin…", expanded=False) as status:
        prompt = GHERKIN_PROMPT.replace("{{STORY_FILE}}", story_file)
        rc = stream_command(
            claude_command(prompt, GHERKIN_TOOLS),
            log_placeholder, st.session_state.log, story_id=project,
        )
        n = len(list(proj_path("feature").glob("*.feature")))
        status.update(label=f"Gherkin ready — {n} file(s)",
                      state="complete" if rc == 0 else "error")
    st.session_state.gherkin_done = True
    st.session_state.last_run = _dt.datetime.now().strftime("%H:%M:%S")
    st.rerun()
```

- [ ] **Step 3: Simplify the `fw_clicked` (Framework) handler.** Remove demo-stash, archive, and `promote_to_shared`. Choose the delta prompt automatically when the project already has framework components. Replace the whole `if fw_clicked:` block with:

```python
if fw_clicked:
    log_event("Step ② clicked — Generate Test Framework")
    project = current_project()
    ws.ensure_project_dirs(project)
    append_process_log(project, "Generate Test Framework clicked")
    has_framework = (
        any(proj_path("pages").glob("page_*.py"))
        or any(proj_path("step_defs").glob("*_steps.py"))
    )
    story_file = st.session_state.get("active_story", "")
    reuse_idx = ws.load_reuse_index(project)
    prompt_base = FRAMEWORK_DELTA_PROMPT if has_framework else FRAMEWORK_PROMPT
    prompt = (prompt_base
              .replace("{{STORY_FILE}}", story_file)
              .replace("{{REUSE_INDEX}}", json.dumps(reuse_idx, indent=2)))
    with st.status("Generating test framework (POMs, step defs, tests)…",
                   expanded=False) as status:
        rc = stream_command(
            claude_command(prompt, BUILD_TOOLS),
            log_placeholder, st.session_state.log,
            story_id=project, heartbeat_secs=10,
        )
        registered = sync_pytest_plugins()
        append_process_log(project, "pytest_plugins: "
                           + (", ".join(registered) if registered else "(none)"))
        ok, errs = syntax_check_generated()
        ws.rebuild_reuse_index(project)   # refresh reuse map after generation
        n_tests = len(list(proj_path("test").glob("test_*.py")))
        status.update(label=f"Framework ready — {n_tests} test(s)",
                      state="complete" if (rc == 0 and ok) else "error")
        for e in errs[:5]:
            st.warning(f"Syntax: {e}")
    st.session_state.framework_done = True
    st.session_state.last_run = _dt.datetime.now().strftime("%H:%M:%S")
    st.rerun()
```

- [ ] **Step 4: Fix `sync_pytest_plugins`, `syntax_check_generated`, `reset_pytest_plugins`, `reset_locators`, and `clean_artifacts`** to use `proj_path(...)` instead of the old `PROJECT_ROOT`-based constants (Grep for each; they currently glob `PAGES_DIR`/`STEP_DEFS_DIR`/`TESTS_DIR`). `clean_artifacts` must operate inside the project's `feature`/`pages`/`step_defs`/`test` folders and must **never** delete user_story files.

Run: `grep -n "def sync_pytest_plugins\|def syntax_check_generated\|def reset_pytest_plugins\|def reset_locators\|def clean_artifacts" core/agent_ui.py`

- [ ] **Step 5: Verify parse**

Run: `python -c "import ast; ast.parse(open('core/agent_ui.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add core/agent_ui.py
git commit -m "feat(agent): generate directly into project dir; delta prompt auto-select; reuse index refresh"
```

### Task 10: Point the pytest run at a timestamped report dir inside the project

**Files:**
- Modify: `core/agent_ui.py` — `pytest_headed_cmd` / `PYTEST_HEADED_CMD_BASE` (lines 86-101) and the run handler (the `if pytest_target:` block around 4768+).

- [ ] **Step 1: Make the pytest command build report paths per run.** Replace `PYTEST_HEADED_CMD_BASE` and `pytest_headed_cmd` with:

```python
def pytest_headed_cmd(project: str, run_dir: Path, target: str | None = None) -> list[str]:
    """Build the pytest --headed command writing HTML+Allure into run_dir.
    target is relative to the project dir (e.g. 'test/test_login.py')."""
    cmd = [
        sys.executable, "-m", "pytest", "-v", "--headed",
        f"--html={run_dir / 'report.html'}",
        "--self-contained-html",
        f"--alluredir={run_dir / 'allure-results'}",
    ]
    if target:
        cmd.append(target)
    else:
        cmd.append("test")
    return cmd
```

- [ ] **Step 2: In the `if pytest_target:` run handler**, create a fresh run dir and run pytest with `cwd` = the project dir. Remove the `restore_artifacts(story_id)` call (no archive anymore). Core of the replacement:

```python
project = current_project()
run_dir = ws.new_report_run_dir(project)
target = None if pytest_target == "all" else pytest_target
sync_pytest_plugins()
cmd = pytest_headed_cmd(project, run_dir, target)
rc = stream_command(cmd, log_placeholder, st.session_state.log,
                    story_id=project, cwd=ws.project_dir(project))
st.session_state["last_report_dir"] = str(run_dir)
```

- [ ] **Step 3: Manual verification** (needs a project with a generated framework — use a real story end-to-end, or hand-place a trivial passing pytest-bdd test under `workspace/<project>/test/`).

Run the app, click Run, then:
Run: `find "workspace" -path "*/report/*" -name report.html | sort`
Expected: a `report.html` under `workspace/<project>/report/<timestamp>/`.

- [ ] **Step 4: Commit**

```bash
git add core/agent_ui.py
git commit -m "feat(agent): timestamped per-run report dirs; pytest runs in project dir"
```

---

## Stage 5 — Report viewing (current run + per-test history)

### Task 11: Show the current run's report and per-test history

**Files:**
- Modify: `core/agent_ui.py` — `render_test_results` (around 3464) and `render_test_runner` (around 3374), plus the report-display section (around 3651-3690).

Desired behavior (from spec §Reports): after a run, show the report for the test(s) just run; for each such test surface prior runs; when a group runs, show fresh results where run and historical where not.

- [ ] **Step 1: Add a history helper near the report renderers** that returns, per test file, its latest run dir and the list of all run dirs that contain a result for it:

```python
def _runs_with_report(project: str) -> list[Path]:
    """Report run dirs that actually produced a report.html, newest first."""
    return [d for d in ws.report_runs(project) if (d / "report.html").exists()]
```

- [ ] **Step 2: Update the report display** to: (a) default to `st.session_state.get("last_report_dir")` if set, else the newest run; (b) render an expander per historical run (newest first) with its `report.html` embedded and a download button; (c) label the run the user just triggered as "Current run".

```python
project = current_project()
runs = _runs_with_report(project)
current = st.session_state.get("last_report_dir")
if not runs:
    st.markdown('<div class="empty-state">No test runs yet.</div>', unsafe_allow_html=True)
else:
    for i, run in enumerate(runs):
        is_current = (str(run) == current)
        label = f"{'▶ Current run · ' if is_current else ''}{run.name}"
        with st.expander(label, expanded=is_current or i == 0):
            html = (run / "report.html").read_text(encoding="utf-8", errors="replace")
            st.components.v1.html(html, height=600, scrolling=True)
            st.download_button("Download report.html", html,
                               file_name=f"{project}_{run.name}.html",
                               mime="text/html", key=f"dl_{run.name}")
```

(`import streamlit.components.v1` is bundled with Streamlit; reference `st.components.v1.html`.)

- [ ] **Step 3: Manual verification** — run tests twice; confirm two run expanders appear, newest/current first, each with its own embedded report; confirm the current run is marked.

- [ ] **Step 4: Commit**

```bash
git add core/agent_ui.py
git commit -m "feat(agent): report viewer shows current run + per-test history"
```

---

## Stage 6 — Prompt edits

### Task 12: gherkin_prompt — read the target story, write a unique feature, never delete

**Files:**
- Modify: `core/prompts/gherkin_prompt.md`

- [ ] **Step 1: Apply these concrete edits.**

Line 1 — change the source from `user_story.txt` to the injected story file:
> Replace: `Read user_story.txt and convert each user story it contains into a Gherkin .feature file under /features.`
> With: `Read the user story file `user_story/{{STORY_FILE}}` (relative to the current working directory) and convert it into Gherkin `.feature` file(s) under `feature/`.`

Replace the "Hard rules" bullets at lines 70-77 with create-only rules:
> - Write feature file(s) into `feature/`. Name each file after the FEATURE under test (a short snake_case slug of the feature), e.g. `feature/login_validation.feature`.
> - **NEVER delete or overwrite an existing `.feature` file.** If a file with your chosen name already exists, append a short disambiguating suffix so the new file is unique.
> - One `.feature` file may contain multiple `Scenario` / `Scenario Outline` blocks. Cover positive, negative, and boundary cases that the story implies.
> - For Scenario Outlines, every Examples row must end with an assertable expected outcome. Negative rows assert the EXACT error string.
> - After writing, list every file you created with one-line summaries.

Update §"ALSO read user_data.json" (line 14): change `user_data.json if it exists in the cwd` to `the test-data JSON file referenced by the story (if any) under the project folder`.

- [ ] **Step 2: Verify the `{{STORY_FILE}}` token is present** (it is injected by Task 9 Step 2).

Run: `grep -n "{{STORY_FILE}}" core/prompts/gherkin_prompt.md`
Expected: at least one match.

- [ ] **Step 3: Commit**

```bash
git add core/prompts/gherkin_prompt.md
git commit -m "docs(prompt): gherkin reads target story, writes unique feature, create-only"
```

### Task 13: framework_prompt + framework_delta_prompt — singular folders, reuse index, no duplication

**Files:**
- Modify: `core/prompts/framework_prompt.md`, `core/prompts/framework_delta_prompt.md`

- [ ] **Step 1: In both files, rename folder references** to the new singular names. Apply globally:
  - `features/` → `feature/`
  - `tests/` → `test/`
  - `reports/` → `report/`
  - (`pages/`, `step_defs/`, `mcp-selectors/` are unchanged.)

Run (to find them): `grep -n "features/\|tests/\|reports/" core/prompts/framework_prompt.md core/prompts/framework_delta_prompt.md`

- [ ] **Step 2: In `framework_prompt.md`,** add an explicit instruction near the top:
> You are operating with the current working directory set to a single project folder. Read every `.feature` file in `feature/`. Build the framework into `pages/` (Page Object Model + a `base_page.py`), `step_defs/`, and `test/`. Generate a `conftest.py` (fixtures for browser setup/teardown, base_url, test_data, screenshot capture) the FIRST time only — if `conftest.py` already exists, extend it rather than overwriting.

- [ ] **Step 3: In `framework_delta_prompt.md`,** add a reuse-first instruction near the top:
> A `reuse_index.json` of the project's existing page-object methods, step definitions, and selectors is provided below. Reuse what already exists — extend existing POMs and add only NEW step defs / page methods / tests for the new feature. **Do NOT** regenerate `base_page.py`, `conftest.py`, fixtures, or duplicate any method already listed in the index.
>
> ```json
> {{REUSE_INDEX}}
> ```
>
> Read the new feature file(s) in `feature/` that do not yet have a matching `test/test_*.py`, and build only those.

- [ ] **Step 4: Commit**

```bash
git add core/prompts/framework_prompt.md core/prompts/framework_delta_prompt.md
git commit -m "docs(prompt): framework prompts use singular folders, reuse index, no duplicate components"
```

### Task 14: scout + synthesis + auditor prompts — folder names + create-only selectors

**Files:**
- Modify: `core/prompts/scout_sitemap_prompt.md`, `scout_inventory_prompt.md`, `scout_flow_prompt.md`, `scout_edge_prompt.md`, `synthesis_prompt.md`, `auditor_prompt.md`

- [ ] **Step 1: Rename folder references** in all six files: `features/`→`feature/`, `tests/`→`test/`, `reports/`→`report/`. The scouts and synthesis write to `mcp-selectors/` (unchanged) — add to each: "Create `mcp-selectors/` if it does not exist; **append** your JSON, never delete existing selector files."

Run: `grep -rn "features/\|tests/\|reports/" core/prompts/`
Expected after edits: no matches (all renamed).

- [ ] **Step 2: In `auditor_prompt.md`,** change report output references to write under the current run's `report/` (it runs with cwd = project dir; the run dir path is provided by the runner). Ensure it reads `report.html` from the run dir, not a fixed `reports/report.html`.

- [ ] **Step 3: Commit**

```bash
git add core/prompts/
git commit -m "docs(prompt): scouts/synthesis/auditor use singular folders + append-only selectors"
```

---

## Stage 7 — Final wiring + verification

### Task 15: Repair remaining call sites + counts/state helpers

**Files:**
- Modify: `core/agent_ui.py` — `story_folder_state`, `story_feature_count`, `story_test_count`, `discover_tests`, `flat_has_features`, `flat_has_framework`, `render_feature_files`, `render_framework_files`, `write_story_readme`, `append_process_log`, and `render_suites_panel`.

- [ ] **Step 1: Rewire each helper** to take/derive the active project and use `proj_path(...)`. `story_folder_state(project)` checks `feature/` + `step_defs/` + `test/` in the project. `discover_tests(project)` globs `proj_path("test").glob("test_*.py")`. `append_process_log(project, msg)` writes to `proj_path("process_log.txt")`.

Run: `grep -n "story_folder_state\|story_feature_count\|story_test_count\|discover_tests\|flat_has_features\|flat_has_framework\|write_story_readme\|append_process_log\|render_suites_panel" core/agent_ui.py`

- [ ] **Step 2: Remove or rewire `render_suites_panel`** — the `_suite_runs` concept belonged to the old archive layout. Either delete it or repoint it at `report/` run dirs. Default: delete it and its call site.

- [ ] **Step 3: Full parse + import smoke test**

Run: `python -c "import sys; sys.path.insert(0,'core'); import ast; ast.parse(open('core/agent_ui.py',encoding='utf-8').read()); import workspace; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Run the unit suite**

Run: `python -m pytest tests/test_workspace.py -q`
Expected: PASS (13 tests).

- [ ] **Step 5: Commit**

```bash
git add core/agent_ui.py
git commit -m "refactor(agent): rewire counts/state/render helpers to active project"
```

### Task 16: End-to-end manual verification

- [ ] **Step 1: Launch** `cd core && python -m streamlit run agent_ui.py`.

- [ ] **Step 2: Verify the full flow** on a real saucedemo-style story file named `saucedemo_login.txt`:
  1. Upload → project `saucedemo` created with all 7 subfolders + `pytest.ini`.
  2. ① Generate Gherkin → a uniquely-named file appears in `feature/`; no file deleted.
  3. ② Generate Framework → `pages/`, `step_defs/`, `test/`, `conftest.py` populated; `reuse_index.json` written.
  4. Upload a SECOND story `saucedemo_cart.txt` → same project, second story file added, first untouched.
  5. ② again → delta prompt used; `base_page.py`/`conftest.py` NOT duplicated; only new feature's artifacts added.
  6. ③ Run → `report/<timestamp>/report.html` created; report viewer shows current run + history.
  7. Re-upload `saucedemo_login.txt` → "same user story exists. Proceed to execute the test"; nothing regenerated.

- [ ] **Step 3: Confirm `core/` stayed pure**

Run: `git status --porcelain core` and `ls core`
Expected: no `feature`/`test`/`report`/`pytest.ini`/`user_story.txt` created under `core/` during the run.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: verify project-scoped workspace flow end-to-end"
```

---

## Self-review notes

- **Spec coverage:** project identity (Tasks 1, 8), reject no-prefix (Task 1/8), flat layout + singular names (Tasks 2, 7, 12-14), core purity (Task 0, verified Task 16), duplicate-by-filename (Tasks 2, 8), direct generation with cwd=project (Task 9), reports timestamped + history viewer (Tasks 4, 10, 11), reuse without `_shared` via `reuse_index.json` + delta prompt (Tasks 5, 9, 13), prompt edits (Tasks 12-14), removal of old machinery (Task 6, 9, 15). All spec sections map to tasks.
- **Token tokens `{{STORY_FILE}}` / `{{REUSE_INDEX}}`** are defined as injection points in Task 9 and consumed in Tasks 12-13 — consistent.
- **Known risk:** `agent_ui.py` is large and tightly coupled; Stage 2 removals will surface call sites that Stage 4/7 fix. After every task, the parse check must pass before moving on. Prefer subagent-driven execution with a review between tasks.

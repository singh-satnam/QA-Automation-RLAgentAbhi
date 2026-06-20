# Staging Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route all generated files through `temp_workspace/` (staging) before the user promotes them to `workspace/` via a UI confirmation dialog.

**Architecture:** Extend `workspace.py` with a `staging=False` parameter on every path-resolving function, backed by a new `TEMP_WORKSPACE_DIR` constant. In `agent_ui.py`, the single `proj_path()` helper reads `st.session_state.staging_active` and passes it through, so all ~30 existing call sites resolve to the correct root without individual changes. A post-test-run promotion dialog handles the additive merge.

**Tech Stack:** Python 3.14, Streamlit, pytest, shutil

## Global Constraints

- `core/` contains only agent logic and prompt files — never generated test artifacts.
- `workspace/<Project>/` folder structure (`user_story/`, `feature/`, `step_defs/`, `pages/`, `test/`, `mcp-selectors/`, `report/`) is unchanged.
- `temp_workspace/<Project>/` mirrors the same structure exactly.
- Additive merge on promotion: never overwrite an existing file in `workspace/`.
- `temp_workspace/` is gitignored.

---

### Task 1: Add staging support to `workspace.py`

**Files:**
- Modify: `core/workspace.py:1-249`
- Test: `tests/test_workspace.py`

**Interfaces:**
- Consumes: nothing new (extends existing module)
- Produces:
  - `TEMP_WORKSPACE_DIR: Path` — constant pointing to `<repo>/temp_workspace/`
  - `project_dir(project: str, staging: bool = False) -> Path`
  - `subdir(project: str, name: str, staging: bool = False) -> Path`
  - `ensure_project_dirs(project: str, staging: bool = False) -> Path`
  - `copy_scaffolding(project: str, staging: bool = False) -> list[str]`
  - `add_story(project: str, filename: str, content: str, staging: bool = False) -> tuple[bool, Path]`
  - `story_exists(project: str, filename: str, staging: bool = False) -> bool`
  - `write_pytest_ini(project: str, base_url: str, staging: bool = False) -> Path`
  - `rebuild_reuse_index(project: str, staging: bool = False) -> dict`
  - `load_reuse_index(project: str, staging: bool = False) -> dict`
  - `new_report_run_dir(project: str, run_id: str | None = None, staging: bool = False) -> Path`
  - `report_runs(project: str, staging: bool = False) -> list[Path]`
  - `reuse_index_path(project: str, staging: bool = False) -> Path`
  - `is_staged(project: str) -> bool`
  - `promote_to_workspace(project: str) -> dict` — returns `{"copied": list[str], "skipped": list[str]}`
  - `discard_staging(project: str) -> None`
  - `list_staged_projects() -> list[str]`
  - `staging_file_summary(project: str) -> dict[str, int]` — returns `{"feature": 3, "pages": 2, ...}`

- [ ] **Step 1: Write failing tests for the staging parameter on existing functions**

Add to `tests/test_workspace.py`:

```python
def test_project_dir_staging_resolves_to_temp_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    assert workspace.project_dir("RLRG") == tmp_path / "workspace" / "RLRG"
    assert workspace.project_dir("RLRG", staging=True) == tmp_path / "temp_workspace" / "RLRG"


def test_ensure_project_dirs_staging_creates_in_temp(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    pd = workspace.ensure_project_dirs("RLRG", staging=True)
    assert pd == tmp_path / "temp_workspace" / "RLRG"
    for sub in workspace.PROJECT_SUBDIRS:
        assert (pd / sub).is_dir()
    assert not (tmp_path / "workspace" / "RLRG").exists()


def test_add_story_staging_writes_to_temp(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    created, path = workspace.add_story("RLRG", "RLRG_login.txt", "story body", staging=True)
    assert created is True
    assert "temp_workspace" in str(path)
    assert path.read_text(encoding="utf-8") == "story body"
    assert not (tmp_path / "workspace" / "RLRG" / "user_story" / "RLRG_login.txt").exists()


def test_story_exists_staging_checks_temp(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    workspace.add_story("RLRG", "RLRG_login.txt", "body", staging=True)
    assert workspace.story_exists("RLRG", "RLRG_login.txt", staging=True) is True
    assert workspace.story_exists("RLRG", "RLRG_login.txt", staging=False) is False


def test_copy_scaffolding_staging(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    written = workspace.copy_scaffolding("RLRG", staging=True)
    assert len(written) > 0
    assert (tmp_path / "temp_workspace" / "RLRG" / "conftest.py").exists()
    assert not (tmp_path / "workspace" / "RLRG" / "conftest.py").exists()


def test_write_pytest_ini_staging(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    workspace.ensure_project_dirs("RLRG", staging=True)
    ini = workspace.write_pytest_ini("RLRG", "https://example.com", staging=True)
    assert "temp_workspace" in str(ini)
    assert ini.exists()
    assert "base_url = https://example.com" in ini.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_workspace.py -v -k "staging"`
Expected: FAIL — `project_dir()` does not accept `staging` parameter

- [ ] **Step 3: Add `TEMP_WORKSPACE_DIR` constant and `staging` parameter to path functions**

In `core/workspace.py`, add the constant after `WORKSPACE_DIR` (line 11):

```python
TEMP_WORKSPACE_DIR = Path(os.environ.get("QA_TEMP_WORKSPACE_DIR", PROJECT_ROOT.parent / "temp_workspace"))
```

Update `project_dir`:

```python
def project_dir(project: str, staging: bool = False) -> Path:
    root = TEMP_WORKSPACE_DIR if staging else WORKSPACE_DIR
    return root / project
```

Update `subdir`:

```python
def subdir(project: str, name: str, staging: bool = False) -> Path:
    return project_dir(project, staging=staging) / name
```

Update `ensure_project_dirs`:

```python
def ensure_project_dirs(project: str, staging: bool = False) -> Path:
    pd = project_dir(project, staging=staging)
    for sub in PROJECT_SUBDIRS:
        (pd / sub).mkdir(parents=True, exist_ok=True)
    return pd
```

Update `copy_scaffolding` — add `staging: bool = False` parameter, replace internal `ensure_project_dirs(project)` and `project_dir(project)` calls to pass `staging`:

```python
def copy_scaffolding(project: str, staging: bool = False) -> list[str]:
    ensure_project_dirs(project, staging=staging)
    pd = project_dir(project, staging=staging)
    written: list[str] = []
    mapping = {
        TEMPLATES_DIR / "conftest.py": pd / "conftest.py",
        TEMPLATES_DIR / "base_page.py": pd / "pages" / "base_page.py",
    }
    for src, dst in mapping.items():
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            written.append(str(dst.relative_to(pd)).replace("\\", "/"))
    for pkg in ("pages", "step_defs"):
        init = pd / pkg / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
    return written
```

Update `story_exists`:

```python
def story_exists(project: str, filename: str, staging: bool = False) -> bool:
    return (subdir(project, "user_story", staging=staging) / filename).exists()
```

Update `add_story`:

```python
def add_story(project: str, filename: str, content: str, staging: bool = False) -> tuple[bool, Path]:
    ensure_project_dirs(project, staging=staging)
    path = subdir(project, "user_story", staging=staging) / filename
    if path.exists():
        return False, path
    path.write_text(content, encoding="utf-8")
    return True, path
```

Update `write_pytest_ini`:

```python
def write_pytest_ini(project: str, base_url: str, staging: bool = False) -> Path:
    ini = project_dir(project, staging=staging) / "pytest.ini"
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

Update `reuse_index_path`:

```python
def reuse_index_path(project: str, staging: bool = False) -> Path:
    return project_dir(project, staging=staging) / REUSE_INDEX_NAME
```

Update `load_reuse_index`:

```python
def load_reuse_index(project: str, staging: bool = False) -> dict:
    p = reuse_index_path(project, staging=staging)
    if not p.exists():
        return _empty_reuse_index()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        base = _empty_reuse_index()
        base.update({k: v for k, v in data.items() if k in base})
        return base
    except (OSError, json.JSONDecodeError):
        return _empty_reuse_index()
```

Update `rebuild_reuse_index`:

```python
def rebuild_reuse_index(project: str, staging: bool = False) -> dict:
    pd = project_dir(project, staging=staging)
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

    reuse_index_path(project, staging=staging).write_text(
        json.dumps(index, indent=2, sort_keys=True), encoding="utf-8"
    )
    return index
```

Update `new_report_run_dir`:

```python
def new_report_run_dir(project: str, run_id: str | None = None, staging: bool = False) -> Path:
    stamp = run_id or _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    d = subdir(project, "report", staging=staging) / stamp
    d.mkdir(parents=True, exist_ok=True)
    return d
```

Update `report_runs`:

```python
def report_runs(project: str, staging: bool = False) -> list[Path]:
    rep = subdir(project, "report", staging=staging)
    if not rep.exists():
        return []
    return sorted((d for d in rep.iterdir() if d.is_dir()),
                  key=lambda p: p.name, reverse=True)
```

- [ ] **Step 4: Run tests to verify staging parameter tests pass**

Run: `python -m pytest tests/test_workspace.py -v -k "staging"`
Expected: All 6 staging tests PASS

- [ ] **Step 5: Run ALL existing tests to verify no regressions**

Run: `python -m pytest tests/test_workspace.py -v`
Expected: ALL tests PASS (existing + new)

- [ ] **Step 6: Commit**

```bash
git add core/workspace.py tests/test_workspace.py
git commit -m "feat(workspace): add staging parameter to all path functions for temp_workspace support"
```

---

### Task 2: Add new staging-specific functions to `workspace.py`

**Files:**
- Modify: `core/workspace.py` (append new functions)
- Test: `tests/test_workspace.py`

**Interfaces:**
- Consumes: `project_dir(project, staging=True)`, `TEMP_WORKSPACE_DIR`, `WORKSPACE_DIR`, `PROJECT_SUBDIRS`, `ensure_project_dirs()`
- Produces:
  - `is_staged(project: str) -> bool`
  - `promote_to_workspace(project: str) -> dict` — `{"copied": list[str], "skipped": list[str]}`
  - `discard_staging(project: str) -> None`
  - `list_staged_projects() -> list[str]`
  - `staging_file_summary(project: str) -> dict[str, int]`

- [ ] **Step 1: Write failing tests for new staging functions**

Add to `tests/test_workspace.py`:

```python
def test_is_staged_detects_temp_workspace_content(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    assert workspace.is_staged("RLRG") is False
    workspace.add_story("RLRG", "RLRG_login.txt", "body", staging=True)
    assert workspace.is_staged("RLRG") is True


def test_is_staged_false_for_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    (tmp_path / "temp_workspace" / "RLRG").mkdir(parents=True)
    assert workspace.is_staged("RLRG") is False


def test_promote_to_workspace_additive_merge(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    # Create a file in workspace that already exists
    workspace.ensure_project_dirs("RLRG", staging=False)
    (tmp_path / "workspace" / "RLRG" / "pages" / "page_login.py").write_text("existing", encoding="utf-8")
    # Create staging files — one overlapping, one new
    workspace.ensure_project_dirs("RLRG", staging=True)
    (tmp_path / "temp_workspace" / "RLRG" / "pages" / "page_login.py").write_text("staged", encoding="utf-8")
    (tmp_path / "temp_workspace" / "RLRG" / "pages" / "page_dashboard.py").write_text("new", encoding="utf-8")
    (tmp_path / "temp_workspace" / "RLRG" / "feature" / "login.feature").write_text("Feature: login", encoding="utf-8")
    result = workspace.promote_to_workspace("RLRG")
    # page_login.py was skipped (already exists), page_dashboard.py and login.feature were copied
    assert "pages/page_dashboard.py" in result["copied"]
    assert "feature/login.feature" in result["copied"]
    assert "pages/page_login.py" in result["skipped"]
    # Workspace file was NOT overwritten
    assert (tmp_path / "workspace" / "RLRG" / "pages" / "page_login.py").read_text(encoding="utf-8") == "existing"
    # New file was copied
    assert (tmp_path / "workspace" / "RLRG" / "pages" / "page_dashboard.py").read_text(encoding="utf-8") == "new"
    # Staging folder is gone
    assert not (tmp_path / "temp_workspace" / "RLRG").exists()


def test_promote_creates_workspace_dirs_if_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    workspace.ensure_project_dirs("RLRG", staging=True)
    (tmp_path / "temp_workspace" / "RLRG" / "feature" / "login.feature").write_text("Feature: login", encoding="utf-8")
    result = workspace.promote_to_workspace("RLRG")
    assert "feature/login.feature" in result["copied"]
    assert (tmp_path / "workspace" / "RLRG" / "feature" / "login.feature").exists()


def test_discard_staging_removes_temp_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    workspace.add_story("RLRG", "RLRG_login.txt", "body", staging=True)
    assert workspace.is_staged("RLRG") is True
    workspace.discard_staging("RLRG")
    assert workspace.is_staged("RLRG") is False
    assert not (tmp_path / "temp_workspace" / "RLRG").exists()


def test_list_staged_projects(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    workspace.add_story("RLRG", "RLRG_a.txt", "a", staging=True)
    workspace.add_story("saucedemo", "saucedemo_x.txt", "x", staging=True)
    assert workspace.list_staged_projects() == ["RLRG", "saucedemo"]


def test_staging_file_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    workspace.ensure_project_dirs("RLRG", staging=True)
    pd = tmp_path / "temp_workspace" / "RLRG"
    (pd / "feature" / "login.feature").write_text("Feature: login", encoding="utf-8")
    (pd / "feature" / "signup.feature").write_text("Feature: signup", encoding="utf-8")
    (pd / "pages" / "page_login.py").write_text("class LoginPage: ...", encoding="utf-8")
    summary = workspace.staging_file_summary("RLRG")
    assert summary["feature"] == 2
    assert summary["pages"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_workspace.py -v -k "is_staged or promote or discard or list_staged or staging_file"`
Expected: FAIL — functions not defined

- [ ] **Step 3: Implement the new functions**

Append to `core/workspace.py`:

```python
def is_staged(project: str) -> bool:
    pd = project_dir(project, staging=True)
    if not pd.exists():
        return False
    return any(pd.rglob("*"))


def promote_to_workspace(project: str) -> dict:
    staging_pd = project_dir(project, staging=True)
    workspace_pd = project_dir(project, staging=False)
    result: dict[str, list[str]] = {"copied": [], "skipped": []}
    if not staging_pd.exists():
        return result
    ensure_project_dirs(project, staging=False)
    for src_file in sorted(staging_pd.rglob("*")):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(staging_pd)
        dst_file = workspace_pd / rel
        rel_str = str(rel).replace("\\", "/")
        if dst_file.exists():
            result["skipped"].append(rel_str)
        else:
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            result["copied"].append(rel_str)
    shutil.rmtree(staging_pd)
    return result


def discard_staging(project: str) -> None:
    pd = project_dir(project, staging=True)
    if pd.exists():
        shutil.rmtree(pd)


def list_staged_projects() -> list[str]:
    if not TEMP_WORKSPACE_DIR.exists():
        return []
    return sorted(
        p.name for p in TEMP_WORKSPACE_DIR.iterdir()
        if p.is_dir() and not p.name.startswith((".", "_"))
    )


def staging_file_summary(project: str) -> dict[str, int]:
    pd = project_dir(project, staging=True)
    summary: dict[str, int] = {}
    if not pd.exists():
        return summary
    for sub in PROJECT_SUBDIRS:
        d = pd / sub
        if d.exists():
            count = sum(1 for f in d.iterdir() if f.is_file())
            if count > 0:
                summary[sub] = count
    return summary
```

- [ ] **Step 4: Run tests to verify new function tests pass**

Run: `python -m pytest tests/test_workspace.py -v -k "is_staged or promote or discard or list_staged or staging_file"`
Expected: All 7 new tests PASS

- [ ] **Step 5: Run ALL tests to verify no regressions**

Run: `python -m pytest tests/test_workspace.py -v`
Expected: ALL tests PASS

- [ ] **Step 6: Commit**

```bash
git add core/workspace.py tests/test_workspace.py
git commit -m "feat(workspace): add is_staged, promote_to_workspace, discard_staging, staging_file_summary"
```

---

### Task 3: Add `temp_workspace/` to `.gitignore`

**Files:**
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing
- Produces: gitignore rule for `temp_workspace/`

- [ ] **Step 1: Add the entry**

Add to `.gitignore` after the existing `workspace/projects/*/*/.demo_stash/` block:

```
# ---------------------------------------------------------------------------
# Staging workspace — generated files before promotion to workspace/
# ---------------------------------------------------------------------------
temp_workspace/
```

- [ ] **Step 2: Verify**

Run: `git status` to confirm `temp_workspace/` would not be tracked.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore temp_workspace/"
```

---

### Task 4: Make `agent_ui.py` staging-aware — `proj_path()` and session state

**Files:**
- Modify: `core/agent_ui.py:39-41` (proj_path), `core/agent_ui.py:1952-1971` (initialize_session)

**Interfaces:**
- Consumes: `ws.project_dir(project, staging=bool)`, `ws.is_staged(project)`
- Produces:
  - `proj_path(*parts)` — now reads `st.session_state.staging_active` to resolve staging vs workspace
  - `st.session_state.staging_active` — initialized in `initialize_session()`

- [ ] **Step 1: Update `proj_path()` to be staging-aware**

In `core/agent_ui.py`, replace `proj_path` (line 39-41):

Old:
```python
def proj_path(*parts: str) -> Path:
    """Resolve a path inside the active project's folder."""
    return ws.project_dir(current_project()).joinpath(*parts)
```

New:
```python
def proj_path(*parts: str) -> Path:
    staging = st.session_state.get("staging_active", True)
    return ws.project_dir(current_project(), staging=staging).joinpath(*parts)
```

- [ ] **Step 2: Update `initialize_session()` to include `staging_active`**

In `core/agent_ui.py`, in the `initialize_session()` function (around line 1965), after the line `st.session_state.framework_done = False`, add:

```python
    st.session_state.staging_active = True
```

- [ ] **Step 3: Update all direct `ws.project_dir()` calls in `agent_ui.py` to pass staging**

There are 6 direct calls to `ws.project_dir()` in `agent_ui.py` that bypass `proj_path()`. Each must become staging-aware:

**Line 364** (`append_process_log`):
Old: `proj = ws.project_dir(project)`
New: `proj = ws.project_dir(project, staging=st.session_state.get("staging_active", True))`

**Line 1118** (`syntax_check_generated`):
Old: `proj_root = ws.project_dir(current_project())`
New: `proj_root = ws.project_dir(current_project(), staging=st.session_state.get("staging_active", True))`

**Line 1567** (`stream_command`):
Old: `proc_cwd = str(cwd or ws.project_dir(current_project()))`
New: `proc_cwd = str(cwd or ws.project_dir(current_project(), staging=st.session_state.get("staging_active", True)))`

**Line 1987** (`render_feature_files`):
Old: `proj = ws.project_dir(story_id)`
New: `proj = ws.project_dir(story_id, staging=st.session_state.get("staging_active", True))`

**Line 2008** (`render_framework_files`):
Old: `proj = ws.project_dir(story_id)`
New: `proj = ws.project_dir(story_id, staging=st.session_state.get("staging_active", True))`

**Line 2910** (pytest cwd):
Old: `story_id=project, cwd=ws.project_dir(project),`
New: `story_id=project, cwd=ws.project_dir(project, staging=st.session_state.get("staging_active", True)),`

- [ ] **Step 4: Update `ws.subdir()` calls that pass through to path resolution**

In `story_feature_count` (line 374):
Old: `p = ws.subdir(project, "feature")`
New: `p = ws.subdir(project, "feature", staging=st.session_state.get("staging_active", True))`

Any other `ws.subdir()` calls should similarly get the staging parameter.

- [ ] **Step 5: Commit**

```bash
git add core/agent_ui.py
git commit -m "feat(ui): make proj_path and direct ws calls staging-aware"
```

---

### Task 5: Route story upload/paste to staging

**Files:**
- Modify: `core/agent_ui.py:2385-2442` (upload and paste handlers)

**Interfaces:**
- Consumes: `ws.add_story(project, filename, content, staging=True)`, `ws.story_exists(project, filename, staging=bool)`, `ws.write_pytest_ini(project, base_url, staging=True)`, `ws.is_staged(project)`
- Produces: Story files written to `temp_workspace/`, `staging_active` set correctly

- [ ] **Step 1: Update the file-upload handler to use staging**

In the upload handler (around line 2394-2408), update the duplicate check and write calls:

Old (line 2394):
```python
                    if ws.story_exists(project, filename):
```
New:
```python
                    if ws.story_exists(project, filename):
                        st.session_state.staging_active = False
```

This handles the case where the story was already promoted to workspace. The user reruns from workspace.

Old (lines 2398-2408):
```python
                    else:
                        ws.add_story(project, filename, content)
                        ws.write_pytest_ini(project, ws.extract_base_url(content))
                        st.session_state.project = project
                        st.session_state.active_story = filename
                        st.session_state.log = []
                        st.session_state.last_run = "never"
```
New:
```python
                    else:
                        ws.add_story(project, filename, content, staging=True)
                        ws.write_pytest_ini(project, ws.extract_base_url(content), staging=True)
                        st.session_state.project = project
                        st.session_state.active_story = filename
                        st.session_state.staging_active = True
                        st.session_state.log = []
                        st.session_state.last_run = "never"
```

- [ ] **Step 2: Update the paste handler similarly**

In the paste handler (around lines 2431-2442):

Old (line 2431):
```python
                    if ws.story_exists(project, filename):
```
New:
```python
                    if ws.story_exists(project, filename):
                        st.session_state.staging_active = False
```

Old (lines 2436-2441):
```python
                    else:
                        ws.add_story(project, filename, content)
                        ws.write_pytest_ini(project, ws.extract_base_url(content))
                        st.session_state.project = project
                        st.session_state.active_story = filename
```
New:
```python
                    else:
                        ws.add_story(project, filename, content, staging=True)
                        ws.write_pytest_ini(project, ws.extract_base_url(content), staging=True)
                        st.session_state.project = project
                        st.session_state.active_story = filename
                        st.session_state.staging_active = True
```

- [ ] **Step 3: Update project selector to detect staging on switch**

In the project/story selector (around line 2362), after `st.session_state.project = sel_proj`, add staging detection:

```python
            st.session_state.project = sel_proj
            st.session_state.staging_active = ws.is_staged(sel_proj)
```

And after the story selector (line 2372), after `st.session_state.active_story = sel_story`, add:

```python
                st.session_state.active_story = sel_story
                st.session_state.staging_active = ws.is_staged(sel_proj)
```

- [ ] **Step 4: Update Step 1 and Step 2 button handlers to pass staging to `ws` calls**

In the Gherkin handler (line 2825):
Old: `ws.ensure_project_dirs(project)`
New: `ws.ensure_project_dirs(project, staging=st.session_state.get("staging_active", True))`

In the Framework handler (line 2846):
Old: `ws.ensure_project_dirs(project)`
New: `ws.ensure_project_dirs(project, staging=st.session_state.get("staging_active", True))`

Line 2850:
Old: `scaffold = ws.copy_scaffolding(project)`
New: `scaffold = ws.copy_scaffolding(project, staging=st.session_state.get("staging_active", True))`

Line 2859:
Old: `reuse_idx = ws.load_reuse_index(project)`
New: `reuse_idx = ws.load_reuse_index(project, staging=st.session_state.get("staging_active", True))`

Line 2875:
Old: `ws.rebuild_reuse_index(project)`
New: `ws.rebuild_reuse_index(project, staging=st.session_state.get("staging_active", True))`

In the pytest run handler (line 2896):
Old: `run_dir = ws.new_report_run_dir(project)`
New: `run_dir = ws.new_report_run_dir(project, staging=st.session_state.get("staging_active", True))`

- [ ] **Step 5: Commit**

```bash
git add core/agent_ui.py
git commit -m "feat(ui): route story upload/paste to staging, detect staging on project switch"
```

---

### Task 6: Add staging badge and promotion dialog to the UI

**Files:**
- Modify: `core/agent_ui.py` — add `render_promotion_dialog()`, update `story_caption`, update reset workspace, add CSS

**Interfaces:**
- Consumes: `ws.promote_to_workspace(project)`, `ws.staging_file_summary(project)`, `ws.discard_staging(project)`, `st.session_state.staging_active`
- Produces: Promotion dialog UI, staging badge, staging-aware reset

- [ ] **Step 1: Add CSS for the promotion dialog and staging badge**

In the `CUSTOM_CSS` string (around line 97), append before the closing `</style>`:

```css
    /* Staging badge */
    .staging-badge {
        display: inline-flex; align-items: center; gap: 0.35rem;
        padding: 0.2rem 0.6rem; border-radius: 999px;
        font-size: 0.78rem; font-weight: 600;
    }
    .staging-badge.staging {
        background: #fef3c7; color: #92400e; border: 1px solid #fde68a;
    }
    .staging-badge.workspace {
        background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0;
    }

    /* Promotion dialog */
    .promotion-card {
        background: #fffbeb; border: 1px solid #fde68a; border-radius: 12px;
        padding: 1.2rem 1.4rem; margin: 1rem 0;
    }
    .promotion-card .promotion-title {
        font-size: 1rem; font-weight: 700; color: #92400e; margin-bottom: 0.5rem;
    }
    .promotion-card .promotion-msg { color: #78350f; font-size: 0.9rem; margin-bottom: 0.75rem; }
    .promotion-card .promotion-summary { color: #a16207; font-size: 0.82rem; margin-top: 0.5rem; }
```

- [ ] **Step 2: Add the staging badge to the story caption**

In `render_sidebar()`, find the `story_caption` block (around line 2444). Replace:

Old:
```python
        story_caption = (
            f"Project `{current_project()}`"
            + (f" · story `{st.session_state.get('active_story', '')}`"
               if st.session_state.get("active_story") else "")
            if current_project() else "Upload or paste a story to begin."
        )
        st.caption(story_caption)
```

New:
```python
        story_caption = (
            f"Project `{current_project()}`"
            + (f" · story `{st.session_state.get('active_story', '')}`"
               if st.session_state.get("active_story") else "")
            if current_project() else "Upload or paste a story to begin."
        )
        if current_project():
            staging = st.session_state.get("staging_active", True)
            badge_class = "staging" if staging else "workspace"
            badge_label = "Staging" if staging else "Workspace"
            st.markdown(
                f'{story_caption} <span class="staging-badge {badge_class}">{badge_label}</span>',
                unsafe_allow_html=True,
            )
        else:
            st.caption(story_caption)
```

- [ ] **Step 3: Add `render_promotion_dialog()` function**

Add this function before `main()` or in the rendering section of `agent_ui.py`:

```python
def render_promotion_dialog() -> None:
    if not st.session_state.get("staging_active", False):
        return
    project = current_project()
    if not project or not ws.is_staged(project):
        return
    summary = ws.staging_file_summary(project)
    if not summary:
        return
    summary_parts = [f"{count} {folder}" for folder, count in sorted(summary.items())]
    summary_text = ", ".join(summary_parts)
    st.markdown(
        '<div class="promotion-card">'
        '<div class="promotion-title">Staging workspace</div>'
        '<div class="promotion-msg">'
        "Test completed from staging workspace.<br>"
        "Move the created project files to workspace. Please confirm."
        "</div>"
        f'<div class="promotion-summary">Files to move: {summary_text}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    col1, col2, _ = st.columns([1, 1, 3])
    with col1:
        if st.button("Yes, promote", key="promote_yes", type="primary"):
            result = ws.promote_to_workspace(project)
            st.session_state.staging_active = False
            copied_n = len(result["copied"])
            skipped_n = len(result["skipped"])
            msg = f"Promoted {copied_n} file(s) to workspace/{project}. Staging cleared."
            if result["skipped"]:
                msg += f" Skipped {skipped_n} file(s) (already in workspace): " + ", ".join(result["skipped"][:5])
            st.session_state["promotion_result"] = msg
            st.rerun()
    with col2:
        if st.button("No, keep staging", key="promote_no"):
            st.info("Files remain in staging. You can re-run tests or promote later.")
    if "promotion_result" in st.session_state:
        st.success(st.session_state.pop("promotion_result"))
```

- [ ] **Step 4: Call `render_promotion_dialog()` after test results**

In the pytest run handler (around line 2937, after the `st.rerun()` at end of Step 3), the promotion dialog is rendered on the next rerun cycle. Insert a call in the main panel rendering area, after the test results section:

Find where test results / reports are rendered in the main panel and add:

```python
    render_promotion_dialog()
```

The exact placement: after the report rendering block but before the `st.rerun()` at the end of the run handler, OR in the main panel layout where test results are shown (since `st.rerun()` triggers a full re-render, the dialog will appear on the re-rendered page).

Since Streamlit re-renders the full page, add `render_promotion_dialog()` in the main panel rendering section (wherever test results are displayed), so it appears on every render when `staging_active` is True.

- [ ] **Step 5: Update reset workspace to be staging-aware**

In the sidebar reset button handler (around line 2572):

Old:
```python
            if st.button("Reset workspace (delete all generated files)"):
                clean_artifacts(scope="gherkin")
                st.session_state.log = []
                st.session_state.last_run = "never"
                log_event("Workspace reset — all generated files deleted")
                st.rerun()
```

New:
```python
            if st.button("Reset workspace (delete all generated files)"):
                if st.session_state.get("staging_active", True):
                    ws.discard_staging(current_project())
                    log_event("Staging workspace reset — all staged files deleted")
                else:
                    clean_artifacts(scope="gherkin")
                    log_event("Workspace reset — all generated files deleted")
                st.session_state.log = []
                st.session_state.last_run = "never"
                st.rerun()
```

- [ ] **Step 6: Add staging notification during test run**

In the pytest run handler (around line 2905), before the `st.status` context, add:

```python
        if st.session_state.get("staging_active", True):
            st.info("Running tests from staging workspace")
```

- [ ] **Step 7: Commit**

```bash
git add core/agent_ui.py
git commit -m "feat(ui): add staging badge, promotion dialog, staging-aware reset"
```

---

### Task 7: Manual integration test

**Files:** none (verification only)

**Interfaces:**
- Consumes: all prior tasks
- Produces: verified working system

- [ ] **Step 1: Start the Streamlit app**

Run: `cd core && python -m streamlit run agent_ui.py`

- [ ] **Step 2: Upload a new story**

Upload a `.txt` file (e.g., `TestProject_login.txt`). Verify:
- Files are created in `temp_workspace/TestProject/user_story/`
- The staging badge shows "Staging"
- No files appear in `workspace/TestProject/`

- [ ] **Step 3: Run Step 1 (Generate Gherkin)**

Click Generate Gherkin. Verify:
- Feature files appear in `temp_workspace/TestProject/feature/`
- No files appear in `workspace/TestProject/feature/`

- [ ] **Step 4: Run Step 2 (Generate Framework)**

Click Generate Framework. Verify:
- POMs, step defs, tests appear in `temp_workspace/TestProject/`
- No files appear in `workspace/TestProject/`

- [ ] **Step 5: Run Step 3 (Run Tests)**

Click Run Tests. Verify:
- Info banner says "Running tests from staging workspace"
- Tests execute from `temp_workspace/TestProject/`
- After completion, the promotion dialog appears with file summary

- [ ] **Step 6: Click "No, keep staging"**

Verify: files remain in `temp_workspace/TestProject/`, dialog stays on next render.

- [ ] **Step 7: Click "Yes, promote"**

Verify:
- Files are moved to `workspace/TestProject/`
- `temp_workspace/TestProject/` is removed
- Badge changes to "Workspace"
- Promotion dialog disappears
- Success message shows count of files promoted

- [ ] **Step 8: Re-run tests**

Verify: tests run from `workspace/TestProject/` — no staging banner, no promotion dialog.

- [ ] **Step 9: Commit final state if any fixups were needed**

```bash
git add -A
git commit -m "fix: integration test fixups for staging workspace"
```

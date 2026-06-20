from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACE_DIR = Path(os.environ.get("QA_WORKSPACE_DIR", PROJECT_ROOT.parent / "workspace"))
TEMP_WORKSPACE_DIR = Path(os.environ.get("QA_TEMP_WORKSPACE_DIR", PROJECT_ROOT.parent / "temp_workspace"))
TEMPLATES_DIR = PROJECT_ROOT / "templates"

# Canonical subfolders of a project, per the design diagram (singular names).
PROJECT_SUBDIRS = (
    "user_story", "feature", "step_defs", "pages", "test", "mcp-selectors", "report",
)

REUSE_INDEX_NAME = "reuse_index.json"

_PROJECT_NAME_RE = re.compile(r"^([A-Za-z0-9]+)_")
_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
_URL_RE = re.compile(r"https?://[^\s\"'>)]+", re.IGNORECASE)
_DEF_RE = re.compile(r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", re.MULTILINE)

_PYTEST_INI_TEMPLATE = """[pytest]
base_url = {base_url}
testpaths = test
addopts = -ra
markers =
"""


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


def project_dir(project: str, staging: bool = False) -> Path:
    root = TEMP_WORKSPACE_DIR if staging else WORKSPACE_DIR
    return root / project


def subdir(project: str, name: str, staging: bool = False) -> Path:
    return project_dir(project, staging=staging) / name


def ensure_project_dirs(project: str, staging: bool = False) -> Path:
    """Create only the missing canonical subfolders. Idempotent; never clears
    an existing folder. Returns the project dir."""
    pd = project_dir(project, staging=staging)
    for sub in PROJECT_SUBDIRS:
        (pd / sub).mkdir(parents=True, exist_ok=True)
    return pd


def copy_scaffolding(project: str, staging: bool = False) -> list[str]:
    """Copy the canonical, project-agnostic scaffolding into the project,
    overwriting any stale copy so harness fixes always propagate.

    The LLM no longer authors these — it only generates the project-specific
    locators / page objects / step defs / tests. `pytest_plugins` in the copied
    conftest stays the empty tuple form; sync_pytest_plugins() fills it from the
    step-def modules on disk after generation. Returns the project-relative paths
    written (for logging)."""
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
    # Package markers so `pages` and `step_defs` import cleanly.
    for pkg in ("pages", "step_defs"):
        init = pd / pkg / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
    return written


def story_exists(project: str, filename: str, staging: bool = False) -> bool:
    """Duplicate check: True if a story with this filename already exists."""
    return (subdir(project, "user_story", staging=staging) / filename).exists()


def add_story(project: str, filename: str, content: str, staging: bool = False) -> tuple[bool, Path]:
    """Write a NEW story file. Returns (created, path). If the file already
    exists it is left untouched and (False, path) is returned."""
    ensure_project_dirs(project, staging=staging)
    path = subdir(project, "user_story", staging=staging) / filename
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


def extract_base_url(text: str) -> str:
    """First http(s) URL in the text (scheme+host+port), or '' if none."""
    if not text:
        return ""
    m = _URL_RE.search(text)
    return m.group(0) if m else ""


def write_pytest_ini(project: str, base_url: str, staging: bool = False) -> Path:
    """Ensure workspace/<project>/pytest.ini exists with base_url + testpaths=test.
    Updates base_url in place if the file already exists; never duplicates keys."""
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


def new_report_run_dir(project: str, run_id: str | None = None, staging: bool = False) -> Path:
    """Create and return report/<timestamp>/ for a fresh run.
    run_id is overridable for deterministic tests."""
    stamp = run_id or _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    d = subdir(project, "report", staging=staging) / stamp
    d.mkdir(parents=True, exist_ok=True)
    return d


def report_runs(project: str, staging: bool = False) -> list[Path]:
    """All report run folders for the project, newest first."""
    rep = subdir(project, "report", staging=staging)
    if not rep.exists():
        return []
    return sorted((d for d in rep.iterdir() if d.is_dir()),
                  key=lambda p: p.name, reverse=True)


def reuse_index_path(project: str, staging: bool = False) -> Path:
    return project_dir(project, staging=staging) / REUSE_INDEX_NAME


def _empty_reuse_index() -> dict:
    return {"page_methods": {}, "step_defs": {}, "selectors": {}, "flows": {}}


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


def rebuild_reuse_index(project: str, staging: bool = False) -> dict:
    """Scan pages/, step_defs/, mcp-selectors/ and write reuse_index.json.
    Best-effort and tolerant of parse errors. Existing files always win on
    first-seen so the index is stable across rebuilds."""
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


def is_staged(project: str) -> bool:
    """Check if a project has any staged content in temp_workspace."""
    pd = project_dir(project, staging=True)
    if not pd.exists():
        return False
    return any(pd.rglob("*"))


def promote_to_workspace(project: str) -> dict:
    """Promote staged files from temp_workspace to workspace.

    Returns dict with "copied" and "skipped" lists (relative paths with forward slashes).
    Uses additive merge: never overwrites existing files in workspace.
    Removes the staging folder after promotion."""
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
    """Remove all staged content for a project (delete temp_workspace/<project>/)."""
    pd = project_dir(project, staging=True)
    if pd.exists():
        shutil.rmtree(pd)


def list_staged_projects() -> list[str]:
    """Return a sorted list of project names that have staged content."""
    if not TEMP_WORKSPACE_DIR.exists():
        return []
    return sorted(
        p.name for p in TEMP_WORKSPACE_DIR.iterdir()
        if p.is_dir() and not p.name.startswith((".", "_"))
    )


def staging_file_summary(project: str) -> dict[str, int]:
    """Count files in each subdirectory of a staged project.

    Returns dict mapping subdirectory names to file counts.
    Omits empty subdirectories."""
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

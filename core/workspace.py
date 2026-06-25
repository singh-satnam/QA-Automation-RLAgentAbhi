from __future__ import annotations

import datetime as _dt
import difflib
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
    names: set[str] = set()
    for root in (WORKSPACE_DIR, TEMP_WORKSPACE_DIR):
        if root.exists():
            names.update(
                p.name for p in root.iterdir()
                if p.is_dir() and not p.name.startswith((".", "_"))
            )
    return sorted(names)


def list_stories(project: str) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for staging in (False, True):
        us = subdir(project, "user_story", staging=staging)
        if us.exists():
            for p in sorted(us.glob("*.txt")):
                if p.name not in seen:
                    seen.add(p.name)
                    result.append(p)
    return sorted(result, key=lambda p: p.name)


_ACTION_RE = re.compile(
    r"(?i)^\s*(?:\d+[\.\)]\s*)?(?:given|when|then|and|but)?\s*"
    r"(?:the\s+user\s+|user\s+|I\s+)?"
)
_ACTION_VERBS = re.compile(
    r"(?i)\b(navigate|click|enter|fill|type|select|verify|check|validate|"
    r"submit|press|open|close|log\s*in|sign\s*in|sign\s*out|log\s*out|"
    r"search|add|remove|delete|update|upload|download|drag|drop|scroll|"
    r"hover|should|is\s+displayed|is\s+available|is\s+present|lands?\s+on)\b"
)


def _extract_action_lines(text: str) -> list[str]:
    """Extract normalised action lines from a user story for comparison."""
    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not _ACTION_VERBS.search(stripped):
            continue
        normalised = _ACTION_RE.sub("", stripped).strip()
        normalised = re.sub(r"\bhttps?://\S+", "<URL>", normalised)
        normalised = re.sub(r"[\"']([^\"']*)[\"']", r"\1", normalised)
        normalised = re.sub(r"\s+", " ", normalised).lower().strip(" ,.;:-")
        if len(normalised) >= 5:
            lines.append(normalised)
    return lines


def _step_similarity(lines_a: list[str], lines_b: list[str]) -> float:
    """Ratio of matching action steps between two stories (0.0–1.0)."""
    if not lines_a or not lines_b:
        return 0.0
    return difflib.SequenceMatcher(None, lines_a, lines_b).ratio()


def _matching_steps(lines_a: list[str], lines_b: list[str]) -> list[str]:
    """Return the steps from lines_a that have a close match in lines_b."""
    matched = []
    for step in lines_a:
        for other in lines_b:
            if difflib.SequenceMatcher(None, step, other).ratio() >= 0.7:
                matched.append(step)
                break
    return matched


def _new_steps(lines_new: list[str], lines_existing: list[str]) -> list[str]:
    """Return steps in the new story that have NO close match in the existing."""
    unmatched = []
    for step in lines_new:
        has_match = any(
            difflib.SequenceMatcher(None, step, other).ratio() >= 0.7
            for other in lines_existing
        )
        if not has_match:
            unmatched.append(step)
    return unmatched


def check_duplicate_story(
    project: str, new_story_file: str, staging: bool = False,
) -> dict | None:
    """Check if a new story duplicates or overlaps an existing one.

    Compares against other stories within the same project, scanning both
    the workspace and staging roots for that project name.

    Returns None if no significant match. Otherwise returns:
        {
            "match_type": "full" | "partial",
            "ratio": float,
            "matched_story_file": str,
            "matched_story_text": str,
            "matching_steps": [str, ...],
            "new_steps": [str, ...],
            "feature_file": Path | None,
            "feature_content": str,
        }
    """
    story_dir = subdir(project, "user_story", staging=staging)
    new_path = story_dir / new_story_file
    if not new_path.exists():
        return None
    new_text = new_path.read_text(encoding="utf-8")
    new_lines = _extract_action_lines(new_text)
    if not new_lines:
        return None

    best: dict | None = None
    best_ratio = 0.0

    # Scan both workspace and staging roots for this project's stories
    scan_dirs: list[tuple[bool, Path]] = []
    for stg in (False, True):
        us = subdir(project, "user_story", staging=stg)
        if us.exists():
            scan_dirs.append((stg, us))

    for _stg, us_dir in scan_dirs:
        for story_path in sorted(us_dir.glob("*.txt")):
            if story_path == new_path:
                continue
            try:
                existing_text = story_path.read_text(encoding="utf-8")
            except OSError:
                continue
            existing_lines = _extract_action_lines(existing_text)
            if not existing_lines:
                continue
            ratio = _step_similarity(new_lines, existing_lines)
            if ratio > best_ratio:
                best_ratio = ratio
                best = {
                    "ratio": ratio,
                    "matched_story_file": story_path.name,
                    "matched_staging": _stg,
                    "matched_story_text": existing_text,
                    "matched_lines": existing_lines,
                }

    if best is None or best_ratio < 0.50:
        return None

    matched_steps = _matching_steps(new_lines, best["matched_lines"])
    delta_steps = _new_steps(new_lines, best["matched_lines"])

    # Look for feature file in the matched root (workspace or staging)
    matched_stg = best["matched_staging"]
    feature_dir = subdir(project, "feature", staging=matched_stg)
    feature_file = None
    feature_content = ""
    if feature_dir.exists():
        stem = Path(best["matched_story_file"]).stem
        for fp in feature_dir.glob("*.feature"):
            if stem in fp.stem or fp.stem in stem:
                feature_file = fp
                feature_content = fp.read_text(encoding="utf-8")
                break
        if not feature_file:
            features = sorted(feature_dir.glob("*.feature"))
            if features:
                feature_file = features[0]
                feature_content = feature_file.read_text(encoding="utf-8")

    return {
        "match_type": "full" if best_ratio >= 0.80 else "partial",
        "ratio": round(best_ratio, 2),
        "matched_story_file": best["matched_story_file"],
        "matched_story_text": best["matched_story_text"],
        "matching_steps": matched_steps,
        "new_steps": delta_steps,
        "feature_file": feature_file,
        "feature_content": feature_content,
    }


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


_RUN_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")


def report_runs(project: str, staging: bool = False) -> list[Path]:
    """All report run folders for the project, newest first.
    Only returns directories matching the YYYY-MM-DD_HH-MM-SS naming convention."""
    rep = subdir(project, "report", staging=staging)
    if not rep.exists():
        return []
    return sorted((d for d in rep.iterdir() if d.is_dir() and _RUN_DIR_RE.match(d.name)),
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


def promote_to_workspace(project: str, max_retries: int = 3) -> dict:
    """Promote staged files from temp_workspace to workspace.

    Returns dict with "copied", "skipped", and "failed" lists (relative paths).
    Uses additive merge: never overwrites existing files in workspace.
    Retries failed copies up to max_retries times before giving up.
    Removes the staging folder only when all files are moved successfully."""
    staging_pd = project_dir(project, staging=True)
    workspace_pd = project_dir(project, staging=False)
    result: dict[str, list[str]] = {"copied": [], "skipped": [], "failed": []}
    if not staging_pd.exists():
        return result
    ensure_project_dirs(project, staging=False)

    pending = []
    for src_file in sorted(staging_pd.rglob("*")):
        if not src_file.is_file():
            continue
        # Skip __pycache__ — .pyc files embed the original source path
        # and will cause FileNotFoundError after promotion
        if "__pycache__" in src_file.parts:
            continue
        rel = src_file.relative_to(staging_pd)
        dst_file = workspace_pd / rel
        rel_str = str(rel).replace("\\", "/")
        if dst_file.exists():
            result["skipped"].append(rel_str)
        else:
            pending.append((src_file, dst_file, rel_str))

    for attempt in range(max_retries):
        still_failing = []
        for src_file, dst_file, rel_str in pending:
            try:
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                result["copied"].append(rel_str)
            except OSError:
                still_failing.append((src_file, dst_file, rel_str))
        pending = still_failing
        if not pending:
            break

    result["failed"] = [rel_str for _, _, rel_str in pending]
    if not result["failed"]:
        shutil.rmtree(staging_pd)
        # Clean __pycache__ in workspace so Python recompiles with correct paths
        for cache_dir in workspace_pd.rglob("__pycache__"):
            if cache_dir.is_dir():
                shutil.rmtree(cache_dir, ignore_errors=True)
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

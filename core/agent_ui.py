from __future__ import annotations

import ast
import base64
import datetime as _dt
import hashlib
import json
import os
import re
import queue
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import workspace as ws

PROJECT_ROOT = Path(__file__).resolve().parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"


def _load_prompt(name: str) -> str:
    """Load an LLM prompt template from prompts/<name>.md (editable without touching code)."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def current_project() -> str:
    """The active project name (from the most recent upload/paste), or ''."""
    return st.session_state.get("project", "")


def proj_path(*parts: str) -> Path:
    """Resolve a path inside the active project's folder."""
    return ws.project_dir(current_project()).joinpath(*parts)


JRE_HOME = Path(os.environ.get("USERPROFILE", "")) / "tools" / "jdk-21.0.10+7-jre"

USER_STORY_PLACEHOLDER = (
    "# Add one or more user stories below in plain English.\n"
    "# Separate distinct stories with a blank line.\n"
)


GHERKIN_PROMPT = _load_prompt("gherkin_prompt")

FRAMEWORK_PROMPT = _load_prompt("framework_prompt")


FRAMEWORK_DELTA_PROMPT = _load_prompt("framework_delta_prompt")


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

GHERKIN_TOOLS = ["Write", "Read", "Edit", "Glob"]
BUILD_TOOLS = [
    "Write", "Read", "Edit", "Glob", "Grep", "Bash",
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_click",
    "mcp__playwright__browser_type",
    "mcp__playwright__browser_take_screenshot",
    "mcp__playwright__browser_close",
    "mcp__playwright__browser_wait_for",
    "mcp__playwright__browser_evaluate",
    "mcp__playwright__browser_press_key",
    "mcp__playwright__browser_hover",
    "mcp__playwright__browser_fill_form",
    "mcp__playwright__browser_handle_dialog",
    "mcp__playwright__browser_navigate_back",
    "mcp__playwright__browser_select_option",
    "mcp__playwright__browser_resize",
    "mcp__playwright__browser_tabs",
]


CUSTOM_CSS = """
<style>
    .block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1400px; }

    .hero-title {
        font-size: 1.85rem; font-weight: 700; color: #0f172a;
        letter-spacing: -0.02em; margin: 0 0 0.25rem 0;
    }
    .hero-title .accent {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .hero-subtitle { color: #64748b; font-size: 0.95rem; margin: 0 0 1.25rem 0; }

    .status-pill {
        display: inline-flex; align-items: center; gap: 0.5rem;
        padding: 0.4rem 0.85rem; border-radius: 999px;
        background: #f1f5f9; border: 1px solid #e2e8f0;
        font-size: 0.82rem; color: #334155; margin-right: 0.5rem;
    }
    .status-pill .dot { width: 8px; height: 8px; border-radius: 50%; background: #cbd5e1; flex: 0 0 8px; }
    .status-pill.ok    .dot { background: #16a34a; box-shadow: 0 0 0 3px rgba(22,163,74,0.15); }
    .status-pill.warn  .dot { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245,158,11,0.15); }
    .status-pill.bad   .dot { background: #dc2626; box-shadow: 0 0 0 3px rgba(220,38,38,0.15); }

    .summary-line { color: #475569; font-size: 0.9rem; margin: 0.5rem 0 1.25rem 0; }
    .summary-line .num { color: #0f172a; font-weight: 700; }
    .summary-line .sep { color: #cbd5e1; margin: 0 0.6rem; }
    .summary-line .story-id { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.82rem; color: #4338ca; }
    .summary-line .story-label {
        background: linear-gradient(135deg, #eef2ff, #f5f3ff);
        color: #4338ca; padding: 0.18rem 0.6rem; border-radius: 999px;
        border: 1px solid #e0e7ff; font-weight: 600; font-size: 0.82rem;
    }

    /* Test runner */
    .runner-header { margin: 0.5rem 0 1rem 0; }
    .runner-header .runner-title {
        font-size: 1rem; font-weight: 700; color: #0f172a;
        margin-bottom: 0.15rem;
    }
    .runner-header .runner-sub { color: #64748b; font-size: 0.85rem; }

    .test-row {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.7rem 0.95rem;
        margin-bottom: 0.55rem;
        transition: border-color 0.12s ease, box-shadow 0.12s ease;
    }
    .test-row:hover {
        border-color: #c7d2fe;
        box-shadow: 0 2px 8px rgba(79, 70, 229, 0.08);
    }
    .test-num {
        display: inline-flex; align-items: center; justify-content: center;
        width: 1.7rem; height: 1.7rem; border-radius: 50%;
        background: linear-gradient(135deg, #4f46e5, #7c3aed);
        color: white; font-weight: 700; font-size: 0.78rem;
        box-shadow: 0 1px 3px rgba(79, 70, 229, 0.35);
    }
    .test-title {
        color: #0f172a; font-weight: 600; font-size: 0.92rem;
        line-height: 1.3; margin-bottom: 0.15rem;
    }
    .test-sub { color: #64748b; font-size: 0.8rem; }
    .test-meta {
        display: inline-flex; align-items: center; gap: 0.25rem;
        margin-right: 0.7rem;
    }
    .test-meta.mono {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 0.78rem; color: #475569;
    }
    .runner-actions { margin-top: 0.6rem; }

    .section-heading {
        font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
        color: #64748b; font-weight: 700; margin: 1.25rem 0 0.5rem 0;
    }

    .step-button-wrapper { margin-bottom: 0.4rem; }
    .step-num {
        display: inline-flex; align-items: center; justify-content: center;
        width: 1.4rem; height: 1.4rem; border-radius: 50%;
        background: #4f46e5; color: white; font-weight: 700; font-size: 0.75rem;
        margin-right: 0.5rem;
    }

    .stButton > button {
        border-radius: 8px; font-weight: 600; padding: 0.6rem 1rem;
        border: 1px solid #e2e8f0; background: #ffffff; color: #0f172a;
        transition: all 0.12s ease;
    }
    .stButton > button:hover { border-color: #cbd5e1; background: #f8fafc; }
    .stButton > button[kind="primary"] {
        background: #4f46e5; border-color: #4f46e5; color: #ffffff;
    }
    .stButton > button[kind="primary"]:hover { background: #4338ca; border-color: #4338ca; }
    .stButton > button:disabled { background: #f1f5f9; border-color: #e2e8f0; color: #94a3b8; }

    section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e2e8f0; }
    section[data-testid="stSidebar"] .stButton > button { width: 100%; }

    .empty-state {
        background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 10px;
        padding: 1.5rem; text-align: center; color: #64748b; font-size: 0.9rem;
    }
    .empty-state strong { color: #0f172a; }

    .activity-banner {
        display: flex; justify-content: space-between; align-items: center;
        margin: 1.5rem 0 0.5rem 0;
    }
    .activity-banner .title { font-size: 0.9rem; font-weight: 700; color: #0f172a; }
    .activity-state { font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.7rem; border-radius: 999px; }
    .activity-state.idle    { background: #f1f5f9; color: #64748b; }
    .activity-state.running { background: #eef2ff; color: #4338ca; }
    .activity-state.ready   { background: #ecfdf5; color: #047857; }
    .activity-state.cached  { background: #fef3c7; color: #92400e; }

    button[data-baseweb="tab"] { font-weight: 600; color: #64748b; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #0f172a; }

    #MainMenu, footer { visibility: hidden; }
    header { background: transparent; }
</style>
"""


def claude_path() -> str | None:
    found = shutil.which("claude") or shutil.which("claude.cmd") or shutil.which("claude.exe")
    if found:
        return found
    appdata = os.environ.get("APPDATA", "")
    candidates = [
        Path(appdata) / "npm" / "claude.cmd",
        Path(appdata) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def java_available() -> bool:
    return bool(shutil.which("java")) or (JRE_HOME / "bin" / "java.exe").exists()


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    if (JRE_HOME / "bin" / "java.exe").exists():
        env["JAVA_HOME"] = str(JRE_HOME)
        env["PATH"] = f"{JRE_HOME / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    return env


def normalize_story_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = re.sub(r"\n{3}", "\n\n", text)
    return text.strip() + "\n"


def parse_stories(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    cleaned_text = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    ).strip()
    if not cleaned_text:
        return []

    def is_substantive(block: str) -> bool:
        non_empty = sum(1 for line in block.splitlines() if line.strip())
        return non_empty >= 3 or len(block) >= 150

    for separator in (r"\n{5,}", r"\n{4,}", r"\n{3,}", r"\n\s*\n"):
        blocks = [b.strip() for b in re.split(separator, cleaned_text) if b.strip()]
        if len(blocks) >= 2 and all(is_substantive(b) for b in blocks):
            return blocks
    return [cleaned_text]


def story_label(text: str) -> str:
    """Short human-readable label for a user story (≤60 chars).
    Picks the first meaningful line, strips ordinal/Gherkin/URL noise, truncates."""
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip ordinal prefix: "1.", "2)", "Story 3:"
        line = re.sub(r"^\s*(\d+[\.\)]\s*|story\s+\d+\s*[:\-]\s*)", "", line, flags=re.IGNORECASE)
        # Strip leading Gherkin keyword
        line = re.sub(r"^\s*(given|when|then|and|but|scenario|feature)\s+", "",
                      line, flags=re.IGNORECASE)
        # Strip URLs and credential-like trailing chunks
        line = re.sub(r"\bhttps?://\S+", "", line)
        line = re.sub(r"\bURL\s*:\s*\S+", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\s+", " ", line).strip(" ,.;:-")
        if len(line) < 4:
            continue
        return (line[:60].rstrip(",.;:- ") + ("…" if len(line) > 60 else ""))
    return "Untitled story"


def append_process_log(project: str, msg: str) -> None:
    if not project:
        return
    proj = ws.project_dir(project)
    proj.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with (proj / "process_log.txt").open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {msg}\n")


def story_feature_count(project: str) -> int:
    if not project:
        return 0
    p = ws.subdir(project, "feature")
    return len(list(p.glob("*.feature"))) if p.exists() else 0


def story_test_count(project: str) -> int:
    if not project:
        return 0
    p = ws.subdir(project, "test")
    return len(list(p.glob("test_*.py"))) if p.exists() else 0


_FEATURE_REF_RE = re.compile(
    r'["\']?\s*([\w\-]+)\.feature\s*["\']?', re.IGNORECASE
)


def _extract_feature_title(feature_path: Path) -> str:
    if not feature_path.exists():
        return ""
    try:
        for raw in feature_path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if stripped.lower().startswith("feature:"):
                return stripped.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def _feature_for_test(test_path: Path, features_dir: Path) -> Path | None:
    """Locate the .feature file referenced by a pytest-bdd test_*.py.
    Falls back to filename-derived match if the file's source doesn't reference one."""
    try:
        text = test_path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    m = _FEATURE_REF_RE.search(text)
    if m:
        candidate = features_dir / f"{m.group(1)}.feature"
        if candidate.exists():
            return candidate
    # fallback: tests/test_<slug>.py  →  features/<slug>.feature
    stem = test_path.stem.replace("test_", "", 1)
    candidate = features_dir / f"{stem}.feature"
    return candidate if candidate.exists() else None


def discover_tests(project: str) -> list[dict]:
    """Return one row per discovered pytest-bdd test file for this project.
    Each row: {file: Path, rel: str, name: str, title: str, feature: Path|None}."""
    if not project:
        return []
    tests_dir = ws.subdir(project, "test")
    features_dir = ws.subdir(project, "feature")
    if not tests_dir.exists():
        return []
    rows: list[dict] = []
    for test_file in sorted(tests_dir.glob("test_*.py")):
        feature = _feature_for_test(test_file, features_dir)
        title = _extract_feature_title(feature) if feature else ""
        # pytest target is relative to the project dir, where pytest runs from.
        rel_target = f"test/{test_file.name}"
        rows.append({
            "file": test_file,
            "rel": rel_target,
            "name": test_file.name,
            "title": title or test_file.stem.replace("_", " ").title(),
            "feature": feature.name if feature else "",
        })
    return rows


def _delete_files(folder: Path, keep: set[str], glob: str = "*") -> None:
    if not folder.exists():
        return
    for child in folder.glob(glob):
        if child.is_file() and child.name not in keep:
            try:
                child.unlink()
            except OSError:
                pass
        elif child.is_dir() and child.name == "__pycache__":
            shutil.rmtree(child, ignore_errors=True)


def reset_pytest_plugins() -> None:
    conftest = proj_path("conftest.py")
    if not conftest.exists():
        return
    text = conftest.read_text(encoding="utf-8")
    new_text = re.sub(
        r"pytest_plugins\s*=\s*\([^)]*\)",
        "pytest_plugins = ()",
        text,
        count=1,
    )
    if new_text != text:
        conftest.write_text(new_text, encoding="utf-8")


def sync_pytest_plugins() -> list[str]:
    """Deterministically register the active story's step-def modules in the
    root conftest's `pytest_plugins`.

    This is what makes pytest-bdd discover @given/@when/@then. Without it every
    scenario dies at its first step with StepDefinitionNotFoundError. We do NOT
    trust the LLM to edit pytest_plugins — it sometimes forgets, or puts an
    ineffective `from step_defs import <module>` in the test file (which imports
    the module object but does NOT expose pytest-bdd's injected step fixtures).
    Instead we derive the plugin list from the artifacts actually on disk.

    Mapping rule (matches the current FRAMEWORK_PROMPT: one step file per
    feature, named /step_defs/<feature_stem>_steps.py):

      * Register the step module that corresponds to each present feature, and
        SKIP stale/reused step modules whose feature is NOT part of this story.
        (A reused login POM can drag along an unrelated *_steps.py whose generic
        patterns — 'the user navigates to ...', 'the user clicks on ...' —
        would collide with the active story's steps.)
      * Fallback: if nothing matches by name (LLM deviated from the naming
        convention), register every *_steps.py so we register SOMETHING rather
        than nothing — mirrors the older shared-steps projects.

    Returns the list of dotted module paths written (for logging)."""
    conftest = proj_path("conftest.py")
    if not conftest.exists():
        return []
    features_dir = proj_path("feature")
    step_defs_dir = proj_path("step_defs")
    feature_stems = (
        {p.stem for p in features_dir.glob("*.feature")}
        if features_dir.exists() else set()
    )
    all_steps = sorted(
        p.stem for p in step_defs_dir.glob("*_steps.py")
    ) if step_defs_dir.exists() else []
    matched = [
        s for s in all_steps
        if any(s == f"{fstem}_steps" for fstem in feature_stems)
    ]
    modules = matched or all_steps
    plugins = tuple(f"step_defs.{m}" for m in modules)

    text = conftest.read_text(encoding="utf-8")
    new_text = re.sub(
        r"pytest_plugins\s*=\s*\([^)]*\)",
        f"pytest_plugins = {plugins!r}",
        text,
        count=1,
    )
    if new_text != text:
        conftest.write_text(new_text, encoding="utf-8")
    return list(plugins)


def reset_locators() -> None:
    locators = proj_path("mcp-selectors", "locators.json")
    discovery_meta = proj_path("mcp-selectors", "discovery_meta.json")
    locators.parent.mkdir(parents=True, exist_ok=True)
    locators.write_text("{}\n", encoding="utf-8")
    if discovery_meta.exists():
        try:
            discovery_meta.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Inline (Python-only) story coverage report builder.
#
# The previous Auditor was a Claude agent that re-read every artifact after
# each pytest run — 2-3 minutes of LLM tool calls just to summarise data we
# already have in captured_values.json + report.html. This deterministic
# replacement computes the verdict, renders the same sections, and writes
# .html/.md/.json in <100 ms.
# ---------------------------------------------------------------------------

def _load_captured_values() -> list[dict]:
    captured = proj_path("report", "captured_values.json")
    if not captured.exists():
        return []
    try:
        data = json.loads(captured.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        return list(data.get("captures") or [])
    if isinstance(data, list):
        return data
    return []


def _load_step_trace() -> list[dict]:
    """Per-step records (keyword/name/status/screenshot) written by conftest's
    pytest_bdd_after_step / pytest_bdd_step_error hooks during the run."""
    p = proj_path("report", "step_trace.json")
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    steps = data.get("steps") if isinstance(data, dict) else data
    return list(steps or [])


def _img_data_uri(rel_path: str) -> str:
    """Inline a screenshot (path relative to report/) as a base64 data URI so
    the report HTML is fully self-contained and portable."""
    if not rel_path:
        return ""
    fp = proj_path("report", rel_path)
    try:
        raw = fp.read_bytes()
    except OSError:
        return ""
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def _render_step_card(s: dict) -> str:
    """One screenshot card for a single step (used only for the important
    frames — failed steps, or the final frame of a clean run)."""
    is_fail = s.get("status") == "failed"
    cls = "step-fail" if is_fail else "step-pass"
    badge = "✗ FAIL" if is_fail else "✓ PASS"
    # Prefer a pre-embedded data URI (used by the suite report, captured before
    # the next story's run overwrites reports/screenshots/); else read the file.
    uri = s.get("_datauri") or _img_data_uri(s.get("screenshot", ""))
    if not uri:
        return ""
    err = ""
    if is_fail and s.get("error"):
        err = (f"<div class='step-error'>"
               f"{_esc(_shorten(s.get('error'), 300))}</div>")
    return (
        f"<div class='step-card {cls}'>"
        f"<div class='step-head'>"
        f"<span class='step-idx'>{_esc(s.get('index'))}</span>"
        f"<span class='step-kw'>{_esc(s.get('keyword', ''))}</span> "
        f"{_esc(s.get('name', ''))}"
        f"<span class='step-badge {cls}'>{badge}</span>{err}</div>"
        f"<a href='{uri}' target='_blank'>"
        f"<img class='step-shot' src='{uri}' alt='step {_esc(s.get('index'))}'></a>"
        f"</div>"
    )


def _render_step_timeline(steps: list[dict]) -> str:
    """Render the step-by-step section.

    Design (per user feedback): a screenshot on EVERY step is visual noise. So:
      * Show a compact, image-free checklist of every step with a ✓/✗ — the
        full flow and the exact failure point at a glance.
      * Embed SCREENSHOTS only for the important frames: the failing step(s),
        or — on a fully passing run — just the final end-state as proof.
    Every per-step screenshot is still saved to disk under reports/screenshots/;
    we just don't dump all of them into the report."""
    if not steps:
        return ""
    failed = [s for s in steps if s.get("status") == "failed"]

    # Top callout naming the breaking step.
    callout = ""
    if failed:
        f0 = failed[0]
        err = ""
        if f0.get("error"):
            err = (f"<div class='step-error'>"
                   f"{_esc(_shorten(f0.get('error'), 400))}</div>")
        callout = (
            f"<div class='step-failcallout'>❌ Failed at step "
            f"{_esc(f0.get('index'))}: <strong>{_esc(f0.get('keyword', ''))} "
            f"{_esc(f0.get('name', ''))}</strong>{err}</div>"
        )

    # Compact checklist of every step (no images).
    items = []
    for s in steps:
        is_fail = s.get("status") == "failed"
        icon = ("<span class='fail-cell'>✗</span>" if is_fail
                else "<span class='pass-cell'>✓</span>")
        items.append(
            f"<li class='{'step-li-fail' if is_fail else ''}'>{icon} "
            f"<span class='step-kw'>{_esc(s.get('keyword', ''))}</span> "
            f"{_esc(s.get('name', ''))}</li>"
        )
    checklist = f"<ol class='step-checklist'>{''.join(items)}</ol>"

    # Curated screenshots: failures, else just the final frame.
    if failed:
        shots, shots_title = failed, "Failure screenshot"
    else:
        shots, shots_title = steps[-1:], "Final state"
    cards = [c for c in (_render_step_card(s) for s in shots) if c]
    gallery = ""
    if cards:
        gallery = (f"<div class='step-shot-title'>{shots_title}</div>"
                   f"<div class='step-grid'>{''.join(cards)}</div>")

    return (
        "<section><h2>Step-by-step</h2>"
        f"{callout}{checklist}{gallery}</section>"
    )


def _classify_captured(entries: list[dict]) -> dict:
    """Bucket captures by their kind so the renderer can emit each section."""
    buckets = {
        "values": [],            # plain `cap.add(label, value)`
        "assertions": [],        # `cap.assert_match(...)`
        "aggregates": [],        # `cap.assert_sum/avg/...`
        "diffs": [],             # `cap.assert_difference(...)`
        "percentages": [],       # `cap.assert_percentage(...)`
        "ratios": [],            # `cap.assert_ratio(...)`
        "ranges": [],            # `cap.assert_in_range(...)`
        "missing": [],           # `cap.record_missing(...)`
        "prerequisites": [],     # `cap.assert_prerequisite(...)`
        "components": [],        # `cap.add_component(...)`
    }
    bucket_for_kind = {
        "value": "values",
        "assertion": "assertions",
        "aggregate_assertion": "aggregates",
        "diff_assertion": "diffs",
        "percentage_assertion": "percentages",
        "ratio_assertion": "ratios",
        "range_assertion": "ranges",
        "missing": "missing",
        "prerequisite": "prerequisites",
        "component": "components",
    }
    for e in entries:
        kind = (e.get("kind") or "value").strip()
        buckets[bucket_for_kind.get(kind, "values")].append(e)
    return buckets


def _compute_verdict(
    buckets: dict, pytest_exit_code: int
) -> tuple[str, str, list[str]]:
    """Return (verdict, css_class, reasons). Hierarchy:
       BLOCKED > FAIL > PARTIAL > PASS.
    `reasons` is a short list of human-readable bullets the banner shows."""
    reasons: list[str] = []

    # BLOCKED — any failed prerequisite halts everything after it.
    blocked = [p for p in buckets["prerequisites"] if not p.get("passed")]
    if blocked:
        first = blocked[0]
        reasons.append(
            f"Prerequisite failed: {first.get('label', '?')} — "
            f"{first.get('reason') or 'no reason given'}"
        )
        if first.get("evidence"):
            reasons.append(f"Evidence: {first['evidence']}")
        return ("BLOCKED", "blocked", reasons)

    # Collect every kind of negative assertion outcome.
    failed_assertions = []
    for key in ("assertions", "aggregates", "diffs",
                "percentages", "ratios", "ranges"):
        failed_assertions.extend(
            e for e in buckets[key] if e.get("passed") is False
        )

    if failed_assertions or pytest_exit_code != 0:
        if failed_assertions:
            reasons.append(
                f"{len(failed_assertions)} assertion(s) failed"
            )
        if pytest_exit_code != 0:
            reasons.append(f"pytest exited with code {pytest_exit_code}")
        return ("FAIL", "fail", reasons)

    # NOTE: we deliberately do NOT auto-fail on a backend-error string appearing
    # in the captured output. Whether a message like "already exists" means PASS
    # or FAIL is STATE- and STORY-specific (creating an org that exists = FAIL;
    # adding a user who already exists = PASS "already present"). Each step def
    # makes that judgment explicitly by reading the site, so a blanket scanner
    # here would wrongly override those intentional verdicts.

    if buckets["missing"]:
        reasons.append(
            f"{len(buckets['missing'])} item(s) not found "
            f"(test continued past each one)"
        )
        return ("PARTIAL", "partial", reasons)

    reasons.append("All captured assertions passed")
    return ("PASS", "pass", reasons)


def _esc(value) -> str:
    """HTML-safe stringify."""
    import html as _h
    return _h.escape("" if value is None else str(value), quote=True)


def _coverage_css() -> str:
    return """
    body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
           color: #0f172a; background: #f8fafc; margin: 0; padding: 24px; }
    .container { max-width: 1100px; margin: 0 auto; }
    h1 { font-size: 1.75rem; margin: 0 0 0.5rem 0; }
    .subtitle { color: #64748b; font-size: 0.9rem; margin-bottom: 1.5rem; }
    .verdict-banner { padding: 16px 20px; border-radius: 8px;
                      margin-bottom: 1.5rem; font-weight: 600; }
    .verdict-banner.pass    { background: #d1fae5; color: #065f46;
                              border-left: 5px solid #10b981; }
    .verdict-banner.partial { background: #fef3c7; color: #92400e;
                              border-left: 5px solid #f59e0b; }
    .verdict-banner.fail    { background: #fee2e2; color: #991b1b;
                              border-left: 5px solid #dc2626; }
    .verdict-banner.blocked { background: #fee2e2; color: #991b1b;
                              border-left: 5px solid #b91c1c;
                              font-size: 1.05rem; }
    .verdict-banner .label  { font-size: 1.3rem; display: block;
                              margin-bottom: 6px; }
    .verdict-banner ul      { margin: 0; padding-left: 1.2rem; font-weight: 500; }
    section { background: white; border-radius: 8px; padding: 18px 20px;
              margin-bottom: 1rem; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
    section h2 { font-size: 1.05rem; margin: 0 0 0.75rem 0; color: #0f172a; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th, td { padding: 8px 10px; text-align: left;
             border-bottom: 1px solid #e2e8f0; }
    th { background: #f1f5f9; font-weight: 600; color: #475569;
         font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }
    tr:last-child td { border-bottom: none; }
    .pass-cell  { color: #047857; font-weight: 600; }
    .fail-cell  { color: #b91c1c; font-weight: 600; }
    .miss-cell  { color: #b45309; font-weight: 600; }
    .ts         { color: #94a3b8; font-family: ui-monospace, monospace;
                  font-size: 0.78rem; }
    code.value  { background: #f1f5f9; padding: 2px 6px; border-radius: 4px;
                  font-family: ui-monospace, monospace; font-size: 0.82rem; }
    .empty      { color: #94a3b8; font-size: 0.9rem; font-style: italic; }
    .pytest-summary { display: flex; gap: 24px; flex-wrap: wrap; }
    .pytest-summary div { font-size: 0.9rem; }
    .pytest-summary strong { display: block; font-size: 1.4rem;
                              color: #0f172a; }
    /* ---- Step-by-step visual timeline ---- */
    .step-failcallout { background: #fee2e2; color: #991b1b;
                        border-left: 5px solid #dc2626; border-radius: 6px;
                        padding: 12px 16px; margin-bottom: 1rem;
                        font-size: 0.95rem; }
    .step-grid { display: grid;
                 grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                 gap: 16px; }
    .step-checklist { margin: 0 0 1rem 0; padding-left: 1.4rem;
                      font-size: 0.9rem; line-height: 1.9; color: #334155; }
    .step-checklist li.step-li-fail { color: #991b1b; font-weight: 600; }
    .step-checklist .step-kw { font-weight: 700; color: #1e293b; }
    .step-shot-title { font-size: 0.78rem; text-transform: uppercase;
                       letter-spacing: 0.04em; color: #64748b; font-weight: 600;
                       margin-bottom: 8px; }
    .step-card { border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;
                 background: #fff; display: flex; flex-direction: column;
                 max-width: 560px; }
    .step-card.step-pass { border-left: 4px solid #10b981; }
    .step-card.step-fail { border-left: 4px solid #dc2626;
                           box-shadow: 0 0 0 2px #fecaca; }
    .step-head { padding: 9px 12px; font-size: 0.85rem; line-height: 1.35;
                 border-bottom: 1px solid #f1f5f9; }
    .step-idx { display: inline-block; min-width: 1.5rem; height: 1.5rem;
                line-height: 1.5rem; text-align: center; border-radius: 50%;
                background: #f1f5f9; color: #475569; font-size: 0.75rem;
                font-weight: 700; margin-right: 6px; }
    .step-kw { font-weight: 700; color: #1e293b; }
    .step-badge { float: right; font-size: 0.72rem; font-weight: 700;
                  padding: 2px 8px; border-radius: 999px; }
    .step-badge.step-pass { background: #d1fae5; color: #065f46; }
    .step-badge.step-fail { background: #fee2e2; color: #991b1b; }
    .step-shot { width: 100%; display: block; background: #f8fafc;
                 border-top: 1px solid #f1f5f9; cursor: zoom-in; }
    .step-noshot { padding: 24px 12px; text-align: center; color: #94a3b8;
                   font-size: 0.82rem; font-style: italic; }
    .step-error { margin-top: 6px; font-family: ui-monospace, monospace;
                  font-size: 0.78rem; color: #b91c1c;
                  white-space: pre-wrap; word-break: break-word; }
    /* ---- Consolidated website-suite report ---- */
    .verdict-chip { padding: 2px 10px; border-radius: 999px; font-size: 0.74rem;
                    font-weight: 700; white-space: nowrap; }
    .verdict-chip.pass    { background: #d1fae5; color: #065f46; }
    .verdict-chip.fail,
    .verdict-chip.blocked { background: #fee2e2; color: #991b1b; }
    .verdict-chip.partial { background: #fef3c7; color: #92400e; }
    .suite-story { border: 1px solid #e2e8f0; }
    .suite-story-head { display: flex; align-items: center; gap: 10px;
                        margin-bottom: 2px; }
    .suite-num { display: inline-flex; align-items: center; justify-content: center;
                 min-width: 1.7rem; height: 1.7rem; border-radius: 50%;
                 background: #0f172a; color: #fff; font-size: 0.8rem;
                 font-weight: 700; }
    .suite-story-title { font-weight: 700; font-size: 1.05rem; flex: 1; }
    .suite-story-meta { color: #64748b; font-size: 0.8rem; margin-bottom: 6px; }
    .suite-story-meta code { background: #f1f5f9; padding: 1px 5px;
                             border-radius: 4px; }
    .suite-reasons { margin: 0 0 0.5rem 1.1rem; color: #475569;
                     font-size: 0.85rem; }
    """


def _render_assertion_table(rows: list[dict], cols: list[tuple[str, str]]) -> str:
    """Generic table renderer. `cols` is [(header, key), ...].
    Special key 'verdict' renders pass/fail icon from row['passed']."""
    if not rows:
        return '<p class="empty">No entries.</p>'
    head = "".join(f"<th>{_esc(h)}</th>" for h, _ in cols)
    body_rows = []
    for r in rows:
        cells = []
        for _, key in cols:
            if key == "verdict":
                p = r.get("passed")
                if p is True:
                    cells.append('<td class="pass-cell">✓ PASS</td>')
                elif p is False:
                    cells.append('<td class="fail-cell">✗ FAIL</td>')
                else:
                    cells.append('<td>—</td>')
            elif key == "ts":
                cells.append(f'<td class="ts">{_esc(r.get(key, ""))}</td>')
            elif key.endswith("_code"):
                cells.append(f'<td><code class="value">{_esc(r.get(key[:-5], ""))}</code></td>')
            else:
                cells.append(f"<td>{_esc(r.get(key, ''))}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        f"<table><thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table>"
    )


def _render_aggregates(rows: list[dict]) -> str:
    if not rows:
        return '<p class="empty">No aggregate assertions.</p>'
    out = []
    for r in rows:
        op = r.get("op", "?")
        computed = r.get(f"computed_{op}", r.get("computed"))
        components = r.get("components") or []
        comp_str = ", ".join(
            f"{c.get('label', '?')}={c.get('value', '?')}" for c in components[:8]
        )
        if len(components) > 8:
            comp_str += f" … (+{len(components) - 8} more)"
        verdict = (
            '<span class="pass-cell">✓ PASS</span>' if r.get("passed")
            else '<span class="fail-cell">✗ FAIL</span>'
        )
        out.append(
            f"<tr>"
            f"<td>{_esc(r.get('label', '?'))}</td>"
            f"<td><code class='value'>{_esc(op)}</code></td>"
            f"<td>{_esc(comp_str) or '<em>no components</em>'}</td>"
            f"<td><code class='value'>{_esc(computed)}</code></td>"
            f"<td><code class='value'>{_esc(r.get('actual', ''))}</code></td>"
            f"<td>{verdict}</td>"
            f"</tr>"
        )
    return (
        "<table><thead><tr><th>Label</th><th>Op</th><th>Components</th>"
        "<th>Computed</th><th>Actual</th><th>Verdict</th></tr></thead>"
        f"<tbody>{''.join(out)}</tbody></table>"
    )


def build_inline_coverage_report(
    story_id: str,
    pytest_exit_code: int,
    run_timestamp: str,
) -> dict[str, str]:
    """Build the story coverage outputs (html/md/json) from captured_values.json
    and the pytest exit code. Pure Python, returns dict ready to write to disk."""
    entries = _load_captured_values()
    buckets = _classify_captured(entries)
    verdict, css_class, reasons = _compute_verdict(buckets, pytest_exit_code)

    story_text = ""
    stories = ws.list_stories(story_id) if story_id else []
    if stories:
        try:
            story_text = stories[0].read_text(encoding="utf-8")
        except OSError:
            story_text = ""

    pytest_html_exists = (
        proj_path("report", run_timestamp, "report.html").exists() if story_id else False
    )

    # ---- JSON ----
    summary = {
        "story_id": story_id,
        "run_timestamp": run_timestamp,
        "pytest_exit_code": pytest_exit_code,
        "verdict": verdict,
        "reasons": reasons,
        "counts": {
            "assertions": sum(
                len(buckets[k]) for k in
                ("assertions", "aggregates", "diffs",
                 "percentages", "ratios", "ranges")
            ),
            "values_captured": len(buckets["values"]),
            "components": len(buckets["components"]),
            "missing_items": len(buckets["missing"]),
            "prerequisites": len(buckets["prerequisites"]),
        },
        "captures": entries,
    }
    json_text = json.dumps(summary, indent=2, ensure_ascii=False)

    # ---- HTML ----
    reasons_html = "".join(f"<li>{_esc(r)}</li>" for r in reasons)
    verdict_label = {
        "PASS": "✓ PASS",
        "PARTIAL": "⚠ PARTIAL",
        "FAIL": "❌ FAIL",
        "BLOCKED": "🚫 BLOCKED",
    }.get(verdict, verdict)

    sections_html = []

    # Story snippet
    if story_text.strip():
        sections_html.append(
            f"<section><h2>User story</h2>"
            f"<pre style='white-space:pre-wrap;font-family:inherit;"
            f"margin:0;color:#334155'>{_esc(story_text.strip())}</pre></section>"
        )

    # Pytest summary
    sections_html.append(
        f"<section><h2>pytest run</h2>"
        f"<div class='pytest-summary'>"
        f"  <div><strong>{pytest_exit_code}</strong>exit code</div>"
        f"  <div><strong>{'yes' if pytest_html_exists else 'no'}</strong>"
        f"report.html present</div>"
        f"  <div><strong>{summary['counts']['assertions']}</strong>"
        f"assertions recorded</div>"
        f"  <div><strong>{summary['counts']['values_captured']}</strong>"
        f"values captured</div>"
        f"</div></section>"
    )

    # Step-by-step visual timeline (screenshots) — the headline visual: shows
    # every step's pass/fail with a picture and points at the failing step.
    step_timeline = _render_step_timeline(_load_step_trace())
    if step_timeline:
        sections_html.append(step_timeline)

    # Prerequisites
    if buckets["prerequisites"]:
        sections_html.append(
            "<section><h2>Prerequisites (blocking checks)</h2>" +
            _render_assertion_table(
                buckets["prerequisites"],
                [("Label", "label"), ("Reason", "reason"),
                 ("Evidence", "evidence"), ("Verdict", "verdict"),
                 ("Time", "ts")],
            ) + "</section>"
        )

    # Missing items
    if buckets["missing"]:
        sections_html.append(
            "<section><h2>Items not found "
            f"<span class='miss-cell'>({len(buckets['missing'])})</span></h2>" +
            _render_assertion_table(
                buckets["missing"],
                [("Label", "label"), ("Target", "target"),
                 ("Reason", "reason"), ("Time", "ts")],
            ) + "</section>"
        )

    # Direct assertions (assert_match)
    if buckets["assertions"]:
        sections_html.append(
            "<section><h2>Assertions</h2>" +
            _render_assertion_table(
                buckets["assertions"],
                [("Label", "label"), ("Expected", "expected"),
                 ("Actual", "actual"), ("Verdict", "verdict"),
                 ("Time", "ts")],
            ) + "</section>"
        )

    # Aggregates
    if buckets["aggregates"]:
        sections_html.append(
            "<section><h2>Aggregate assertions</h2>" +
            _render_aggregates(buckets["aggregates"]) + "</section>"
        )

    # Other arithmetic assertions (diff/percentage/ratio/range)
    arith_rows = []
    for kind, key, label_extra in (
        ("diff_assertion", "diffs",
         [("Larger", "larger"), ("Smaller", "smaller"),
          ("Computed", "computed_diff"), ("Expected", "expected_diff")]),
        ("percentage_assertion", "percentages",
         [("Part", "part"), ("Whole", "whole"),
          ("Computed %", "computed_percentage"),
          ("Expected %", "expected_percentage")]),
        ("ratio_assertion", "ratios",
         [("Numerator", "numerator"), ("Denominator", "denominator"),
          ("Computed", "computed_ratio"),
          ("Expected", "expected_ratio")]),
        ("range_assertion", "ranges",
         [("Actual", "actual"), ("Low", "low"), ("High", "high")]),
    ):
        if buckets[key]:
            cols = [("Label", "label")] + label_extra + [("Verdict", "verdict"), ("Time", "ts")]
            arith_rows.append(
                f"<h3 style='margin-top:0.75rem;font-size:0.95rem'>{kind}</h3>"
                + _render_assertion_table(buckets[key], cols)
            )
    if arith_rows:
        sections_html.append(
            "<section><h2>Arithmetic checks</h2>" + "".join(arith_rows) + "</section>"
        )

    # Plain values captured (audit trail)
    if buckets["values"]:
        sections_html.append(
            "<section><h2>Values observed during the test</h2>" +
            _render_assertion_table(
                buckets["values"],
                [("Label", "label"), ("Value", "value"), ("Time", "ts")],
            ) + "</section>"
        )

    html_doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Story coverage — {_esc(verdict)} — {_esc(run_timestamp)}</title>
<style>{_coverage_css()}</style></head>
<body><div class="container">
  <h1>Story coverage report</h1>
  <div class="subtitle">Run: <code>{_esc(run_timestamp)}</code> ·
       Story: <code>{_esc(story_id)}</code></div>
  <div class="verdict-banner {css_class}">
    <span class="label">{verdict_label}</span>
    <ul>{reasons_html}</ul>
  </div>
  {''.join(sections_html)}
</div></body></html>"""

    # ---- Markdown ----
    md_lines = [
        f"# Story coverage — {verdict}",
        f"_Run: `{run_timestamp}` · Story: `{story_id}`_",
        "",
        f"**Verdict:** {verdict_label}",
        "",
    ]
    for r in reasons:
        md_lines.append(f"- {r}")
    md_lines.append("")
    md_lines.append(f"pytest exit code: `{pytest_exit_code}` · "
                     f"assertions: {summary['counts']['assertions']} · "
                     f"missing: {summary['counts']['missing_items']} · "
                     f"prerequisites: {summary['counts']['prerequisites']}")
    md_lines.append("")
    if buckets["missing"]:
        md_lines.append("## Items not found")
        for m in buckets["missing"]:
            md_lines.append(
                f"- ✗ {m.get('label', '?')}: `{m.get('target', '?')}` — "
                f"{m.get('reason', '')}"
            )
        md_lines.append("")
    if buckets["assertions"]:
        md_lines.append("## Assertions")
        for a in buckets["assertions"]:
            icon = "✓" if a.get("passed") else "✗"
            md_lines.append(
                f"- {icon} **{a.get('label', '?')}** — expected "
                f"`{a.get('expected', '')}`, actual `{a.get('actual', '')}`"
            )
        md_lines.append("")

    return {
        "html": html_doc,
        "md": "\n".join(md_lines) + "\n",
        "json": json_text,
        "verdict": verdict,
    }


def write_inline_coverage_report(
    project: str,
    pytest_exit_code: int,
    run_dir: Path,
) -> dict[str, str]:
    """Build + write the report into the run dir. Returns the dict so callers
    can inspect the verdict."""
    run_timestamp = run_dir.name
    out = build_inline_coverage_report(project, pytest_exit_code, run_timestamp)
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "story_coverage.html").write_text(out["html"], encoding="utf-8")
        (run_dir / "story_coverage.md").write_text(out["md"], encoding="utf-8")
        (run_dir / "story_coverage.json").write_text(out["json"], encoding="utf-8")
        # Mirror the captured values into the run dir for portability.
        captured = proj_path("report", "captured_values.json")
        if captured.exists() and captured.parent != run_dir:
            try:
                (run_dir / "captured_values.json").write_bytes(captured.read_bytes())
            except OSError:
                pass
    except OSError:
        pass
    out["run_timestamp"] = run_timestamp
    return out


def discover_run_history(project: str) -> list[dict]:
    """Return list of historical runs for a project, newest first.
    Each entry: {timestamp, verdict, html_path, dir, has_pytest_html}."""
    if not project:
        return []
    results: list[dict] = []
    for d in ws.report_runs(project):
        verdict = "?"
        cv_json = d / "story_coverage.json"
        if cv_json.exists():
            try:
                summary = json.loads(cv_json.read_text(encoding="utf-8"))
                verdict = summary.get("verdict", "?")
            except (OSError, ValueError):
                pass
        results.append({
            "timestamp": d.name,
            "verdict": verdict,
            "dir": d,
            "html_path": (d / "story_coverage.html"),
            "has_pytest_html": (d / "report.html").exists(),
        })
    return results


def clean_artifacts(scope: str, *, preserve_code: bool = False) -> None:
    """Wipe generated artifacts inside the active project's folders.

    scope='gherkin' → wipes feature/*.feature in addition to the framework code.
    scope='tests'   → leaves feature/ alone; just wipes framework code.
    scope='all'     → wipes both.

    NEVER touches user_story/ — source stories are preserved. preserve_code=True
    keeps pages/step_defs/test intact."""
    if scope in ("gherkin", "all"):
        _delete_files(proj_path("feature"), keep=set(), glob="*.feature")
    if not preserve_code:
        _delete_files(proj_path("pages"), keep={"base_page.py", "__init__.py"}, glob="*.py")
        _delete_files(proj_path("step_defs"), keep={"__init__.py"}, glob="*.py")
        _delete_files(proj_path("test"), keep={"__init__.py"}, glob="test_*.py")
        reset_pytest_plugins()
        reset_locators()


def syntax_check_generated() -> tuple[bool, list[str]]:
    errors: list[str] = []
    pages = proj_path("pages")
    steps = proj_path("step_defs")
    tests = proj_path("test")
    targets: list[Path] = []
    targets.extend([p for p in pages.glob("*.py") if p.name not in ("__init__.py",)])
    targets.extend([p for p in steps.glob("*.py") if p.name != "__init__.py"])
    targets.extend(tests.glob("test_*.py"))
    proj_root = ws.project_dir(current_project())
    for f in targets:
        try:
            ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as e:
            try:
                label = f.relative_to(proj_root)
            except ValueError:
                label = f.name
            errors.append(f"{label}: {e.msg} (line {e.lineno})")
    return (not errors, errors)


def _shorten(value: object, limit: int = 80) -> str:
    s = str(value).replace("\n", " ").strip()
    return s if len(s) <= limit else s[:limit - 1] + "…"


def _format_tool_use(block: dict, state: dict | None = None) -> str:
    """Translate a Claude tool_use block into one human-readable activity line.
    Reads what the agent is ACTUALLY doing — no fabrication. Also bumps activity
    counters in `state` (tool count, files touched) so the heartbeat can show
    progress stats instead of just 'still alive'."""
    name = (block.get("name") or "").strip()
    inp = block.get("input") or {}
    short_name = name.replace("mcp__playwright__", "")

    # ---- Activity stats ----
    if state is not None:
        state["tool_calls_total"] = state.get("tool_calls_total", 0) + 1
        state.setdefault("tool_counts", {})
        state["tool_counts"][short_name] = state["tool_counts"].get(short_name, 0) + 1
        # Track files touched
        for path_key in ("file_path", "path", "filename"):
            p = inp.get(path_key)
            if p:
                state.setdefault("files_touched", set()).add(str(p))
                break

    if name == "mcp__playwright__browser_navigate":
        return f"🌐 Navigating to {_shorten(inp.get('url', '?'), 100)}"
    if name == "mcp__playwright__browser_click":
        target = inp.get("element") or inp.get("ref") or "element"
        return f"👆 Clicking {_shorten(target, 80)}"
    if name == "mcp__playwright__browser_type":
        target = inp.get("element") or inp.get("ref") or "input"
        text = inp.get("text", "")
        if "password" in str(target).lower() or "passw" in str(target).lower():
            text = "•" * len(str(text))
        return f"⌨ Typing into {_shorten(target, 50)}: {_shorten(text, 30)}"
    if name == "mcp__playwright__browser_fill_form":
        fields = inp.get("fields", []) or []
        names = ", ".join(_shorten(f.get("name") or f.get("element") or "?", 20)
                          for f in fields[:4])
        more = f" (+{len(fields)-4} more)" if len(fields) > 4 else ""
        return f"📝 Filling form: {names}{more}"
    if name == "mcp__playwright__browser_snapshot":
        return "📸 Capturing accessibility snapshot of current page"
    if name == "mcp__playwright__browser_wait_for":
        target = inp.get("text") or inp.get("textGone") or inp.get("time")
        return f"⏳ Waiting for {_shorten(target, 80)}"
    if name == "mcp__playwright__browser_take_screenshot":
        return f"📷 Saving screenshot: {_shorten(inp.get('filename', 'page.png'), 60)}"
    if name == "mcp__playwright__browser_press_key":
        return f"⌨ Pressing key: {inp.get('key', '?')}"
    if name == "mcp__playwright__browser_hover":
        return f"🖱 Hovering over {_shorten(inp.get('element', '?'), 60)}"
    if name == "mcp__playwright__browser_select_option":
        return f"🔽 Selecting {_shorten(inp.get('values', '?'), 60)} in {_shorten(inp.get('element', '?'), 40)}"
    if name == "mcp__playwright__browser_handle_dialog":
        return f"💬 Handling dialog: {inp.get('action', '?')}"
    if name == "mcp__playwright__browser_navigate_back":
        return "⬅ Browser back"
    if name == "mcp__playwright__browser_close":
        return "🚪 Closing browser"
    if name == "mcp__playwright__browser_evaluate":
        fn = _shorten(inp.get("function", "?"), 80)
        return f"🧪 Evaluating JS: {fn}"
    if name == "Write":
        path = inp.get("file_path", "?")
        return f"✍ Writing {_shorten(path, 80)}"
    if name == "Read":
        path = inp.get("file_path", "?")
        return f"📖 Reading {_shorten(path, 80)}"
    if name == "Edit":
        path = inp.get("file_path", "?")
        return f"✏ Editing {_shorten(path, 80)}"
    if name == "Glob":
        return f"🔍 Glob: {_shorten(inp.get('pattern', '?'), 80)}"
    if name == "Grep":
        return f"🔎 Grep: {_shorten(inp.get('pattern', '?'), 60)}"
    if name == "Bash":
        return f"💻 Bash: {_shorten(inp.get('command', '?'), 100)}"
    # Unknown tool — show name + first input key for context
    keys = list(inp.keys())[:3]
    return f"🔧 {short_name}({', '.join(keys)})"


_COUNT_SUFFIX_RE = re.compile(r"^(.+?)(\s+\(×(\d+)\))?$")  # × is U+00D7


_HEARTBEAT_PREFIX = "⏱ "


def _emit_heartbeat(log_buf: list[str], phrase: str) -> None:
    """Emit a heartbeat line — but if the LAST line is already a heartbeat,
    REPLACE it in place. The result: the activity log shows ONE ticking
    heartbeat line that updates every poll, not a wall of identical rows."""
    line = f"{_HEARTBEAT_PREFIX}{phrase}"
    if log_buf and log_buf[-1].startswith(_HEARTBEAT_PREFIX):
        log_buf[-1] = line
    else:
        list.append(log_buf, line)


def _emit(log_buf: list[str], line: str) -> None:
    """Append `line` to log_buf, but if it matches the previous line (ignoring
    any '(×N)' suffix), merge them by bumping the count instead of duplicating.
    Turns 15 identical "🧠 thinking: …" rows into ONE row '… (×15)'.

    When a real event arrives after a heartbeat-only stretch, the heartbeat
    line is REMOVED so the timeline reads cleanly (heartbeats are filler that
    only exist to reassure the user during silence — once a real event lands,
    the filler is no longer informative)."""
    if not line:
        return
    # If the last line is a heartbeat, drop it before appending the real event.
    # Heartbeats are filler — once a real event arrives they have no value.
    if log_buf and log_buf[-1].startswith(_HEARTBEAT_PREFIX):
        log_buf.pop()
    if not log_buf:
        list.append(log_buf, line)
        return
    prev = log_buf[-1]
    m_new = _COUNT_SUFFIX_RE.match(line)
    m_prev = _COUNT_SUFFIX_RE.match(prev)
    if not m_new or not m_prev:
        list.append(log_buf, line)
        return
    base_new = m_new.group(1)
    base_prev = m_prev.group(1)
    if base_new != base_prev:
        list.append(log_buf, line)
        return
    count_prev = int(m_prev.group(3)) if m_prev.group(3) else 1
    count_new = int(m_new.group(3)) if m_new.group(3) else 1
    log_buf[-1] = f"{base_new}  (×{count_prev + count_new})"


def _flush_buffered(log_buf: list[str], buf_map: dict, idx,
                    prefix: str, soft_limit: int = 220) -> None:
    """Emit a log line once the buffered text for content-block `idx` contains
    a sentence break OR exceeds `soft_limit` chars. Leaves any trailing
    incomplete sentence in the buffer."""
    text = buf_map.get(idx, "")
    if not text:
        return
    # Find a good break: newline OR sentence end + space
    cut = -1
    for marker in ("\n", ". ", "? ", "! "):
        pos = text.rfind(marker)
        if pos > cut:
            cut = pos + (len(marker) - 1)  # keep the punctuation
    if cut < 0 and len(text) < soft_limit:
        return  # wait for more
    if cut < 0:
        cut = soft_limit
    line = text[: cut + 1].strip()
    if line:
        _emit(log_buf, f"{prefix}{_shorten(line, 220)}")
    buf_map[idx] = text[cut + 1:]


def _format_stream_event(line: str, log_buf: list[str],
                          state: dict | None = None) -> None:
    """Parse one stream-json line from `claude --output-format stream-json` and
    append human-readable lines to log_buf. `state` is an optional mutable dict
    used to ACCUMULATE thinking-delta / text-delta chunks across calls so the
    user sees Claude's reasoning streaming in real time, not just at the end
    of a content block. Falls back to raw output on JSON parse failures."""
    import json as _json
    if state is None:
        state = {}
    state.setdefault("thinking_buf", {})   # block_index -> str
    state.setdefault("text_buf", {})
    state.setdefault("block_kinds", {})    # block_index -> "thinking|text|tool_use"
    state.setdefault("delta_kinds_seen", set())  # which block kinds streamed via deltas

    raw = (line or "").strip()
    if not raw:
        return
    try:
        event = _json.loads(raw)
    except ValueError:
        _emit(log_buf, raw)
        return
    if not isinstance(event, dict):
        _emit(log_buf, raw)
        return
    etype = event.get("type")
    if etype == "system":
        if event.get("subtype") == "init":
            model = event.get("model") or "?"
            _emit(log_buf, f"⚙ Session started · model={model}")
        # other system events ('status:requesting' etc.) are noise — silent.
        return
    if etype == "rate_limit_event":
        # Internal rate-limit telemetry — not actionable for the user. Silent.
        return
    if etype == "assistant":
        msg = event.get("message") or {}
        for block in (msg.get("content") or []):
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                # Skip if text was already streamed via text_delta events.
                if "text" in state["delta_kinds_seen"]:
                    continue
                text = (block.get("text") or "").strip()
                if not text:
                    continue
                for ln in text.splitlines():
                    ln = ln.rstrip()
                    if ln:
                        _emit(log_buf, f"💬 {ln}")
            elif btype == "tool_use":
                # Always emit full tool_use from assistant message (has complete input).
                # The stream_event "starting X …" line gave the announcement; this is
                # the detailed call with args.
                _emit(log_buf, _format_tool_use(block, state))
            elif btype == "thinking":
                # Skip if thinking already streamed via thinking_delta events.
                if "thinking" in state["delta_kinds_seen"]:
                    continue
                # Extended thinking — surface a SHORT summary line so the user
                # sees what Claude is reasoning about (previously skipped, which
                # meant nothing appeared in the log during long reasoning passes).
                t = (block.get("thinking") or "").strip()
                if t:
                    # Take the most informative line: prefer the first non-empty,
                    # otherwise truncate the whole thing.
                    lines = [l.strip() for l in t.splitlines() if l.strip()]
                    snippet = lines[0] if lines else t
                    _emit(log_buf, f"🧠 thinking: {_shorten(snippet, 140)}")
        return
    # Streamed-chunk events from --include-partial-messages: surface tool
    # invocations, thinking deltas, and text deltas as they arrive. This is
    # the activity the user actually wants to see in real time.
    if etype == "stream_event":
        sub = event.get("event") or {}
        if not isinstance(sub, dict):
            return
        sub_type = sub.get("type") or ""
        idx = sub.get("index", 0)

        # ---- content_block_start: announce kind & remember it for deltas ----
        if sub_type == "content_block_start":
            cb = sub.get("content_block") or {}
            if isinstance(cb, dict):
                cb_type = cb.get("type")
                state["block_kinds"][idx] = cb_type
                if cb_type == "tool_use":
                    # Tool name is in the start event; args stream as deltas
                    name = cb.get("name") or "?"
                    short = name.replace("mcp__playwright__", "")
                    _emit(log_buf, f"🔧 starting {short} …")
                elif cb_type == "thinking":
                    state["thinking_buf"][idx] = ""
                elif cb_type == "text":
                    state["text_buf"][idx] = ""
            return

        # ---- content_block_delta: text/thinking chunks streaming in ----
        if sub_type == "content_block_delta":
            delta = sub.get("delta") or {}
            dtype = delta.get("type") if isinstance(delta, dict) else None

            if dtype == "thinking_delta":
                chunk = delta.get("thinking") or ""
                if chunk:
                    state["delta_kinds_seen"].add("thinking")
                    state["thinking_buf"][idx] = state["thinking_buf"].get(idx, "") + chunk
                    _flush_buffered(log_buf, state["thinking_buf"], idx, prefix="🧠 ")
                return

            if dtype == "text_delta":
                chunk = delta.get("text") or ""
                if chunk:
                    state["delta_kinds_seen"].add("text")
                    state["text_buf"][idx] = state["text_buf"].get(idx, "") + chunk
                    _flush_buffered(log_buf, state["text_buf"], idx, prefix="💬 ")
                return

            if dtype == "signature_delta":
                # Opus extended thinking with ENCRYPTED reasoning — content
                # isn't readable, but we count chunks so the user sees Claude
                # is actively reasoning (not stalled). One announcement on first
                # chunk, then heartbeat picks up the count.
                state.setdefault("sig_counts", {})
                state["sig_counts"][idx] = state["sig_counts"].get(idx, 0) + 1
                state["delta_kinds_seen"].add("thinking")  # so assistant block doesn't duplicate
                if state["sig_counts"][idx] == 1:
                    _emit(log_buf, "🧠 Claude is reasoning (extended thinking)…")
                return

            # input_json_delta — tool args streaming in; full input arrives in
            # the assistant message. Silent here.
            return

        # ---- content_block_stop: flush any remainder ----
        if sub_type == "content_block_stop":
            remaining = state["thinking_buf"].pop(idx, "")
            if remaining.strip():
                _emit(log_buf, f"🧠 {_shorten(remaining.strip(), 200)}")
            remaining = state["text_buf"].pop(idx, "")
            if remaining.strip():
                _emit(log_buf, f"💬 {_shorten(remaining.strip(), 200)}")
            return

        # message_start, message_delta, message_stop, signature_delta — silent
        return

    if etype == "message_delta":
        # Top-level (not wrapped in stream_event) — usually just stop_reason. Silent.
        return
    if etype == "user":
        # Tool result echoed back. Usually verbose — only surface failures.
        msg = event.get("message") or {}
        for block in (msg.get("content") or []):
            if isinstance(block, dict) and block.get("is_error"):
                err = block.get("content")
                if isinstance(err, list) and err and isinstance(err[0], dict):
                    err = err[0].get("text", err)
                _emit(log_buf, f"⚠ Tool error: {_shorten(err, 200)}")
        return
    if etype == "result":
        rc = event.get("subtype") or "done"
        total = event.get("duration_ms")
        bits = [f"verdict={rc}"]
        if total:
            bits.append(f"{total/1000:.1f}s")
        # Cost intentionally NOT shown in the UI log — user does not want
        # dollar amounts surfacing during demos.
        _emit(log_buf, f"✓ Claude session done · {' · '.join(bits)}")
        return
    # Unknown event type — keep raw for debugging
    _emit(log_buf, f"· {_shorten(raw, 200)}")


def _redact_command(cmd: list[str]) -> str:
    """Build a clean one-line representation of the subprocess command for the UI log,
    hiding the prompt (now piped via stdin) and the tools list so it doesn't flood."""
    display_parts: list[str] = []
    i = 0
    while i < len(cmd):
        c = cmd[i]
        # Legacy: '-p <prompt>' (kept for backwards compatibility if anyone bypasses claude_command)
        if c == "-p" and i + 1 < len(cmd) and not cmd[i + 1].startswith("--"):
            display_parts.append("-p <prompt>")
            i += 2
            continue
        if c == "--allowedTools":
            display_parts.append("--allowedTools <tools>")
            i += 1
            while i < len(cmd) and not cmd[i].startswith("--"):
                i += 1
            continue
        if c.lower().endswith("claude.cmd") or c.lower().endswith("claude.exe"):
            display_parts.append("claude")
        else:
            display_parts.append(shlex.quote(c))
        i += 1
    # Indicate prompt-via-stdin if we have --print without explicit -p prompt
    if "--print" in cmd and "-p <prompt>" not in " ".join(display_parts):
        display_parts.append("(<prompt via stdin>)")
    return " ".join(display_parts)


_CLAUDE_PHRASES = (
    "Still working — Claude is thinking…",
    "Still working — Playwright MCP is walking the live site…",
    "Still working — capturing selectors / building POMs…",
    "Still working — discovery in progress, no output yet…",
    "Still working — long-running step, hang tight…",
)

_PYTEST_PHRASES = (
    "Test running — browser is interacting with the page",
    "pytest still executing — watch the headed window for the current step",
    "Step in progress — waiting on a Playwright action (click / wait / assert)",
    "Test running — no console output yet, but the browser is busy",
    "Long-running test step — likely an explicit wait or page load",
)

_AUDITOR_PHRASES = (
    "Auditor analysing the pytest report…",
    "Auditor checking each story requirement against tests…",
    "Auditor cross-referencing data assertions with run output…",
    "Auditor reviewing screenshots / generation log…",
    "Auditor writing story_coverage.md…",
)


def _heartbeat_phrases_for(cmd: list[str]) -> tuple[str, ...]:
    """Pick the right rotation of heartbeat phrases based on what we're running.

    Match on COMMAND STRUCTURE, not substring search across the whole cmd:
    every prompt mentions 'pytest' and 'claude' somewhere, so substring matching
    misroutes scouts/auditor into the pytest bucket."""
    if not cmd:
        return ("Still working…",)
    exe = cmd[0].lower()
    # pytest invocation: either `pytest …` or `python -m pytest …`
    is_pytest = exe.endswith("pytest") or exe.endswith("pytest.exe") or (
        "python" in exe and len(cmd) >= 3 and cmd[1] == "-m" and cmd[2] == "pytest"
    )
    if is_pytest:
        return _PYTEST_PHRASES
    # Claude CLI invocation. The prompt is now piped via stdin (not in argv) so
    # we can't peek at it for routing. Default to the generic Claude phrases.
    is_claude = "claude" in exe
    if is_claude:
        return _CLAUDE_PHRASES
    return (
        "Still working…",
        "Process running — no output yet",
        "Long step in progress, hang tight",
    )


def stream_command(cmd, placeholder, log: list[str], story_id: str = "",
                   heartbeat_secs: int = 10, cwd: Path | None = None) -> int:
    """Run a command, stream stdout to the activity panel, and emit a heartbeat
    line every `heartbeat_secs` seconds of silence so long MCP/Claude steps with
    no console output don't make the UI look frozen.

    Runs in `cwd` if given, else the active project's folder.

    `cmd` may be either:
      - a list[str]  → no stdin, run as-is (pytest, generic commands)
      - a tuple (list[str], str)  → first element is argv, second is text to
        pipe via stdin. Used by `claude_command()` so huge prompts don't blow
        through Windows' 8KB cmdline limit.
    """
    stdin_text: str | None = None
    if isinstance(cmd, tuple) and len(cmd) == 2 and isinstance(cmd[1], str):
        cmd, stdin_text = list(cmd[0]), cmd[1]

    proc_cwd = str(cwd or ws.project_dir(current_project()))
    display = _redact_command(cmd)
    log.append(f"$ {display}")
    if story_id:
        append_process_log(story_id, f"exec: {display}")
    placeholder.code("\n".join(log[-500:]) or "(no output)", language="bash")

    try:
        process = subprocess.Popen(
            cmd,
            cwd=proc_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
            text=True,
            encoding="utf-8",       # prompt contains Unicode (═ · → 🧠 etc.)
            errors="replace",       # never crash on unmappable bytes
            bufsize=1,
            env=build_env(),
        )
    except FileNotFoundError as exc:
        log.append(f"ERROR: {exc}")
        if story_id:
            append_process_log(story_id, f"ERROR FileNotFound: {exc}")
        placeholder.code("\n".join(log[-500:]), language="bash")
        return 127

    log.append(f"(pid {process.pid} started)")
    if story_id:
        append_process_log(story_id, f"pid {process.pid} started")
    placeholder.code("\n".join(log[-500:]), language="bash")

    # Pipe the prompt via stdin (for claude_command's huge prompts).
    if stdin_text is not None and process.stdin is not None:
        try:
            process.stdin.write(stdin_text)
            process.stdin.close()
        except Exception as exc:
            log.append(f"ERROR writing stdin: {exc}")

    # Drain stdout from a worker thread — on Windows we can't select() on a pipe,
    # so the only portable way to support timeouts (= heartbeats) is a queue.
    assert process.stdout is not None
    output_q: queue.Queue = queue.Queue()
    SENTINEL = object()

    def _drain(stream, q):
        try:
            for line in stream:
                q.put(line.rstrip())
        finally:
            q.put(SENTINEL)

    drain_thread = threading.Thread(target=_drain, args=(process.stdout, output_q),
                                    daemon=True)
    drain_thread.start()

    # Streaming mode — if the command is `claude … --output-format stream-json …`,
    # every stdout line is a JSON event we parse into human-readable activity.
    # For pytest / generic commands we just pass lines through verbatim.
    is_claude_json = (
        len(cmd) >= 1 and "claude" in cmd[0].lower()
        and "--output-format" in cmd and "stream-json" in cmd
    )
    # State for accumulating thinking/text deltas across consecutive stream events.
    stream_state: dict = {}
    started = time.monotonic()
    last_log_len = len(log)
    # Reset any stale stop signal so an old click doesn't fire this run
    _clear_stop_signal()
    while True:
        # Check for user Stop signal (writable from any Streamlit tab)
        if _stop_signal_fresh():
            try:
                process.kill()
            except Exception:
                pass
            _emit(log, "🛑 STOP requested by user — subprocess killed")
            placeholder.code("\n".join(log[-500:]), language="bash")
            _clear_stop_signal()
            # Drain the queue best-effort so we exit the loop
            try:
                process.wait(timeout=5)
            except Exception:
                pass
            break
        try:
            item = output_q.get(timeout=heartbeat_secs)
        except queue.Empty:
            # ONE honest heartbeat — only if nothing has been logged since
            # the last check. No rotation, no fabrication of what's happening.
            elapsed = int(time.monotonic() - started)
            if len(log) == last_log_len:
                ts = _dt.datetime.now().strftime("%H:%M:%S")
                # Honest heartbeat — only fires when NOTHING new arrived in
                # `heartbeat_secs`. For Claude runs, include reasoning-chunk
                # counts so the user sees progress during extended thinking
                # (the encrypted signature_delta stream).
                if is_claude_json:
                    sig_total = sum((stream_state.get("sig_counts") or {}).values()) \
                        if isinstance(stream_state, dict) else 0
                    tool_total = stream_state.get("tool_calls_total", 0)
                    files = stream_state.get("files_touched") or set()
                    tool_counts = stream_state.get("tool_counts") or {}
                    parts = []
                    if tool_total:
                        parts.append(f"{tool_total} tool calls")
                    if files:
                        parts.append(f"{len(files)} files touched")
                    # Surface the top-3 tools by frequency
                    if tool_counts:
                        top = sorted(tool_counts.items(), key=lambda x: -x[1])[:3]
                        breakdown = ", ".join(f"{n}×{c}" for n, c in top)
                        parts.append(f"top tools: {breakdown}")
                    if sig_total:
                        parts.append(f"{sig_total} reasoning chunks")
                    if parts:
                        phrase = "Claude active — " + " · ".join(parts)
                    else:
                        phrase = "Claude session still alive — waiting on next event"
                elif any("pytest" in p.lower() for p in cmd):
                    phrase = "pytest still running — waiting on a Playwright action"
                else:
                    phrase = "Process running — no output yet"
                # Build a heartbeat line that OVERWRITES any previous heartbeat
                # rather than piling up identical-looking rows.
                heartbeat_phrase = (
                    f"{phrase} · pid {process.pid} · {elapsed}s elapsed (last update {ts})"
                )
                _emit_heartbeat(log, heartbeat_phrase)
                if story_id:
                    # Persist to the on-disk log only every N heartbeats so we
                    # don't pollute the process_log with replaced lines.
                    if elapsed % 30 < heartbeat_secs:
                        append_process_log(story_id, heartbeat_phrase)
                placeholder.code("\n".join(log[-500:]), language="bash")
            last_log_len = len(log)
            continue

        if item is SENTINEL:
            break
        if is_claude_json:
            before = len(log)
            _format_stream_event(item, log, state=stream_state)
            for new_line in log[before:]:
                if story_id:
                    append_process_log(story_id, new_line)
        else:
            log.append(item)
            if story_id:
                append_process_log(story_id, item)
        last_log_len = len(log)
        placeholder.code("\n".join(log[-500:]), language="bash")

    code = process.wait()
    drain_thread.join(timeout=2)
    total = int(time.monotonic() - started)
    log.append(f"--- exit code {code} (took {total}s) ---")
    if story_id:
        append_process_log(story_id, f"exit {code} after {total}s")
    placeholder.code("\n".join(log[-500:]), language="bash")
    return code


def claude_command(prompt: str, tools: list[str], model: str | None = None) -> tuple[list[str], str]:
    """Invoke Claude Code CLI in stream-json mode so every assistant message AND
    every tool_use event arrives on stdout as a separate JSON line.

    Returns (cmd_args, stdin_text). The PROMPT IS NOT in cmd_args — it's piped
    via stdin. On Windows, cmd.exe limits command lines to ~8KB; our generation
    prompts exceed that, so passing `-p <huge prompt>` causes `The command line
    is too long.` Piping via stdin sidesteps the limit entirely.

    `model` selects which Claude model. Default (None) uses Opus 4.7 — slow but
    deep. For pure text-to-text tasks (Gherkin generation, Auditor report) we
    pass `claude-sonnet-4-6` which is 3-5× faster with no quality loss for
    those tasks. Opus stays for the Framework generation where MCP discovery
    and code synthesis benefit from extended reasoning."""
    cli = claude_path() or "claude"
    cmd = [
        cli, "--print",  # non-interactive; prompt comes from stdin
        "--permission-mode", "bypassPermissions",
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--verbose",
    ]
    if model:
        cmd.extend(["--model", model])
    cmd.extend(["--allowedTools", *tools])
    return cmd, prompt


def user_data_path() -> Path:
    """Path to the active project's test-data sidecar (user_data.json)."""
    return proj_path("user_data.json")


def _read_user_data_text() -> str:
    """Raw text of the active project's user_data.json (or '' if missing/empty)."""
    if not current_project():
        return ""
    p = user_data_path()
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Multi-format test-data ingestion
# ---------------------------------------------------------------------------
# The user can upload .json / .csv / .tsv / .xlsx / .xls. Every format is
# converted to a canonical user_data.json (list-of-dicts for tabular data,
# original object for JSON). The runtime `test_data` fixture in conftest.py
# only ever reads user_data.json, so step defs stay format-agnostic.
# The original file is also preserved at `user_data.<ext>` so the user can
# download/inspect it later, and Claude can read it if needed.

USER_DATA_SUPPORTED_EXTENSIONS = ("json", "csv", "tsv", "xlsx", "xls")

# Stop-signal file. The sidebar Stop button writes this; stream_command polls
# it every heartbeat tick. When a fresh signal (<5 min old) is detected, the
# running subprocess is killed.  Cross-tab usage: if a run is stuck and the
# main tab is blocked, open this Streamlit URL in a SECOND browser tab and
# click Stop — that new session can write the file freely.
STOP_SIGNAL_PATH = PROJECT_ROOT / ".stop_signal"


def _stop_signal_fresh() -> bool:
    """True if a stop signal file exists and was created within the last 5 min."""
    try:
        if not STOP_SIGNAL_PATH.exists():
            return False
        age = time.time() - STOP_SIGNAL_PATH.stat().st_mtime
        return age < 300
    except OSError:
        return False


def _clear_stop_signal() -> None:
    try:
        if STOP_SIGNAL_PATH.exists():
            STOP_SIGNAL_PATH.unlink()
    except OSError:
        pass


def _write_stop_signal(reason: str = "user_clicked_stop") -> None:
    try:
        STOP_SIGNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        STOP_SIGNAL_PATH.write_text(
            f"{reason}\n{_dt.datetime.now().isoformat()}\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _csv_bytes_to_json_text(raw: bytes, delimiter: str = ",") -> tuple[str | None, str | None]:
    import csv as _csv
    import io
    import json as _json
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return None, "Could not decode CSV/TSV (tried utf-8 and latin-1)."
    try:
        rows = list(_csv.DictReader(io.StringIO(text), delimiter=delimiter))
    except _csv.Error as exc:
        return None, f"CSV parse error: {exc}"
    if not rows:
        return "[]", "(CSV had no data rows — saved as empty array)"
    # Strip whitespace from keys and values for cleaner downstream use
    rows = [{(k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
             for k, v in row.items()} for row in rows]
    return _json.dumps(rows, indent=2, ensure_ascii=False), None


def _excel_bytes_to_json_text(raw: bytes) -> tuple[str | None, str | None]:
    """Parse the FIRST sheet of an .xlsx/.xls workbook into list-of-dicts.
    Row 1 is treated as headers. Empty rows are skipped."""
    try:
        import openpyxl  # type: ignore[import-untyped]
    except ImportError:
        return None, ("Excel parsing requires openpyxl. Install with: "
                      "pip install openpyxl")
    import io
    import json as _json
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
    except Exception as exc:
        return None, f"Could not open Excel file: {exc}"
    sheet = wb.active
    if sheet is None:
        return "[]", "(workbook had no active sheet)"
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return "[]", "(sheet was empty)"
    raw_header = rows[0]
    header = []
    for i, cell in enumerate(raw_header):
        if cell is None or str(cell).strip() == "":
            header.append(f"col{i + 1}")
        else:
            header.append(str(cell).strip())
    data: list[dict] = []
    for row in rows[1:]:
        if all(c is None or (isinstance(c, str) and not c.strip()) for c in row):
            continue
        entry = {}
        for h, v in zip(header, row):
            if v is None:
                entry[h] = ""
            elif isinstance(v, (int, float)):
                entry[h] = v
            else:
                entry[h] = str(v).strip()
        data.append(entry)
    return _json.dumps(data, indent=2, ensure_ascii=False), None


def convert_uploaded_to_json(filename: str, raw_bytes: bytes) -> tuple[str | None, str | None]:
    """Dispatch on file extension. Returns (json_text, status_or_error)."""
    import json as _json
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    if ext == "json":
        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None, "JSON must be UTF-8 encoded."
        try:
            data = _json.loads(text)
        except ValueError as exc:
            return None, f"Not valid JSON: {exc}"
        if not isinstance(data, (dict, list)):
            return None, "Top-level JSON must be an object or an array."
        # Re-serialise so we strip BOM and normalise indentation
        return _json.dumps(data, indent=2, ensure_ascii=False), None
    if ext == "csv":
        return _csv_bytes_to_json_text(raw_bytes, delimiter=",")
    if ext == "tsv":
        return _csv_bytes_to_json_text(raw_bytes, delimiter="\t")
    if ext in ("xlsx", "xls"):
        return _excel_bytes_to_json_text(raw_bytes)
    return None, (
        f"Unsupported file type: .{ext}. "
        f"Allowed: {', '.join('.' + e for e in USER_DATA_SUPPORTED_EXTENSIONS)}"
    )


def parse_user_data(text: str) -> tuple[object | None, str | None]:
    """Returns (parsed, error_message). parsed is dict / list / None. error_message
    is None on success, otherwise a short reason for the UI."""
    text = (text or "").strip()
    if not text:
        return None, None
    import json
    try:
        data = json.loads(text)
    except ValueError as exc:
        return None, f"Not valid JSON: {exc}"
    if not isinstance(data, (dict, list)):
        return None, "Top-level JSON must be an object or an array of objects."
    if isinstance(data, list):
        if not all(isinstance(row, dict) for row in data):
            return None, "JSON arrays must contain only objects (one per scenario row)."
    return data, None


def log_event(msg: str) -> None:
    """Append a timestamped line to the visible activity log."""
    ts = _dt.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    if "log" not in st.session_state:
        st.session_state.log = []
    st.session_state.log.append(line)


def initialize_session() -> None:
    """Clean slate for the *UI session only*: wipe session_state on fresh page
    load so the user always starts from a blank slate on refresh.

    Project folders under workspace/<project>/ are NOT touched — they remain the
    persistent source of truth, retrievable by selecting the project/story."""
    if st.session_state.get("session_initialized"):
        return
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.session_initialized = True
    st.session_state.log = []
    st.session_state.last_run = "never"
    st.session_state.gherkin_done = False
    st.session_state.framework_done = False
    log_event("Session initialized — awaiting user story")


def render_status_pills() -> None:
    cli = claude_path() is not None
    java = java_available()
    pills = [
        ("Claude CLI", "Connected" if cli else "Not installed", "ok" if cli else "bad"),
        ("Playwright MCP", "Headless", "ok"),
        ("Allure", "Available" if java else "Disabled", "ok" if java else "warn"),
    ]
    html = "".join(
        f'<span class="status-pill {klass}">'
        f'<span class="dot"></span><span><strong>{label}</strong> · {value}</span>'
        f"</span>"
        for label, value, klass in pills
    )
    st.markdown(html, unsafe_allow_html=True)


def render_summary_line(stories: int, features: int, tests: int) -> None:
    parts = [
        f'<span><span class="num">{stories}</span> stor{"y" if stories == 1 else "ies"}</span>',
        f'<span><span class="num">{features}</span> feature file{"s" if features != 1 else ""}</span>',
        f'<span><span class="num">{tests}</span> test{"s" if tests != 1 else ""}</span>',
    ]
    st.markdown(
        '<div class="summary-line">' + '<span class="sep">|</span>'.join(parts) + "</div>",
        unsafe_allow_html=True,
    )


def render_feature_files(story_id: str) -> None:
    proj = ws.project_dir(story_id)
    feat_dir = proj / "feature"
    files = sorted(feat_dir.glob("*.feature")) if feat_dir.exists() else []
    if not files:
        st.markdown(
            '<div class="empty-state"><strong>No feature files for this story yet.</strong><br>'
            "Click <b>① Generate Gherkin</b>.</div>",
            unsafe_allow_html=True,
        )
        return
    for f in files:
        body = f.read_text(encoding="utf-8")
        with st.expander(f.name, expanded=len(files) <= 3):
            st.code(body, language="gherkin")
            st.download_button(
                "Download", body, file_name=f.name, mime="text/plain",
                key=f"dl_{story_id}_{f.name}", use_container_width=False,
            )


def render_framework_files(story_id: str) -> None:
    proj = ws.project_dir(story_id)
    pages_dir = proj / "pages"
    step_dir = proj / "step_defs"
    tests_dir = proj / "test"
    locators = proj / "mcp-selectors" / "locators.json"
    page_files = sorted([p for p in pages_dir.glob("*.py") if p.name not in ("base_page.py", "__init__.py")]) if pages_dir.exists() else []
    step_files = sorted([p for p in step_dir.glob("*.py") if p.name != "__init__.py"]) if step_dir.exists() else []
    test_files = sorted(tests_dir.glob("test_*.py")) if tests_dir.exists() else []
    if not (page_files or step_files or test_files):
        st.markdown(
            '<div class="empty-state"><strong>No framework code for this story yet.</strong><br>'
            "After feature files exist, click <b>② Generate Test Framework</b>.</div>",
            unsafe_allow_html=True,
        )
        return
    cols = st.columns(3)
    cols[0].metric("Page Objects", len(page_files))
    cols[1].metric("Step defs", len(step_files))
    cols[2].metric("Test files", len(test_files))
    for label, files in [("Page Objects", page_files), ("Step Definitions", step_files), ("Tests", test_files)]:
        if not files:
            continue
        st.markdown(f'<div class="section-heading">{label}</div>', unsafe_allow_html=True)
        for f in files:
            with st.expander(f.relative_to(proj).as_posix()):
                st.code(f.read_text(encoding="utf-8"), language="python")
    if locators.exists() and locators.read_text(encoding="utf-8").strip() not in ("", "{}"):
        st.markdown('<div class="section-heading">Locators (MCP-captured)</div>', unsafe_allow_html=True)
        with st.expander("mcp-selectors/locators.json"):
            st.code(locators.read_text(encoding="utf-8"), language="json")


def render_test_runner(story_id: str, framework_ready: bool) -> str | None:
    """Render the per-test runner panel. Returns the pytest target (relative to
    PROJECT_ROOT) the user clicked, or 'all', or None if nothing was clicked."""
    if not framework_ready:
        st.markdown(
            '<div class="empty-state"><strong>Generate the framework first.</strong><br>'
            "Click <b>② Generate Test Framework</b> in the sidebar to create runnable tests "
            "for this story.</div>",
            unsafe_allow_html=True,
        )
        return None

    rows = discover_tests(story_id)
    if not rows:
        st.markdown(
            '<div class="empty-state"><strong>No test files found for this story.</strong><br>'
            "Re-run <b>② Generate Test Framework</b> to regenerate tests.</div>",
            unsafe_allow_html=True,
        )
        return None

    n = len(rows)
    st.markdown(
        f'<div class="runner-header">'
        f'  <div class="runner-title">{n} test{"s" if n != 1 else ""} ready to run</div>'
        f'  <div class="runner-sub">Click <b>▶ Run</b> on any row to run that test alone, '
        f'or <b>Run All</b> below to run them in sequence. Tests run headed so you can watch.</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    clicked: str | None = None

    for idx, row in enumerate(rows, start=1):
        st.markdown('<div class="test-row">', unsafe_allow_html=True)
        cols = st.columns([0.55, 6, 1.2])
        with cols[0]:
            st.markdown(
                f'<div class="test-num">{idx}</div>',
                unsafe_allow_html=True,
            )
        with cols[1]:
            feature_badge = (
                f'<span class="test-meta">📄 {row["feature"]}</span>'
                if row["feature"] else ""
            )
            st.markdown(
                f'<div class="test-title">{row["title"]}</div>'
                f'<div class="test-sub">'
                f'  <span class="test-meta mono">{row["name"]}</span>'
                f'  {feature_badge}'
                f'</div>',
                unsafe_allow_html=True,
            )
        with cols[2]:
            if st.button("▶ Run", key=f"runtest_{story_id}_{idx}", use_container_width=True,
                         help=f"Run only {row['name']} (headed)"):
                clicked = row["rel"]
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="runner-actions">', unsafe_allow_html=True)
    cols = st.columns([1, 1, 4])
    with cols[0]:
        if st.button("▶▶ Run All", key=f"runall_{story_id}", type="primary",
                     use_container_width=True, help="Run every test for this story (headed)"):
            clicked = "all"
    with cols[1]:
        runs = ws.report_runs(story_id)
        html_report = (runs[0] / "report.html") if runs else Path()
        if html_report.exists():
            try:
                st.download_button(
                    "⬇ Download last report",
                    data=html_report.read_bytes(),
                    file_name=f"report_{story_id}.html",
                    mime="text/html",
                    key=f"dl_runner_{story_id}",
                    use_container_width=True,
                    help="Download. The full report is also embedded below in this tab.",
                )
            except OSError:
                st.button("Open last report", disabled=True, use_container_width=True)
        else:
            st.button("⬇ Download last report", disabled=True, use_container_width=True,
                      help="No report yet — run a test first.")
    st.markdown('</div>', unsafe_allow_html=True)

    return clicked


def _runs_with_report(project: str) -> list[Path]:
    """Report run dirs that actually produced a report.html, newest first."""
    return [d for d in ws.report_runs(project) if (d / "report.html").exists()]


def render_test_results(story_id: str) -> None:
    runs = ws.report_runs(story_id)
    latest = runs[0] if runs else Path()
    html_report = latest / "report.html"
    allure = latest / "allure-results"
    screenshots = latest / "screenshots"
    coverage_md = latest / "story_coverage.md"
    coverage_json = latest / "story_coverage.json"
    coverage_html = latest / "story_coverage.html"
    captured_values = latest / "captured_values.json"

    # ============================================================
    # RUN HISTORY — every ③ Run press snapshots its outputs into
    # projects/<id>/reports/runs/<ts>/ so users can browse prior verdicts.
    # The latest run's report is also mirrored to projects/<id>/reports/
    # for the primary embedded view below.
    # ============================================================
    history = discover_run_history(story_id)
    if history:
        st.markdown(
            '<div class="section-heading" style="margin-top: 1.5rem;">'
            '🕘 Run history</div>',
            unsafe_allow_html=True,
        )
        selected_run = st.session_state.get(f"hist_view_{story_id}")
        for run in history[:25]:  # show last 25 runs
            ts = run["timestamp"]
            v = run["verdict"]
            pill_class = {
                "PASS": "ok", "FAIL": "bad",
                "PARTIAL": "warn", "BLOCKED": "bad",
            }.get(v, "warn")
            cols = st.columns([3, 1.2, 1.2, 1])
            with cols[0]:
                st.markdown(
                    f'<code style="font-family:ui-monospace,monospace;'
                    f'font-size:0.85rem;color:#475569">{ts}</code>',
                    unsafe_allow_html=True,
                )
            with cols[1]:
                st.markdown(
                    f'<span class="status-pill {pill_class}" '
                    f'style="font-size:0.78rem;padding:0.25rem 0.6rem">'
                    f'<span class="dot"></span><strong>{v}</strong></span>',
                    unsafe_allow_html=True,
                )
            with cols[2]:
                if run["html_path"].exists():
                    st.download_button(
                        "⬇ HTML",
                        data=run["html_path"].read_bytes(),
                        file_name=f"story_coverage_{ts}.html",
                        mime="text/html",
                        key=f"dl_hist_{story_id}_{ts}",
                        use_container_width=True,
                    )
            with cols[3]:
                if st.button("View", key=f"view_hist_{story_id}_{ts}",
                             use_container_width=True):
                    st.session_state[f"hist_view_{story_id}"] = ts
                    st.rerun()
        if selected_run:
            chosen = next((r for r in history if r["timestamp"] == selected_run), None)
            if chosen and chosen["html_path"].exists():
                st.markdown(
                    f"**Viewing run `{selected_run}` (verdict: "
                    f"`{chosen['verdict']}`)** — "
                    f"[clear](#) to return to latest"
                )
                if st.button("← Back to latest run",
                             key=f"clear_hist_{story_id}"):
                    st.session_state.pop(f"hist_view_{story_id}", None)
                    st.rerun()
                try:
                    import streamlit.components.v1 as components
                    components.html(
                        chosen["html_path"].read_text(encoding="utf-8", errors="replace"),
                        height=900, scrolling=True,
                    )
                    # When viewing a historical run, skip the "latest" render below.
                    return
                except OSError:
                    pass

    # ============================================================
    # PRIMARY view: our custom Story Coverage HTML report (Auditor)
    # Embedded inline at the top of the tab — large iframe.
    # The pytest-html / Allure reports drop to small fallback links.
    # ============================================================
    if coverage_html.exists() or coverage_md.exists() or coverage_json.exists():
        st.markdown(
            '<div class="section-heading" style="margin-top: 1.5rem;">'
            '📋 Story Coverage Report</div>',
            unsafe_allow_html=True,
        )
        # Verdict pill at the top
        if coverage_json.exists():
            try:
                import json as _json
                verdict_data = _json.loads(coverage_json.read_text(encoding="utf-8"))
                verdict = verdict_data.get("overall_verdict", "")
                summary = verdict_data.get("test_summary") or {}
                badge_class = {"PASS": "ok", "FAIL": "bad", "PARTIAL": "warn"}.get(verdict, "warn")
                summary_line = (
                    f"{summary.get('passed', '?')} passed · "
                    f"{summary.get('failed', '?')} failed · "
                    f"{summary.get('skipped', '?')} skipped"
                    if summary else ""
                )
                st.markdown(
                    f'<div class="status-pill {badge_class}" '
                    f'style="font-size:0.95rem;padding:0.5rem 1rem;margin-bottom:0.75rem;">'
                    f'<span class="dot"></span><span><strong>Verdict: {verdict}</strong>'
                    + (f" · {summary_line}" if summary_line else "")
                    + "</span></span>",
                    unsafe_allow_html=True,
                )
            except (OSError, ValueError):
                pass

        # PRIMARY: Auditor's HTML report inline
        if coverage_html.exists():
            try:
                html_body = coverage_html.read_text(encoding="utf-8", errors="replace")
                import streamlit.components.v1 as components
                components.html(html_body, height=1100, scrolling=True)
                st.download_button(
                    "⬇ Download story_coverage.html",
                    data=coverage_html.read_bytes(),
                    file_name=f"story_coverage_{story_id}.html",
                    mime="text/html",
                    key=f"dl_coverage_{story_id}",
                    use_container_width=False,
                )
            except OSError as exc:
                st.error(f"Could not read story_coverage.html: {exc}")
        else:
            # No HTML yet — fall back to rendering the .md inline
            if coverage_md.exists():
                with st.expander("📖 Coverage report (markdown fallback)", expanded=True):
                    try:
                        st.markdown(coverage_md.read_text(encoding="utf-8"))
                    except OSError:
                        st.caption("(could not read story_coverage.md)")

        # Captured values json — what the test actually recorded
        if captured_values.exists():
            with st.expander("🧾 Captured values (raw captured_values.json)", expanded=False):
                try:
                    st.code(captured_values.read_text(encoding="utf-8"), language="json")
                except OSError:
                    st.caption("(could not read captured_values.json)")

        # Machine-readable verdict
        if coverage_json.exists():
            with st.expander("🧾 Machine-readable verdict (story_coverage.json)", expanded=False):
                try:
                    st.code(coverage_json.read_text(encoding="utf-8"), language="json")
                except OSError:
                    st.caption("(could not read story_coverage.json)")

    # ============================================================
    # Raw pytest-html reports — one per run, newest first. The run the
    # user just triggered (st.session_state["last_report_dir"]) is
    # labelled "Current run" and expanded by default; older runs are
    # available as collapsed history, each with its own download button.
    # ============================================================
    report_runs = _runs_with_report(story_id)
    if report_runs:
        st.markdown('<div class="section-heading" style="margin-top: 1.5rem;">'
                    'Raw pytest artifacts (secondary)</div>',
                    unsafe_allow_html=True)
        current = st.session_state.get("last_report_dir")
        for i, run in enumerate(report_runs):
            is_current = (str(run) == current)
            label = f"{'▶ Current run · ' if is_current else ''}{run.name}"
            with st.expander(label, expanded=is_current or i == 0):
                try:
                    run_html = (run / "report.html").read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    st.error(f"Could not read report.html: {exc}")
                    continue
                components.html(run_html, height=700, scrolling=True)
                st.download_button(
                    "⬇ Download report.html",
                    data=run_html,
                    file_name=f"{story_id}_{run.name}.html",
                    mime="text/html",
                    key=f"dl_{run.name}",
                )

    if allure.exists():
        st.markdown('<div class="section-heading">Serve the Allure dashboard</div>', unsafe_allow_html=True)
        java_prefix = "" if shutil.which("java") else (
            "$env:JAVA_HOME = \"$env:USERPROFILE\\tools\\jdk-21.0.10+7-jre\"; "
            "$env:PATH = \"$env:JAVA_HOME\\bin;$env:PATH\"; "
        )
        st.code(f"{java_prefix}npx allure-commandline serve {allure}", language="powershell")
    if screenshots.exists():
        shots = sorted(screenshots.glob("*.png"))[-6:]
        if shots:
            st.markdown('<div class="section-heading">Latest screenshots</div>', unsafe_allow_html=True)
            cols = st.columns(min(3, len(shots)))
            for idx, shot in enumerate(shots):
                with cols[idx % len(cols)]:
                    st.image(str(shot), caption=shot.name, use_container_width=True)


def feature_count() -> int:
    fdir = proj_path("feature")
    return len(list(fdir.glob("*.feature"))) if fdir.exists() else 0


def test_count() -> int:
    tdir = proj_path("test")
    return len(list(tdir.glob("test_*.py"))) if tdir.exists() else 0


def render_sidebar(stories_n: int, story_id: str,
                   gherkin_done_session: bool, framework_done_session: bool) -> tuple[bool, bool, bool]:
    with st.sidebar:
        st.markdown(
            '<div style="font-size: 1rem; font-weight: 700; color: #0f172a; margin: 0.25rem 0 1rem 0;">Workflow</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-heading" style="margin-top:0;">User stories</div>', unsafe_allow_html=True)

        # ----- Project / story selector (switch between existing stories) -----
        projects = ws.list_projects()
        if projects:
            sel_proj = st.selectbox(
                "Project", projects,
                index=(projects.index(current_project())
                       if current_project() in projects else 0),
            )
            st.session_state.project = sel_proj
            stories = ws.list_stories(sel_proj)
            if stories:
                names = [p.name for p in stories]
                sel_story = st.selectbox(
                    "Story", names,
                    index=(names.index(st.session_state.get("active_story"))
                           if st.session_state.get("active_story") in names else 0),
                )
                st.session_state.active_story = sel_story

        # ----- Upload a .txt story (project derived from filename prefix) -----
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

        if "last_upload_info" in st.session_state:
            st.success("Uploaded: " + st.session_state.last_upload_info)

        # ----- Or paste a story (explicit project name + filename) -----
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
                    st.session_state.log = []
                    st.session_state.last_run = "never"
                    st.rerun()

        story_caption = (
            f"Project `{current_project()}`"
            + (f" · story `{st.session_state.get('active_story', '')}`"
               if st.session_state.get("active_story") else "")
            if current_project() else "Upload or paste a story to begin."
        )
        st.caption(story_caption)

        # ----- Optional test data (JSON / CSV / TSV / Excel) -----
        st.markdown(
            '<div class="section-heading">Test data (optional · JSON / CSV / TSV / Excel)</div>',
            unsafe_allow_html=True,
        )
        data_uploaded = st.file_uploader(
            "Upload data file",
            type=list(USER_DATA_SUPPORTED_EXTENSIONS),
            label_visibility="collapsed",
            key=f"data_upload_{st.session_state.get('data_upload_nonce', 0)}",
            help=(
                "Upload a .json (object or array of objects), a .csv/.tsv (header row + "
                "data rows), or an Excel .xlsx/.xls file (first sheet). It will be "
                "converted to user_data.json and exposed to your tests via the "
                "test_data fixture. The original file is preserved as user_data.<ext>."
            ),
        )
        if data_uploaded is not None and current_project():
            raw_bytes = data_uploaded.read()
            json_text, msg = convert_uploaded_to_json(data_uploaded.name, raw_bytes)
            if json_text is None:
                st.error(msg or "Could not convert file.")
            else:
                # Canonical JSON used by the runtime test_data fixture
                user_data_path().parent.mkdir(parents=True, exist_ok=True)
                user_data_path().write_text(json_text, encoding="utf-8")
                # Persist the ORIGINAL file too so the user can download/inspect
                ext = data_uploaded.name.rsplit(".", 1)[-1].lower() if "." in data_uploaded.name else "bin"
                # Clear any stale original-format files first
                for prev_ext in USER_DATA_SUPPORTED_EXTENSIONS:
                    prev = proj_path(f"user_data.{prev_ext}")
                    if prev != user_data_path() and prev.exists():
                        try:
                            prev.unlink()
                        except OSError:
                            pass
                if ext != "json":
                    try:
                        proj_path(f"user_data.{ext}").write_bytes(raw_bytes)
                    except OSError:
                        pass
                if msg:
                    st.info(msg)
                st.session_state["user_uploaded_data"] = True
                st.session_state.data_upload_nonce = st.session_state.get("data_upload_nonce", 0) + 1
                st.rerun()
        elif data_uploaded is not None and not current_project():
            st.warning("Select or create a project before adding test data.")

        # Test data is stored per project under user_data.json. It persists with
        # the project — no session-scoped purge.
        current_data_text = _read_user_data_text()
        data_edited = st.text_area(
            "Test data JSON",
            current_data_text,
            height=140,
            label_visibility="collapsed",
            placeholder='Optional. Paste JSON like {"productid":"123","Subtotal":48.99} '
                        'OR an array of objects for parameterised rows (positive + negative).',
        )
        if data_edited != current_data_text and current_project():
            if data_edited.strip():
                user_data_path().parent.mkdir(parents=True, exist_ok=True)
                user_data_path().write_text(data_edited, encoding="utf-8")
                st.session_state["user_uploaded_data"] = True
            elif user_data_path().exists():
                try:
                    user_data_path().unlink()
                except OSError:
                    pass
                st.session_state.pop("user_uploaded_data", None)

        # Show parse status + a tiny preview if the project has test data.
        if _read_user_data_text().strip():
            parsed, err = parse_user_data(_read_user_data_text())
            # Detect if there's a preserved original (non-JSON) file
            original_ext = None
            for ext in USER_DATA_SUPPORTED_EXTENSIONS:
                if ext == "json":
                    continue
                if proj_path(f"user_data.{ext}").exists():
                    original_ext = ext
                    break
            origin = f" (auto-converted from .{original_ext})" if original_ext else ""
            if err:
                st.caption(f"⚠ {err}")
            elif isinstance(parsed, list):
                st.caption(
                    f"✓ {len(parsed)} row(s) → Scenario Outline with Examples{origin}"
                )
            elif isinstance(parsed, dict):
                keys = ", ".join(list(parsed.keys())[:5])
                more = "…" if len(parsed) > 5 else ""
                st.caption(f"✓ object with keys: {keys}{more}{origin}")
        else:
            st.caption("No test data — story will be used as-is.")

        st.markdown('<div class="section-heading">Pipeline (3 steps)</div>', unsafe_allow_html=True)

        # Step gating is purely session-state driven. Refresh the page → all three
        # locks reset; the user must always start from ①.
        # ① is enabled whenever a story is present, even after it's been clicked
        # (re-clicks just re-load the same files instantly).
        # ② is locked until ① has been clicked in this session.
        # ③ is locked until ② has been clicked in this session.
        has_active_story = bool(current_project() and st.session_state.get("active_story"))
        if not gherkin_done_session:
            next_step = "gherkin"
        elif not framework_done_session:
            next_step = "framework"
        else:
            next_step = "run"

        gen_clicked = st.button(
            "① Generate Gherkin",
            type="primary" if next_step == "gherkin" and has_active_story else "secondary",
            disabled=not has_active_story,
            help="Generate feature files from your user story. Re-click anytime — the same files re-load.",
        )

        fw_clicked = st.button(
            "② Generate Test Framework",
            type="primary" if next_step == "framework" else "secondary",
            disabled=not gherkin_done_session,
            help="Generate POMs, step defs, and pytest-bdd tests. Unlocked after ① is run in this session.",
        )

        run_clicked = st.button(
            "③ Run All Tests (headed)",
            type="primary" if next_step == "run" else "secondary",
            disabled=not framework_done_session,
            help="Headed pytest run of every test for this story. Run as many times as you like. "
                 "Use the per-test ▶ Run buttons in Test results to run one at a time.",
        )

        # Stop button — writes a signal file that the running subprocess polls
        # every ~10s and kills itself when it sees. Works mid-run if the user
        # opens a SECOND browser tab (Streamlit blocks the main tab while a
        # subprocess runs, but a fresh tab can still render+click this button).
        st.markdown(
            '<div class="section-heading" style="margin-top:1rem;">Run control</div>',
            unsafe_allow_html=True,
        )
        if st.button("🛑 Stop current run",
                     help="Kill the running Claude/pytest subprocess. If the page "
                          "appears frozen, open this URL in a NEW browser tab and "
                          "click here — the new tab can still write the stop signal."):
            _write_stop_signal("sidebar_button")
            log_event("🛑 Stop requested via sidebar button")
            st.rerun()
        if _stop_signal_fresh():
            st.caption("⚠ Stop signal active — next subprocess poll will kill the run.")

        with st.expander("More", expanded=False):
            if st.button("Reset workspace (delete all generated files)"):
                clean_artifacts(scope="gherkin")
                st.session_state.log = []
                st.session_state.last_run = "never"
                log_event("Workspace reset — all generated files deleted")
                st.rerun()
            if st.button("Clear log"):
                st.session_state.log = []
            st.caption(f"Project · `{PROJECT_ROOT.name}`")

    return gen_clicked, fw_clicked, run_clicked


def main() -> None:
    st.set_page_config(page_title="QE Agent", layout="wide", initial_sidebar_state="expanded")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    initialize_session()

    st.markdown(
        '<div class="hero-title"><span class="accent">QE Agent</span></div>'
        '<div class="hero-subtitle">'
        "Convert plain-English user stories into self-healing pytest-bdd tests in "
        "three steps: <b>Gherkin</b> → <b>Framework</b> → <b>Run</b>."
        "</div>",
        unsafe_allow_html=True,
    )

    render_status_pills()

    # The active project + story are set by the sidebar (upload/paste/selector).
    # Render the sidebar first so a just-selected project is reflected this run.
    gherkin_done = bool(st.session_state.get("gherkin_done"))
    framework_done = bool(st.session_state.get("framework_done"))
    story_id = current_project()
    gen_clicked, fw_clicked, run_clicked = render_sidebar(
        0, story_id, gherkin_done, framework_done,
    )
    # Re-read the project after the sidebar (it may have changed it this run).
    story_id = current_project()

    n_stories = len(ws.list_stories(story_id)) if story_id else 0
    if story_id and st.session_state.get("logged_story_id") != story_id:
        log_event(f"Project `{story_id}` selected — {n_stories} stor"
                  f"{'y' if n_stories == 1 else 'ies'}")
        st.session_state.logged_story_id = story_id
    features = story_feature_count(story_id)
    tests_n = story_test_count(story_id)

    render_summary_line(n_stories, features, tests_n)

    # Reset session flags if the project changed.
    if st.session_state.get("flags_for_story") != story_id:
        st.session_state.gherkin_done = False
        st.session_state.framework_done = False
        st.session_state.flags_for_story = story_id
        gherkin_done = False
        framework_done = False

    tab_features, tab_framework, tab_results = st.tabs(
        ["Feature files", "Framework code", "Test results"]
    )
    no_story_msg = (
        '<div class="empty-state"><strong>No project selected.</strong><br>'
        "Upload or paste a user story in the sidebar to begin.</div>"
    )
    runner_target: str | None = None
    with tab_features:
        if not story_id:
            st.markdown(no_story_msg, unsafe_allow_html=True)
        else:
            render_feature_files(story_id)
    with tab_framework:
        if not story_id:
            st.markdown(no_story_msg, unsafe_allow_html=True)
        else:
            render_framework_files(story_id)
    with tab_results:
        if not story_id:
            st.markdown(no_story_msg, unsafe_allow_html=True)
        else:
            runner_target = render_test_runner(story_id, framework_done)
            render_test_results(story_id)

    # Sidebar "Run All" or per-test "▶ Run" both feed the same handler.
    pytest_target = "all" if run_clicked else runner_target

    # Double-click guard: if the same Run target fired less than 5 seconds ago,
    # ignore the second click. Prevents two parallel pytest processes from
    # racing each other for the headed browser + report.html.
    if pytest_target:
        now = time.monotonic()
        last_target = st.session_state.get("last_run_target")
        last_when = st.session_state.get("last_run_when", 0.0)
        if last_target == pytest_target and (now - last_when) < 5.0:
            log_event(f"Ignored duplicate Run click for {pytest_target} (cooldown)")
            pytest_target = None
        else:
            st.session_state.last_run_target = pytest_target
            st.session_state.last_run_when = now

    is_running = gen_clicked or fw_clicked or bool(pytest_target)
    state = ("running", "Running") if is_running else (("ready", "Ready") if st.session_state.log else ("idle", "Idle"))
    st.markdown(
        f'<div class="activity-banner">'
        f'<div class="title">Activity</div>'
        f'<div class="activity-state {state[0]}">{state[1]}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    log_placeholder = st.empty()
    log_placeholder.code(
        "\n".join(st.session_state.log[-500:]) or "Idle. Run an action from the sidebar.",
        language="bash",
    )

    if not claude_path() and (gen_clicked or fw_clicked):
        st.error("Claude Code CLI is not installed. Run: `npm install -g @anthropic-ai/claude-code`.")
        return

    # ---- Button 1 — Generate Gherkin ----
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
            log_event(f"Gherkin done — {n} feature file(s) written, exit {rc}")
            status.update(label=f"Gherkin ready — {n} file(s)",
                          state="complete" if rc == 0 else "error")
        st.session_state.gherkin_done = True
        st.session_state.last_run = _dt.datetime.now().strftime("%H:%M:%S")
        st.rerun()

    # ---- Button 2 — Generate Test Framework ----
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
            log_event(f"Framework done — {n_tests} test file(s) written, exit {rc}")
            status.update(label=f"Framework ready — {n_tests} test(s)",
                          state="complete" if (rc == 0 and ok) else "error")
            for e in errs[:5]:
                st.warning(f"Syntax: {e}")
        st.session_state.framework_done = True
        st.session_state.last_run = _dt.datetime.now().strftime("%H:%M:%S")
        st.rerun()


    # ---- Run Tests (sidebar "Run All" OR per-test ▶ Run from main panel) ----
    if pytest_target:
        project = current_project()
        is_all = pytest_target == "all"
        target = None if is_all else pytest_target
        label = "Run All Tests" if is_all else f"Run {Path(pytest_target).name}"
        log_event(f"{label} clicked — project {project}")
        append_process_log(project, f"{label} clicked")
        # Fresh timestamped report dir for this run.
        run_dir = ws.new_report_run_dir(project)
        # Deterministically register the project's step-def modules. Never rely on
        # the LLM to have populated pytest_plugins — if it didn't, pytest-bdd
        # finds zero steps and every scenario fails with StepDefinitionNotFound.
        registered = sync_pytest_plugins()
        log_event(
            "Step-def modules registered in conftest pytest_plugins: "
            + (", ".join(registered) if registered else "(none found)")
        )
        with st.status(f"Running pytest in headed mode — {label} ...", expanded=True) as status:
            cmd = pytest_headed_cmd(project, run_dir, target)
            log_event(f"Invoking pytest --headed (target={target or 'all'})")
            rc = stream_command(
                cmd, log_placeholder, st.session_state.log,
                story_id=project, cwd=ws.project_dir(project),
            )
            log_event(f"Pytest finished — exit code {rc}")
            status.update(label=f"{label} finished (exit {rc})",
                          state="complete" if rc == 0 else "error")
        st.session_state["last_report_dir"] = str(run_dir)
        # Inline (Python-only) coverage report — reads captured_values.json + the
        # pytest result and writes story_coverage.html/md/json into the run dir.
        collection_failed = rc in (2, 3, 4) and not (run_dir / "report.html").exists()
        try:
            report = write_inline_coverage_report(project, rc, run_dir)
            verdict = report["verdict"]
            ts = report["run_timestamp"]
            log_event(f"📊 Coverage report ready (inline, {verdict}) — report/{ts}/")
        except Exception as exc:
            log_event(f"⚠ Inline coverage report failed: {exc}")
            verdict = "ERROR"
        if collection_failed:
            st.error(
                f"Pytest could not collect tests (exit {rc}) — most often an "
                f"ImportError in conftest.py. The coverage report still opened, "
                f"but you'll likely want to fix imports before rerunning."
            )
        log_event(f"Run reports + coverage saved to report/{run_dir.name}/")
        st.session_state.last_run = _dt.datetime.now().strftime(
            f"%H:%M:%S · {'run-all' if is_all else 'run-single'}"
        )
        st.rerun()


if __name__ == "__main__":
    main()

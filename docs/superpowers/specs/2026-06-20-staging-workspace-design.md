# Staging Workspace — Design Spec

**Date:** 2026-06-20
**Status:** Approved

---

## Problem

Currently, file generation (feature files, POMs, step defs, locators, tests) writes directly into `workspace/<Project>/`. If the generation is bad or the user wants to iterate, generated artifacts pollute the workspace and require manual cleanup.

## Solution

Introduce a **staging workspace** (`temp_workspace/<Project>/`) that mirrors the workspace structure. All generated files land in staging first. The user runs tests from staging, reviews results, and then explicitly promotes files to the real workspace via a confirmation dialog.

---

## Requirements (from user)

1. Do not create any file in `workspace/` during generation. Use `temp_workspace/` instead.
2. `temp_workspace/` follows the same folder structure as `workspace/<Project>/`.
3. When user runs tests from staging, the UI notifies: "Test is run from staging workspace."
4. After test run (while in staging), show: "Move the created project files to workspace. Please confirm" with **Yes** / **No** buttons.
5. On **Yes**: move all generated files to `workspace/<Project>/` using additive merge (never overwrite existing files). Clear the staging folder.
6. On **No**: files remain in staging for further iteration.
7. Once promoted, subsequent test runs execute from `workspace/` directly. No promotion dialog.
8. Multiple stories can accumulate in staging independently.
9. "Promote to Workspace" button is only shown when files are in staging.
10. Core folder structure is unchanged — only agent logic and prompts live there.
11. Existing workspace structure and component mapping are retained.

---

## Architecture: Approach A — Workspace Module Dual-Path

### workspace.py Changes

**New constant:**

```python
TEMP_WORKSPACE_DIR = Path(os.environ.get(
    "QA_TEMP_WORKSPACE_DIR", PROJECT_ROOT.parent / "temp_workspace"
))
```

**Dual-path resolution:**

Key functions gain an optional `staging=False` parameter:

- `project_dir(project, staging=False)` — returns `temp_workspace/<Project>/` when `staging=True`, otherwise `workspace/<Project>/`.
- `ensure_project_dirs(project, staging=False)` — creates canonical subfolders in whichever root.
- `subdir(project, name, staging=False)` — delegates to `project_dir()`.
- `copy_scaffolding(project, staging=False)` — copies templates to the active root.
- `add_story(project, filename, content, staging=False)` — writes story to staging or workspace.
- `story_exists(project, filename, staging=False)` — checks in the active root.
- `write_pytest_ini(project, base_url, staging=False)` — writes to active root.
- `rebuild_reuse_index(project, staging=False)` — scans and writes index in active root.
- `load_reuse_index(project, staging=False)` — reads from active root.
- `new_report_run_dir(project, run_id=None, staging=False)` — creates report dir in active root.
- `report_runs(project, staging=False)` — lists runs from active root.

**New functions:**

- `is_staged(project) -> bool` — returns `True` if `temp_workspace/<Project>/` exists and has content.
- `promote_to_workspace(project) -> dict` — additive merge: walks every canonical subfolder in `temp_workspace/<Project>/`, copies each file to `workspace/<Project>/` only if it doesn't already exist there. Returns `{"copied": [...], "skipped": [...]}`. After copying, removes `temp_workspace/<Project>/`.
- `discard_staging(project)` — removes `temp_workspace/<Project>/` entirely.
- `list_staged_projects() -> list[str]` — scans `temp_workspace/` for project folders.

**Unchanged:**

- `list_projects()` — still scans only `workspace/`.
- `PROJECT_SUBDIRS`, `REUSE_INDEX_NAME` — same constants.
- `derive_project_name()`, `sanitize_filename()` — pure string functions, no path changes.

---

### agent_ui.py Changes

**Session state — new keys:**

- `st.session_state.staging_active` (bool) — `True` when files are in `temp_workspace/`. Set `True` on story upload, set `False` after promotion.

**`proj_path()` becomes staging-aware:**

```python
def proj_path(*parts: str) -> Path:
    staging = st.session_state.get("staging_active", True)
    return ws.project_dir(current_project(), staging=staging).joinpath(*parts)
```

This is the single choke point — all ~30 call sites resolve correctly without changes.

**Story upload/paste flow:**

- On upload, story goes to `temp_workspace/<Project>/user_story/`.
- `st.session_state.staging_active = True`.
- If the story already exists in `workspace/<Project>/user_story/`, detected as already promoted → `staging_active = False`, tests run from workspace.

**Steps 1-3 (Gherkin, Framework, Run Tests):**

No logic changes. They call `proj_path()` which resolves to staging or workspace based on `staging_active`. Claude CLI, pytest, scaffolding all work identically because folder structure is the same.

**Post-test-run — promotion dialog:**

After Step 3 completes, if `staging_active is True`:

1. Banner: "Test completed from staging workspace"
2. Message: "Move the created project files to workspace. Please confirm"
3. File summary (count by folder): e.g., "3 feature, 2 pages, 2 step_defs, 1 test"
4. **Yes** button → `ws.promote_to_workspace(project)`, set `staging_active = False`, show summary
5. **No** button → files stay in staging, card remains visible

**Staging badge (project caption):**

- Staging: `Project ResGate · story ResGate_login.txt · Staging`
- Workspace: `Project ResGate · story ResGate_login.txt · Workspace`

**Reset workspace:**

- In staging mode → clears `temp_workspace/<Project>/`
- In workspace mode → behaves as today

---

### Stepper

No new step. The 3-step stepper (Gherkin → Framework → Run Tests) stays as-is. Promotion is a post-pipeline action, not a pipeline step. `render_promotion_dialog()` renders below test results.

---

### Promotion Dialog UI

```
┌─────────────────────────────────────────────────┐
│  Staging workspace                              │
│                                                 │
│  Test completed from staging workspace.         │
│  Move the created project files to workspace.   │
│  Please confirm.                                │
│                                                 │
│  [ Yes, promote ]    [ No, keep staging ]       │
│                                                 │
│  Files to move: 3 feature, 2 pages, 2 step_defs │
│  1 test, 1 locators.json                        │
└─────────────────────────────────────────────────┘
```

On Yes — success banner: "Promoted 9 files to workspace/ResGate. Staging cleared."
Lists skipped files: "Skipped: pages/page_login.py (already in workspace)"

On No — info note: "Files remain in staging. You can re-run tests or promote later."

---

## Edge Cases

**Multiple stories in staging:** Each story generates files within the same `temp_workspace/<Project>/`. Promotion moves the entire project folder's contents. Matches existing workspace model.

**Re-upload of same story:** If exists in staging → `story_exists()` returns True (proceed to execute). If exists in workspace (promoted earlier) → `staging_active = False`, tests run from workspace.

**App restart / page refresh:** Session state is lost. Detect staging by checking: does `temp_workspace/<Project>/` exist? If yes → `staging_active = True`. If not → `False`.

**Partial promotion failure:** `promote_to_workspace()` copies files one at a time. On failure mid-way, staging folder is NOT deleted — user can retry. Summary reports what was copied vs failed.

**`.gitignore`:** Add `temp_workspace/` to `.gitignore`.

---

## Files Changed

| File | Change |
|------|--------|
| `core/workspace.py` | Add `TEMP_WORKSPACE_DIR`, `staging` param to all path functions, new `promote_to_workspace()`, `discard_staging()`, `is_staged()`, `list_staged_projects()` |
| `core/agent_ui.py` | `proj_path()` staging-aware, story upload targets staging, promotion dialog after Step 3, staging badge, reset workspace staging-aware |
| `.gitignore` | Add `temp_workspace/` |
| `tests/test_workspace.py` | Add tests for staging functions, promote, discard, additive merge |

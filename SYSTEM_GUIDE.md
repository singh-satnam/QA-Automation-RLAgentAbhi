# QE Agent — System Guide

**What this is:** the single source of truth for how the QE Agent is structured,
designed, and operated. Part 1 is for executives and delivery managers
(no code). Part 2 is for engineers extending, debugging, or operating the system.

**Stack:** Python · Streamlit · pytest-bdd · Playwright (via MCP) · Claude Code CLI · Allure / pytest-html

> This guide reflects the **project-scoped workspace** architecture (filename-derived
> projects, flat per-project folders, reuse via `reuse_index.json`). It supersedes
> the older `ARCHITECTURE.md` / `AGENT_FLOW.md`, which described a now-removed
> URL-derived `app_id` + `_shared/` model.

---

# Part 1 — Executive Summary

## What the system does

It turns a **plain-English user story** — written by a QE engineer, PM, or
business analyst — into a **runnable, browser-driven automated test**, complete
with selectors, page objects, step definitions, and an evidence-based report.
The operator uploads a short text file; the system writes the test code, runs it
against the live application, and produces a report showing exactly what the test
observed.

## The flow in one picture

```
   Upload  "RLRG_login.txt"            ┌─────────────────────────────┐
   (the filename's prefix    ───────►  │  Project = "RLRG"           │
    "RLRG" names the project)          │  (all RLRG stories share    │
                                       │   one folder & one test set)│
                                       └──────────────┬──────────────┘
                                                      │
                 ① Generate Gherkin  ────────────────►│  feature/*.feature
                 ② Generate Framework ───────────────►│  pages/ step_defs/ test/
                 ③ Run Tests         ────────────────►│  report/<timestamp>/
                                                      │
                                       ┌──────────────▼──────────────┐
                                       │  Evidence report + history  │
                                       └─────────────────────────────┘
```

## Why it matters (business outcomes)

- **Days → minutes.** A suite that takes a QE engineer 1–2 days to author is
  produced from a paragraph in minutes.
- **Organized by project automatically.** The file's name (e.g. `RLRG_…`,
  `saucedemo_…`, `caedu_…`) decides which project it belongs to. Every story for
  the same project lands in the same place; different projects never mix.
- **Reuse makes each next test cheaper.** Within a project, the agent reuses the
  page objects, step definitions, and selectors it already built — so the second,
  third, and tenth story on the same application are faster and cost less than the
  first. Nothing is duplicated.
- **Never overwrites your work.** Re-uploading the same story is detected and
  refused; existing features and framework code are extended, never deleted.
- **Evidence, not a checkmark.** Every run produces a timestamped report and keeps
  history, so you can see what each test actually saw — not just green/red.

## The three operator actions

| Action | What the operator sees | What the system produces |
|---|---|---|
| **① Generate Gherkin** | "Gherkin ready — N file(s)" | Human-readable Given/When/Then scenarios (positive, negative, boundary) |
| **② Generate Framework** | "Framework ready — N test(s)" | Page objects, step definitions, runnable tests |
| **③ Run** | A live, timestamped test report | Pass/fail evidence + screenshots, with run history |

---

# Part 2 — Technical Guide

## 1. Two top-level areas: `core/` and `workspace/`

The repository cleanly separates **the agent (code)** from **its output (client
data)**.

```
repo/
├── core/                     ← the agent. ONLY code lives here.
│   ├── agent_ui.py           ← Streamlit UI + orchestration
│   ├── workspace.py          ← pure project/path/reuse logic (no Streamlit)
│   ├── prompts/*.md          ← the LLM prompt templates
│   ├── requirements.txt
│   └── .streamlit/
├── workspace/                ← all generated artifacts, one subtree per project
│   └── <project>/            ← e.g. RLRG/, saucedemo/, caedu/
└── tests/                    ← unit tests for the agent itself (workspace.py)
```

**Invariant:** nothing client-specific is ever written into `core/`. The agent
generates **directly into `workspace/<project>/`** (see §5).

## 2. Project identity

A "project" is derived from the **uploaded story filename**, not from any URL or
content hash.

- **Upload:** the project is the substring **before the first underscore** in the
  filename. `RLRG_login_flow.txt → RLRG`. A filename with **no** underscore prefix
  is **rejected** with a UI error.
- **Paste:** the operator supplies a **Project name** field and a **Story
  filename** field explicitly.

Implemented in `workspace.derive_project_name()` / `workspace.sanitize_filename()`.

## 3. The per-project folder layout

Every project is one flat tree (singular folder names):

```
workspace/<project>/
├── user_story/         one .txt per story (never overwritten or deleted)
├── feature/            Gherkin .feature files (unique per feature; create-only)
├── step_defs/          pytest-bdd step definitions
├── pages/              Page Object Model classes + base_page.py
├── test/               pytest-bdd entrypoints
├── mcp-selectors/      selectors discovered by Playwright MCP (locators.json)
├── report/
│   └── <timestamp>/    one folder per test run (report.html, allure-results, …)
├── pytest.ini          generated per project (base_url from the story's URL)
├── conftest.py         generated per project (fixtures / setup / teardown)
└── reuse_index.json    map of known page-methods / step-defs / selectors → file
```

All stories of a project **share** `feature/`, `step_defs/`, `pages/`, `test/`,
and `mcp-selectors/`. There is **no** per-story subfolder and **no** `_shared/`
folder — the project folder *is* the shared layer.

## 4. The pipeline (what each button does)

```
                 ┌───────────────────────────────────────────┐
  user_story/    │ ① Gherkin  (LLM, text→text)               │
  <file>.txt ───►│   reads user_story/<file>                 │──► feature/<feat>.feature
                 │   writes a UNIQUE feature; never deletes  │
                 └─────────────────────┬─────────────────────┘
                                       │
                 ┌─────────────────────▼─────────────────────┐
  feature/*  ───►│ ② Framework (LLM + Playwright MCP)         │──► pages/ step_defs/
                 │   first time → framework_prompt           │    test/ conftest.py
                 │   already has framework → DELTA prompt     │    mcp-selectors/
                 │   (+ reuse_index.json injected)            │
                 │   refreshes reuse_index.json after         │
                 └─────────────────────┬─────────────────────┘
                                       │
                 ┌─────────────────────▼─────────────────────┐
  test/*     ───►│ ③ Run  (pytest-bdd, headed)               │──► report/<timestamp>/
                 │   cwd = workspace/<project>/              │    report.html + allure
                 └─────────────────────┬─────────────────────┘
                                       │
                 ┌─────────────────────▼─────────────────────┐
                 │ Report viewer: current run + per-run hist │
                 └───────────────────────────────────────────┘
```

## 5. How generation actually runs

The agent shells out to the **Claude Code CLI** (`claude --print … --output-format
stream-json`) with the prompt piped on stdin and **`cwd` set to
`workspace/<project>/`**. Because the prompts use relative paths (`user_story/…`,
`feature/`, `pages/`, …), everything the model writes lands inside the project
folder; `core/` is never touched.

Two tokens are substituted into the prompts before they're sent:

- `{{STORY_FILE}}` → the active story's filename (the Gherkin prompt reads
  `user_story/{{STORY_FILE}}`).
- `{{REUSE_INDEX}}` → the JSON contents of `reuse_index.json` (injected into the
  framework **delta** prompt so the model reuses what already exists).

Orchestration lives in `agent_ui.py` (`stream_command`, `claude_command`, and the
`gen_clicked` / `fw_clicked` / run handlers).

## 6. Reuse and efficiency (no `_shared/`, no duplication)

The goal is aggressive reuse with no duplicate code, files, or MCP discovery.
Three mechanisms deliver it:

1. **The flat project folders are the shared store.** Every story writes into the
   same `pages/`, `step_defs/`, `mcp-selectors/`.
2. **`reuse_index.json`** maps known page-object methods, step definitions, and
   selectors to the file that provides them. Built by
   `workspace.rebuild_reuse_index()` after each framework pass and consulted before
   new generation.
3. **Read-before-generate.** Discovery only maps screens not already in
   `mcp-selectors/`; for any story *after the first* in a project, the **delta
   prompt** extends existing POMs and never regenerates `base_page.py`,
   `conftest.py`, fixtures, or an existing method.

## 7. Duplicate handling

On upload/paste, the agent checks `workspace.story_exists(project, filename)`. If
that filename already exists under `user_story/`, it stops and shows
**"same user story exists. Proceed to execute the test"** — nothing is generated
and no file is overwritten. Detection is **by filename**.

## 8. Reports and history

Each run writes a fresh `report/<timestamp>/` (created by
`workspace.new_report_run_dir()`); pytest's `--html` / `--alluredir` point inside
it. The UI report viewer shows the run just triggered ("Current run") expanded,
plus every prior run as collapsed history, each with its own embedded
`report.html` and a download button. `workspace.report_runs()` lists runs newest
first.

## 9. Module map — where to look

| File | Responsibility |
|---|---|
| `core/workspace.py` | **Pure logic, no Streamlit.** Project-name derivation, filename sanitising, per-project paths + folder creation, duplicate check, `base_url` extraction, `pytest.ini` writer, timestamped report dirs + history, `reuse_index.json` build/load. Fully unit-tested in `tests/test_workspace.py`. |
| `core/agent_ui.py` | Streamlit UI (sidebar upload/paste/selectors, tabs, report viewer) + orchestration (subprocess invocation with project `cwd`, the ①/②/③ handlers, pytest run, plugin registration, inline coverage report). |
| `core/prompts/gherkin_prompt.md` | Turns the story into `.feature` files (create-only, unique names, positive/negative/boundary). |
| `core/prompts/framework_prompt.md` | First-time framework build (POMs, base_page, step_defs, test, conftest). |
| `core/prompts/framework_delta_prompt.md` | Incremental build for later stories; reuses via the injected `reuse_index.json`. |
| `core/prompts/scout_*.md`, `synthesis_prompt.md`, `auditor_prompt.md` | Templates for the optional multi-agent discovery/audit path (kept for future use; **not** invoked by the current single-agent flow). |
| `tests/test_workspace.py` | Unit tests for `workspace.py` (project logic, dedupe, reuse index). |

## 10. Extending / debugging — quick pointers

- **Project not created or wrong name?** Check `workspace.derive_project_name()`
  and the upload handler in `agent_ui.py` (filename must be `<project>_<name>.txt`).
- **Generation wrote nothing?** Inspect the activity log for the subprocess `cwd`
  (must be `workspace/<project>/`) and confirm the `{{STORY_FILE}}` /
  `{{REUSE_INDEX}}` tokens were substituted.
- **Duplicates not detected?** Detection is by filename in
  `workspace.story_exists()`; a renamed file counts as new by design.
- **Reuse not happening?** Confirm `reuse_index.json` exists and is populated
  (`workspace.rebuild_reuse_index()` runs after ②), and that ② chose the delta
  prompt (it does when `pages/page_*.py` or `step_defs/*_steps.py` already exist).
- **Report missing/empty?** The HTML report is per-run under `report/<timestamp>/`;
  inline coverage artifacts (`captured_values.json`, `step_trace.json`,
  screenshots) are written by the generated `conftest.py` into the project's
  `report/` — verify the conftest honors those paths.
- **Changing folder names or the pipeline?** `workspace.PROJECT_SUBDIRS` is the
  canonical list; the prompts reference these folder names directly, so keep them
  in sync.

## 11. Design references

The design intent and decision history live in:

- `docs/superpowers/specs/2026-06-13-project-scoped-workspace-layout-design.md`
- `docs/superpowers/plans/2026-06-13-project-scoped-workspace-layout.md`

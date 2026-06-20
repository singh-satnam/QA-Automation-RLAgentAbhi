# QE Agent — Story-to-Test Automation Framework

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![Stack](https://img.shields.io/badge/stack-Playwright%20%2B%20pytest--bdd%20%2B%20Streamlit%20%2B%20Claude%20Code-purple)]()

Turn a plain-English user story into a runnable, browser-driven automated test
in three button clicks. Selectors are discovered against the live application
via Playwright MCP (never hallucinated); generated tests are governed by a
strict captured-values audit log and a "report-is-truth" rule.

---

## Table of contents

1. [The 60-second pitch](#1-the-60-second-pitch)
2. [Architecture at a glance](#2-architecture-at-a-glance)
3. [Quick start](#3-quick-start)
4. [The three-step pipeline](#4-the-three-step-pipeline)
5. [Project structure](#5-project-structure)
6. [Per-app knowledge base (RAG)](#6-per-app-knowledge-base-rag)
7. [Reliability rules — what the agent will and won't do](#7-reliability-rules)
8. [The captured_values API](#8-the-captured_values-api)
9. [Coverage report & run history](#9-coverage-report--run-history)
10. [All prompts in this repo (verbatim)](#10-all-prompts-in-this-repo)
11. [Configuration & environment variables](#11-configuration--environment-variables)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. The 60-second pitch

A QE engineer types a paragraph. Within minutes the system has:

1. Read every Page Object Model (POM) and locator the team has ever built for
   the target application,
2. Re-used what fits the new story,
3. Browsed the live site (headlessly) to discover only the *genuinely new*
   selectors,
4. Written runnable Python test code,
5. Run it against a real browser (headed, so you can watch), and
6. Emitted a human-readable verdict report citing every value the test
   observed.

Every subsequent test on that application costs less and runs faster because
the system retains its learnings as a per-application knowledge base.

When the application's data isn't what the story expects, the system reports
the truth rather than fabricating success.

---

## 2. Architecture at a glance

```
                ┌──────────────────────────┐
                │  Plain-English story     │
                │  (paste / upload .txt)   │
                └────────────┬─────────────┘
                             │
            ┌────────────────▼─────────────────┐
            │  ① Gherkin (LLM)                  │   feature files
            │     Given/When/Then per sentence  │
            └────────────────┬─────────────────┘
                             │
            ┌────────────────▼─────────────────┐
            │  ② Test Framework (LLM + MCP)     │   POMs, step defs,
            │     • Reads app's _shared/        │   locators, tests
            │     • Reuses prior POMs           │
            │     • MCP discovers new selectors │
            └────────────────┬─────────────────┘
                             │
            ┌────────────────▼─────────────────┐
            │  ③ Run (pytest-bdd, headed)       │   pytest report,
            │     • Captures every value        │   captured_values.json
            │     • Records misses + halts      │
            │       on missing data             │
            └────────────────┬─────────────────┘
                             │
            ┌────────────────▼─────────────────┐
            │  Inline coverage report (Python)  │   story_coverage.html,
            │     <100 ms, no LLM call          │   per-run snapshot
            └──────────────────────────────────┘
```

For an executive-grade write-up of the architecture, see
[`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## 3. Quick start

### Prerequisites
- Windows 10/11, macOS, or Linux
- Python 3.11+
- Node.js 18+ (for the Claude Code CLI)
- Chromium installed via Playwright (`python -m playwright install chromium`)
- `claude` CLI, authenticated: `npm install -g @anthropic-ai/claude-code` then `claude login`
- A running target application (e.g. `http://localhost:5173/`)

### Install
```bash
git clone <this-repo-url>
cd RL-Agentic-QEAutomation/core
pip install -r requirements.txt
python -m playwright install chromium
```

The engine is self-contained inside **`core/`** — that's the directory you `cd`
into and run from. It ships as pure code with no app-specific data.

### Where your data goes — `QA_WORKSPACE_DIR`

On first run, the engine creates a **sibling `workspace/` directory** next to
`core/` (i.e. `RL-Agentic-QEAutomation/workspace/projects/`) and stores every
application's automation framework there — POMs, step defs, selectors, and
reports, one isolated project per application (see
[AGENT_FLOW.md](AGENT_FLOW.md) for exactly how that isolation works).

To point the knowledge base somewhere else (e.g. a per-client path), set the
`QA_WORKSPACE_DIR` environment variable before launching:

```bash
# Windows (PowerShell)
$env:QA_WORKSPACE_DIR = "D:\Clients\AcmeCorp\qa-workspace"

# macOS / Linux
export QA_WORKSPACE_DIR=/clients/acmecorp/qa-workspace
```

If unset, it defaults to the sibling `workspace/` directory described above.

### Run the UI
```bash
# from core/
streamlit run agent_ui.py
```

Open **http://localhost:8501**, paste a user story into the textarea, and click
the three pipeline buttons in order. The application-under-test is identified
automatically from the first URL in your story — no manual project naming or
`pytest.ini` editing required.

---

## 4. The three-step pipeline

| Step | What it does | Engine | Output |
|---|---|---|---|
| **① Generate Gherkin** | Converts each sentence of the user story into Given/When/Then steps in a `.feature` file. | Claude (LLM) | `features/*.feature` |
| **② Generate Test Framework** | Reads existing POMs / step defs / selectors for the app; reuses what fits; runs Playwright MCP headlessly for genuinely new flow steps; writes Python test code. | Claude (LLM) + Playwright MCP | `pages/`, `step_defs/`, `tests/`, `mcp-selectors/locators.json` |
| **③ Run All Tests** | Executes the generated test against a real browser (headed). Captures every observed value. After the run, builds the coverage report deterministically in Python. | `pytest --headed` + Python | `reports/report.html`, `reports/story_coverage.html`, `reports/captured_values.json` |

Each step is **gated** by the previous one — ② is locked until ① has run in
the current session; ③ is locked until ② has run. Each step **persists** its
outputs to `workspace/projects/<app_id>/<story_id>/` so the run is resumable.
See [AGENT_FLOW.md](AGENT_FLOW.md) for the full internal call sequence.

---

## 5. Project structure

The repo splits cleanly into **`core/`** (the shippable engine — pure code, no
app data) and a sibling **`workspace/`** (the per-client knowledge base,
created on first run and relocatable via `QA_WORKSPACE_DIR`):

```
RL-Agentic-QEAutomation/
├── ARCHITECTURE.md
├── README.md
│
├── core/                             # ── THE ENGINE — ship this ──
│   ├── agent_ui.py                   # Streamlit UI + orchestrator (~4800 LOC)
│   ├── conftest.py                   # pytest fixtures, CaptureLog, TabRegistry
│   ├── pytest.ini                    # auto-rewritten per story (base_url)
│   ├── requirements.txt
│   ├── user_story.txt                # current story (reset on refresh)
│   │
│   ├── prompts/                      # the 9 LLM prompts as editable .md templates
│   │   ├── gherkin_prompt.md, framework_prompt.md, …
│   │
│   ├── pages/base_page.py            # framework template (shared Playwright helpers)
│   ├── step_defs/__init__.py         # generated POMs/step_defs/tests/selectors/
│   ├── tests/conftest.py             # reports land here per-run, then get archived
│   └── features/, mcp-selectors/, reports/   # … into workspace/projects/<app_id>/
│
└── workspace/                        # ── PER-CLIENT DATA — never ship ──
    └── projects/                     # persistent per-app knowledge base
        ├── localhost_5173/
        │   ├── _shared/              # reusable knowledge for THIS app only
        │   │   ├── pages/
        │   │   ├── step_defs/
        │   │   ├── mcp-selectors/locators.json
        │   │   └── flow_index.json   # {method_name: file} index
        │   │
        │   └── <slug>__<digest>/     # per-story archive
        │       ├── .story_id         # 8-char digest sidecar
        │       ├── user_story.txt
        │       ├── features/, pages/, step_defs/, tests/
        │       └── reports/
        │           ├── story_coverage.html
        │           └── runs/<YYYY-MM-DD_HH-MM-SS>/
        │               ├── story_coverage.html, report.html
        │               └── screenshots/
        │
        └── education_qa_scholastic_ca/
            └── …
```

> Set `QA_WORKSPACE_DIR=/path/to/workspace` to relocate the entire knowledge
> base — e.g. one path per client engagement — without touching `core/`.

---

## 6. Per-app knowledge base (RAG)

Every artifact the agent produces is grouped by **application** (derived from
the first URL in the user story — e.g. `localhost:5173` → `localhost_5173`).

Within each app's folder is a `_shared/` subdirectory containing reusable
Page Object Models, step definitions, MCP-discovered selectors, and a
`flow_index.json` that maps method names to their files.

**On every new story for an existing app**, the agent:
1. Retrieves `_shared/` for that app *before* doing any MCP browser
   discovery.
2. Reads the existing POM methods and step def patterns.
3. Matches each Gherkin step against existing patterns — reuses if a match
   exists; flags for MCP discovery only when genuinely new.
4. After a successful ② / ③, any new POMs / step defs / healed selectors
   are **promoted back** to `_shared/` so the next story inherits them.

**Result:** after the first 2-3 stories on an application, subsequent
stories reuse 80%+ of existing artefacts. Only genuinely new flow verbs
trigger MCP discovery.

---

## 7. Reliability rules

### NO FABRICATION

The user story is the literal contract. Generated tests do **exactly** what
the story names — no more, no less. The agent will not:

- Auto-create application data ("first add Priya so the delete test has
  something to act on").
- Pre-seed the database / API to make the scenario succeed.
- Substitute alternate credentials when the story names specific ones.
- Add `@pytest.fixture(autouse=True)` hooks that mutate app state.
- Write helpers that POST/PUT/DELETE to the app's REST API to "ensure
  preconditions" — HTTP reads for assertions are OK, writes are banned.

If the story says *"delete Priya Sharma"* and Priya isn't in the live
application, the test reports:

> 🚫 **BLOCKED — Locate 'Priya Sharma' on Manage Employees table:**
> Employee 'Priya Sharma' is not present in the Manage Employees table
> for manager 499. The story expects this row to exist; since it does
> not, the delete cannot proceed.

…and halts. The report reflects the truth of the application's data —
bugs and missing data are surfaced, not masked.

### MISSING-DATA / PER-ITEM HANDLING

When a story has multiple independent targets (search A **and** B; delete
X **and** Y), each is handled independently:

- Found → executed, recorded, asserted.
- Not found → recorded via `cap.record_missing()`, loop continues.
- Report shows both outcomes: *"✓ chocolate added to cart, ✗ ice cream
  NOT FOUND (search returned 0 results)"*.

### FULL-ROW DATA SCOPE

When the user provides a sidecar CSV / XLSX / JSON and the story says
"verify the entire file", the agent generates a test that loops over
**every row × every column the story scopes** — no sampling, no first-25
truncation. The auditor marks PARTIAL if the captured assertions don't
match the file's row count.

### REPORT IS THE TRUTH

The HTML report must show every outcome the test saw, with the actual
observed value and timestamps. Helpers like `cap.add` / `cap.assert_match`
/ `cap.record_missing` exist to make this rule mechanical: if the test
saw it, the report shows it.

---

## 8. The `captured_values` API

Step defs receive a `captured_values` fixture (`CaptureLog`) and use it to
record every observation. All entries persist to
`reports/captured_values.json`, which drives the coverage report.

```python
def my_step(captured_values, page):
    # Record an observed value
    captured_values.add("Manager name on toggle", page.locator(".name").inner_text())

    # Direct assertion
    captured_values.assert_match(
        "Welcome banner",
        expected="Nitin Kumar",
        actual=page.locator(".welcome").inner_text(),
    )

    # Arithmetic / aggregate assertions (sum, avg, min, max, count,
    # product, range, median)
    captured_values.assert_sum(
        "Total revenue across departments",
        group="dept_revenues", actual=displayed_total,
    )
    captured_values.assert_percentage(
        "HST is 13% of subtotal",
        part=hst_value, whole=subtotal, expected_pct=13,
    )

    # Per-item miss (loop continues)
    if not search_page.has_results_for(product):
        captured_values.record_missing(
            "Product search", target=product,
            reason="search returned 0 results",
        )
        return

    # Blocking prerequisite (raises AssertionError, scenario halts)
    captured_values.assert_prerequisite(
        "Manager login",
        condition=login_page.is_logged_in(),
        reason="manager_id=499 rejected",
        evidence=login_page.last_error_text(),
    )
```

Full helper list: `add`, `assert_match`, `add_component`, `assert_sum`,
`assert_avg`, `assert_min`, `assert_max`, `assert_count`, `assert_product`,
`assert_range`, `assert_median`, `assert_aggregate`, `assert_difference`,
`assert_percentage`, `assert_ratio`, `assert_in_range`, `record_missing`,
`assert_prerequisite`.

---

## 9. Coverage report & run history

After each ③ Run, a **pure-Python builder** (no LLM) reads
`captured_values.json` + the pytest exit code and emits:

- `reports/story_coverage.html` — styled report with verdict banner,
  assertions, missing items, prerequisites, observed values.
- `reports/story_coverage.md` — Markdown for Slack / email.
- `reports/story_coverage.json` — machine-readable for downstream tooling.

### Verdict hierarchy

| Verdict | Meaning |
|---|---|
| 🚫 BLOCKED | A `cap.assert_prerequisite` failed — the test couldn't begin meaningfully. |
| ❌ FAIL | At least one assertion failed, or pytest exited nonzero. |
| ⚠ PARTIAL | Some items were not found via `cap.record_missing`; rest passed. |
| ✓ PASS | All recorded assertions passed and pytest exited 0. |

### Run history

Each ③ Run snapshots its outputs to
`projects/<app>/<story_id>/reports/runs/<YYYY-MM-DD_HH-MM-SS>/`. The UI's
**Run history** section lists every prior verdict and lets you view that
run's report in-place.

---

## 10. All prompts in this repo

The agent's behaviour is governed by a small set of system prompts kept in
[`agent_ui.py`](./agent_ui.py). Each prompt is a "contract" — non-negotiable
fidelity rules at the top, concrete templates below, hard rules at the
bottom.

| Prompt | Location | Used by |
|---|---|---|
| `GHERKIN_PROMPT` | `agent_ui.py:50` | **① Generate Gherkin** — converts user_story.txt into feature files |
| `FRAMEWORK_PROMPT` | `agent_ui.py:175` | **② Generate Test Framework** — full pipeline path (MCP discovery + POMs + step defs + tests) |
| `FRAMEWORK_DELTA_PROMPT` | `agent_ui.py:587` | **② DELTA mode** — runs when `_shared/` already has artefacts (extend, don't regenerate) |
| `SCOUT_SITEMAP_PROMPT` | `agent_ui.py:530` | Optional — produces a per-page sitemap of clickable destinations |
| `SCOUT_INVENTORY_PROMPT` | `agent_ui.py:556` | Optional — full per-page locator inventory |
| `SCOUT_FLOW_PROMPT` | `agent_ui.py:661` | Optional — story replay scout that captures real selectors per step |
| `SCOUT_EDGE_PROMPT` | `agent_ui.py:703` | Optional — overlay discovery (cookie banners, sign-in modals, iframes) |
| `AUDITOR_PROMPT` | `agent_ui.py:734` | **Legacy** — was used to write the coverage report; replaced by deterministic Python builder |
| `SYNTHESIS_PROMPT` | `agent_ui.py:931` | Optional — synthesises multiple scout outputs into a unified plan |

### `GHERKIN_PROMPT` (① Generate Gherkin) — key rules

- Every meaningful line of `user_story.txt` becomes **at least one** Gherkin
  step. No line is silently dropped, no two are merged.
- Do not invent steps that aren't in the story. No extra "best-practice"
  checks the user didn't ask for.
- Preserve story order. If the story says A then B then C, the scenario
  does A then B then C.
- Every "Verify"/"Check"/"Validate"/"should be"/"is displayed"/"matches"
  becomes ONE explicit `Then` step.
- Negative cases (invalid creds, "user already exists", "out of stock")
  appear as their own step sequence — never skipped or replaced by the
  happy path.
- If a sidecar `user_data.json` is present:
  - **SHAPE A** (object) — substitute values inline; emit explicit Then
    assertions for any expected outcome.
  - **SHAPE B** (array) — Scenario Outline with one Examples row per dict,
    every row included (no truncation). Positive and negative rows alike.
  - **SHAPE C** (CSV reference table) — iterate the array at runtime,
    asserting every row × every column the story scopes.
- Each named target (search "ice cream" AND "chocolate") gets its own step
  so missing items can be individually reported.

### `FRAMEWORK_PROMPT` (② Generate Test Framework — full mode) — key rules

- Every Given/When/Then in the `.feature` MUST have a matching step-def
  function. No step is allowed to be unimplemented — if you don't know how,
  write a step def with a clear `pytest.fail(f"…not implemented…")`.
- Every "Verify" step calls **exactly one** `captured_values.*` method.
- Test order matches story order. No reordering for "convenience".
- If a UI element can't be found, raise `AssertionError` with a descriptive
  message; don't fall through to the next step.
- **NO FABRICATION / NO HIDDEN SETUP** (non-negotiable):
  - The story is the literal contract; the test does exactly what the
    story names.
  - No `@pytest.fixture(autouse=True)` that seeds data.
  - No HTTP writes (`requests.post` / `urllib.request.POST` / etc.) to the
    app's API to "ensure preconditions". Reads for assertions are OK,
    writes are banned.
  - Common bad rationalisations explicitly banned: *"the test needs to
    be idempotent"*, *"the backend persists state"*, *"the user clearly
    wants this to pass"*, *"the fabricated setup is just helper
    plumbing"* — all ruled out.
  - Pre-flight check: *Does this code mutate app data? Was that mutation
    named in the story? If mutation YES and named NO → delete the code,
    use `record_missing` or `assert_prerequisite` instead.*
- **MISSING-DATA / NEGATIVE-PATH** rules:
  - Blocking prerequisite (login, page-open) → use
    `cap.assert_prerequisite(condition=…)` which raises and halts the
    scenario with a clear reason.
  - Per-item miss (one product among many, one row among many) → use
    `cap.record_missing(label, target, reason)` and `continue` the loop.
  - Never silently skip; never wrap missing-data in `try: …: pass`.
- **ROW-COVERAGE rule** — if the story verifies a file or `user_data.json`,
  iterate every row in the scope the story names. No `[:25]` slicing, no
  `.head(N)`, no "first few rows". Final assertion count =
  rows-in-scope × columns-in-scope.
- **FILE DOWNLOADS** — Chromium is configured (via CDP
  `Browser.setDownloadBehavior`) to save downloads natively to
  `~/Downloads` with the server's suggested filename. The test does
  `with page.expect_download(): click_button()` and then asserts the file
  appeared.
- **MULTI-TAB / NEW-WINDOW** — use the `tabs` fixture (`TabRegistry`)
  exposed by conftest.py, not bare `page`.

Hard rules: per-feature isolation (N features → N step-def files → N
tests); live DOM via MCP is the only source of truth for selectors;
step defs call POM methods, never raw Playwright; headless validation
only in ②; `wait_until="domcontentloaded"` + finite timeouts (never
`networkidle` — most storefronts have long-tail tracking traffic that
never settles).

### `FRAMEWORK_DELTA_PROMPT` (② DELTA mode) — key rules

Used when the workspace was forked from an existing per-app `_shared/`
folder. Everything from `FRAMEWORK_PROMPT` applies, **plus**:

- **READ FIRST.** Before generating anything, read every file under
  `/pages/`, `/step_defs/`, and `mcp-selectors/locators.json`. Note class
  names + public method names + locator keys.
- **DIFF the new story** against existing patterns:
  - Steps already covered by an existing pattern → REUSE.
  - Steps that use an existing POM method → call from a new step def.
  - Steps truly new to this app → MCP-discover only those.
- **EXTEND, don't replace.** If a new step belongs to an existing POM
  class, add ONE method; do not rewrite the class.
- **Don't delete existing files** unless the new story explicitly
  contradicts them.
- Final report must list: files MODIFIED (appended to), files CREATED
  (brand-new), files UNCHANGED (intentionally left alone — proof the
  fork was respected).

### `AUDITOR_PROMPT` (legacy)

Originally an LLM agent that read every artefact post-pytest and wrote
the coverage report. **Now replaced** by the deterministic Python builder
[`build_inline_coverage_report()`](./agent_ui.py) which produces the same
sections in <100 ms with zero LLM calls.

The prompt enforces:

- **Verdict hierarchy:** BLOCKED > FAIL > PARTIAL > PASS.
- **Every requirement** in the story becomes EXACTLY ONE row in the
  checklist. No merging, no omission.
- **Every captured_values entry** becomes a row in the report. Don't
  drop duplicates — show all with timestamps so the user sees the trace.
- A story step with **no** matching captured-values entry AND no test
  step is marked `not exercised — step def missing or skipped`.
- **Negative scenarios** get their own section AND a row in the main
  checklist.

### Scout prompts (optional, opt-in)

`SCOUT_SITEMAP_PROMPT`, `SCOUT_INVENTORY_PROMPT`, `SCOUT_FLOW_PROMPT`,
`SCOUT_EDGE_PROMPT` are headless MCP-only agents that produce JSON
artefacts the framework prompt can ingest:

- **SITEMAP** — `mcp-selectors/sitemap.json`: per-page list of clickable
  destinations.
- **INVENTORY** — `mcp-selectors/scout_inventory.json`: confirmed-clickable
  selectors per page, capped at 6 pages × 30 selectors.
- **FLOW** — `mcp-selectors/scout_flow.json`: end-to-end story replay with
  trigger_selector + post-URL + observed_changes per step.
- **EDGE** — `mcp-selectors/scout_edge.json`: cookie banners, sign-in
  modals, iframes, age gates with confirmed dismiss selectors.

All scouts share a `ROLE: <NAME>. EXECUTE IMMEDIATELY. NO PREAMBLE. NO
QUESTIONS. Make real tool calls. Do not summarise — execute.` pattern.

---

## 11. Configuration & environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PLAYWRIGHT_SLOW_MO` | `500` (headed) / `0` (headless) | Per-action delay in ms — slow tests down for demos |
| `STEP_DELAY_SEC` | `1.5` (headed) / `0` (headless) | Delay after each pytest-bdd step |
| `PLAYWRIGHT_DOWNLOADS_DIR` | `~/Downloads` | Where downloaded files land |
| `STREAMLIT_HEADLESS` | unset | If set, Streamlit's own headless mode |

CLI flags for pytest (passed automatically by the runner):
- `--headed` — visible browser
- `--html=reports/report.html --self-contained-html` — pytest-html report
- `--alluredir=reports/allure-results` — Allure raw events

---

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'step_defs.X'` at pytest collection | `tests/conftest.py` references a step_defs file that was deleted | Edit `tests/conftest.py` and remove the stale import |
| Test "passes" but does mysterious things (creates Priya before deleting her, etc.) | LLM fabricated setup despite the rules | Read the relevant step_def file, remove any `@pytest.fixture(autouse=True)` that mutates app state, remove any `urllib.request` POST helpers |
| `gh: command not found` when pushing | GitHub CLI not installed | Use `git remote add origin <https-url>` + `git push -u origin main` directly |
| `Filename too long` when committing on Windows | Windows MAX_PATH limit (260 chars) | `git config core.longpaths true` |
| Auto-fork wipes my working archive | Old auto-fork code with destructive deletes | The current code uses `_archive_has_any_work(story_id)` as a gate — locked when archive has any feature / page / step / test |
| Story I pasted before doesn't load cached files | Story text changed (even whitespace) → different digest | Paste the exact bytes from `projects/<app>/<story_id>/user_story.txt` |
| Coverage report empty | `captured_values.json` empty — step defs didn't call `cap.*` | Audit step defs: every Verify step must call exactly one `captured_values.*` method |

---

## License

Internal — Scholastic QE engineering.

## Contact

Owner: Scholastic QE — see `git log` for commit authorship.

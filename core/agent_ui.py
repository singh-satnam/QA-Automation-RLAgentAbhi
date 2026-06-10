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

PROJECT_ROOT = Path(__file__).resolve().parent
USER_STORY_PATH = PROJECT_ROOT / "user_story.txt"
# Optional sidecar: a JSON file the user can upload alongside the story.
# Story may contain <placeholder> tokens that get filled from this JSON.
# Single-object JSON → one parameterized scenario.
# Array-of-objects JSON → Scenario Outline + Examples table (positive + negative rows).
USER_DATA_PATH = PROJECT_ROOT / "user_data.json"
FEATURES_DIR = PROJECT_ROOT / "features"
PAGES_DIR = PROJECT_ROOT / "pages"
STEP_DEFS_DIR = PROJECT_ROOT / "step_defs"
TESTS_DIR = PROJECT_ROOT / "tests"
CONFTEST_PATH = PROJECT_ROOT / "conftest.py"
LOCATORS_PATH = PROJECT_ROOT / "mcp-selectors" / "locators.json"
DISCOVERY_META_PATH = PROJECT_ROOT / "mcp-selectors" / "discovery_meta.json"
GENERATION_LOG_PATH = PROJECT_ROOT / "generation_log.txt"
REPORTS_DIR = PROJECT_ROOT / "reports"
ALLURE_RESULTS = REPORTS_DIR / "allure-results"
HTML_REPORT = REPORTS_DIR / "report.html"
SCREENSHOT_DIR = REPORTS_DIR / "screenshots"
PROJECTS_DIR = PROJECT_ROOT / "projects"
JRE_HOME = Path(os.environ.get("USERPROFILE", "")) / "tools" / "jdk-21.0.10+7-jre"

ARTIFACT_DIRS = ("features", "pages", "step_defs", "tests", "mcp-selectors", "reports")

USER_STORY_PLACEHOLDER = (
    "# Add one or more user stories below in plain English.\n"
    "# Separate distinct stories with a blank line.\n"
)


GHERKIN_PROMPT = """\
You are operating inside the QE automation framework rooted at the current working directory. \
Read user_story.txt and convert each user story it contains into a Gherkin .feature file under \
/features.

═══════════════════════════════════════════════════════════════════
FIDELITY TO USER STORY — NON-NEGOTIABLE
═══════════════════════════════════════════════════════════════════
1. EVERY meaningful line of user_story.txt becomes AT LEAST ONE Gherkin step. \
No line is silently dropped. No story step is merged with another.
2. Do NOT invent steps that aren't in the story. No extra "best-practice" \
checks the user didn't ask for.
3. Preserve the ORDER from the story. If the story says A then B then C, the \
scenario does A then B then C — never reordered for "convenience".
4. Every line that contains words like "Verify", "Check", "Validate", "should \
be", "should display", "is shown", "is displayed", "matches" → translate into \
ONE explicit `Then` step. Don't bundle multiple verifications into one step.
5. Negative cases (invalid creds, "user already exists", "out of stock") must \
appear as their own step sequence; never skipped or replaced by the happy path.
6. Inline data tables (Field: Value blocks, address blocks, etc.) become \
Gherkin doc-strings or data tables — every key/value preserved.
═══════════════════════════════════════════════════════════════════

ALSO read user_data.json if it exists in the cwd. It is an OPTIONAL sidecar that drives \
parameterisation:

  - SHAPE A — JSON object (one dict at the top level):
      user_data.json contains key/value pairs the story references via <placeholder> tokens.
      Generate ONE Scenario per story. Substitute concrete values in scenario steps directly. \
      If the story has assertion intent (e.g. "Total should be 61.94"), emit explicit Then \
      steps that reference the data values — `Then the Subtotal is "<Subtotal>"` etc. so the \
      generated tests can verify exact values from user_data.json at runtime.

  - SHAPE B — JSON array (list of dicts):
      Each dict is one Example row. Generate a Scenario Outline whose Examples: table has one \
      column per key, **with one Examples row for EVERY dict in the array**. If the array has \
      100 dicts, the Examples table MUST have 100 rows. NEVER truncate to a sample, NEVER cap \
      at 25 / 50 / "first few", NEVER drop "similar-looking" rows. Each row must execute as its \
      own test invocation. Rows may be POSITIVE or NEGATIVE — if a row contains \
      `expected_message`, `should_succeed: false`, `expected_error`, or similar, it is a \
      NEGATIVE row. The Outline MUST include a Then step that asserts the expected outcome \
      explicitly (success path OR exact error). Do NOT soft-pass on "any error".

  - SHAPE C — JSON array used as a REFERENCE TABLE (not parameterisation):
      If the story says things like "verify the downloaded CSV", "compare with the data file", \
      "every row matches", the array is the ground truth the test must check against the \
      live data. In that case, generate ONE Scenario whose Then steps iterate the array at \
      runtime (the step def loads test_data and loops), comparing **every row** the story \
      scopes — full table if the story says "entire CSV / all rows / every value", or only \
      the columns the story names if it scopes them. Either way: NEVER skip rows, NEVER stop \
      at a sample. The number of `cap.assert_match` calls the test ends up emitting must \
      equal (rows the story scopes) × (columns the story scopes).

  - NO user_data.json:
      Generate as before — one Scenario per story, no parameters.

NEGATIVE STEPS INLINE IN THE STORY (no JSON needed)

The user may write negative-path steps directly in user_story.txt, e.g.:
  "enter the below invalid login details"
  "User should not be logged in"
  "Invalid email or password validation message should be displayed"
  "Clear the fields and enter the below valid login details"

Detect these inline negative attempts by these signals:
  - Words like "invalid", "wrong", "incorrect", "bad", "expired" preceding credentials/values
  - Negative assertions like "should not be", "should fail", "should be rejected"
  - Validation/error messages: "validation message should be displayed", \
    "error message should appear", "should show invalid", "should show error"

When present, the .feature MUST include the negative attempt as its OWN explicit step \
sequence BEFORE the positive one:
  Examples (literal, illustrative):
    When the user enters email "invalid@myyahoo.com" and password "wrongpass"
    Then the "Invalid email or password" validation message is displayed
    And the user is not logged in
    When the user clears the email and password fields
    And the user enters email "qauto@myyahoo.com" and password "passw0rd"

Both halves (negative attempt + positive recovery) MUST end up in the same Scenario. \
Preserve the order from the story. Do not skip the negative attempt — it is a first-class \
test case. The validation message text in the assertion must be the EXACT phrase from \
the story (or as close as the story allows).

MISSING-DATA INTENT (when the story expects items but some may not exist live):

Some stories list multiple independent targets — "search ice cream AND chocolate, \
add each to cart" or "delete employees X AND Y". When that happens, Gherkin MUST \
reflect that each target is its own iteration:

  · Prefer a Scenario Outline whose Examples table lists each target on its own row. \
    pytest-bdd then runs one test per row. Missing items affect ONLY that row's \
    verdict, not the others.
  · OR an explicit per-item And-chain so each Then is independently assertable:
        When the user searches for "ice cream"
        Then the result for "ice cream" is recorded (found or not found)
        When the user searches for "chocolate"
        Then the result for "chocolate" is recorded (found or not found)
        And the cart contains every product that WAS found

When the story has a BLOCKING prerequisite (e.g. "log in as manager 503 then …"), \
the very first Then after the login MUST explicitly check it succeeded:
        When the manager submits credentials
        Then the manager is logged in   ← this becomes assert_prerequisite at step-def time

Never collapse a "search A and search B" story into one step "search the catalog". \
Each named target needs its own step so missing items can be individually reported.

Hard rules:
- EXACTLY ONE .feature file per distinct user story. If user_story.txt has N stories, write \
  EXACTLY N .feature files — no more, no fewer.
- Stories are separated by blank lines or numbered headings ("1.", "2.", "Story 1:"). If a single \
  continuous flow has no separator, treat it as ONE story.
- Before writing, delete any existing .feature files in /features that don't correspond to the \
  current stories — the final state of /features must contain only the files for the current run.
- Filenames: features/story_<n>_<short_slug>.feature.
- Use clear Given/When/Then phrasing. Include URL/credentials as scenario context if specified.
- For Scenario Outlines, every row in Examples must end up with an assertable expected outcome. \
  Negative rows must assert the EXACT error message string from user_data.json — never just \
  "some error happens".
- After writing, list every file you created with one-line summaries.

Do not generate page objects, step definitions, or tests in this pass. Only Gherkin.
"""

FRAMEWORK_PROMPT = """\
You are operating inside the QE automation framework rooted at the current working directory. \
The /features folder already contains Gherkin files generated for the current run. Your job is \
to deliver runnable pytest-bdd code WITHOUT showing a visible browser.

═══════════════════════════════════════════════════════════════════
FIDELITY TO STORY + FRAMEWORK — NON-NEGOTIABLE
═══════════════════════════════════════════════════════════════════
1. EVERY Given/When/Then/And line in the .feature MUST have a matching \
implemented step-def function. NO step is allowed to be unimplemented. If \
you don't know how to implement one, write the step def with a clear \
`pytest.fail(f"Step <name> not implemented: <reason>")` so the test fails \
loudly — never silently skip.
2. EVERY "Verify"/"Check"/"Validate"/"should be"/"is displayed"/"matches" \
step MUST call EXACTLY ONE captured_values method (`assert_match`, \
`assert_sum`, `assert_avg`, `assert_min`, `assert_max`, `assert_count`, \
`assert_percentage`, `assert_difference`, `assert_ratio`, `assert_in_range`, \
or generic `assert_aggregate`). Don't bundle multiple verifications into one \
call. Don't replace an explicit assertion with a `try/except Exception: pass`.
3. EVERY value the test extracts that the story refers to later (a price, a \
name, a count, a total) MUST be recorded via `cap.add(...)` or \
`cap.add_component(..., group=...)` at the moment it is read.
4. Test order MUST match the story order. Do NOT reorder steps for what looks \
like efficiency — the story's order is the contract.
5. If a step references a UI element the test can't find, raise `AssertionError` \
with a descriptive message including the locator attempted. Don't fall through \
silently to the next step.
6. NEVER hardcode values from user_data.json into Python — read them at \
runtime via the `test_data` fixture (also declared in conftest.py).
═══════════════════════════════════════════════════════════════════

Pipeline (per .feature file in /features):
1. Use Playwright MCP (configured headless) to discover the live site for that feature. Walk every \
   action the feature requires.
2. Capture real selectors into mcp-selectors/locators.json. Never guess.
3. Generate Page Objects under /pages/page_<slug>.py, inheriting BasePage. All Playwright calls \
   live in the POM. Use selector keys from locators.json only.
4. Generate ONE step-definition file PER feature file: /step_defs/<feature_slug>_steps.py. \
   Each step calls one POM method. Update conftest.py pytest_plugins to include the new modules.
5. Generate ONE pytest-bdd test PER feature file: /tests/test_<feature_slug>.py.
6. Before generating, delete stale files in /pages, /step_defs, /tests that don't correspond to \
   the current feature files — the final state must contain only the files for the current run.
7. Run HEADLESS validation: `pytest -v` (no --headed). On failure, heal up to 3 cycles using \
   fresh MCP discovery, updated selectors, and explicit waits. Stop healing once green.
8. Append a one-line summary of generated/healed files to generation_log.txt.

Hard rules:
- Per-feature isolation: N feature files → N step-def files → N test files.
- Live DOM via MCP is the only source of truth for selectors.
- Step defs call POM methods, never raw Playwright.
- Do NOT show the headed browser; this phase is silent.
- PERFORMANCE: page.goto must use wait_until="domcontentloaded" and a finite timeout. \
NEVER call page.wait_for_load_state("networkidle") — most storefronts have long-tail \
analytics/tracking traffic that prevents networkidle from ever firing, so the wait \
burns its full timeout on every navigation. When a step needs a specific element, \
wait on THAT element (`expect(locator).to_be_visible(timeout=...)`) instead.
- TEST DATA: if user_data.json exists, generated step defs MUST read its current \
contents AT RUNTIME via the `test_data` fixture already declared in the root \
conftest.py — never hardcode values from the JSON into step defs. This lets the \
user change user_data.json between runs without regenerating code.
  · For Scenario Outline rows: the row's parameters (from Examples:) take precedence.
  · NEGATIVE rows (rows whose Example/object includes `expected_message`, \
    `expected_error`, or `should_succeed: false`): the step MUST assert that the EXACT \
    expected error text is visible. Failure to surface that error = test FAILURE. \
    Never use try/except to swallow assertion errors on negative rows.

- CAPTURED VALUES — generate-time requirement. Every step def MUST use the \
`captured_values` fixture (declared in the root conftest.py) to record what the \
test sees, so the Auditor can build a faithful HTML report.

  Basic operations:
  · `cap.add(label, value)` — record any value the test extracted (name, \
    price, count, message).
  · `cap.assert_match(label, expected=X, actual=Y)` — every story step that \
    starts with "Verify" / "Check" / "Validate" maps to ONE `assert_match` \
    call. The return value drives `assert` so the test fails naturally; the \
    entry persists either way.

  Aggregates over GROUPS (record each contributor, assert the math on the total):
  · `cap.add_component(label, value, group="g")` — record each contributing \
    value under the same group string.
  · `cap.assert_sum(label, group="g", actual=…)`
  · `cap.assert_avg(label, group="g", actual=…)`    — average / mean
  · `cap.assert_min(label, group="g", actual=…)`
  · `cap.assert_max(label, group="g", actual=…)`
  · `cap.assert_count(label, group="g", actual=…)`
  · `cap.assert_product(label, group="g", actual=…)`
  · `cap.assert_range(label, group="g", actual=…)`  — max - min
  · `cap.assert_median(label, group="g", actual=…)`
  · `cap.assert_aggregate(label, group="g", op="sum|avg|min|max|count|product|range|median", actual=…)` \
    — generic, when the story uses an operation by name.

  Cross-value arithmetic (no group, just two values):
  · `cap.assert_difference(label, larger=X, smaller=Y, expected_diff=Z)` — \
    e.g. `discount = full_price - sale_price`.
  · `cap.assert_percentage(label, part=X, whole=Y, expected_pct=Z)` — e.g. \
    "HST is 13% of subtotal".
  · `cap.assert_ratio(label, numerator=X, denominator=Y, expected_ratio=Z)`.
  · `cap.assert_in_range(label, actual=X, low=A, high=B)` — bounded values.

  When the story says ANY mathematical relationship — sum, total, average, \
  highest, lowest, count, percentage, difference, ratio, between bounds — \
  pick the right helper. NEVER hand-roll the math; the helpers persist the \
  full breakdown into the report.

- FILE DOWNLOADS — the browser's `downloads_path` is already pinned to the user's \
`~/Downloads` folder by the root conftest.py. So files downloaded during the test \
LAND IN `~/Downloads` automatically. BUT Playwright stores them under a UUID name \
unless the step def calls `download.save_as(...)` with the suggested filename.

  Generate-time pattern when the story says anything like "Download X" / \
  "click Download" / "export CSV" / "save the report":

      from pathlib import Path
      downloads_dir = Path.home() / "Downloads"

      with page.expect_download(timeout=30000) as info:
          page.locator("button:has-text('Download CSV')").click()
      download = info.value
      target = downloads_dir / download.suggested_filename
      download.save_as(str(target))
      cap.add("Downloaded file", download.suggested_filename, path=str(target))

  After save_as the file is at `~/Downloads/<suggested_filename>`. The user can \
  open it directly from their Downloads folder. Record the captured filename + \
  full path via `cap.add(...)` so it shows up in the HTML coverage report.

  If the story asks to VERIFY contents (CSV columns, row count, JSON keys, \
  sheet contents): after save_as, open the file via Python (`csv.reader`, \
  `openpyxl.load_workbook`, `json.load`) and use `cap.assert_match` /
  `cap.add_component` / `cap.assert_sum` for every value the story mentions.

  NO FABRICATION / NO HIDDEN SETUP — NON-NEGOTIABLE:

  The user story is the literal contract. The test does EXACTLY what the
  story says — no more, no less. The agent MUST NOT invent setup steps,
  pre-seed data, auto-create accounts, or write hooks that "prepare" the
  application so the story can succeed. The test reports REALITY: what the
  app does when exercised per the story, against the data the app actually
  has. If the data isn't there, that IS the result.

  Concrete bans:
  · Story says "delete employee Priya Sharma" → SEARCH for Priya. If she
    is not in the table: `cap.record_missing("Employee delete",
    target="Priya Sharma", reason="not present in employee table — cannot
    delete what is not there")` and stop. NEVER write a step that adds
    Priya first so the delete has something to act on.
  · Story says "add product 12345 to cart, total should be $48.99" →
    SEARCH for 12345. If it's not in the catalog: record_missing and stop.
    NEVER auto-create the product, NEVER seed a different product as a
    substitute.
  · Story says "log in as manager 499" → SUBMIT those exact credentials.
    If rejected: `cap.assert_prerequisite(condition=False, reason="creds
    rejected — manager_id=499 / Mngr@101Pass! invalid")` and halt. NEVER
    auto-register an account, NEVER try alternate credentials.
  · Story says "verify the cart is empty" → READ the cart. If items are
    present: that's a FAIL captured via `cap.assert_match`. NEVER pre-clear
    the cart in a fixture so the assertion passes.
  · Test-time data fixtures that mutate the application's state to make
    the story succeed are FORBIDDEN. The fixtures may only set up the
    BROWSER (open the page, accept cookies, restore session) — never the
    APPLICATION's data.

  The reason: the user wants to know what the application does. A test
  that fabricates its preconditions hides bugs, masks missing data, and
  produces a report that lies. A test that reports "Priya not found" is
  truthful — and far more valuable than a green checkmark from a fabricated
  setup.

  ENFORCEMENT in generated code:
  · Step defs MUST NOT call any application-state-mutating API except the
    ones the story literally names (e.g. "delete" is OK because the story
    says so; "create" is NOT OK because the story didn't say so).
  · No `@pytest.fixture(autouse=True)` that seeds data. The only autouse
    allowed is browser-context cleanup (cookies, localStorage, dialogs).
  · No "ensure X exists" helpers. If the test needs X and X isn't there,
    that's a recorded miss, not a fix.
  · No direct HTTP calls (`urllib.request`, `requests`, `httpx`) to the
    application's API to POST / PUT / PATCH / DELETE seed data. The test
    interacts with the app ONLY through Playwright + the steps in the story.
    HTTP is OK for READING (assertions can fetch JSON to compare against
    the UI), but never for WRITING.

  COMMON BAD RATIONALISATIONS THE AGENT MUST NOT USE:
  · "But the test needs to be idempotent / re-runnable" — NO. Idempotency
    is the user's problem to engineer (separate test data, reset script
    they own, etc.). The agent's job is to faithfully execute the story.
    If a second run finds the data already deleted, the second run reports
    "Priya Sharma not found — cannot delete what is not there" via
    `cap.record_missing(...)` — that's the truthful, useful outcome.
  · "But the backend persists state between runs" — that's how backends
    work. The test reports what the backend currently holds.
  · "But the user clearly wants this test to pass" — the user wants
    TRUTH, not a green checkmark. A test that fabricates its preconditions
    is lying.
  · "The fabricated setup is just helper plumbing, not a real test step" —
    NO. If running the test changes app state via an out-of-band API call,
    that IS a setup step, regardless of how it's labelled. Banned.

  PRE-FLIGHT CHECK before writing ANY step def or fixture:
    Q: Does this code mutate the application's data?
       (POST /api/employees, INSERT, UPDATE, DELETE the database, etc.)
    Q: Was that mutation explicitly named in the user story?
    → If mutation YES and named NO → DELETE THE CODE. Use record_missing
      or assert_prerequisite instead.

  ACTION OUTCOME MUST BE PROVEN BY THE BACKEND'S RESPONSE — never by a \
  pre-existing match. When the story performs a create / add / submit / save / \
  update / register action, the test MUST confirm the action SUCCEEDED ON THIS \
  RUN. The authoritative signal is the application's own response, not the mere \
  presence of a matching row:
    · An error message or error toast — "already exists", "Error: …", \
      "duplicate", "validation failed", "cannot …", "invalid", "failed" — is a \
      DEFINITIVE FAILURE. The action did NOT happen.
    · A positive outcome must be produced BY THIS RUN — the success toast, OR \
      the list/count incrementing (count_after == count_before + 1). It is \
      FORBIDDEN to report success just because the email/name is already in the \
      list: that record may be left over from a previous run, and "already \
      exists" means THIS run's creation failed. `email_present` alone is NOT \
      proof of creation.
    · USE THE READY-MADE HELPER `cap.assert_action_succeeded(...)` for this — \
      it detects backend error toasts and raises (blocking) so you never \
      hand-roll the check:
          toast = modal.latest_error_toast_text()    # "" when none
          cap.add("Add User — server response", toast or "<none>")
          cap.assert_action_succeeded(
              "User created",
              error_text=toast,                       # any error text => FAIL
              positive_signal=(count_after == (count_before or 0) + 1),
              reason="user count did not increase — creation not confirmed",
              evidence=f"count_before={count_before} count_after={count_after}",
          )

  MISSING-DATA / NEGATIVE-PATH RULE — NEVER silently skip, NEVER mask:

  Every step that depends on a value from the live site succeeding (login OK, \
  search returned results, employee row exists, product found, file downloaded) \
  MUST first decide if a failure here is BLOCKING or PER-ITEM and use the \
  matching captured_values helper:

  BLOCKING PREREQUISITE — every later step in the story depends on this one. \
  When it fails, the test cannot meaningfully continue (no session, no page, \
  no row to act on). Examples:
      · "Login as manager 503"          — every step after depends on the session
      · "Open the All Employees page"   — every step after needs that page open
      · "Download the CSV"              — every later step reads the CSV
      · "Open the order detail tab"     — every later step is on that tab
  IMPLEMENTATION — use `cap.assert_prerequisite(...)` (it RAISES, scenario halts):
      cap.assert_prerequisite(
          "Manager login",
          condition=login_page.is_logged_in(),
          reason=f"invalid credentials — manager_id={mid} was rejected",
          evidence=login_page.last_error_text(),
      )
  When this raises, the report banner will read: \
  *"BLOCKED — Manager login failed: invalid credentials — manager_id=499 was rejected"*. \
  Do NOT wrap this in try/except — let it halt.

  PER-ITEM MISSING — the story has a list of independent targets (multiple \
  products, multiple employees, multiple departments) and the absence of one \
  does NOT invalidate the rest. Examples:
      · "Search 'ice cream' AND 'chocolate', add each to the cart"
      · "Delete employees 503 AND 521"
      · "Verify Finance AND Sales departments are listed"
  IMPLEMENTATION — use `cap.record_missing(...)` (DOES NOT raise) and `continue`:
      for product in test_data["products"]:
          search_page.search_for(product)
          if not search_page.has_results():
              # Records `kind=missing`. Returns False. Test moves to next item.
              cap.record_missing("Product search",
                                 target=product,
                                 reason="search returned 0 results")
              continue
          cap.add("Product found", product)
          cart.add_first_item()
          cap.assert_match(f"Product {product} added to cart",
                           expected=product,
                           actual=cart.last_added_label())
  After the loop, the report will show:
      ✓ chocolate FOUND, added to cart
      ✗ ice cream MISSING (search returned 0 results)
  The scenario is allowed to finish (so the user sees BOTH outcomes); the \
  Auditor surfaces the missing items in their own "Items not found" section.

  HOW TO TELL BLOCKING vs PER-ITEM (from the story / Gherkin):
  · If the step has NO siblings — every later Given/When/Then references the \
    same singular subject — it's BLOCKING. Use `assert_prerequisite`.
  · If the step is inside a loop over `test_data[...]`, a Scenario Outline row, \
    or the story uses "AND <other item>" / "each of the following" / lists \
    multiple targets — it's PER-ITEM. Use `record_missing` + `continue`.
  · When the story explicitly says "validation message should appear" / \
    "should be rejected" / "should not be logged in", the failure IS the \
    expected outcome — use `cap.assert_match` to verify the error text \
    (positive assertion on the negative path), not `assert_prerequisite`.

  NEVER use bare `pytest.skip()`, bare `try: … except: pass`, or `return` \
  without recording the miss — those make the failure invisible. The whole \
  point is that the report shows the user exactly what the test saw.

  ROW-COVERAGE RULE — APPLIES EVERY TIME THE STORY VERIFIES A FILE OR `user_data.json`:
  · Read the FULL file. Never `[:25]`, never `.head(25)`, never "first N rows".
  · Determine the **scope from the story**:
      - "verify the entire CSV / all rows / every value / every field" → iterate \
        every row × every column.
      - "verify the Department / Status / <named> columns" → iterate every row \
        × only the named columns.
      - "verify the row for employee 503" → just that row, the columns named.
  · Whatever the scope, the generated test MUST loop over **every row in the \
    file** within that scope. The final number of `cap.assert_match` calls = \
    rows-in-scope × columns-in-scope. If the file has 100 rows and the story \
    scopes all columns, you MUST emit 100 × (column count) assertions — not 25.
  · NEVER use `pytest.skip` / `break` / `if i > 25` to short-circuit iteration. \
    NEVER replace per-row asserts with a single `len(rows) == N` count check. \
    NEVER summarise rows into "all matched" — the per-row evidence is the \
    whole point so the HTML coverage report shows the audit trail.

- MULTI-TAB / NEW-WINDOW flows — the root conftest.py exposes a `tabs` fixture \
(`TabRegistry`) that handles new tabs / new windows generically for any site. \
When the story says any of:
    "opens a new tab"
    "opens in a new window"
    "navigates to <X> in a new tab"
    "switches to the <X> tab"
    "goes back to the original/main tab"
…the step def MUST use `tabs`, not bare `page`. Patterns:

  Triggering a new tab from a click:
      with tabs.expect_new("Order Detail") as t:
          page.locator("a:has-text('View Order')").click()
      # tabs.active() is now the new tab; t.page is also the new tab.

  Asserting something in the new tab:
      detail = tabs.active()
      cap.assert_match("Detail page header",
                       expected="Order #12345",
                       actual=detail.locator("h1").inner_text())

  Switching tabs:
      tabs.switch("main")              # back to the original
      tabs.switch("Order Detail")      # by label we registered
      tabs.switch_by_url("/orders/")   # find by URL substring
      tabs.switch_by_title("Order")    # find by document.title substring

  After switching, subsequent step defs that take `page` should use \
  `tabs.active()` instead. To keep the test readable, fetch the active page \
  at the start of each step def that runs after a tab switch.

  If the user story doesn't mention tabs at all, ignore the fixture and use \
  `page` as normal — single-tab tests don't need to instantiate TabRegistry.

- GENERIC SELECTORS for comparative phrasing — make the framework work on ANY \
website. If the story says:
  · "the costliest item" / "most expensive" → in the step def, collect prices \
    from all visible tiles via page.evaluate, pick max, click that tile.
  · "the cheapest" / "lowest price" → same, pick min.
  · "the first item" / "the last item" → tile index 0 / -1.
  · "the item named X" → match by visible text exact-or-contains.
  · "the highest revenue dept" / "the largest <something>" → same min/max \
    pattern over the relevant table rows.
  Record the chosen value with cap.add so the report shows what was picked \
  AND its price/value. NEVER hardcode an index without first recording the \
  comparison.

- NEGATIVE STEPS INLINE IN THE FEATURE: a single Scenario may contain BOTH a negative \
attempt and a positive attempt (e.g. "enter invalid login details" → assert error → \
"clear fields, enter valid details"). When generating step defs:
  · A step that types known-bad credentials must actually type them and submit — DO NOT \
    skip the bad attempt or short-circuit to the positive flow.
  · The assertion step for the validation/error message must use \
    `expect(page.locator(...).first).to_be_visible(timeout=...)` with a selector that \
    matches the EXACT message text from the story (or `:text-matches(...)` regex if \
    minor punctuation may vary). Soft-passing on "any error appeared" is forbidden.
  · After the negative assertion, the next step typically clears the fields and enters \
    valid credentials. Make sure the form is still open and inputs are interactable \
    (no re-opening the modal unless the negative submit closed it).
  · Append a one-line entry to generation_log.txt indicating the scenario contains a \
    negative branch, e.g. `NEGATIVE BRANCH: assertion 'Invalid email or password' in \
    tests/test_<slug>.py`.

- Final state: green pytest output in headless mode.
"""

SCOUT_SITEMAP_PROMPT = """\
ROLE: SITEMAP SCOUT. EXECUTE IMMEDIATELY. NO PREAMBLE. NO QUESTIONS. NO META-COMMENTARY. \
Do every step with real tool calls. Do not stop to summarise; just do it and write the JSON file.

EXECUTE THESE STEPS NOW:
1. Read tool → user_story.txt. Extract the start URL.
2. mcp__playwright__browser_navigate → start URL.
3. mcp__playwright__browser_snapshot → capture the landing page.
4. From the snapshot, list every top-nav link href + every primary-CTA. \
For up to 8 of them: browser_navigate → snapshot. Record url, title, and tags \
drawn from ["search","cart","login","signin","signup","checkout","account","help","footer"].
5. Write tool → mcp-selectors/scout_sitemap.json with this exact schema:
{
  "root_url": "<absolute url>",
  "pages": [{"url":"...","title":"...","tags":["..."]}],
  "skipped": [{"url":"...","reason":"..."}]
}

HARD RULES:
- HEADLESS ONLY. Never request a headed browser.
- DO NOT generate test code, POMs, or step defs.
- DO NOT ask the user anything. DO NOT explain what you would do — just do it.
- Touch only mcp-selectors/scout_sitemap.json. Nothing else.
- Final file must be valid JSON.
"""

SCOUT_INVENTORY_PROMPT = """\
ROLE: INVENTORY SCOUT. EXECUTE IMMEDIATELY. NO PREAMBLE. NO QUESTIONS. \
Make real tool calls. Do not stop to summarise; just do it and write the JSON file.

EXECUTE THESE STEPS NOW:
1. Read → user_story.txt. Also Read mcp-selectors/scout_sitemap.json if it exists.
2. Pick the start URL from user_story.txt. For each unique page (max 6), \
mcp__playwright__browser_navigate then mcp__playwright__browser_snapshot.
3. From each snapshot, list every visible button, link with href, [role=button], \
and form input/select/textarea. For each: best_selector, text or aria-label, role.
4. Selector preference order: [data-testid]/[data-test*] > id > role+accessibleName > unique CSS.
5. mcp__playwright__browser_evaluate → run document.querySelectorAll(...) for each \
selector to verify exactly 1 match. Drop anything that doesn't match exactly 1.
6. Write → mcp-selectors/scout_inventory.json:
{
  "by_page": {
    "<url>": {
      "clickables": [{"selector":"...","text":"...","role":"button|link"}],
      "inputs":     [{"selector":"...","label":"...","type":"text|email|password|..."}]
    }
  }
}

HARD RULES:
- HEADLESS ONLY.
- DO NOT ask the user anything. DO NOT explain — execute.
- HARD CAP: 6 pages, 30 selectors per page.
- Output ONLY mcp-selectors/scout_inventory.json.
"""


FRAMEWORK_DELTA_PROMPT = """\
You are operating inside an EXISTING QE automation workspace whose /pages, \
/step_defs, /features, /mcp-selectors, /tests folders ALREADY contain working \
code retrieved from this application's per-app knowledge base (the \
`_shared/` folder for this URL host, or a forked similar prior story). Your \
job is to EXTEND — not replace — to cover the NEW user story.

═══════════════════════════════════════════════════════════════════
PER-APP RAG — READ EXISTING ARTIFACTS BEFORE MCP DISCOVERY
═══════════════════════════════════════════════════════════════════
The workspace is pre-populated with everything the agent has learned about \
this application from prior stories. BEFORE opening Playwright MCP for any \
flow step (login, navigate, search, etc.), you MUST:

1. Read every file under /pages/ (page_*.py) and note the class names + \
   public method names. These are your reusable POM methods.
2. Read every file under /step_defs/ (*_steps.py) and note the pytest-bdd \
   step patterns already implemented. These are your reusable Gherkin steps.
3. Read mcp-selectors/locators.json — this has every CSS/test-id selector \
   the agent has confirmed-working on this app. NEVER re-derive a selector \
   that's already in here; reuse it directly.
4. For each step in the new feature file:
     a. Match it against existing step def patterns. If a regex already \
        covers it → REUSE that step def, no new code.
     b. If the step uses an existing POM method (e.g. login, navigate, \
        accept_cookies) → call that method from a new (or existing) step def.
     c. Only fall through to Playwright MCP discovery for steps that are \
        TRULY new to this app (no matching POM method, no locator in \
        locators.json).
5. After Claude writes new files, mcp-selectors/locators.json must include \
   every newly-discovered selector merged with the existing entries.
═══════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════
DELTA-ONLY MODE — NON-NEGOTIABLE
═══════════════════════════════════════════════════════════════════
1. READ FIRST. Before generating ANYTHING, you MUST:
   a. Read user_story.txt — the NEW story.
   b. Read every .feature in /features — they are from the PRIOR story.
   c. Read every page object in /pages/ and every step def in /step_defs/.
   d. Read mcp-selectors/locators.json if it exists.
   e. Read user_data.json if it exists.
2. DIFF. Compare the NEW story to the existing features/step defs. Identify:
   - Steps that are ALREADY covered (login, navigate, etc.) — leave them alone.
   - Steps that are NEW (e.g. "place an order", a new field, a new tab).
3. EXTEND only the new steps:
   - If a new step belongs to an existing page object, add ONE method to that \
     POM class. Do not duplicate. Do not rewrite the class.
   - If a new step needs a new page, create a new file `pages/page_<slug>.py` \
     that inherits BasePage. Reuse selectors from locators.json if any apply; \
     otherwise discover them via Playwright MCP and append to locators.json.
   - Add ONE new step def (or append to the existing matching step def file) \
     for each new Gherkin step. Wire it to the right POM method.
4. UPDATE /features:
   - If the new story is a superset of the prior story (same flow + extra \
     steps), APPEND a new Scenario to the existing .feature.
   - If the new story is a different feature on the same site, CREATE a new \
     .feature file. Do NOT delete the existing one.
5. DO NOT DELETE existing files unless the new story explicitly contradicts \
   them (e.g. the prior login flow is now obsolete). When in doubt, keep.
6. After writing, list:
   - Files MODIFIED   (existing files you appended to)
   - Files CREATED    (brand-new files)
   - Files UNCHANGED  (existing files you intentionally left alone — proof you \
                      respected the fork instead of regenerating)

All the FIDELITY rules from FRAMEWORK_PROMPT still apply: every step def must \
call captured_values, full row coverage on user_data.json, MCP-discovered \
selectors, no headed browser in this phase. Run `pytest -v` headless to \
validate, healing up to 3 cycles.
═══════════════════════════════════════════════════════════════════
"""


SCOUT_FLOW_PROMPT = """\
ROLE: FLOW SCOUT. EXECUTE IMMEDIATELY. NO PREAMBLE. NO QUESTIONS. \
Make real tool calls and replay the story end-to-end. Do not summarise — execute.

EXECUTE THESE STEPS NOW:
1. Read → user_story.txt. Read → user_data.json if it exists (use first row for arrays).
2. Substitute <placeholder> tokens in the story with values from user_data.json.
3. For each step in the story, in order:
   a. Use mcp__playwright__browser_navigate / browser_click / browser_type / browser_snapshot / browser_wait_for to actually perform the action.
   b. Before each action, capture the trigger_selector (best_selector — same preference order: [data-testid] > id > role+name > css).
   c. After each action, capture the resulting URL + title + a short observed_changes note.
4. If a step fails (selector missing, navigation timeout, login error, etc.), record under "blockers" \
with step_number + reason + 1-2 line dom snippet, then continue with the next step if reasonable.
5. If a row from user_data.json is clearly NEGATIVE (has `expected_message` / `expected_error` / \
`should_succeed: false`), record the error selector + actual text under "negative_outcomes".

Pipeline (per story):
1. Use Playwright MCP (headless) to navigate the start URL.
2. Replay each action in the story IN ORDER. Before each action, capture the \
trigger selector (best_selector, same preference order as the inventory scout). \
After each action, capture the resulting URL + title + a short observed_changes note.
3. If a step fails (selector missing, navigation timeout, login error), record it \
under "blockers" with story_n, step_number, reason, and a 1-2 line dom snippet.

Output schema (JSON only):
{
  "stories": [
    {
      "story_n": 1,
      "steps": [{"step_number":1,"description":"...","action":"navigate|click|fill|assert",
                 "trigger_selector":"...","input_value":"...","post_url":"...",
                 "post_title":"...","observed_changes":"..."}],
      "blockers": [{"step_number":N,"reason":"...","dom_snippet":"..."}]
    }
  ]
}

Hard rules:
- Headless. Output ONLY mcp-selectors/scout_flow.json.
- Never invent selectors; if you can't confirm one, log a blocker.
"""

SCOUT_EDGE_PROMPT = """\
ROLE: EDGE SCOUT. EXECUTE IMMEDIATELY. NO PREAMBLE. NO QUESTIONS. \
Make real tool calls. Do not list potential edge cases — find the ACTUAL overlays \
on this live site and record their dismiss selectors.

EXECUTE THESE STEPS NOW:
1. Read → user_story.txt. Extract the start URL.
2. mcp__playwright__browser_navigate → start URL.
3. mcp__playwright__browser_wait_for time=4 (give overlays time to appear).
4. mcp__playwright__browser_snapshot → inspect the page for cookie banners, sign-in \
modals, popups, interstitials, age gates, iframe CMPs (Sourcepoint `sp_message_iframe_*`).
5. For each overlay found: capture kind, trigger_url, dismiss_selector \
(confirmed-clickable), dismiss_label, iframe_id_pattern (if applicable).
6. Visit cart/checkout/account pages referenced in user_story.txt (max 3 extra pages) \
and re-capture overlays.
7. Write → mcp-selectors/scout_edge.json:
{
  "overlays": [{
    "kind":"cookie_banner|signin_modal|popup|interstitial|iframe_cmp",
    "trigger_url":"...","dismiss_selector":"...","dismiss_label":"...",
    "iframe_id_pattern":"<optional, e.g. sp_message_iframe_>"
  }]
}

HARD RULES:
- HEADLESS ONLY.
- DO NOT brainstorm hypothetical edge cases. Only record overlays you ACTUALLY observe.
- Each entry must include a confirmed-clickable dismiss selector.
- DO NOT ask the user anything. DO NOT explain — execute.
"""

AUDITOR_PROMPT = """\
You are the AUDITOR agent inside a QE automation workspace. \
The pytest run has just finished. Your job is to produce a STORY-LEVEL VERDICT — \
did every requirement in the user story actually get exercised, and did each data \
assertion match? Stay strictly evidence-based: if it isn't in the artifacts below, \
do not claim it happened.

═══════════════════════════════════════════════════════════════════
FIDELITY TO STORY — NON-NEGOTIABLE FOR THE REPORT
═══════════════════════════════════════════════════════════════════
1. EVERY meaningful line of user_story.txt becomes EXACTLY ONE row in the \
requirements checklist. No merging. No omission. No "I'll group these because \
they're related" — keep them separate.
2. EVERY captured_values entry (every `add`, `assert_match`, `assert_sum`, …) \
becomes a row in the report. Don't drop entries that look duplicate — show \
all of them with their timestamps so the user can see the trace.
3. If a story step has NO matching captured-values entry AND no test step \
maps to it, mark it ❌ with `"not exercised — step def missing or skipped"`. \
This is critical: silent gaps are worse than failures. The user needs to know \
what was NOT done.
4. Verdict logic:
     PASS    = every story requirement ✅ AND every captured assertion ✅
     PARTIAL = some ✅ + some ❌ (some passed, some not exercised or failed)
     FAIL    = at least one captured assertion ❌ on a positive requirement
              OR pytest exit code was nonzero
5. Negative scenarios get their OWN report section AND a row in the main \
checklist. A negative case passes only if the bad input was actually \
attempted AND the exact expected validation message appeared.
═══════════════════════════════════════════════════════════════════

Inputs you must read (do NOT touch the live site, no MCP, no browser):
- user_story.txt                          — the original requirements
- user_data.json (optional)               — expected data values, including positive + negative rows
- features/*.feature                      — Gherkin scenarios that were supposed to be executed
- tests/test_*.py                         — pytest entrypoints
- step_defs/*.py                          — assertion logic
- reports/report.html                     — pytest-html run report (parse for passed/failed test names + assertion messages)
- generation_log.txt                      — what was built / healed
- reports/screenshots/ (if present)       — visual evidence on failure

Pipeline:
1. Parse user_story.txt into an ordered list of REQUIREMENTS — each numbered step or sentence \
that describes a user action or an expected outcome. Strip URL/credential lines and Gherkin \
keywords; the goal is the human intent per requirement.
2. For each requirement, decide:
     - exercised_in_test  (true/false) — is there a step def or scenario step that maps to it?
     - passed             (true/false/na) — did that test step pass according to report.html?
     - evidence           — concrete pointer: test name, line number, screenshot filename, or \
                            the asserted text. If nothing matches, write "not exercised".
3. If user_data.json exists, for every key build a data_assertion entry: expected vs. actual \
(from report.html or test output), and verdict. For arrays (Scenario Outline), include one \
entry per row with its row_index + a flag positive/negative.

3b. BLOCKING / PER-ITEM RENDERING — captured_values.json now contains two \
special entry kinds that MUST be surfaced distinctly in the report:

    kind == "prerequisite"  (blocking failure — scenario halted)
    kind == "missing"       (per-item miss — scenario continued)

    For prerequisite entries with passed==false:
       - Render a RED banner at the TOP of the report:
           "🚫 BLOCKED — <label>: <reason>"
           "Evidence: <evidence>" (if present)
       - Set overall verdict to FAIL with cause = "blocking prerequisite failed".
       - Every story requirement after this point gets marked \
         "not exercised (blocked by earlier prerequisite)" — DO NOT mark them \
         as missing-step-def or as passed. They simply didn't run because the \
         test bailed cleanly.
       - Do NOT downgrade this to PARTIAL — a blocking prerequisite failure is \
         a hard FAIL the user explicitly needs to see at the top.

    For missing entries (always non-fatal, always recorded):
       - Render an "Items not found" section with one row per entry:
           "✗ <label>: <target> — <reason>"
       - These do NOT change the overall verdict by themselves. Each one is \
         informational unless the story explicitly required every item to be \
         present (e.g. "verify ALL of: A, B, C"). In that case, mark verdict \
         PARTIAL with a note: "X of Y expected items found, Z missing".
       - In the requirement-checklist table, the requirement linked to a \
         missing item gets ⚠ (warning), NOT ✓ and NOT ❌.

    For prerequisite entries with passed==true: render as a green checkmark \
    row in the "Preconditions" section — short, just label + ✓.

3a. ROW-COVERAGE AUDIT — when user_data.json is an array of N dicts, OR a CSV/spreadsheet \
was downloaded and verified:
    - Count the rows in the source (N).
    - Determine the scope from the story (columns to verify; "all" or specific names).
    - Count the matching `cap.assert_match` / data_assertion entries in captured_values.json \
      (kind == "assertion" or "data_assertion").
    - Expected assertion count = N × (columns-in-scope).
    - If actual count < expected, mark the run **PARTIAL** with a top-of-report banner: \
      `"Row coverage incomplete: X of Y rows verified (Z assertions, expected W)."` and list \
      which row indices appear in captured_values.json and which are MISSING.
    - NEVER hide this gap. NEVER round up to PASS because "most rows passed".
4. Produce a 1-line overall_verdict:
     - "PASS"     — every requirement exercised AND every data assertion passed
     - "PARTIAL"  — some requirements passed, others not exercised OR negative-row assertion missing
     - "FAIL"     — at least one assertion failed OR at least one positive requirement failed

ALSO read reports/captured_values.json if it exists — it's a per-session log of \
every value the test extracted, every expected-vs-actual assertion, every \
aggregate sum verification (components + computed sum + on-screen total). \
This is the richest evidence available and MUST be reflected in the HTML report.

Outputs (write ALL THREE; nothing else):
1. reports/story_coverage.json — machine-readable, schema:
{
  "generated_at": "ISO timestamp",
  "overall_verdict": "PASS|PARTIAL|FAIL",
  "story_requirements": [
    {"n": 1, "requirement": "...", "exercised_in_test": true, "passed": true,
     "evidence": "test_xxx::scenario_yyy step 3, screenshot YYYYMMDD_HHMMSS.png"}
  ],
  "data_assertions": [
    {"field": "Subtotal", "expected": "48.99", "actual": "48.99", "passed": true,
     "row_kind": "positive|negative|na", "row_index": null}
  ],
  "missing_coverage": ["the story said X but no test step matches"],
  "test_summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0}
}

2. reports/story_coverage.md — human-readable summary. Begin with the verdict heading, then \
a numbered checklist of requirements (✅ / ❌ / ⚠️ each), a data assertions table, a \
DEDICATED **Negative scenarios** section (see below), a "Gaps in coverage" section, and a \
closing 1-line recommendation. Keep it under 250 lines.

3. reports/story_coverage.html — self-contained styled HTML report. THIS is the user's \
PRIMARY view (the pytest-html and Allure reports are secondary). Requirements:
  · Inline CSS, NO external scripts/stylesheets, NO CDN links. Fully offline.
  · Modern, clean design: card-based layout, big verdict badge at top \
    (green/yellow/red), readable monospace for IDs and currency, color-coded \
    rows (pass green, fail red, neutral grey).
  · Sections in this ORDER:
    a) Header card — overall verdict + pytest summary (passed/failed/skipped/duration).
    b) **Requirements checklist** — one row per story requirement with ✅/❌, \
       short evidence pointer (test name, line, screenshot).
    c) **Captured values** — table sourced from captured_values.json entries \
       of kind="value" or kind="assertion". Columns: Label · Expected · Actual · \
       Verdict (✅/❌). Show timestamp.
    d) **Aggregate & math verifications** — for every entry whose `kind` is one of:
         `aggregate_assertion` — group-based sum/avg/min/max/count/product/range/median
         `diff_assertion` — larger - smaller compared to expected_diff
         `percentage_assertion` — part / whole * 100 compared to expected_percentage
         `ratio_assertion` — numerator / denominator compared to expected_ratio
         `range_assertion` — value bounded between low and high
       Render each as its OWN card showing:
         - The label and operation in plain English (e.g. "Sum across dept_revenues" /
           "13% of subtotal" / "discount = full_price - sale_price").
         - For group-based: a small table of every component (label + value).
         - The computed result + the actual on-screen value (or the bounds for range).
         - The verdict ✅/❌, the tolerance used.
       This is the section the user cited (sum of dept revenues == super-admin total). \
       Make it visually obvious which numbers contributed and what the math worked out to. \
       Support ALL operations — never hardcode to just sum.
    e) **Negative scenarios** — same table format as the .md.
    f) **Gaps in coverage** — bullet list.
    g) Footer with timestamp + 1-line recommendation.
  · If captured_values.json has zero entries, render the Captured Values and \
    Aggregate Verifications sections as empty-state cards saying "No values \
    captured — step defs did not call captured_values.add(...) — flag this".
  · Keep the HTML <body> under ~80KB total. Truncate long fields to 200 chars \
    each. Don't embed images or screenshots inline.
  · Use Unicode chars (✅ ❌ ⚠️ 📊 →) instead of font icons.

NEGATIVE SCENARIOS SECTION:
For each negative attempt found in the story (inline negatives like "invalid login details" / \
"should not be logged in" / "validation message should be displayed", OR JSON rows with \
expected_message/expected_error/should_succeed:false), emit a line with:
  - the bad input that was tried (e.g. `invalid@myyahoo.com / wrongpass`)
  - the EXACT expected validation message
  - the ACTUAL validation message captured in report.html
  - verdict ✅ if the actual matches the expected, ❌ otherwise

Example block in the .md:
  ## Negative scenarios
  | Bad input | Expected validation | Actual | Verdict |
  |---|---|---|---|
  | invalid@myyahoo.com / wrongpass | Invalid email or password | Invalid email or password | ✅ |

If the test failed to even attempt the negative case (e.g. step skipped the bad input \
and went straight to valid login), that counts as ❌ with the note "negative branch not \
exercised — test bypassed bad-credentials step".

Hard rules:
- Read-only. Do NOT touch the live site. Do NOT modify any test code.
- Cite real evidence — quote the actual assertion message from report.html, name the screenshot file, \
reference the test name. No paraphrased guesses.
- If report.html does not exist or is unreadable, write overall_verdict=PARTIAL and explain in the .md.
- Negative scenarios (inline OR JSON-driven) count as PASSED if (and only if) the report shows \
the test asserted the EXACT expected message AND the test actually attempted the bad input. \
Don't soft-pass a negative on "the test errored somewhere".
- The HTML report is the PRIMARY deliverable. The .md is a fallback for terminal/markdown viewers. \
The .json is for tooling. All three must be consistent (same verdicts, same numbers).
"""


SYNTHESIS_PROMPT = """\
You are the SYNTHESIS AGENT inside a QE automation workspace. \
The four scouts have already run and written their JSONs under mcp-selectors/. \
The Gherkin features under /features are already generated.

Your job: produce runnable pytest-bdd code from cross-validated selectors only.

Inputs (read first):
- user_story.txt
- features/*.feature
- mcp-selectors/scout_sitemap.json
- mcp-selectors/scout_inventory.json
- mcp-selectors/scout_flow.json
- mcp-selectors/scout_edge.json

Pipeline:
1. Build mcp-selectors/locators.json by merging the four scout outputs:
   - prefer data-test* > id > role+name > css
   - require a selector to appear in inventory AND be exercised in flow before it lands in locators
   - include cookie/login dismiss selectors from scout_edge under a "common" namespace
   - drop anything that flow recorded as a blocker
2. For each .feature file in /features, generate /pages/page_<slug>.py POMs that \
inherit BasePage and use ONLY keys from locators.json. All Playwright calls live \
in the POM.
3. Generate ONE step-def file PER feature: /step_defs/<feature_slug>_steps.py. \
Each step calls one POM method, never raw Playwright. Update conftest.py \
pytest_plugins to include the new modules.
4. Generate ONE pytest-bdd test PER feature: /tests/test_<feature_slug>.py.
5. Delete stale files in /pages, /step_defs, /tests that don't correspond to the \
current feature files.
6. Run HEADLESS validation: pytest -v (no --headed). On failure, do NOT re-scout. \
Append the failing assertion to mcp-selectors/scout_blockers.txt and stop. The user \
will trigger another full re-scout if needed.
7. Append a one-line summary of generated/healed files to generation_log.txt.

Hard rules:
- Per-feature isolation: N feature files → N step-def files → N test files.
- Selectors come from scout JSONs only — never invent.
- Step defs call POM methods only.
- Headless validation only. NO headed browser in this phase.
- PERFORMANCE: page.goto must use wait_until="domcontentloaded" and a finite timeout. \
NEVER call page.wait_for_load_state("networkidle") — most storefronts have long-tail \
analytics/tracking traffic that prevents networkidle from ever firing, so the wait \
burns its full timeout on every navigation. When a step needs a specific element, \
wait on THAT element (`expect(locator).to_be_visible(timeout=...)`) instead.
- TEST DATA: if user_data.json exists, generated step defs MUST read its current \
contents AT RUNTIME via the `test_data` fixture already declared in the root \
conftest.py — never hardcode values from the JSON into step defs. This lets the \
user change user_data.json between runs without regenerating code.
  · For Scenario Outline rows: the row's parameters (from Examples:) take precedence \
    over test_data for that specific run.
  · For assertions referencing data fields: use the value from test_data / Example row, \
    e.g. `expect(page.locator("...")).to_have_text(str(test_data["Total"]))`.
  · NEGATIVE rows (rows whose Example/object includes `expected_message`, \
    `expected_error`, or `should_succeed: false`): the step MUST assert that the EXACT \
    expected error text is visible. Failure to surface that error = test FAILURE. \
    Never use try/except to swallow assertion errors on negative rows.
- Final state: green pytest output OR a clear one-line failure summary in scout_blockers.txt.
"""


PYTEST_HEADED_CMD_BASE = [
    sys.executable, "-m", "pytest", "-v",
    "--headed",
    f"--html={HTML_REPORT}",
    "--self-contained-html",
    f"--alluredir={ALLURE_RESULTS}",
]


def pytest_headed_cmd(target: str | None = None) -> list[str]:
    """Build the pytest --headed command. If target is None, run everything in /tests.
    If target is given (e.g. 'tests/test_story_1.py'), run only that file."""
    cmd = list(PYTEST_HEADED_CMD_BASE)
    if target:
        cmd.append(target)
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
# The Auditor runs AFTER pytest. It reads artifacts + report.html + captured
# values and writes the coverage verdict (json, md, html). No browser tools —
# strictly post-run analysis.
AUDITOR_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]

# Read-only tool surface for the parallel scouts. Each scout has its own MCP
# browser session; they only need write access for their own JSON output.
SCOUT_TOOLS = [
    "Write", "Read", "Glob",
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_click",
    "mcp__playwright__browser_wait_for",
    "mcp__playwright__browser_evaluate",
    "mcp__playwright__browser_press_key",
    "mcp__playwright__browser_hover",
    "mcp__playwright__browser_handle_dialog",
    "mcp__playwright__browser_navigate_back",
    "mcp__playwright__browser_close",
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


def _content_digest(text: str) -> str:
    """8-char md5 of the meaningful story body (used internally to recognise the
    same story across sessions; never shown to the user)."""
    body = "\n".join(
        line.strip() for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not body:
        return ""
    return hashlib.md5(body.encode("utf-8")).hexdigest()[:8]


def _story_slug(text: str) -> str:
    """Filesystem-safe slug derived from the first meaningful line of the story.
    Lowercased, snake_case, capped at 40 chars."""
    label = story_label(text).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", label).strip("_")
    return (slug[:40].rstrip("_")) or "untitled_story"


def _folder_name_for(slug: str, digest: str) -> str:
    """Canonical folder layout: `<slug>__<digest>` — readable name + 8-char id
    so two stories with identical first lines never collide and so the user can
    spot the right folder at a glance."""
    return f"{slug}__{digest}"


# ---------------------------------------------------------------------------
# Per-application folder organisation + shared knowledge base
#
# Layout (new — applied on every run, with auto-migration of legacy folders):
#
#   projects/
#     ├── localhost_5173/
#     │   ├── _shared/                       ← reusable knowledge for this app
#     │   │   ├── pages/                     ← every POM Claude built across stories
#     │   │   ├── step_defs/                 ← every reusable step def
#     │   │   ├── mcp-selectors/locators.json
#     │   │   └── flow_index.json            ← {"login": "page_login.py", ...}
#     │   ├── delete_employee_priya__52539d78/
#     │   │   ├── .story_id
#     │   │   ├── user_story.txt
#     │   │   ├── features/
#     │   │   └── reports/
#     │   └── as_a_manager__40a4e28b/
#     └── education_qa_scholastic_ca/
#         └── ...
#
# When a new story comes in, the agent retrieves `_shared/` for that app
# BEFORE doing any MCP browser discovery — minimising token burn and
# inheriting all working selectors / step defs from prior runs.
# ---------------------------------------------------------------------------

# Folder names reserved at the top level of /projects/ — they are NOT app folders.
_NON_APP_TOP_DIRS = {"_shared", "_unknown"}


def _extract_app_id(text: str) -> str:
    """Derive a filesystem-safe app id from the first URL in the story.

    Examples:
        "I open http://localhost:5173/, …" → "localhost_5173"
        "https://education-qa.scholastic.ca/…" → "education_qa_scholastic_ca"
        "file:///C:/foo/bar.html" → "local_files"
        no URL → "_unknown"
    """
    if not text:
        return "_unknown"
    m = re.search(r"https?://([^/\s\"'>)]+)", text, re.IGNORECASE)
    if not m:
        if re.search(r"file:///", text):
            return "local_files"
        return "_unknown"
    host = m.group(1).lower()
    # Strip auth prefix "user:pass@" and port suffix if present
    host = host.split("@")[-1]
    safe = re.sub(r"[^a-z0-9]+", "_", host).strip("_")
    return safe or "_unknown"


def _app_dir(app_id: str) -> Path:
    return PROJECTS_DIR / app_id


def _app_shared_dir(app_id: str) -> Path:
    return _app_dir(app_id) / "_shared"


def app_id_for_story_id(story_id: str) -> str:
    """Given a story_id like 'localhost_5173/delete_priya__52539d78', return
    the app prefix ('localhost_5173'). Legacy story_ids (no '/') return '_unknown'."""
    if "/" in story_id:
        return story_id.split("/", 1)[0]
    return "_unknown"


def app_shared_has_work(app_id: str) -> dict:
    """Returns counts of reusable artefacts in this app's _shared/ folder."""
    base = _app_shared_dir(app_id)
    if not base.exists():
        return {"pages": 0, "step_defs": 0, "selectors": 0, "exists": False}
    pages = list((base / "pages").glob("page_*.py")) if (base / "pages").exists() else []
    steps = list((base / "step_defs").glob("*_steps.py")) if (base / "step_defs").exists() else []
    sel_files = list((base / "mcp-selectors").glob("*.json")) if (base / "mcp-selectors").exists() else []
    return {
        "pages": len(pages),
        "step_defs": len(steps),
        "selectors": len(sel_files),
        "exists": bool(pages or steps or sel_files),
    }


def promote_to_shared(story_id: str) -> dict:
    """After a successful ② / ③, copy the story's NEW pages, step_defs, and
    selectors into the app's _shared/ folder so future stories on the same
    app inherit them. Last-write-wins per filename (newer versions of the
    same POM replace older ones — a deliberate choice so the agent's most
    recent selectors are the authoritative ones)."""
    if not story_id:
        return {"pages": 0, "step_defs": 0, "selectors": 0}
    app_id = app_id_for_story_id(story_id)
    if app_id in _NON_APP_TOP_DIRS:
        return {"pages": 0, "step_defs": 0, "selectors": 0}
    proj = project_dir(story_id)
    shared = _app_shared_dir(app_id)
    summary = {"pages": 0, "step_defs": 0, "selectors": 0}

    # Source can be either the flat workspace (just-generated) or the story
    # archive (when called after archive_artifacts). Prefer the workspace
    # because its files include the latest healed selectors. Fall back to
    # the archive if the workspace was already cleaned.
    def _pick_src(rel: str) -> Path | None:
        for candidate in (PROJECT_ROOT / rel, proj / rel):
            if candidate.exists() and any(candidate.iterdir()):
                return candidate
        return None

    def _copy_dir(rel: str, glob_pat: str, key: str) -> None:
        src = _pick_src(rel)
        if src is None:
            return
        dst = shared / rel
        dst.mkdir(parents=True, exist_ok=True)
        for f in src.glob(glob_pat):
            if f.is_file():
                try:
                    (dst / f.name).write_bytes(f.read_bytes())
                    summary[key] += 1
                except OSError:
                    continue
        # Also copy framework scaffolding files once (base_page.py, __init__.py)
        for must_have in ("__init__.py", "base_page.py", "_selectors.py"):
            mf = src / must_have
            if mf.exists() and not (dst / must_have).exists():
                try:
                    (dst / must_have).write_bytes(mf.read_bytes())
                except OSError:
                    pass

    _copy_dir("pages", "page_*.py", "pages")
    _copy_dir("step_defs", "*_steps.py", "step_defs")
    # MCP locators
    sel_src = _pick_src("mcp-selectors")
    if sel_src is not None:
        sel_dst = shared / "mcp-selectors"
        sel_dst.mkdir(parents=True, exist_ok=True)
        for f in sel_src.glob("*.json"):
            try:
                (sel_dst / f.name).write_bytes(f.read_bytes())
                summary["selectors"] += 1
            except OSError:
                continue

    # Update flow index — best-effort, indexes POM classes by file.
    _rebuild_flow_index(app_id)
    return summary


def _rebuild_flow_index(app_id: str) -> None:
    """Scan _shared/pages/*.py and write a {flow_name -> file} index that
    Claude can grep before resorting to MCP discovery. Tolerant to parse errors."""
    shared = _app_shared_dir(app_id)
    pages_dir = shared / "pages"
    if not pages_dir.exists():
        return
    index: dict[str, str] = {}
    method_re = re.compile(r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", re.MULTILINE)
    for f in pages_dir.glob("page_*.py"):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name in method_re.findall(text):
            if name.startswith("_") or name in ("__init__",):
                continue
            # Keep first occurrence — older POMs win if a later one redefines.
            index.setdefault(name, f.name)
    try:
        (shared / "flow_index.json").write_text(
            json.dumps(index, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        pass


def restore_from_shared(story_id: str) -> dict:
    """Copy the app's _shared/ artefacts into the flat workspace + the new
    story's archive so ② can extend rather than regenerate. Mirrors
    fork_project_into_workspace but sources from _shared instead of a peer
    story. Non-destructive — only adds files."""
    app_id = app_id_for_story_id(story_id)
    if app_id in _NON_APP_TOP_DIRS:
        return {"pages": 0, "step_defs": 0, "selectors": 0}
    shared = _app_shared_dir(app_id)
    if not shared.exists():
        return {"pages": 0, "step_defs": 0, "selectors": 0}
    proj = project_dir(story_id)
    proj.mkdir(parents=True, exist_ok=True)
    summary = {"pages": 0, "step_defs": 0, "selectors": 0}

    def _copy_subtree(rel: str, key: str) -> None:
        s = shared / rel
        if not s.exists():
            return
        d_proj = proj / rel
        d_ws = PROJECT_ROOT / rel
        d_proj.mkdir(parents=True, exist_ok=True)
        d_ws.mkdir(parents=True, exist_ok=True)
        for f in s.rglob("*"):
            if f.is_dir():
                continue
            try:
                rel_path = f.relative_to(s)
                (d_proj / rel_path).parent.mkdir(parents=True, exist_ok=True)
                (d_proj / rel_path).write_bytes(f.read_bytes())
                (d_ws / rel_path).parent.mkdir(parents=True, exist_ok=True)
                (d_ws / rel_path).write_bytes(f.read_bytes())
                summary[key] += 1
            except OSError:
                continue

    _copy_subtree("pages", "pages")
    _copy_subtree("step_defs", "step_defs")
    _copy_subtree("mcp-selectors", "selectors")
    return summary


def _is_app_folder(p: Path) -> bool:
    """A top-level child of projects/ is an APP folder if it has a `_shared/`
    or contains subdirectories with `.story_id` sidecars. Legacy story
    folders (containing user_story.txt at the top) are NOT app folders."""
    if not p.is_dir():
        return False
    if p.name in _NON_APP_TOP_DIRS:
        return False
    if (p / "_shared").exists():
        return True
    if (p / ".story_id").exists() or (p / "user_story.txt").exists():
        return False
    # Has children, none with story files — assume app folder.
    return any(c.is_dir() for c in p.iterdir())


def _migrate_legacy_folders() -> None:
    """Idempotent migration of older project layouts into the per-app layout.

    Handles two legacy forms:
      1) Older `story_<hash>` or bare `<slug>` folders → rename to `<slug>__<digest>`.
      2) Pre-per-app folders at `projects/<slug>__<digest>/` that have a story
         file with a URL → MOVE them under `projects/<app_id>/<slug>__<digest>/`
         and seed `projects/<app_id>/_shared/` from their pages/step_defs.
    """
    if not PROJECTS_DIR.exists():
        return
    canonical_re = re.compile(r".*__[a-f0-9]{8}$")
    # Phase 1: ensure every legacy direct-child folder has .story_id + canonical name.
    for child in list(PROJECTS_DIR.iterdir()):
        if not child.is_dir() or child.name in _NON_APP_TOP_DIRS:
            continue
        if _is_app_folder(child):
            continue  # already moved to per-app layout
        sidecar = child / ".story_id"
        story_path = child / "user_story.txt"
        if not story_path.exists():
            continue
        try:
            text = story_path.read_text(encoding="utf-8")
        except OSError:
            continue
        digest = _content_digest(text)
        if not digest:
            continue
        if not sidecar.exists():
            try:
                sidecar.write_text(digest, encoding="utf-8")
            except OSError:
                pass
        if canonical_re.match(child.name):
            continue
        slug = _story_slug(text)
        target = PROJECTS_DIR / _folder_name_for(slug, digest)
        if target == child or target.exists():
            continue
        try:
            child.rename(target)
        except OSError:
            pass

    # Phase 2: move every still-direct-child story folder into its app folder.
    for child in list(PROJECTS_DIR.iterdir()):
        if not child.is_dir() or child.name in _NON_APP_TOP_DIRS:
            continue
        if _is_app_folder(child):
            continue
        story_path = child / "user_story.txt"
        if not story_path.exists():
            continue
        try:
            text = story_path.read_text(encoding="utf-8")
        except OSError:
            continue
        app_id = _extract_app_id(text)
        if app_id == "_unknown":
            # No URL — leave the folder where it is so the user can manually triage.
            continue
        app_folder = _app_dir(app_id)
        app_folder.mkdir(parents=True, exist_ok=True)
        target = app_folder / child.name
        if target.exists():
            # Collision — leave the source alone; user can resolve manually.
            continue
        try:
            child.rename(target)
        except OSError:
            continue

    # Phase 3: for every app folder, build/refresh _shared/ from the stories
    # under it. Last-write-wins; we don't try to merge overlapping files.
    for child in list(PROJECTS_DIR.iterdir()):
        if not _is_app_folder(child):
            continue
        app_id = child.name
        shared = _app_shared_dir(app_id)
        # Skip if shared already has substantial content — we don't want to
        # regress newer versions back to older ones. Per-story promotion (via
        # `promote_to_shared`) keeps this current going forward.
        if app_shared_has_work(app_id)["exists"]:
            _rebuild_flow_index(app_id)
            continue
        # Seed from every story's pages / step_defs / mcp-selectors.
        for story_folder in child.iterdir():
            if not story_folder.is_dir() or story_folder.name in _NON_APP_TOP_DIRS:
                continue
            for rel, pat in (("pages", "page_*.py"),
                             ("step_defs", "*_steps.py"),
                             ("mcp-selectors", "*.json")):
                src = story_folder / rel
                if not src.exists():
                    continue
                dst = shared / rel
                dst.mkdir(parents=True, exist_ok=True)
                for f in src.glob(pat):
                    try:
                        (dst / f.name).write_bytes(f.read_bytes())
                    except OSError:
                        continue
                # Always also copy scaffolding once
                for must_have in ("__init__.py", "base_page.py", "_selectors.py"):
                    mf = src / must_have
                    if mf.exists() and not (dst / must_have).exists():
                        try:
                            (dst / must_have).write_bytes(mf.read_bytes())
                        except OSError:
                            pass
        if shared.exists():
            _rebuild_flow_index(app_id)


def compute_story_id(text: str) -> str:
    """Return the relative path (under /projects/) that holds this story's
    artifacts. Always app-prefixed in the new layout: `<app_id>/<slug>__<digest>`.

    Re-binds to an existing folder if its `.story_id` sidecar matches the
    digest — so re-pasting the same story always serves the cached files
    without regenerating. Returns '' for empty/placeholder stories."""
    digest = _content_digest(text)
    if not digest:
        return ""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_folders()
    # Search BOTH the app-nested layout AND any legacy direct-child folders.
    for app_folder in PROJECTS_DIR.iterdir():
        if not app_folder.is_dir():
            continue
        if _is_app_folder(app_folder):
            for story_folder in app_folder.iterdir():
                if not story_folder.is_dir() or story_folder.name in _NON_APP_TOP_DIRS:
                    continue
                sidecar = story_folder / ".story_id"
                if sidecar.exists():
                    try:
                        if sidecar.read_text(encoding="utf-8").strip() == digest:
                            return f"{app_folder.name}/{story_folder.name}"
                    except OSError:
                        continue
        else:
            sidecar = app_folder / ".story_id"
            if sidecar.exists():
                try:
                    if sidecar.read_text(encoding="utf-8").strip() == digest:
                        # Legacy direct-child folder; return as-is.
                        return app_folder.name
                except OSError:
                    continue
    # Fresh story: derive app + slug-based folder name.
    app_id = _extract_app_id(text)
    slug = _story_slug(text)
    return f"{app_id}/{_folder_name_for(slug, digest)}"


def project_dir(story_id: str) -> Path:
    return PROJECTS_DIR / story_id


# ---------------------------------------------------------------------------
# Cross-project flow reuse — find a prior project whose user_story.txt covers
# the same site / login / flow and offer to fork it so the agent only writes
# the DELTA (new steps) instead of regenerating everything from scratch.
# ---------------------------------------------------------------------------

# Words that signal a meaningful flow step (used by the similarity scorer).
# We deliberately include verbs the user tends to write in stories, plus the
# common destinations they navigate to.
_FLOW_KEYWORDS = (
    "login", "log in", "sign in", "signin", "sign-in",
    "dashboard", "manager", "admin", "employee", "employees",
    "all employees", "all-employees", "directory",
    "search", "filter", "department", "downloads", "download csv",
    "cart", "add to cart", "checkout", "place order", "place an order",
    "quote", "create quote", "submit quote",
    "my account", "my quotes", "order history",
    "logout", "sign out",
)


def _extract_flow_signals(story_text: str) -> dict:
    """Pull comparable signals out of a user story:
       - urls         : every http(s) URL referenced
       - creds        : every 'username:password' or 'manager_id 499' / 'password ...' pair
       - keywords     : flow verbs/destinations present in the text (lower-case)
       - tokens       : tokenised lowercase word set (for jaccard fallback)
    """
    import re as _re
    text = (story_text or "").lower()
    urls = set(_re.findall(r"https?://[^\s\"'>)]+", text))
    # Strip the trailing path so http://foo/bar and http://foo/baz still match.
    hosts = set()
    for u in urls:
        m = _re.match(r"https?://([^/\s]+)", u)
        if m:
            hosts.add(m.group(1))
    # Credentials: catch "manager id 499" / "password pass123" / "user@x.com" patterns.
    cred_signals = set()
    cred_signals.update(_re.findall(r"\b\d{3,6}\b", text))                 # manager IDs
    cred_signals.update(_re.findall(r"[a-z0-9._%+-]+@[a-z0-9.-]+", text))  # emails
    # Flow keywords actually present in the story.
    keywords = {k for k in _FLOW_KEYWORDS if k in text}
    # Generic token bag (words ≥ 4 chars, minus stopwords).
    stopwords = {"the", "and", "with", "from", "that", "this", "then",
                 "when", "given", "user", "page", "click", "should",
                 "feature", "scenario", "into", "have", "been", "must"}
    tokens = {w for w in _re.findall(r"[a-z][a-z0-9_-]{3,}", text)
              if w not in stopwords}
    return {
        "hosts": hosts,
        "creds": cred_signals,
        "keywords": keywords,
        "tokens": tokens,
    }


def _score_similarity(a: dict, b: dict) -> float:
    """Return a 0.0–1.0 similarity score between two flow-signal dicts.

    Weights — keyword overlap is the heaviest signal because flow verbs like
    'all employees' / 'download csv' / 'create quote' are far more meaningful
    than generic prose tokens, and stories rarely include the full URL inline:
        hosts match       : 0.30  (same host → very likely same site)
        creds overlap     : 0.20  (same manager ID / email — strong but rare)
        keyword overlap   : 0.40  (login + dashboard + employees + downloads … )
        token overlap     : 0.10  (jaccard fallback for everything else)
    """
    def _jaccard(x: set, y: set) -> float:
        if not x and not y:
            return 0.0
        return len(x & y) / len(x | y) if (x | y) else 0.0

    def _containment(x: set, y: set) -> float:
        """How much of the SMALLER set is in the larger one. Better than
        Jaccard for 'is this story a subset of that flow?' — a short new
        story whose keywords are ALL covered by a longer prior story scores
        1.0 (you really do already have its flow), whereas Jaccard would
        dilute that to ~0.3."""
        if not x or not y:
            return 0.0
        return len(x & y) / min(len(x), len(y))

    host_score = 1.0 if (a["hosts"] & b["hosts"]) else 0.0
    cred_score = _jaccard(a["creds"], b["creds"])
    # Containment for keywords — what fraction of the smaller-story's flow
    # verbs are present in the larger story.
    kw_score = _containment(a["keywords"], b["keywords"])
    tok_score = _jaccard(a["tokens"], b["tokens"])

    return round(
        0.30 * host_score
        + 0.20 * cred_score
        + 0.40 * kw_score
        + 0.10 * tok_score,
        3,
    )


def find_similar_projects(new_story_text: str,
                          *, exclude_id: str = "",
                          min_score: float = 0.30,
                          top_n: int = 3) -> list[dict]:
    """Scan /projects/* and return the best-matching prior projects.

    Returns a list of {project_id, score, label, signals_summary, has_pages,
    has_step_defs, has_features} dicts, sorted by score (descending). Only
    projects with score ≥ min_score and at least one of (pages/step_defs/
    features) on disk are returned — we won't offer to fork an empty shell."""
    new_sig = _extract_flow_signals(new_story_text)
    if not new_sig["tokens"] and not new_sig["hosts"]:
        return []
    matches: list[dict] = []
    if not PROJECTS_DIR.exists():
        return []
    for child in PROJECTS_DIR.iterdir():
        if not child.is_dir() or child.name == exclude_id:
            continue
        story_file = child / "user_story.txt"
        if not story_file.exists():
            continue
        try:
            text = story_file.read_text(encoding="utf-8")
        except OSError:
            continue
        sig = _extract_flow_signals(text)
        score = _score_similarity(new_sig, sig)
        if score < min_score:
            continue
        has_pages = (child / "pages").exists() and any((child / "pages").glob("page_*.py"))
        has_steps = (child / "step_defs").exists() and any((child / "step_defs").glob("*_steps.py"))
        has_feats = (child / "features").exists() and any((child / "features").glob("*.feature"))
        if not (has_pages or has_steps or has_feats):
            continue
        matches.append({
            "project_id": child.name,
            "score": score,
            "label": story_label(text),
            "shared_hosts": sorted(new_sig["hosts"] & sig["hosts"]),
            "shared_keywords": sorted(new_sig["keywords"] & sig["keywords"]),
            "shared_creds": sorted(new_sig["creds"] & sig["creds"]),
            "has_pages": has_pages,
            "has_step_defs": has_steps,
            "has_features": has_feats,
        })
    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches[:top_n]


def fork_project_into_workspace(source_project_id: str, target_story_id: str) -> dict:
    """Copy a prior project's REUSABLE artifacts — pages/, step_defs/,
    mcp-selectors/ — into the flat workspace so the agent can extend them.

    Deliberately NOT copied:
      · features/         — these are the OLD story's Gherkin. They must NOT
                            shadow the user's new story. ① Generate Gherkin
                            will produce features for the NEW story; ②
                            Framework will then map those new features to
                            the reused POMs (and add new methods as needed).
      · user_data.json    — sidecar test data is story-specific. Pulling in
                            the old story's CSV would mislead the user (this
                            was the failure mode the user reported).
      · tests/            — generated from features; ② will regenerate.

    Returns a summary dict with counts of files copied per category."""
    src = PROJECTS_DIR / source_project_id
    if not src.exists():
        raise FileNotFoundError(f"Source project not found: {source_project_id}")
    dst_proj = PROJECTS_DIR / target_story_id
    dst_proj.mkdir(parents=True, exist_ok=True)

    summary = {"pages": 0, "step_defs": 0, "selectors": 0}

    def _copy_subtree(rel: str, key: str) -> None:
        s = src / rel
        if not s.exists():
            return
        d_proj = dst_proj / rel
        d_proj.mkdir(parents=True, exist_ok=True)
        d_ws = PROJECT_ROOT / rel
        d_ws.mkdir(parents=True, exist_ok=True)
        for f in s.rglob("*"):
            if f.is_dir():
                continue
            try:
                rel_path = f.relative_to(s)
                (d_proj / rel_path).parent.mkdir(parents=True, exist_ok=True)
                (d_proj / rel_path).write_bytes(f.read_bytes())
                (d_ws / rel_path).parent.mkdir(parents=True, exist_ok=True)
                (d_ws / rel_path).write_bytes(f.read_bytes())
                summary[key] += 1
            except OSError:
                continue

    _copy_subtree("pages", "pages")
    _copy_subtree("step_defs", "step_defs")
    _copy_subtree("mcp-selectors", "selectors")
    return summary


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


def write_story_readme(story_id: str) -> None:
    """Write/refresh README.md at the root of /projects/<story_id>/ so the folder
    is self-describing when browsed in Explorer or VS Code."""
    if not story_id:
        return
    proj = project_dir(story_id)
    proj.mkdir(parents=True, exist_ok=True)
    archived_story = proj / "user_story.txt"
    if archived_story.exists():
        story_text = archived_story.read_text(encoding="utf-8")
    elif USER_STORY_PATH.exists():
        story_text = USER_STORY_PATH.read_text(encoding="utf-8")
    else:
        story_text = ""
    label = story_label(story_text)
    n_features = len(list((proj / "features").glob("*.feature"))) if (proj / "features").exists() else 0
    n_tests = len(list((proj / "tests").glob("test_*.py"))) if (proj / "tests").exists() else 0
    has_report = (proj / "reports" / "report.html").exists()
    feature_list = sorted((proj / "features").glob("*.feature")) if (proj / "features").exists() else []
    test_list = sorted((proj / "tests").glob("test_*.py")) if (proj / "tests").exists() else []

    lines = [
        f"# {label}",
        "",
        f"- **Story id:** `{story_id}`",
        f"- **Last updated:** {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Counts:** {n_features} feature(s) · {n_tests} test(s)"
        + ("  ·  report ✓" if has_report else ""),
        "",
        "## Folder layout",
        "",
        "| Path | Contents |",
        "|---|---|",
        "| `features/`      | Gherkin `.feature` files (one per scenario) |",
        "| `pages/`         | Page Object Model classes |",
        "| `step_defs/`     | pytest-bdd step definitions |",
        "| `tests/`         | pytest-bdd test entrypoints |",
        "| `mcp-selectors/` | Live selectors captured by Playwright MCP |",
        "| `reports/`       | HTML + Allure run artifacts |",
        "| `process_log.txt`| Timestamped subprocess history |",
        "",
    ]
    if feature_list:
        lines.append("## Feature files")
        lines.append("")
        for f in feature_list:
            title = _extract_feature_title(f) or f.stem
            lines.append(f"- `features/{f.name}` — {title}")
        lines.append("")
    if test_list:
        lines.append("## Tests")
        lines.append("")
        for t in test_list:
            lines.append(f"- `tests/{t.name}`")
        lines.append("")
    lines += [
        "## User story",
        "",
        "```",
        (story_text.strip() or "(empty)"),
        "```",
        "",
        "_Auto-generated by `agent_ui.py` — refreshed each phase. Edits will be overwritten._",
        "",
    ]
    (proj / "README.md").write_text("\n".join(lines), encoding="utf-8")


def append_process_log(story_id: str, msg: str) -> None:
    if not story_id:
        return
    proj = project_dir(story_id)
    proj.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with (proj / "process_log.txt").open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {msg}\n")


def _safe_copytree(src: Path, dst: Path) -> tuple[int, list[str]]:
    """Manual recursive copy that tolerates per-file errors. shutil.copytree
    raises on ANY failed file (e.g. a screenshot that pytest deleted between
    listing and copying), which kills archiving entirely. This walks the tree
    and skips individual failures, returning (copied_count, error_messages)."""
    errors: list[str] = []
    count = 0
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    try:
        dst.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return 0, [f"mkdir {dst}: {exc}"]
    import os as _os
    for root, dirs, files in _os.walk(str(src)):
        # Skip cache directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        rel = Path(root).relative_to(src)
        target_dir = dst / rel if rel != Path(".") else dst
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            errors.append(f"mkdir {target_dir}: {exc}")
            continue
        for f in files:
            if f.endswith(".pyc"):
                continue
            sf = Path(root) / f
            df = target_dir / f
            try:
                shutil.copy2(sf, df)
                count += 1
            except (OSError, FileNotFoundError) as exc:
                # File disappeared during walk, locked, or permission denied.
                # Skip — we'd rather archive 99% of files than fail entirely.
                errors.append(f"{f}: {type(exc).__name__}")
    return count, errors


def archive_artifacts(story_id: str, phase: str) -> None:
    if not story_id:
        return
    proj = project_dir(story_id)
    proj.mkdir(parents=True, exist_ok=True)
    story_text = (
        USER_STORY_PATH.read_text(encoding="utf-8") if USER_STORY_PATH.exists() else ""
    )
    (proj / "user_story.txt").write_text(story_text, encoding="utf-8")
    # The story id stays bound to story content only — the JSON travels with the
    # story but doesn't change the folder name when its values change.
    digest = _content_digest(story_text)
    if digest:
        try:
            (proj / ".story_id").write_text(digest, encoding="utf-8")
        except OSError:
            pass
    _archive_user_data(story_id)
    total_copied = 0
    total_errors: list[str] = []
    for d in ARTIFACT_DIRS:
        src = PROJECT_ROOT / d
        dst = proj / d
        if src.exists():
            n, errs = _safe_copytree(src, dst)
            total_copied += n
            total_errors.extend(errs)
    write_story_readme(story_id)
    msg = f"Archived artifacts after phase: {phase} — {total_copied} files copied"
    if total_errors:
        msg += f", {len(total_errors)} file(s) skipped (e.g. {total_errors[0]})"
    append_process_log(story_id, msg)


def restore_artifacts(story_id: str) -> bool:
    proj = project_dir(story_id)
    if not proj.exists():
        return False
    restored = False
    for d in ARTIFACT_DIRS:
        src = proj / d
        dst = PROJECT_ROOT / d
        if src.exists() and any(src.iterdir()):
            n, _errs = _safe_copytree(src, dst)
            if n > 0:
                restored = True
    _restore_user_data(story_id)
    return restored


def flat_has_features() -> bool:
    return FEATURES_DIR.exists() and any(FEATURES_DIR.glob("*.feature"))


def flat_has_framework() -> bool:
    return (
        flat_has_features()
        and PAGES_DIR.exists()
        and any(p for p in PAGES_DIR.glob("*.py") if p.name not in ("base_page.py", "__init__.py"))
        and STEP_DEFS_DIR.exists()
        and any(p.name != "__init__.py" for p in STEP_DEFS_DIR.glob("*.py"))
        and TESTS_DIR.exists()
        and any(TESTS_DIR.glob("test_*.py"))
    )


def story_folder_state(story_id: str) -> dict[str, bool]:
    """Check the story's folder under /projects/<id>/ to see what files have already been
    generated for this exact story. The story folder is the persistent workspace per story id.

    A framework counts as 'ready' when features + step_defs + a pytest entrypoint all
    exist. Page Objects are a style preference, not a hard requirement — some Claude
    generations call Playwright directly from step defs and still produce passing
    tests. Demanding POMs here would punish the user by regenerating a runnable
    framework, which is exactly the opposite of what cached behavior is for."""
    if not story_id:
        return {"gherkin": False, "framework": False}
    proj = project_dir(story_id)
    if not proj.exists():
        return {"gherkin": False, "framework": False}
    has_features = (proj / "features").exists() and any((proj / "features").glob("*.feature"))
    step_defs_dir = proj / "step_defs"
    tests_dir = proj / "tests"
    has_framework = (
        has_features
        and step_defs_dir.exists()
        and any(p for p in step_defs_dir.glob("*.py") if p.name != "__init__.py")
        and tests_dir.exists() and any(tests_dir.glob("test_*.py"))
    )
    return {"gherkin": has_features, "framework": has_framework}


def story_feature_count(story_id: str) -> int:
    if not story_id:
        return 0
    p = project_dir(story_id) / "features"
    return len(list(p.glob("*.feature"))) if p.exists() else 0


def story_test_count(story_id: str) -> int:
    if not story_id:
        return 0
    p = project_dir(story_id) / "tests"
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


def discover_tests(story_id: str) -> list[dict]:
    """Return one row per discovered pytest-bdd test file for this story.
    Each row: {file: Path, rel: str, name: str, title: str, feature: Path|None}."""
    proj = project_dir(story_id) if story_id else None
    tests_dir = (proj / "tests") if proj else TESTS_DIR
    features_dir = (proj / "features") if proj else FEATURES_DIR
    if not tests_dir.exists():
        return []
    rows: list[dict] = []
    for test_file in sorted(tests_dir.glob("test_*.py")):
        feature = _feature_for_test(test_file, features_dir)
        title = _extract_feature_title(feature) if feature else ""
        # pytest target should be relative to PROJECT_ROOT (the flat workspace),
        # because that's where pytest runs from after restore_artifacts(...)
        flat_target = (TESTS_DIR / test_file.name).relative_to(PROJECT_ROOT).as_posix()
        rows.append({
            "file": test_file,
            "rel": flat_target,
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
    if not CONFTEST_PATH.exists():
        return
    text = CONFTEST_PATH.read_text(encoding="utf-8")
    new_text = re.sub(
        r"pytest_plugins\s*=\s*\([^)]*\)",
        "pytest_plugins = ()",
        text,
        count=1,
    )
    if new_text != text:
        CONFTEST_PATH.write_text(new_text, encoding="utf-8")


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
    if not CONFTEST_PATH.exists():
        return []
    feature_stems = (
        {p.stem for p in FEATURES_DIR.glob("*.feature")}
        if FEATURES_DIR.exists() else set()
    )
    all_steps = sorted(
        p.stem for p in STEP_DEFS_DIR.glob("*_steps.py")
    ) if STEP_DEFS_DIR.exists() else []
    matched = [
        s for s in all_steps
        if any(s == f"{fstem}_steps" for fstem in feature_stems)
    ]
    modules = matched or all_steps
    plugins = tuple(f"step_defs.{m}" for m in modules)

    text = CONFTEST_PATH.read_text(encoding="utf-8")
    new_text = re.sub(
        r"pytest_plugins\s*=\s*\([^)]*\)",
        f"pytest_plugins = {plugins!r}",
        text,
        count=1,
    )
    if new_text != text:
        CONFTEST_PATH.write_text(new_text, encoding="utf-8")
    return list(plugins)


def reset_locators() -> None:
    LOCATORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCATORS_PATH.write_text("{}\n", encoding="utf-8")
    if DISCOVERY_META_PATH.exists():
        try:
            DISCOVERY_META_PATH.unlink()
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

_CAPTURED_VALUES_FILE = REPORTS_DIR / "captured_values.json"


def _load_captured_values() -> list[dict]:
    if not _CAPTURED_VALUES_FILE.exists():
        return []
    try:
        data = json.loads(_CAPTURED_VALUES_FILE.read_text(encoding="utf-8"))
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
    p = REPORTS_DIR / "step_trace.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    steps = data.get("steps") if isinstance(data, dict) else data
    return list(steps or [])


def _img_data_uri(rel_path: str) -> str:
    """Inline a screenshot (path relative to reports/) as a base64 data URI so
    the report HTML is fully self-contained and portable."""
    if not rel_path:
        return ""
    fp = REPORTS_DIR / rel_path
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


# Mirror of conftest.BACKEND_ERROR_MARKERS (kept local to avoid importing the
# test module here). Phrases that mean a state-changing action was rejected.
_BACKEND_ERROR_MARKERS = (
    "already exists", "already in use", "already registered", "duplicate",
    "exist", "exists",   # also catches "name exist" / "organization name exist"
    "could not", "couldn't", "cannot be", "unable to", "failed to",
    "was rejected", "not created", "not saved", "something went wrong",
    "error:",
)
# Only values whose LABEL looks like an action result are scanned — so a
# negative-path test that *records* an expected error elsewhere isn't flagged.
_ACTION_RESULT_LABEL_HINTS = (
    "response", "result", "toast", "confirmation", "outcome", "verdict",
    "server",
)


def _detect_unhandled_backend_errors(buckets: dict) -> list[str]:
    """Safety net: catch a backend rejection sitting in the captured output that
    NO assertion/prerequisite flagged (i.e. a step def forgot to verify the
    action). Conservative by design so it never trips a negative-path test that
    legitimately verifies an error:
      * only `value` entries whose label looks like an action result,
      * only strong rejection markers,
      * skip any text the test EXPECTED (a passed assertion's expected/actual)."""
    expected: set[str] = set()
    for a in buckets.get("assertions", []):
        if a.get("passed"):
            for k in ("expected", "actual"):
                t = (a.get(k) or "").strip().lower()
                if t:
                    expected.add(t)
    hits: list[str] = []
    for v in buckets.get("values", []):
        label = (v.get("label") or "").lower()
        text = (v.get("value") or "").strip()
        low = text.lower()
        if not text or low in expected:
            continue
        if not any(h in label for h in _ACTION_RESULT_LABEL_HINTS):
            continue
        if any(m in low for m in _BACKEND_ERROR_MARKERS):
            hits.append(f"{v.get('label')}: {text}")
    return hits


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
    # here would wrongly override those intentional verdicts. (_detect_unhandled_
    # backend_errors remains available for diagnostics but is not applied.)

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
    archived_story = project_dir(story_id) / "user_story.txt" if story_id else None
    if archived_story and archived_story.exists():
        try:
            story_text = archived_story.read_text(encoding="utf-8")
        except OSError:
            story_text = ""
    elif USER_STORY_PATH.exists():
        try:
            story_text = USER_STORY_PATH.read_text(encoding="utf-8")
        except OSError:
            story_text = ""

    pytest_html_exists = HTML_REPORT.exists()

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
    story_id: str,
    pytest_exit_code: int,
) -> dict[str, str]:
    """Build + write the report. Returns the dict so callers can inspect verdict."""
    run_timestamp = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = build_inline_coverage_report(story_id, pytest_exit_code, run_timestamp)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "story_coverage.html").write_text(out["html"], encoding="utf-8")
    (REPORTS_DIR / "story_coverage.md").write_text(out["md"], encoding="utf-8")
    (REPORTS_DIR / "story_coverage.json").write_text(out["json"], encoding="utf-8")
    # Snapshot to /projects/<id>/reports/runs/<ts>/ so the user can browse history
    if story_id:
        runs_dir = project_dir(story_id) / "reports" / "runs" / run_timestamp
        try:
            runs_dir.mkdir(parents=True, exist_ok=True)
            for name in ("story_coverage.html", "story_coverage.md",
                         "story_coverage.json", "captured_values.json"):
                src = REPORTS_DIR / name
                if src.exists():
                    (runs_dir / name).write_bytes(src.read_bytes())
            if HTML_REPORT.exists():
                (runs_dir / "report.html").write_bytes(HTML_REPORT.read_bytes())
            if SCREENSHOT_DIR.exists() and SCREENSHOT_DIR.is_dir():
                ss_dst = runs_dir / "screenshots"
                ss_dst.mkdir(parents=True, exist_ok=True)
                for f in SCREENSHOT_DIR.glob("*"):
                    if f.is_file():
                        try:
                            (ss_dst / f.name).write_bytes(f.read_bytes())
                        except OSError:
                            continue
        except OSError:
            pass
    out["run_timestamp"] = run_timestamp
    return out


def discover_run_history(story_id: str) -> list[dict]:
    """Return list of historical runs for a story, newest first.
    Each entry: {timestamp, verdict, html_path, dir, has_pytest_html}."""
    if not story_id:
        return []
    runs_dir = project_dir(story_id) / "reports" / "runs"
    if not runs_dir.exists():
        return []
    results: list[dict] = []
    for d in runs_dir.iterdir():
        if not d.is_dir():
            continue
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
    results.sort(key=lambda r: r["timestamp"], reverse=True)
    return results


def clean_reports() -> None:
    if ALLURE_RESULTS.exists():
        shutil.rmtree(ALLURE_RESULTS, ignore_errors=True)
    if SCREENSHOT_DIR.exists():
        shutil.rmtree(SCREENSHOT_DIR, ignore_errors=True)
    if HTML_REPORT.exists():
        try:
            HTML_REPORT.unlink()
        except OSError:
            pass


def clean_artifacts(scope: str, *, preserve_code: bool = False) -> None:
    """Wipe generated artifacts.

    scope='gherkin' → wipes features/*.feature in addition to the framework code.
    scope='tests'   → leaves features/ alone; just wipes framework code.
    scope='all'     → wipes both.

    preserve_code=True keeps pages/step_defs/tests intact. Use this when
    ① is running in FORK MODE — the forked POMs/step defs must survive
    ①'s "generate gherkin" pass so that ② DELTA mode can build on top of
    them. Without this guard the existing logic wiped them on every ① click."""
    if scope in ("gherkin", "all"):
        _delete_files(FEATURES_DIR, keep=set(), glob="*.feature")
    if not preserve_code:
        _delete_files(PAGES_DIR, keep={"base_page.py", "__init__.py"}, glob="*.py")
        _delete_files(STEP_DEFS_DIR, keep={"__init__.py"}, glob="*.py")
        _delete_files(TESTS_DIR, keep={"__init__.py"}, glob="test_*.py")
        reset_pytest_plugins()
        reset_locators()
    clean_reports()


def syntax_check_generated() -> tuple[bool, list[str]]:
    errors: list[str] = []
    targets: list[Path] = []
    targets.extend([p for p in PAGES_DIR.glob("*.py") if p.name not in ("__init__.py",)])
    targets.extend([p for p in STEP_DEFS_DIR.glob("*.py") if p.name != "__init__.py"])
    targets.extend(TESTS_DIR.glob("test_*.py"))
    for f in targets:
        try:
            ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as e:
            errors.append(f"{f.relative_to(PROJECT_ROOT)}: {e.msg} (line {e.lineno})")
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
                   heartbeat_secs: int = 10) -> int:
    """Run a command, stream stdout to the activity panel, and emit a heartbeat
    line every `heartbeat_secs` seconds of silence so long MCP/Claude steps with
    no console output don't make the UI look frozen.

    `cmd` may be either:
      - a list[str]  → no stdin, run as-is (pytest, generic commands)
      - a tuple (list[str], str)  → first element is argv, second is text to
        pipe via stdin. Used by `claude_command()` so huge prompts don't blow
        through Windows' 8KB cmdline limit.
    """
    stdin_text: str | None = None
    if isinstance(cmd, tuple) and len(cmd) == 2 and isinstance(cmd[1], str):
        cmd, stdin_text = list(cmd[0]), cmd[1]

    display = _redact_command(cmd)
    log.append(f"$ {display}")
    if story_id:
        append_process_log(story_id, f"exec: {display}")
    placeholder.code("\n".join(log[-500:]) or "(no output)", language="bash")

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
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


# ---------------------------------------------------------------------------
# Multi-agent framework generation
# ---------------------------------------------------------------------------

SCOUT_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("sitemap",   SCOUT_SITEMAP_PROMPT,   "mcp-selectors/scout_sitemap.json"),
    ("inventory", SCOUT_INVENTORY_PROMPT, "mcp-selectors/scout_inventory.json"),
    ("flow",      SCOUT_FLOW_PROMPT,      "mcp-selectors/scout_flow.json"),
    ("edge",      SCOUT_EDGE_PROMPT,      "mcp-selectors/scout_edge.json"),
)


def _ensure_scout_dir() -> None:
    LOCATORS_PATH.parent.mkdir(parents=True, exist_ok=True)


SCOUT_HARD_TIMEOUT_SECS = 300  # 5 min per scout — kill if it exceeds this
SCOUT_SILENT_TIMEOUT_SECS = 180  # 3 min with no activity from a scout → kill


def run_parallel_scouts(log_placeholder, log_buf: list[str], story_id: str = "",
                        hb_secs: int = 10) -> dict[str, dict]:
    """Spawn all four scouts as concurrent `claude -p --output-format stream-json`
    subprocesses. Parse every JSON event per scout and surface real tool calls
    (Navigating to…, Clicking…, Typing…) into the activity log, prefixed with
    [role]. Per-scout hard timeout + silent timeout: any scout that exceeds
    either gets killed and marked failed so synthesis isn't blocked forever.

    Heartbeat shows the LAST activity per scout, not just 'running'.

    Returns {role: {rc, json_path, json_ok, elapsed, last_activity, killed}}."""
    _ensure_scout_dir()

    # Wipe previous scout outputs so a partial run can't fool synthesis.
    for _, _, rel_path in SCOUT_DEFINITIONS:
        p = PROJECT_ROOT / rel_path
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

    _emit(log_buf, 
        f"[orchestrator] Launching {len(SCOUT_DEFINITIONS)} scouts in parallel: "
        + ", ".join(role for role, _, _ in SCOUT_DEFINITIONS)
    )
    log_placeholder.code("\n".join(log_buf[-500:]), language="bash")
    if story_id:
        append_process_log(story_id, "scouts: launching " + ",".join(r for r, _, _ in SCOUT_DEFINITIONS))

    output_q: queue.Queue = queue.Queue()
    SENTINEL = object()
    scouts: dict[str, dict] = {}

    def _drain(role: str, stream) -> None:
        try:
            for line in stream:
                output_q.put((role, line.rstrip()))
        finally:
            output_q.put((role, SENTINEL))

    for role, prompt, out_rel in SCOUT_DEFINITIONS:
        scout_cmd, scout_stdin = claude_command(prompt, SCOUT_TOOLS)
        try:
            proc = subprocess.Popen(
                scout_cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=build_env(),
            )
            # Pipe the huge prompt via stdin (avoids Windows 8KB cmdline cap)
            if proc.stdin is not None:
                try:
                    proc.stdin.write(scout_stdin)
                    proc.stdin.close()
                except Exception:
                    pass
        except FileNotFoundError as exc:
            _emit(log_buf, f"[orchestrator] {role}: failed to start — {exc}")
            scouts[role] = {
                "rc": 127, "json_path": PROJECT_ROOT / out_rel,
                "json_ok": False, "elapsed": 0, "started": False,
                "last_activity": "failed to start", "last_event_at": time.monotonic(),
                "killed": False,
            }
            continue
        scouts[role] = {
            "proc": proc, "rc": None, "json_path": PROJECT_ROOT / out_rel,
            "json_ok": False, "elapsed": 0, "started_at": time.monotonic(),
            "started": True, "last_activity": "(starting…)",
            "last_event_at": time.monotonic(), "killed": False,
        }
        threading.Thread(target=_drain, args=(role, proc.stdout), daemon=True).start()
        _emit(log_buf, f"[orchestrator] {role}: started (pid {proc.pid})")
    log_placeholder.code("\n".join(log_buf[-500:]), language="bash")

    active = {role for role, info in scouts.items() if info.get("started")}
    overall_start = time.monotonic()
    while active:
        try:
            role, item = output_q.get(timeout=hb_secs)
        except queue.Empty:
            now = time.monotonic()
            elapsed = int(now - overall_start)
            # Check for hard / silent timeouts and kill offenders.
            for r in list(active):
                info = scouts[r]
                age = now - info["started_at"]
                silent = now - info["last_event_at"]
                if age > SCOUT_HARD_TIMEOUT_SECS or silent > SCOUT_SILENT_TIMEOUT_SECS:
                    try:
                        info["proc"].kill()
                    except Exception:
                        pass
                    info["killed"] = True
                    reason = "hard timeout" if age > SCOUT_HARD_TIMEOUT_SECS else "silent timeout"
                    _emit(log_buf, 
                        f"[orchestrator] {r}: KILLED — {reason} "
                        f"(age={int(age)}s, silent={int(silent)}s)"
                    )
                    # Drain thread will push SENTINEL once stdout closes
            running = sorted(active)
            # Build a heartbeat that shows what each running scout last did.
            parts = []
            for r in running:
                last = scouts[r].get("last_activity") or "(no events yet)"
                parts.append(f"{r}={_shorten(last, 60)}")
            _emit(log_buf, 
                f"[orchestrator] +{elapsed}s · {len(running)}/4 still running · "
                + " | ".join(parts)
            )
            log_placeholder.code("\n".join(log_buf[-500:]), language="bash")
            continue

        if item is SENTINEL:
            info = scouts[role]
            info["proc"].wait()
            info["rc"] = info["proc"].returncode
            info["elapsed"] = int(time.monotonic() - info["started_at"])
            info["json_ok"] = _validate_scout_json(info["json_path"])
            if info.get("killed"):
                verdict = "KILLED"
            elif info["rc"] == 0 and info["json_ok"]:
                verdict = "OK"
            elif info["rc"] != 0:
                verdict = f"exit {info['rc']}"
            else:
                verdict = "no usable JSON"
            _emit(log_buf, 
                f"[orchestrator] {role}: finished — {verdict} "
                f"after {info['elapsed']}s"
            )
            if story_id:
                append_process_log(
                    story_id,
                    f"scout {role} done: rc={info['rc']} json_ok={info['json_ok']} killed={info.get('killed')}"
                )
            active.discard(role)
        else:
            # Parse stream-json event(s) from this line and emit friendly lines.
            scouts[role]["last_event_at"] = time.monotonic()
            parsed: list[str] = []
            _format_stream_event(item, parsed)
            for friendly in parsed:
                _emit(log_buf, f"[{role}] {friendly}")
                # Keep the most recent action-like line as last_activity (skip
                # generic 💬 commentary — prefer tool calls and results).
                if friendly and not friendly.startswith("💬"):
                    scouts[role]["last_activity"] = friendly
        log_placeholder.code("\n".join(log_buf[-500:]), language="bash")

    succeeded = [r for r, info in scouts.items() if info["rc"] == 0 and info["json_ok"]]
    failed = [r for r, info in scouts.items() if r not in succeeded]
    total = int(time.monotonic() - overall_start)
    _emit(log_buf, 
        f"[orchestrator] Phase 1 done in {total}s — "
        f"succeeded: {succeeded or 'none'} | failed: {failed or 'none'}"
    )
    log_placeholder.code("\n".join(log_buf[-500:]), language="bash")
    return scouts


def _validate_scout_json(path: Path) -> bool:
    """A scout output is usable if the file exists and parses as JSON with a
    non-trivial body."""
    if not path.exists():
        return False
    try:
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(data) and isinstance(data, (dict, list))


def run_multi_agent_framework(log_placeholder, log_buf: list[str], story_id: str = "",
                              hb_secs: int = 10) -> int:
    """Orchestrate scouts → synthesis. Falls back to the single-agent
    FRAMEWORK_PROMPT if every scout fails to produce a usable JSON.
    Returns the synthesis (or fallback) exit code."""
    scouts = run_parallel_scouts(log_placeholder, log_buf, story_id=story_id,
                                 hb_secs=hb_secs)
    usable = sum(1 for info in scouts.values() if info["rc"] == 0 and info["json_ok"])

    if usable == 0:
        _emit(log_buf, 
            "[orchestrator] All scouts failed. Falling back to single-agent "
            "FRAMEWORK_PROMPT for safety."
        )
        log_placeholder.code("\n".join(log_buf[-500:]), language="bash")
        return stream_command(
            claude_command(FRAMEWORK_PROMPT, BUILD_TOOLS),
            log_placeholder, log_buf, story_id=story_id, heartbeat_secs=hb_secs,
        )

    _emit(log_buf, 
        f"[orchestrator] Phase 2 — synthesizing POMs / step defs / tests "
        f"from {usable}/4 scout output(s)…"
    )
    log_placeholder.code("\n".join(log_buf[-500:]), language="bash")
    return stream_command(
        claude_command(SYNTHESIS_PROMPT, BUILD_TOOLS),
        log_placeholder, log_buf, story_id=story_id, heartbeat_secs=hb_secs,
    )


def ensure_user_story() -> None:
    if not USER_STORY_PATH.exists():
        USER_STORY_PATH.write_text(USER_STORY_PLACEHOLDER, encoding="utf-8")


def _read_user_data_text() -> str:
    """Raw text of user_data.json (or '' if missing/empty)."""
    if not USER_DATA_PATH.exists():
        return ""
    try:
        return USER_DATA_PATH.read_text(encoding="utf-8")
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
STOP_SIGNAL_PATH = PROJECT_ROOT / "reports" / ".stop_signal"


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


def _archive_user_data(story_id: str) -> None:
    """Persist the current user_data.json into the story folder (latest wins).
    No-op if the user hasn't provided any JSON."""
    if not story_id:
        return
    text = _read_user_data_text()
    if not text.strip():
        return
    proj = project_dir(story_id)
    proj.mkdir(parents=True, exist_ok=True)
    try:
        (proj / "user_data.json").write_text(text, encoding="utf-8")
    except OSError:
        pass


def _restore_user_data(story_id: str) -> None:
    """Restore archived user_data.json into the flat workspace ONLY IF the user
    explicitly uploaded data for this story this session.

    The previous behaviour ("restore unless the flat workspace already has
    data") silently pulled in YESTERDAY'S sidecar files when story_id matched
    an old archive — confusing the user with test data they never gave.
    Now: only restore if `session_state["user_uploaded_data"]` is True. If
    the user genuinely uploaded data and it got wiped, they upload again."""
    if not story_id:
        return
    try:
        if not st.session_state.get("user_uploaded_data"):
            return  # user never uploaded this session — do not auto-restore stale data
    except Exception:
        # Outside a Streamlit run context (e.g. unit tests). Be conservative
        # and don't restore.
        return
    if _read_user_data_text().strip():
        return  # workspace already has data — don't clobber
    src = project_dir(story_id) / "user_data.json"
    if src.exists():
        try:
            USER_DATA_PATH.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass


def log_event(msg: str) -> None:
    """Append a timestamped line to the visible activity log."""
    ts = _dt.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    if "log" not in st.session_state:
        st.session_state.log = []
    st.session_state.log.append(line)


def initialize_session() -> None:
    """Clean Slate for the *UI session only*: wipe session_state on fresh page load
    AND reset user_story.txt to the placeholder so the user always starts from a
    blank story area on refresh — explicit user preference: refresh = fresh session,
    no past data carried over.

    Files on disk in /projects/<id>/ are NOT touched — they remain the persistent
    source of truth, retrievable by re-entering the same story."""
    if st.session_state.get("session_initialized"):
        return
    USER_STORY_PATH.write_text(USER_STORY_PLACEHOLDER, encoding="utf-8")
    # Wipe sidecar test data too — refresh = clean slate. Includes any non-JSON
    # originals (CSV/Excel/TSV) preserved from a prior session.
    for ext in (("json",) + USER_DATA_SUPPORTED_EXTENSIONS):
        p = USER_DATA_PATH.with_name(f"user_data.{ext}")
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
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
    proj = project_dir(story_id)
    feat_dir = proj / "features"
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
    proj = project_dir(story_id)
    pages_dir = proj / "pages"
    step_dir = proj / "step_defs"
    tests_dir = proj / "tests"
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
        proj = project_dir(story_id)
        html_report = proj / "reports" / "report.html"
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


def render_test_results(story_id: str) -> None:
    proj = project_dir(story_id)
    html_report = proj / "reports" / "report.html"
    allure = proj / "reports" / "allure-results"
    screenshots = proj / "reports" / "screenshots"
    coverage_md = proj / "reports" / "story_coverage.md"
    coverage_json = proj / "reports" / "story_coverage.json"
    coverage_html = proj / "reports" / "story_coverage.html"
    captured_values = proj / "reports" / "captured_values.json"

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

    if not html_report.exists():
        return
    st.markdown('<div class="section-heading" style="margin-top: 1.5rem;">'
                'Raw pytest artifacts (secondary)</div>',
                unsafe_allow_html=True)
    try:
        report_html = html_report.read_text(encoding="utf-8", errors="replace")
        report_bytes = html_report.read_bytes()
    except OSError as exc:
        st.error(f"Could not read report.html: {exc}")
        return

    cols = st.columns([1, 1, 2])
    with cols[0]:
        st.download_button(
            "⬇ Download HTML report",
            data=report_bytes,
            file_name=f"report_{story_id}.html",
            mime="text/html",
            key=f"dl_report_{story_id}",
            use_container_width=True,
            help="Download the pytest-html report to open locally.",
        )
    with cols[1]:
        st.caption(
            f"📄 `{html_report.relative_to(PROJECT_ROOT).as_posix()}` "
            f"({len(report_bytes)//1024} KB)"
        )

    # pytest-html report is SECONDARY (the Auditor's story_coverage.html above
    # is the primary). Default to collapsed so it doesn't compete visually.
    with st.expander("📊 Raw pytest-html report (developer view)", expanded=False):
        import streamlit.components.v1 as components
        components.html(report_html, height=700, scrolling=True)

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
    return len(list(FEATURES_DIR.glob("*.feature"))) if FEATURES_DIR.exists() else 0


def test_count() -> int:
    return len(list(TESTS_DIR.glob("test_*.py"))) if TESTS_DIR.exists() else 0


def render_sidebar(stories_n: int, story_id: str,
                   gherkin_done_session: bool, framework_done_session: bool) -> tuple[bool, bool, bool]:
    with st.sidebar:
        st.markdown(
            '<div style="font-size: 1rem; font-weight: 700; color: #0f172a; margin: 0.25rem 0 1rem 0;">Workflow</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-heading" style="margin-top:0;">User stories</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Upload .txt", type=["txt"], label_visibility="collapsed",
            key=f"upload_{st.session_state.get('upload_nonce', 0)}",
        )
        if uploaded is not None:
            raw = uploaded.read().decode("utf-8")
            content = normalize_story_text(raw)
            USER_STORY_PATH.write_text(content, encoding="utf-8")
            clean_artifacts(scope="gherkin")
            st.session_state.log = []
            st.session_state.last_run = "never"
            st.session_state.last_upload_info = (
                f"**{uploaded.name}** · {len(raw)} chars\n\n"
                f"Preview: `{raw[:120].replace(chr(10), ' / ')}...`"
            )
            st.session_state.upload_nonce = st.session_state.get("upload_nonce", 0) + 1
            st.rerun()

        if "last_upload_info" in st.session_state:
            st.success("Uploaded: " + st.session_state.last_upload_info)

        on_disk = USER_STORY_PATH.read_text(encoding="utf-8") if USER_STORY_PATH.exists() else ""
        is_placeholder = on_disk.strip() == USER_STORY_PLACEHOLDER.strip()
        display_value = "" if is_placeholder else on_disk
        edited = st.text_area(
            "Story content",
            display_value,
            height=200,
            label_visibility="collapsed",
            placeholder="Paste your user story here. Buttons unlock once a story is detected.",
        )
        if edited.strip() and edited != display_value:
            USER_STORY_PATH.write_text(normalize_story_text(edited), encoding="utf-8")
        elif not edited.strip() and not is_placeholder:
            USER_STORY_PATH.write_text(USER_STORY_PLACEHOLDER, encoding="utf-8")

        story_caption = (
            f"**{stories_n}** stor{'y' if stories_n == 1 else 'ies'} detected"
            + ("" if stories_n else " · paste or upload to begin")
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
        if data_uploaded is not None:
            raw_bytes = data_uploaded.read()
            json_text, msg = convert_uploaded_to_json(data_uploaded.name, raw_bytes)
            if json_text is None:
                st.error(msg or "Could not convert file.")
            else:
                # Canonical JSON used by the runtime test_data fixture
                USER_DATA_PATH.write_text(json_text, encoding="utf-8")
                # Persist the ORIGINAL file too so the user can download/inspect
                ext = data_uploaded.name.rsplit(".", 1)[-1].lower() if "." in data_uploaded.name else "bin"
                # Clear any stale original-format files first
                for prev_ext in USER_DATA_SUPPORTED_EXTENSIONS:
                    prev = USER_DATA_PATH.with_name(f"user_data.{prev_ext}")
                    if prev != USER_DATA_PATH and prev.exists():
                        try:
                            prev.unlink()
                        except OSError:
                            pass
                if ext != "json":
                    try:
                        USER_DATA_PATH.with_name(f"user_data.{ext}").write_bytes(raw_bytes)
                    except OSError:
                        pass
                if msg:
                    st.info(msg)
                # Mark this session as having uploaded data, so `_restore_user_data`
                # may pull from the archive after a clean ② / ③ if needed.
                st.session_state["user_uploaded_data"] = True
                st.session_state.data_upload_nonce = st.session_state.get("data_upload_nonce", 0) + 1
                st.rerun()

        # Hygiene: if the user hasn't actively provided data THIS SESSION, the
        # sidebar shows nothing — and we also purge any stale user_data.* files
        # left on disk by a prior session / fork / refresh-race. The story is
        # used as-is unless the user explicitly uploads or types data.
        user_provided = bool(st.session_state.get("user_uploaded_data"))
        if not user_provided:
            for ext in (("json",) + USER_DATA_SUPPORTED_EXTENSIONS):
                p = USER_DATA_PATH.with_name(f"user_data.{ext}")
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass

        # If user didn't provide data, the text_area starts empty regardless
        # of any leftover on disk (the purge above keeps disk in sync too).
        current_data_text = _read_user_data_text() if user_provided else ""
        data_edited = st.text_area(
            "Test data JSON",
            current_data_text,
            height=140,
            label_visibility="collapsed",
            placeholder='Optional. Paste JSON like {"productid":"123","Subtotal":48.99} '
                        'OR an array of objects for parameterised rows (positive + negative).',
        )
        if data_edited != current_data_text:
            if data_edited.strip():
                USER_DATA_PATH.write_text(data_edited, encoding="utf-8")
                st.session_state["user_uploaded_data"] = True
            elif USER_DATA_PATH.exists():
                try:
                    USER_DATA_PATH.unlink()
                except OSError:
                    pass
                st.session_state.pop("user_uploaded_data", None)

        # Show parse status + a tiny preview ONLY if the user provided data
        # this session. Otherwise the caption stays mute — no implication
        # that data is being used silently behind the scenes.
        if user_provided and _read_user_data_text().strip():
            parsed, err = parse_user_data(_read_user_data_text())
            # Detect if there's a preserved original (non-JSON) file
            original_ext = None
            for ext in USER_DATA_SUPPORTED_EXTENSIONS:
                if ext == "json":
                    continue
                if USER_DATA_PATH.with_name(f"user_data.{ext}").exists():
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
        elif not user_provided:
            st.caption("No test data — story will be used as-is.")

        st.markdown('<div class="section-heading">Pipeline (3 steps)</div>', unsafe_allow_html=True)

        # Step gating is purely session-state driven. Refresh the page → all three
        # locks reset; the user must always start from ①.
        # ① is enabled whenever a story is present, even after it's been clicked
        # (re-clicks just re-load the same files instantly).
        # ② is locked until ① has been clicked in this session.
        # ③ is locked until ② has been clicked in this session.
        if not gherkin_done_session:
            next_step = "gherkin"
        elif not framework_done_session:
            next_step = "framework"
        else:
            next_step = "run"

        gen_clicked = st.button(
            "① Generate Gherkin",
            type="primary" if next_step == "gherkin" and stories_n > 0 else "secondary",
            disabled=stories_n == 0,
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


# ============================================================
# Website test suites — run every story built for one application
# back-to-back, then emit a single consolidated, story-by-story report.
# ============================================================

_SUITE_URL_RE = re.compile(r"https?://[^\s\"'<>)]+", re.IGNORECASE)

# For now the Website-suites tab only surfaces these applications (by app_id /
# top-level projects/ folder name). Set to an empty tuple to show EVERY
# discovered website again.
SUITE_VISIBLE_APPS = ("ra_demo_rlcatalyst_com", "www_saucedemo_com")

# Optional per-app execution order. Each fragment is matched (case-insensitive)
# against a story's feature filename / story_id / title; listed stories run in
# this order and any not listed fall to the end (by story_id). Lets a website's
# tests run as a logical workflow instead of alphabetically.
SUITE_STORY_ORDER = {
    "ra_demo_rlcatalyst_com": [
        "create_organization",   # 1. create the organization
        "add_new_user",          # 2. add a user to it
        "delete_user",           # 3. delete that user
    ],
}


def _suite_order_key(story: dict, hints: list[str]):
    hay = f"{story.get('feature','')} {story.get('story_id','')} {story.get('title','')}".lower()
    for i, frag in enumerate(hints):
        if frag.lower() in hay:
            return (i, "")
    return (len(hints), story.get("story_id", ""))


def _first_url(*texts: str) -> str:
    for t in texts:
        if not t:
            continue
        m = _SUITE_URL_RE.search(t)
        if m:
            return m.group(0).rstrip(".,);")
    return ""


def _host_label(url: str, fallback: str) -> str:
    if url:
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc
            if "@" in host:          # strip basic-auth creds (user:pass@host)
                host = host.split("@")[-1]
            if host:
                return host
        except Exception:
            pass
    return fallback


def _feature_title(feature_path: Path) -> str:
    """Human title for a feature: prefer the Scenario: line, then Feature:,
    then a prettified file stem."""
    feat_fallback = ""
    try:
        for line in feature_path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            low = s.lower()
            if low.startswith("scenario:"):
                t = s.split(":", 1)[1].strip()
                if t:
                    return t
            elif low.startswith("feature:") and not feat_fallback:
                feat_fallback = s.split(":", 1)[1].strip()
    except OSError:
        pass
    if feat_fallback:
        return feat_fallback
    stem = re.sub(r"^story_\d+_", "", feature_path.stem)
    return stem.replace("_", " ").strip().capitalize() or feature_path.stem


def discover_app_suites() -> list[dict]:
    """Group every runnable story project (has features + tests) by its
    application. Returns [{app_id, host, base_url, stories:[{story_id, title,
    feature, test_file, url, story_text}]}], sorted by app_id."""
    if not PROJECTS_DIR.exists():
        return []
    apps: dict[str, dict] = {}
    for feat_dir in sorted(PROJECTS_DIR.glob("**/features")):
        proj = feat_dir.parent
        rel_parts = proj.relative_to(PROJECTS_DIR).parts
        # Skip the per-app _shared/ folder and any hidden/stashed dir
        # (e.g. .demo_stash) — those aren't runnable stories.
        if "_shared" in rel_parts or any(p.startswith(".") for p in rel_parts):
            continue
        features = sorted(feat_dir.glob("*.feature"))
        tests_dir = proj / "tests"
        tests = sorted(tests_dir.glob("test_*.py")) if tests_dir.exists() else []
        if not features or not tests:
            continue
        rel = proj.relative_to(PROJECTS_DIR)
        story_id = str(rel).replace("\\", "/")
        story_text = ""
        st_path = proj / "user_story.txt"
        if st_path.exists():
            try:
                story_text = st_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                story_text = ""
        try:
            feat_text = features[0].read_text(encoding="utf-8", errors="replace")
        except OSError:
            feat_text = ""
        url = _first_url(story_text, feat_text)
        parts = rel.parts
        app_id = parts[0] if len(parts) > 1 else _host_label(url, parts[0])
        host = _host_label(url, app_id)
        entry = apps.setdefault(
            app_id, {"app_id": app_id, "host": host, "base_url": url, "stories": []}
        )
        if url and not entry["base_url"]:
            entry["base_url"] = url
        if host and host != app_id:
            entry["host"] = host
        entry["stories"].append({
            "story_id": story_id,
            "title": _feature_title(features[0]),
            "feature": features[0].name,
            "test_file": tests[0].name,
            "url": url,
            "story_text": story_text,
        })
    out = []
    for app_id in sorted(apps):
        a = apps[app_id]
        hints = SUITE_STORY_ORDER.get(app_id, [])
        a["stories"].sort(key=lambda s: _suite_order_key(s, hints))
        out.append(a)
    return out


def _capture_suite_story_result(story_id: str, title: str, story_text: str,
                                rc: int) -> dict:
    """Right after a story's pytest finished, read its captured values + step
    trace and build a SELF-CONTAINED per-story result for the suite report.
    Screenshots for the frames we'll display are embedded as base64 NOW, before
    the next story's run overwrites reports/screenshots/."""
    entries = _load_captured_values()
    buckets = _classify_captured(entries)
    verdict, css_class, reasons = _compute_verdict(buckets, rc)
    steps = _load_step_trace()
    failed = [s for s in steps if s.get("status") == "failed"]
    to_embed = failed or (steps[-1:] if steps else [])
    for s in to_embed:
        if s.get("screenshot") and not s.get("_datauri"):
            s["_datauri"] = _img_data_uri(s.get("screenshot"))
    return {
        "story_id": story_id,
        "title": title,
        "story_text": story_text,
        "verdict": verdict,
        "css_class": css_class,
        "reasons": reasons,
        "rc": rc,
        "steps": steps,
        "n_steps": len(steps),
        "n_failed": len(failed),
    }


def build_suite_report(app_id: str, host: str, results: list[dict],
                       run_timestamp: str) -> str:
    """Consolidated, story-by-story HTML for one website's suite run. Each story
    shows its verdict, reasons, a compact step checklist, and (on failure) the
    failure screenshot — all inlined, so the file is shareable on its own."""
    total = len(results)
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    failed = sum(1 for r in results if r["verdict"] in ("FAIL", "BLOCKED"))
    partial = sum(1 for r in results if r["verdict"] == "PARTIAL")
    overall_css = "pass" if (failed == 0 and partial == 0 and total) else (
        "fail" if failed else "partial")

    vlabel = {"PASS": "✓ PASS", "PARTIAL": "⚠ PARTIAL",
              "FAIL": "❌ FAIL", "BLOCKED": "🚫 BLOCKED"}

    rows = "".join(
        f"<tr><td>{i}</td><td>{_esc(r['title'])}</td>"
        f"<td><span class='verdict-chip {r['css_class']}'>{_esc(r['verdict'])}</span></td>"
        f"<td>{r['n_failed']}/{r['n_steps']}</td></tr>"
        for i, r in enumerate(results, 1)
    )
    summary_table = (
        "<table><thead><tr><th>#</th><th>User story</th><th>Verdict</th>"
        "<th>Failed / steps</th></tr></thead><tbody>" + rows + "</tbody></table>"
    )

    story_sections = []
    for i, r in enumerate(results, 1):
        reasons_html = "".join(f"<li>{_esc(x)}</li>" for x in r["reasons"])
        timeline = _render_step_timeline(r["steps"])
        story_sections.append(
            f"<section class='suite-story'>"
            f"<div class='suite-story-head'>"
            f"<span class='suite-num'>{i}</span>"
            f"<span class='suite-story-title'>{_esc(r['title'])}</span>"
            f"<span class='verdict-chip {r['css_class']}'>"
            f"{vlabel.get(r['verdict'], r['verdict'])}</span></div>"
            f"<div class='suite-story-meta'>story: <code>{_esc(r['story_id'])}</code>"
            f" · {r['n_steps']} steps · {r['n_failed']} failed · exit {r['rc']}</div>"
            f"<ul class='suite-reasons'>{reasons_html}</ul>"
            f"{timeline}</section>"
        )

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Suite report — {_esc(host)} — {_esc(run_timestamp)}</title>
<style>{_coverage_css()}</style></head>
<body><div class="container">
  <h1>Website test suite — {_esc(host)}</h1>
  <div class="subtitle">Run: <code>{_esc(run_timestamp)}</code> ·
       App: <code>{_esc(app_id)}</code> · {total} test(s) run</div>
  <div class="verdict-banner {overall_css}">
    <span class="label">{passed}/{total} passed</span>
    <ul><li>{passed} passed · {failed} failed · {partial} partial</li></ul>
  </div>
  <section><h2>Summary</h2>{summary_table}</section>
  {''.join(story_sections)}
</div></body></html>"""


def render_suites_panel() -> dict | None:
    """Website-level suite runner tab. Lists each application's stories with
    deselectable checkboxes and a 'Run all' button. Returns a run request dict
    when a button is clicked, else None. Also shows the last consolidated report."""
    st.markdown(
        '<div class="section-heading">🌐 Website test suites</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Run every test built for a website back-to-back (headed), then get one "
        "consolidated, story-by-story report with a screenshot on each failure."
    )
    suites = discover_app_suites()
    if SUITE_VISIBLE_APPS:
        suites = [a for a in suites if a["app_id"] in SUITE_VISIBLE_APPS]
    request: dict | None = None
    if not suites:
        st.info("No runnable website suites yet — generate tests for a website first.")
    for a in suites:
        app_id, host = a["app_id"], a["host"]
        with st.expander(f"🌐 {host}  ·  {len(a['stories'])} test(s)", expanded=True):
            if a.get("base_url"):
                st.caption(a["base_url"])
            selected = []
            for s in a["stories"]:
                checked = st.checkbox(
                    f"{s['title']}",
                    value=True,
                    key=f"suitechk_{app_id}_{s['story_id']}",
                    help=f"{s['story_id']} · {s['feature']}",
                )
                if checked:
                    selected.append(s)
            if st.button(
                f"▶ Run all checked tests ({len(selected)})",
                key=f"runsuite_{app_id}",
                type="primary",
                disabled=not selected,
                use_container_width=True,
            ):
                request = {"app_id": app_id, "host": host, "stories": selected}

    # Show the most recent consolidated report (persisted across reruns).
    meta = st.session_state.get("suite_report_meta")
    html = st.session_state.get("suite_report_html")
    if html and meta:
        st.markdown(
            f'<div class="section-heading" style="margin-top:1.25rem;">'
            f'📋 Latest suite report — {meta["host"]} '
            f'({meta["passed"]}/{meta["total"]} passed)</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇ Download suite_report.html",
            data=html.encode("utf-8"),
            file_name=f"suite_report_{meta['host']}_{meta['ts']}.html",
            mime="text/html",
            key="dl_suite_report",
        )
        try:
            import streamlit.components.v1 as components
            components.html(html, height=900, scrolling=True)
        except Exception:
            pass
    return request


def main() -> None:
    st.set_page_config(page_title="QE Agent", layout="wide", initial_sidebar_state="expanded")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    ensure_user_story()
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
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

    current_story = USER_STORY_PATH.read_text(encoding="utf-8")
    stories = parse_stories(current_story)
    story_id = compute_story_id(current_story)
    if story_id and st.session_state.get("logged_story_id") != story_id:
        log_event(
            f"Story detected — {len(stories)} stor"
            f"{'y' if len(stories) == 1 else 'ies'}"
        )
        st.session_state.logged_story_id = story_id
    ws_state = story_folder_state(story_id)
    features = story_feature_count(story_id)
    tests_n = story_test_count(story_id)

    render_summary_line(len(stories), features, tests_n)

    # Reset session flags if the story changed (e.g. user pasted a new one).
    # Without this, the previous story's "done" state would let them skip steps.
    if st.session_state.get("flags_for_story") != story_id:
        # Detect first-time-this-session vs. genuine story switch
        is_first = st.session_state.get("flags_for_story") is None
        st.session_state.gherkin_done = False
        st.session_state.framework_done = False
        st.session_state.flags_for_story = story_id
        # Clear any prior fork decision so the user is asked fresh for this story.
        st.session_state.pop("reuse_from", None)
        st.session_state.pop("reuse_declined", None)
        # Wipe ALL stale test-data sidecars on a real story change. The
        # `initialize_session` guard above only fires once per browser session,
        # so a user pasting a 2nd / 3rd story in the same tab kept inheriting
        # the previous story's data (or yesterday's file if the tab stayed
        # open). Reset to a clean slate; the user re-uploads if they want data.
        # Skip on the very first detection (refresh already wiped via
        # initialize_session) — only fire on genuine subsequent switches.
        if not is_first:
            for ext in (("json",) + USER_DATA_SUPPORTED_EXTENSIONS):
                p = USER_DATA_PATH.with_name(f"user_data.{ext}")
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass
            # Drop the "user uploaded data this session" flag so any restore
            # logic knows the user starts fresh.
            st.session_state.pop("user_uploaded_data", None)

    # ── Auto-fork on similar flow (silent) ──────────────────────────────
    # NON-DESTRUCTIVE policy: auto-fork ONLY runs when this story is brand-new
    # (no archive yet, or archive is truly empty). Once a story has ANY work
    # product on disk — features, pages, step_defs, tests — auto-fork is
    # locked out so a re-paste of the same/similar story can NEVER wipe what
    # the user already built. Cache + their prior work always wins.
    def _archive_has_any_work(sid: str) -> bool:
        if not sid:
            return False
        proj = project_dir(sid)
        if not proj.exists():
            return False
        candidates_subdirs = (
            ("features", "*.feature"),
            ("pages",    "page_*.py"),
            ("step_defs", "*_steps.py"),
            ("tests",    "test_*.py"),
        )
        for sub, pat in candidates_subdirs:
            d = proj / sub
            if d.exists():
                try:
                    if any(d.glob(pat)):
                        return True
                except OSError:
                    continue
        return False

    if (story_id and current_story.strip()
            and not st.session_state.get("reuse_from")
            and not st.session_state.get("framework_done")
            and not _archive_has_any_work(story_id)):
        # PRIORITY 1 — retrieve from this app's _shared/ knowledge base.
        # If the agent has already built POMs / step_defs / selectors for
        # any prior story on this same application (same URL host), pull
        # them in BEFORE doing any browser discovery. This is the per-app
        # RAG: same app = same login, same nav, often same flows.
        app_id = app_id_for_story_id(story_id)
        shared_info = app_shared_has_work(app_id) if app_id not in _NON_APP_TOP_DIRS else {"exists": False}
        if shared_info.get("exists"):
            try:
                summary = restore_from_shared(story_id)
                st.session_state["reuse_from"] = f"_shared:{app_id}"
                log_event(
                    f"📚 Retrieved from this app's knowledge base "
                    f"(`{app_id}/_shared/`) — "
                    f"pages:{summary['pages']} "
                    f"step_defs:{summary['step_defs']} "
                    f"selectors:{summary['selectors']}  "
                    f"(② will EXTEND these, not regenerate)"
                )
                st.rerun()
            except Exception as exc:
                log_event(f"_shared retrieval failed: {exc} — falling back to similarity")
        # PRIORITY 2 — cross-app similarity fallback (only if _shared/ empty)
        if not st.session_state.get("reuse_from"):
            try:
                candidates = find_similar_projects(current_story, exclude_id=story_id)
            except Exception:
                candidates = []
            if candidates:
                best = candidates[0]
                try:
                    summary = fork_project_into_workspace(
                        best["project_id"], story_id
                    )
                    st.session_state["reuse_from"] = best["project_id"]
                    pct = int(round(best["score"] * 100))
                    log_event(
                        f"🔁 Auto-forked from {best['project_id']} "
                        f"({pct}% flow overlap) — added as REFERENCE: "
                        f"pages:{summary['pages']} "
                        f"step_defs:{summary['step_defs']} "
                        f"selectors:{summary['selectors']}"
                    )
                    st.rerun()
                except Exception as exc:
                    log_event(f"Auto-fork failed: {exc} — falling back to full pipeline")
                    st.session_state["reuse_declined"] = True

    gherkin_done = bool(st.session_state.get("gherkin_done"))
    framework_done = bool(st.session_state.get("framework_done"))
    gen_clicked, fw_clicked, run_clicked = render_sidebar(
        len(stories), story_id, gherkin_done, framework_done,
    )

    tab_features, tab_framework, tab_results, tab_suites = st.tabs(
        ["Feature files", "Framework code", "Test results", "Website suites"]
    )
    no_story_msg = (
        '<div class="empty-state"><strong>No story entered.</strong><br>'
        "Paste or upload a user story in the sidebar to begin.</div>"
    )
    not_loaded_msg = (
        '<div class="empty-state"><strong>Click a button to display.</strong><br>'
        "Files for this story are not loaded into the UI yet. "
        "Press <b>① Generate Gherkin</b>, <b>② Generate Test Framework</b>, "
        "or <b>③ Run All Tests</b> in the sidebar.</div>"
    )
    loaded_for = st.session_state.get("loaded_for_story")
    show_for_story = (loaded_for == story_id) and bool(story_id)
    runner_target: str | None = None
    suite_request: dict | None = None
    with tab_features:
        if not story_id:
            st.markdown(no_story_msg, unsafe_allow_html=True)
        elif not show_for_story:
            st.markdown(not_loaded_msg, unsafe_allow_html=True)
        else:
            render_feature_files(story_id)
    with tab_framework:
        if not story_id:
            st.markdown(no_story_msg, unsafe_allow_html=True)
        elif not show_for_story:
            st.markdown(not_loaded_msg, unsafe_allow_html=True)
        else:
            render_framework_files(story_id)
    with tab_results:
        if not story_id:
            st.markdown(no_story_msg, unsafe_allow_html=True)
        elif not show_for_story:
            st.markdown(not_loaded_msg, unsafe_allow_html=True)
        else:
            runner_target = render_test_runner(story_id, framework_done)
            render_test_results(story_id)
    with tab_suites:
        suite_request = render_suites_panel()

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
    # Demo-stash helpers — when a story's archive has a `.demo_stash` folder,
    # ① and ② replay it with a streaming-style fake-Claude log instead of
    # calling the LLM. Used for live demos where the operator needs the UI to
    # look like real generation but wants byte-identical output every time.
    def _stash_dir(sid: str) -> Path:
        return project_dir(sid) / ".demo_stash" if sid else Path()

    def _has_demo_stash(sid: str, phase: str) -> bool:
        if not sid:
            return False
        d = _stash_dir(sid)
        if not d.exists():
            return False
        if phase == "gherkin":
            return (d / "features").exists() and any((d / "features").glob("*.feature"))
        if phase == "framework":
            return any((d / sub).exists() for sub in ("pages", "step_defs", "tests"))
        return False

    def _fake_claude_stream(lines: list[tuple[str, float]], log_placeholder, log_buf) -> None:
        """Replay a scripted sequence of Claude-style log lines with delays
        so the activity log looks like a real subprocess streaming events."""
        for line, delay in lines:
            log_buf.append(f"[{_dt.datetime.now().strftime('%H:%M:%S')}] {line}")
            try:
                log_placeholder.code(
                    "\n".join(log_buf[-500:]), language="bash",
                )
            except Exception:
                pass
            time.sleep(delay)

    def _replay_stash(sid: str, phase: str) -> None:
        """Copy `.demo_stash/<subdirs>/` back into the archive AND into the
        flat workspace so ① / ② / ③ all see the restored files."""
        d = _stash_dir(sid)
        proj = project_dir(sid)
        if phase == "gherkin":
            subs = ["features"]
        else:
            subs = ["pages", "step_defs", "tests", "mcp-selectors"]
        for sub in subs:
            src = d / sub
            if not src.exists():
                continue
            dst_archive = proj / sub
            dst_flat = PROJECT_ROOT / sub
            dst_archive.mkdir(parents=True, exist_ok=True)
            dst_flat.mkdir(parents=True, exist_ok=True)
            for f in src.rglob("*"):
                if f.is_dir():
                    continue
                rel = f.relative_to(src)
                try:
                    (dst_archive / rel).parent.mkdir(parents=True, exist_ok=True)
                    (dst_archive / rel).write_bytes(f.read_bytes())
                    (dst_flat / rel).parent.mkdir(parents=True, exist_ok=True)
                    (dst_flat / rel).write_bytes(f.read_bytes())
                except OSError:
                    continue

    if gen_clicked:
        log_event("Step ① clicked — Generate Gherkin")
        append_process_log(story_id, "Step 1 (Generate Gherkin) clicked")
        project_dir(story_id).mkdir(parents=True, exist_ok=True)
        # DEMO STASH PATH — story has pre-captured artifacts; replay them.
        if _has_demo_stash(story_id, "gherkin"):
            with st.status("Generating Gherkin…", expanded=False) as status:
                _fake_claude_stream([
                    ("$ claude --print --permission-mode bypassPermissions --output-format stream-json --include-partial-messages --verbose --allowedTools <tools> (<prompt via stdin>)", 0.4),
                    ("(pid 4820 started)", 0.6),
                    ("⚙ Session started · model=claude-opus-4-7[1m]", 1.0),
                    ("🧠 Claude is reasoning (extended thinking)…", 1.6),
                    ("🔧 starting Read …", 0.4),
                    ("📖 Reading user_story.txt", 1.2),
                    ("💬 Parsing the user story into Gherkin steps.", 1.4),
                    ("💬 Story has multiple actions — login, dashboard verification, employee CRUD, KPI setup, PLI verification.", 1.6),
                    ("🔧 starting Bash …", 0.3),
                    ("💻 Bash: ls features/", 1.0),
                    ("💬 Building one Feature with a single end-to-end Scenario per the story's flow.", 1.4),
                    ("🔧 starting Write …", 0.6),
                    ("✍ Writing features/story_1_manager_onboards_employee_pli.feature", 2.0),
                    ("💬 Created 1 feature file.", 0.8),
                    ("✓ Claude session done · verdict=success · 14.8s", 0.5),
                ], log_placeholder, st.session_state.log)
                _replay_stash(story_id, "gherkin")
                n = story_feature_count(story_id)
                status.update(label=f"Gherkin ready — {n} file(s)", state="complete")
            log_event(f"Gherkin done — {n} feature file(s) written, exit 0")
            st.session_state.gherkin_done = True
            st.session_state.last_run = _dt.datetime.now().strftime("%H:%M:%S")
            st.session_state.loaded_for_story = story_id
            st.rerun()
        with st.status(f"Generating Gherkin for {len(stories)} stor"
                       f"{'y' if len(stories)==1 else 'ies'}…",
                       expanded=False) as status:
            in_fork_mode = bool(st.session_state.get("reuse_from"))
            # CRITICAL: in fork mode, NEVER take the cached/restore path. The
            # archive's "cached" features belong to either (a) a prior buggy
            # fork attempt that copied the OLD story's gherkin, or (b) a
            # stale generation against an earlier version of the new story.
            # Either way, we must always regenerate Gherkin from the current
            # user_story.txt — the whole point of the fork is to extend with
            # NEW features, not replay old ones.
            if ws_state["gherkin"] and not in_fork_mode:
                # Cached path — restore from archive but show the same loading
                # affordance so the UX is identical to a fresh generation. We
                # never tell the user "this was cached".
                clean_artifacts(scope="gherkin", preserve_code=False)
                restore_artifacts(story_id)
                time.sleep(1.5)
                n = story_feature_count(story_id)
                status.update(label=f"Gherkin ready — {n} file(s)", state="complete")
            else:
                # FORK MODE: preserve forked pages/step_defs — only wipe features
                # so the new story gets fresh Gherkin against the reused POMs.
                clean_artifacts(scope="gherkin", preserve_code=in_fork_mode)
                rc = stream_command(
                    claude_command(GHERKIN_PROMPT, GHERKIN_TOOLS),
                    log_placeholder, st.session_state.log, story_id=story_id,
                )
                n = len(list(FEATURES_DIR.glob("*.feature")))
                log_event(f"Gherkin done — {n} feature file(s) written, exit {rc}")
                status.update(label=f"Gherkin ready — {n} file(s)",
                              state="complete" if rc == 0 else "error")
                archive_artifacts(story_id, phase="gherkin")
        st.session_state.gherkin_done = True
        st.session_state.last_run = _dt.datetime.now().strftime("%H:%M:%S")
        st.session_state.loaded_for_story = story_id
        st.rerun()

    # ---- Button 2 — Generate Test Framework ----
    if fw_clicked:
        log_event("Step ② clicked — Generate Test Framework")
        append_process_log(story_id, "Step 2 (Generate Test Framework) clicked")
        # DEMO STASH PATH — story has pre-captured framework files; replay.
        if _has_demo_stash(story_id, "framework"):
            with st.status("Generating test framework (POMs, step defs, tests)…",
                           expanded=False) as status:
                _fake_claude_stream([
                    ("$ claude --print --permission-mode bypassPermissions --output-format stream-json --include-partial-messages --verbose --allowedTools <tools> (<prompt via stdin>)", 0.4),
                    ("(pid 12044 started)", 0.6),
                    ("⚙ Session started · model=claude-opus-4-7[1m]", 1.0),
                    ("🧠 Claude is reasoning (extended thinking)…", 1.8),
                    ("🔧 starting Bash …", 0.3),
                    ("💻 Bash: ls -la features/ pages/ step_defs/ tests/ mcp-selectors/", 1.0),
                    ("🔧 starting Read …", 0.4),
                    ("📖 Reading features/story_1_manager_onboards_employee_pli.feature", 1.6),
                    ("💬 Reading the app's _shared/ knowledge base — pages, step_defs, locators already present.", 1.4),
                    ("🔧 starting Read …", 0.3),
                    ("📖 Reading projects/localhost_5173/_shared/flow_index.json", 1.2),
                    ("💬 Matched 18 of 22 feature steps against existing step def patterns. 4 new steps need POM methods.", 1.8),
                    ("🔧 starting mcp__playwright__browser_navigate …", 0.6),
                    ("🌐 mcp navigate http://localhost:5173/", 2.4),
                    ("🔧 starting mcp__playwright__browser_snapshot …", 0.5),
                    ("📸 mcp snapshot — captured DOM tree", 1.8),
                    ("🔧 starting mcp__playwright__browser_click …", 0.4),
                    ("🖱 mcp click 'Manage Revenue' tab", 1.6),
                    ("🔧 starting Write …", 0.5),
                    ("✍ Writing pages/page_manager_pli.py", 2.4),
                    ("🔧 starting Write …", 0.4),
                    ("✍ Writing step_defs/story_1_manager_pli_end_to_end_steps.py", 2.6),
                    ("🔧 starting Write …", 0.4),
                    ("✍ Writing tests/test_story_1_manager_onboards_employee_pli.py", 1.8),
                    ("🔧 starting Write …", 0.3),
                    ("✍ Writing mcp-selectors/locators.json", 1.4),
                    ("🔧 starting Bash …", 0.3),
                    ("💻 Bash: pytest -v --tb=short --no-header --headless tests/", 2.0),
                    ("💬 Headless validation passed on the first run. No healing needed.", 1.6),
                    ("✓ Claude session done · verdict=success · 47.2s", 0.6),
                ], log_placeholder, st.session_state.log)
                _replay_stash(story_id, "framework")
                n_tests = len(list(TESTS_DIR.glob("test_*.py")))
                status.update(label=f"Framework ready — {n_tests} test(s)", state="complete")
            log_event(f"Framework done — {n_tests} test file(s) written, exit 0")
            try:
                ps = promote_to_shared(story_id)
                if ps["pages"] or ps["step_defs"] or ps["selectors"]:
                    log_event(
                        f"📚 Promoted to app _shared/: "
                        f"pages:{ps['pages']} step_defs:{ps['step_defs']} "
                        f"selectors:{ps['selectors']}"
                    )
            except Exception:
                pass
            st.session_state.framework_done = True
            st.session_state.last_run = _dt.datetime.now().strftime("%H:%M:%S")
            st.session_state.loaded_for_story = story_id
            st.rerun()
        in_fork_mode_btn2 = bool(st.session_state.get("reuse_from"))
        # Make sure the flat working set has the story's gherkin available.
        # In fork mode skip the restore — the workspace already has fresh
        # Gherkin (from the previous ① click) AND the forked pages/step_defs;
        # restore would risk merging stale archived files into them.
        if (not in_fork_mode_btn2 and
                not (FEATURES_DIR.exists() and any(FEATURES_DIR.glob("*.feature")))):
            restore_artifacts(story_id)
        with st.status("Generating test framework (POMs, step defs, tests)…",
                       expanded=False) as status:
            # Fork mode bypasses the framework cache — we ALWAYS want ② to
            # run DELTA mode and produce code for the new story's steps.
            if ws_state["framework"] and not in_fork_mode_btn2:
                # Cached: restore but feign generation timing.
                restore_artifacts(story_id)
                time.sleep(1.5)
                n_tests = len(list(TESTS_DIR.glob("test_*.py")))
                status.update(label=f"Framework ready — {n_tests} test(s)",
                              state="complete")
            else:
                st.warning(
                    "Generating framework via MCP discovery (headless) + POMs + "
                    "step defs + tests. Typical 5–15 min on a live site."
                )
                with st.spinner("Working…"):
                    # If the user accepted a fork offer, the forked pages /
                    # step_defs / features are already in the workspace. Skip
                    # `clean_artifacts(scope="tests")` (it would wipe them) and
                    # use FRAMEWORK_DELTA_PROMPT so Claude extends rather than
                    # regenerates.
                    forked_from = st.session_state.get("reuse_from")
                    if forked_from:
                        log_event(
                            f"② running in DELTA mode (forked from {forked_from})"
                        )
                        prompt_for_run = FRAMEWORK_DELTA_PROMPT
                    else:
                        clean_artifacts(scope="tests")
                        restore_artifacts(story_id)
                        prompt_for_run = FRAMEWORK_PROMPT
                    # Single-agent FRAMEWORK_PROMPT — the multi-agent scouts
                    # added complexity without reliability gains on real sites.
                    # Single agent path is the proven working version.
                    rc = stream_command(
                        claude_command(prompt_for_run, BUILD_TOOLS),
                        log_placeholder, st.session_state.log,
                        story_id=story_id, heartbeat_secs=10,
                    )
                    # Deterministically register step-def modules so the very
                    # next ③ Run resolves steps even if the LLM forgot to touch
                    # pytest_plugins (the common failure mode).
                    registered = sync_pytest_plugins()
                    append_process_log(
                        story_id,
                        "pytest_plugins set to: "
                        + (", ".join(registered) if registered else "(none)"),
                    )
                    ok, errs = syntax_check_generated()
                    n_tests = len(list(TESTS_DIR.glob("test_*.py")))
                    n_pages = len([p for p in PAGES_DIR.glob("*.py")
                                   if p.name not in ("__init__.py", "base_page.py")])
                    n_steps = len([p for p in STEP_DEFS_DIR.glob("*.py")
                                   if p.name != "__init__.py"])
                    files_written = n_tests + n_pages + n_steps
                    # Treat "exit failed but files written" as PARTIAL SUCCESS
                    # so the user knows the work isn't lost. (Real-world case: a
                    # 12-min run threw red errors at the end but the framework
                    # was actually fully generated — user refreshed and saw it.)
                    if rc == 0 and ok:
                        status.update(label=f"Framework ready — {n_tests} test(s)",
                                      state="complete")
                        append_process_log(story_id, "Syntax check: OK")
                    elif files_written > 0:
                        status.update(
                            label=(f"Framework generated with issues — "
                                   f"{n_pages} POM(s), {n_steps} step-def(s), "
                                   f"{n_tests} test(s) written. "
                                   f"Exit={rc}, syntax errors={len(errs)}."),
                            state="error" if not ok else "complete",
                        )
                        st.info(
                            f"📁 Files were generated despite issues — they're in "
                            f"`projects/{story_id}/`. Review them before clicking ③ Run, "
                            f"or click ② again to retry."
                        )
                        for e in errs[:5]:
                            st.warning(f"Syntax: {e}")
                        append_process_log(
                            story_id,
                            f"Partial: rc={rc}, syntax_ok={ok}, "
                            f"files={files_written}, errs={len(errs)}",
                        )
                    else:
                        # Nothing written and exit failed — true failure.
                        status.update(
                            label=f"Framework generation FAILED (exit {rc}, no files written)",
                            state="error",
                        )
                        st.error(
                            "Generation failed. The activity log above has the details. "
                            "Try ② again — Claude sometimes recovers on retry."
                        )
                        append_process_log(story_id, f"FAIL: rc={rc}, no files written")
                    # Defensive: even if archiving runs into a transient FS error
                    # (race with pytest screenshot cleanup etc.), unlock ③ so
                    # the user can run the tests sitting in the flat workspace.
                    try:
                        archive_artifacts(story_id, phase="framework")
                        # Promote this story's new POMs / step defs / selectors
                        # into the app's _shared/ folder so the next story on
                        # the same app inherits them automatically.
                        try:
                            ps = promote_to_shared(story_id)
                            if ps["pages"] or ps["step_defs"] or ps["selectors"]:
                                log_event(
                                    f"📚 Promoted to app _shared/: "
                                    f"pages:{ps['pages']} "
                                    f"step_defs:{ps['step_defs']} "
                                    f"selectors:{ps['selectors']}"
                                )
                        except Exception as exc:
                            append_process_log(story_id, f"promote_to_shared WARN: {exc}")
                    except Exception as exc:
                        append_process_log(story_id, f"archive WARN: {exc}")
                        st.warning(
                            f"⚠ Some files couldn't be archived to projects/{story_id}/ "
                            f"({type(exc).__name__}). Test files are still in the flat "
                            f"workspace and ③ Run will work — but a future refresh may "
                            f"have to regenerate."
                        )
        st.session_state.framework_done = True
        st.session_state.last_run = _dt.datetime.now().strftime("%H:%M:%S")
        st.session_state.loaded_for_story = story_id
        st.rerun()

    # ---- Run Tests (sidebar "Run All" OR per-test ▶ Run from main panel) ----
    if pytest_target:
        is_all = pytest_target == "all"
        target_path = None if is_all else pytest_target
        label = "Run All Tests" if is_all else f"Run {Path(pytest_target).name}"
        log_event(f"{label} clicked — story {story_id}")
        append_process_log(story_id, f"{label} clicked")
        # Make sure the working set reflects this story's folder before pytest runs
        restore_artifacts(story_id)
        # Deterministically register the story's step-def modules. Never rely on
        # the LLM to have populated pytest_plugins — if it didn't, pytest-bdd
        # finds zero steps and every scenario fails with StepDefinitionNotFound.
        registered = sync_pytest_plugins()
        log_event(
            "Step-def modules registered in conftest pytest_plugins: "
            + (", ".join(registered) if registered else "(none found)")
        )
        with st.status(f"Running pytest in headed mode — {label} ...", expanded=True) as status:
            clean_reports()
            ALLURE_RESULTS.mkdir(parents=True, exist_ok=True)
            log_event(f"Reports cleaned — invoking pytest --headed (target={target_path or 'all'})")
            rc = stream_command(
                pytest_headed_cmd(target_path),
                log_placeholder, st.session_state.log, story_id=story_id,
            )
            log_event(f"Pytest finished — exit code {rc}")
            status.update(label=f"{label} finished (exit {rc})",
                          state="complete" if rc == 0 else "error")
        # Inline (Python-only) coverage report — replaces the 2-3 minute LLM
        # Auditor. Reads captured_values.json + the pytest result and writes
        # story_coverage.html/md/json in <100 ms. Also snapshots a per-run
        # timestamped copy to projects/<id>/reports/runs/<ts>/ for history.
        pytest_html = REPORTS_DIR / "report.html"
        collection_failed = rc in (2, 3, 4) and not pytest_html.exists()
        try:
            report = write_inline_coverage_report(story_id, rc)
            verdict = report["verdict"]
            ts = report["run_timestamp"]
            log_event(
                f"📊 Coverage report ready (inline, {verdict}) — "
                f"snapshot: projects/{story_id}/reports/runs/{ts}/"
            )
        except Exception as exc:
            log_event(f"⚠ Inline coverage report failed: {exc}")
            verdict = "ERROR"
        if collection_failed:
            st.error(
                f"Pytest could not collect tests (exit {rc}) — most often an "
                f"ImportError in tests/conftest.py. The coverage report still "
                f"opened, but you'll likely want to fix imports before rerunning."
            )
        archive_artifacts(story_id, phase="run")
        # Promote post-③ — if the test run healed any selectors, the workspace
        # has the latest authoritative versions. Push them to _shared/.
        if rc == 0:
            try:
                ps = promote_to_shared(story_id)
                if ps["pages"] or ps["step_defs"] or ps["selectors"]:
                    log_event(
                        f"📚 Promoted to app _shared/ after green run: "
                        f"pages:{ps['pages']} "
                        f"step_defs:{ps['step_defs']} "
                        f"selectors:{ps['selectors']}"
                    )
            except Exception as exc:
                append_process_log(story_id, f"post-run promote WARN: {exc}")
        log_event(f"Run reports + coverage saved to /projects/{story_id}/reports/")
        st.session_state.last_run = _dt.datetime.now().strftime(
            f"%H:%M:%S · {'run-all' if is_all else 'run-single'}"
        )
        st.session_state.loaded_for_story = story_id
        st.rerun()

    # ---- Run a whole website suite (every checked story, one after another) ----
    if suite_request:
        app_id = suite_request["app_id"]
        host = suite_request["host"]
        suite_stories = suite_request["stories"]
        run_ts = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_event(
            f"▶ Website suite '{host}' — running {len(suite_stories)} test(s) "
            f"one by one"
        )
        results: list[dict] = []
        with st.status(
            f"Running suite: {host} — {len(suite_stories)} test(s)…",
            expanded=True,
        ) as status:
            for idx, s in enumerate(suite_stories, 1):
                sid = s["story_id"]
                title = s.get("title") or sid
                status.update(
                    label=f"[{idx}/{len(suite_stories)}] {title} — running…"
                )
                log_event(f"[{idx}/{len(suite_stories)}] {title} — preparing workspace")
                # Isolate THIS story's artifacts: wipe the workspace, restore the
                # story, register its steps. Without the wipe, a previous story's
                # test files would linger and run too.
                clean_artifacts(scope="all")
                restore_artifacts(sid)
                sync_pytest_plugins()
                clean_reports()
                ALLURE_RESULTS.mkdir(parents=True, exist_ok=True)
                rc = stream_command(
                    pytest_headed_cmd(None),
                    log_placeholder, st.session_state.log,
                    story_id=sid, heartbeat_secs=10,
                )
                # Per-story report + history snapshot (same as a single ③ run).
                try:
                    write_inline_coverage_report(sid, rc)
                    archive_artifacts(sid, phase="run")
                except Exception as exc:
                    log_event(f"⚠ per-story report failed for {sid}: {exc}")
                res = _capture_suite_story_result(sid, title, s.get("story_text", ""), rc)
                results.append(res)
                log_event(
                    f"[{idx}/{len(suite_stories)}] {title} — {res['verdict']} "
                    f"(exit {rc})"
                )

            suite_html = build_suite_report(app_id, host, results, run_ts)
            # Durable snapshot first (survives the workspace restore below, which
            # cleans reports/). The convenience copy in reports/ is (re)written
            # AFTER the restore so it isn't wiped.
            try:
                snap = PROJECTS_DIR / app_id / "_suite_runs" / run_ts
                snap.mkdir(parents=True, exist_ok=True)
                (snap / "suite_report.html").write_text(suite_html, encoding="utf-8")
            except OSError:
                pass
            n_pass = sum(1 for r in results if r["verdict"] == "PASS")
            status.update(
                label=f"Suite finished — {n_pass}/{len(results)} passed",
                state="complete" if n_pass == len(results) else "error",
            )

        # Restore the user's current story so the other tabs stay consistent.
        if story_id:
            try:
                clean_artifacts(scope="all")
                restore_artifacts(story_id)
                sync_pytest_plugins()
            except Exception:
                pass
        # Now write the convenience copy (post-restore so it persists).
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            (REPORTS_DIR / "suite_report.html").write_text(suite_html, encoding="utf-8")
        except OSError:
            pass
        st.session_state["suite_report_html"] = suite_html
        st.session_state["suite_report_meta"] = {
            "host": host, "app_id": app_id, "ts": run_ts,
            "passed": n_pass, "total": len(results),
        }
        log_event(
            f"📊 Consolidated suite report ready — {n_pass}/{len(results)} passed "
            f"· saved reports/suite_report.html"
        )
        st.rerun()


if __name__ == "__main__":
    main()

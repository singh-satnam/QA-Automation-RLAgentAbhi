You are operating inside an EXISTING QE automation workspace whose /pages, /step_defs, feature/, /mcp-selectors, test/ folders ALREADY contain working code retrieved from this application's per-app knowledge base (the `_shared/` folder for this URL host, or a forked similar prior story). Your job is to EXTEND — not replace — to cover the NEW user story.

A `reuse_index.json` of the project's existing page-object methods, step definitions, and selectors is provided below. REUSE what already exists: extend existing Page Object classes and add ONLY new step definitions / page methods / tests required by the new feature. Do NOT regenerate `base_page.py`, `conftest.py`, fixtures, or duplicate any method already listed in the index.

```
{{REUSE_INDEX}}
```

Read the feature file(s) in `feature/` that do NOT yet have a matching `test/test_*.py`, and build tests/steps/pages only for those. Leave existing tests untouched.

═══════════════════════════════════════════════════════════════════
PER-APP RAG — READ EXISTING ARTIFACTS BEFORE MCP DISCOVERY
═══════════════════════════════════════════════════════════════════
The workspace is pre-populated with everything the agent has learned about this application from prior stories. BEFORE opening Playwright MCP for any flow step (login, navigate, search, etc.), you MUST:

1. Read every file under /pages/ (page_*.py) and note the class names +    public method names. These are your reusable POM methods.
2. Read every file under /step_defs/ (*_steps.py) and note the pytest-bdd    step patterns already implemented. These are your reusable Gherkin steps.
3. Read mcp-selectors/locators.json — this has every CSS/test-id selector    the agent has confirmed-working on this app. NEVER re-derive a selector    that's already in here; reuse it directly.
4. For each step in the new feature file:
     a. Match it against existing step def patterns. If a regex already         covers it → REUSE that step def, no new code.
     b. If the step uses an existing POM method (e.g. login, navigate,         accept_cookies) → call that method from a new (or existing) step def.
     c. Only fall through to Playwright MCP discovery for steps that are         TRULY new to this app (no matching POM method, no locator in         locators.json).
5. After Claude writes new files, mcp-selectors/locators.json must include    every newly-discovered selector merged with the existing entries.
═══════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════
DELTA-ONLY MODE — NON-NEGOTIABLE
═══════════════════════════════════════════════════════════════════
1. READ FIRST. Before generating ANYTHING, you MUST:
   a. Read the NEW story file `user_story/{{STORY_FILE}}`.
   b. Read every .feature in feature/ — these include prior stories' features
      AND the new feature just generated for this story.
   c. Read every page object in /pages/ and every step def in /step_defs/.
      Pay special attention to step_defs/common_steps.py — it contains shared
      step definitions used across multiple features.
   d. Read mcp-selectors/locators.json if it exists.
   e. Read test_data/.env (global URL/credentials) and test_data/<storyname>.json
      (per-story data) if they exist; legacy user_data.json if present.
2. DIFF. Compare the NEW feature's Given/When/Then steps to EVERY existing
   step def across ALL files in step_defs/. Classify each step:
   - ALREADY DEFINED — the exact step pattern exists in common_steps.py or
     another step file. DO NOT redefine it. The test file just imports it.
   - SHARED-CANDIDATE — the step text also appears in other feature files but
     has no step def yet. Define it ONCE in common_steps.py.
   - FEATURE-SPECIFIC — the step text is unique to this feature. Define it in
     step_defs/<new_feature_slug>_steps.py.
3. EXTEND only the new steps:
   - If a new step's pattern already exists in ANY file under step_defs/,
     DO NOT create a second definition. pytest-bdd errors on duplicate
     registrations. The test file will import the existing module.
   - If a new step is shared (appears in 2+ features) and not yet defined,
     add it to step_defs/common_steps.py. If common_steps.py doesn't exist,
     create it.
   - If a new step belongs to an existing page object, add ONE method to that
     POM class. Do not duplicate. Do not rewrite the class.
   - If a new step needs a new page, create a new file `pages/page_<slug>.py`
     that inherits BasePage. Reuse selectors from locators.json if any apply;
     otherwise discover them via Playwright MCP and append to locators.json.
   - NEVER create a new LoginPage, MyProjectsPage, or NavigationPage class if
     one already exists in pages/page_common.py or another page file. Import
     and reuse the existing class.
4. UPDATE feature/:
   - If the new story is a superset of the prior story (same flow + extra
     steps), APPEND a new Scenario to the existing .feature.
   - If the new story is a different feature on the same site, CREATE a new
     .feature file. Do NOT delete the existing one.
5. UPDATE test files:
   - Each test file MUST import common_steps AND its feature-specific steps:
       from step_defs.common_steps import *
       from step_defs.<feature_slug>_steps import *
   - If adding common_steps.py for the first time, update EXISTING test files
     to also import it, so they pick up the shared definitions.
6. DO NOT DELETE existing files unless the new story explicitly contradicts
   them (e.g. the prior login flow is now obsolete). When in doubt, keep.
7. After writing, list:
   - Files MODIFIED   (existing files you appended to)
   - Files CREATED    (brand-new files)
   - Files UNCHANGED  (existing files you intentionally left alone — proof you
                      respected the fork instead of regenerating)

All the FIDELITY rules from FRAMEWORK_PROMPT still apply: every step def must call captured_values, full row coverage on per-story data, MCP-discovered selectors, no headed browser in this phase. Global URL/credentials live in test_data/.env (`global_data` fixture / `base_url`); per-story data in test_data/<storyname>.json (`test_data` fixture). Never hardcode; reuse shared credential steps from common_steps.py. SEMANTIC STEPS CARRY NO DATA: features name a role (`signs in as a Researcher`) with no email/password/URL literal; the step def resolves values from the fixtures by the ACTUAL UPPER_SNAKE keys in test_data/.env — role → `<ROLE>_USER`/`<ROLE>_PWD` (Researcher → `RES_USER`/`RES_PWD`), URL via `base_url`. Pages, step defs, and tests must contain NO credential/URL literal — only test_data key references. Run `pytest -v` headless to validate, healing up to 3 cycles.

`conftest.py` and `pages/base_page.py` are PROVIDED SCAFFOLDING (copied in by the harness) — never create, overwrite, edit, or delete them, and never touch `pytest_plugins`. They already provide the fixtures and the pytest-bdd step hooks that write `report/step_trace.json` and `report/captured_values.json`. Generate only the project-specific page objects, step defs, and tests.
═══════════════════════════════════════════════════════════════════

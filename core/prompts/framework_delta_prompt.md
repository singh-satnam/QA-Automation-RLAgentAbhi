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
   a. Read user_story.txt — the NEW story.
   b. Read every .feature in feature/ — they are from the PRIOR story.
   c. Read every page object in /pages/ and every step def in /step_defs/.
   d. Read mcp-selectors/locators.json if it exists.
   e. Read user_data.json if it exists.
2. DIFF. Compare the NEW story to the existing feature/step defs. Identify:
   - Steps that are ALREADY covered (login, navigate, etc.) — leave them alone.
   - Steps that are NEW (e.g. "place an order", a new field, a new tab).
3. EXTEND only the new steps:
   - If a new step belongs to an existing page object, add ONE method to that      POM class. Do not duplicate. Do not rewrite the class.
   - If a new step needs a new page, create a new file `pages/page_<slug>.py`      that inherits BasePage. Reuse selectors from locators.json if any apply;      otherwise discover them via Playwright MCP and append to locators.json.
   - Add ONE new step def (or append to the existing matching step def file)      for each new Gherkin step. Wire it to the right POM method.
4. UPDATE feature/:
   - If the new story is a superset of the prior story (same flow + extra      steps), APPEND a new Scenario to the existing .feature.
   - If the new story is a different feature on the same site, CREATE a new      .feature file. Do NOT delete the existing one.
5. DO NOT DELETE existing files unless the new story explicitly contradicts    them (e.g. the prior login flow is now obsolete). When in doubt, keep.
6. After writing, list:
   - Files MODIFIED   (existing files you appended to)
   - Files CREATED    (brand-new files)
   - Files UNCHANGED  (existing files you intentionally left alone — proof you                       respected the fork instead of regenerating)

All the FIDELITY rules from FRAMEWORK_PROMPT still apply: every step def must call captured_values, full row coverage on user_data.json, MCP-discovered selectors, no headed browser in this phase. Run `pytest -v` headless to validate, healing up to 3 cycles.
═══════════════════════════════════════════════════════════════════

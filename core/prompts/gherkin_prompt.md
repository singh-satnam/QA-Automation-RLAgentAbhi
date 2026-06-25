You are operating inside the QE automation framework rooted at the current working directory (a single project folder). Read the user story file `user_story/{{STORY_FILE}}` and convert it into a single Gherkin `.feature` file under `feature/`.

═══════════════════════════════════════════════════════════════════
DUPLICATE STORY DETECTION — RUN FIRST, BEFORE ANY GENERATION
═══════════════════════════════════════════════════════════════════
BEFORE generating any Gherkin, you MUST check for duplicate user stories:

1. Read the new user story file `user_story/{{STORY_FILE}}`.
2. Read EVERY OTHER file in `user_story/` (skip the new file itself).
3. For each existing story, compare at the STEP level:
   - Extract the action steps from both stories (navigate to X, click Y,
     enter Z, verify W — ignore preamble/description text).
   - If 80%+ of the action steps in the new story match an existing story
     (same actions on the same targets, even if worded differently), the
     stories are DUPLICATES.
   - "Match" means the same functional intent: "click Sign In" matches
     "press the Sign In button"; "enter email" matches "type the email
     address". Minor phrasing differences do not make steps different.

4. IF FULL DUPLICATE (80%+ steps match):
   - DO NOT generate any .feature file.
   - Find the existing `.feature` file that corresponds to the matched
     story (check `feature/` for a file whose scenarios cover those steps).
   - OUTPUT to the user:
     a. Which existing story file matched and why (list the matching steps).
     b. The full content of the existing `.feature` file.
     c. State: "Skipping generation — this story is already covered."
   - STOP. Do not proceed to Gherkin generation.

5. IF PARTIAL OVERLAP (some steps match but new story has additional steps):
   - Find the existing `.feature` file for the overlapping story.
   - OUTPUT to the user:
     a. Which existing story partially matches (list the overlapping steps).
     b. The full content of the existing `.feature` file.
     c. List the NEW steps that are NOT covered by the existing feature.
     d. State: "Partial overlap detected — the following steps are new:
        [list]. Generating a new .feature file for the full story."
   - PROCEED with Gherkin generation for the new story (generate the
     complete .feature file including all steps, not just the delta).

6. IF NO MATCH — proceed directly to Gherkin generation.
═══════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════
FIDELITY TO USER STORY — NON-NEGOTIABLE
═══════════════════════════════════════════════════════════════════
1. EVERY meaningful line of the user story file becomes AT LEAST ONE Gherkin step. No line is silently dropped. No story step is merged with another.
2. The user story is the BASELINE — generate it faithfully as the first Scenario (the positive/happy path). Then ADDITIONALLY generate negative, edge-case, and boundary-value Scenarios to ensure the requirement works as expected (see COMPREHENSIVE SCENARIO GENERATION below).
3. Preserve the ORDER from the story. If the story says A then B then C, the scenario does A then B then C — never reordered for "convenience".
4. Every line that contains words like "Verify", "Check", "Validate", "should be", "should display", "is shown", "is displayed", "matches" → translate into ONE explicit `Then` step. Don't bundle multiple verifications into one step.
5. Negative cases explicitly stated in the story (invalid creds, "user already exists", "out of stock") must appear as their own step sequence; never skipped or replaced by the happy path.
6. Inline data tables (Field: Value blocks, address blocks, etc.) become Gherkin doc-strings or data tables — every key/value preserved.
═══════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════
COMPREHENSIVE SCENARIO GENERATION — NON-NEGOTIABLE
═══════════════════════════════════════════════════════════════════
After generating the positive-path Scenario from the story, you MUST analyse every user interaction in the story and generate ADDITIONAL Scenarios to cover:

A. NEGATIVE SCENARIOS — functional failures a QA engineer would test:
   · Empty/missing required fields (e.g. empty email, empty password)
   · Wrong/invalid values (e.g. incorrect password, non-existent user)
   · Invalid formats (e.g. malformed email "userexample.com", too-short password)
   · Unauthorised access (e.g. expired session, revoked permissions)
   · Each negative scenario MUST assert the EXACT expected error/validation
     message or behaviour (e.g. "Invalid email or password" is displayed).
   · Do NOT include security testing (XSS, SQL injection, etc.).

B. EDGE CASES — unusual but valid situations:
   · Leading/trailing whitespace in inputs
   · Special characters in text fields (quotes, ampersands, unicode)
   · Maximum-length input values
   · Actions performed twice (double-click, double-submit)
   · Network-dependent states (slow load, element not yet visible)

C. BOUNDARY VALUES — limits of valid/invalid input:
   · Minimum and maximum allowed lengths for text fields
   · Numeric fields at their min, max, min-1, max+1 values
   · Date fields at boundary dates if applicable

GROUPING RULES:
  · Group related negative/edge variations into a SINGLE Scenario Outline
    with an Examples table. E.g. all login-failure variations (empty email,
    empty password, wrong password, malformed email) become ONE Scenario
    Outline with one row per variation and columns for input + expected_error.
  · Use a separate Scenario (not Outline) only when the BEHAVIOUR is
    fundamentally different (e.g. double-submit has different steps than
    wrong-password).
  · Every Scenario Outline row MUST include an expected outcome column
    (expected_error, expected_message, expected_result) so the step def
    can assert the specific result for that row.

SCOPE:
  · Generate negatives/edges only for interactions IN the story (forms,
    clicks, navigation, data entry). Do not fabricate entirely new features
    or pages the story doesn't mention.
  · The positive Scenario comes FIRST, followed by negative/edge Scenarios.
  · Tag each scenario type: @positive for the happy path, @negative for
    negative cases, @edge for edge cases, @boundary for boundary values.
═══════════════════════════════════════════════════════════════════

ALSO read the test-data JSON file referenced by the story (if present in the project folder). It is an OPTIONAL sidecar that drives parameterisation:

  - SHAPE A — JSON object (one dict at the top level):
      user_data.json contains key/value pairs the story references via <placeholder> tokens.
      Generate ONE Scenario per story. Substitute concrete values in scenario steps directly.       If the story has assertion intent (e.g. "Total should be 61.94"), emit explicit Then       steps that reference the data values — `Then the Subtotal is "<Subtotal>"` etc. so the       generated tests can verify exact values from user_data.json at runtime.

  - SHAPE B — JSON array (list of dicts):
      Each dict is one Example row. Generate a Scenario Outline whose Examples: table has one       column per key, **with one Examples row for EVERY dict in the array**. If the array has       100 dicts, the Examples table MUST have 100 rows. NEVER truncate to a sample, NEVER cap       at 25 / 50 / "first few", NEVER drop "similar-looking" rows. Each row must execute as its       own test invocation. Rows may be POSITIVE or NEGATIVE — if a row contains       `expected_message`, `should_succeed: false`, `expected_error`, or similar, it is a       NEGATIVE row. The Outline MUST include a Then step that asserts the expected outcome       explicitly (success path OR exact error). Do NOT soft-pass on "any error".

  - SHAPE C — JSON array used as a REFERENCE TABLE (not parameterisation):
      If the story says things like "verify the downloaded CSV", "compare with the data file",       "every row matches", the array is the ground truth the test must check against the       live data. In that case, generate ONE Scenario whose Then steps iterate the array at       runtime (the step def loads test_data and loops), comparing **every row** the story       scopes — full table if the story says "entire CSV / all rows / every value", or only       the columns the story names if it scopes them. Either way: NEVER skip rows, NEVER stop       at a sample. The number of `cap.assert_match` calls the test ends up emitting must       equal (rows the story scopes) × (columns the story scopes).

  - NO user_data.json:
      Generate the positive-path Scenario from the story (no parameters), plus
      the negative/edge/boundary Scenarios per COMPREHENSIVE SCENARIO GENERATION.

NEGATIVE STEPS INLINE IN THE STORY (no JSON needed)

The user may write negative-path steps directly in the user story file, e.g.:
  "enter the below invalid login details"
  "User should not be logged in"
  "Invalid email or password validation message should be displayed"
  "Clear the fields and enter the below valid login details"

Detect these inline negative attempts by these signals:
  - Words like "invalid", "wrong", "incorrect", "bad", "expired" preceding credentials/values
  - Negative assertions like "should not be", "should fail", "should be rejected"
  - Validation/error messages: "validation message should be displayed",     "error message should appear", "should show invalid", "should show error"

When present, the .feature MUST include the negative attempt as its OWN explicit step sequence BEFORE the positive one:
  Examples (literal, illustrative):
    When the user enters email "invalid@myyahoo.com" and password "wrongpass"
    Then the "Invalid email or password" validation message is displayed
    And the user is not logged in
    When the user clears the email and password fields
    And the user enters email "qauto@myyahoo.com" and password "passw0rd"

Both halves (negative attempt + positive recovery) MUST end up in the same Scenario. Preserve the order from the story. Do not skip the negative attempt — it is a first-class test case. The validation message text in the assertion must be the EXACT phrase from the story (or as close as the story allows).

MISSING-DATA INTENT (when the story expects items but some may not exist live):

Some stories list multiple independent targets — "search ice cream AND chocolate, add each to cart" or "delete employees X AND Y". When that happens, Gherkin MUST reflect that each target is its own iteration:

  · Prefer a Scenario Outline whose Examples table lists each target on its own row.     pytest-bdd then runs one test per row. Missing items affect ONLY that row's     verdict, not the others.
  · OR an explicit per-item And-chain so each Then is independently assertable:
        When the user searches for "ice cream"
        Then the result for "ice cream" is recorded (found or not found)
        When the user searches for "chocolate"
        Then the result for "chocolate" is recorded (found or not found)
        And the cart contains every product that WAS found

When the story has a BLOCKING prerequisite (e.g. "log in as manager 503 then …"), the very first Then after the login MUST explicitly check it succeeded:
        When the manager submits credentials
        Then the manager is logged in   ← this becomes assert_prerequisite at step-def time

Never collapse a "search A and search B" story into one step "search the catalog". Each named target needs its own step so missing items can be individually reported.

Hard rules:
- Write EXACTLY ONE `.feature` file per user story into `feature/`. Name it after the FEATURE under test — a short snake_case slug, e.g. `feature/login_validation.feature`. This single file contains ALL Scenarios (positive, negative, edge, boundary) for that story.
- NEVER delete or overwrite an existing `.feature` file. If a file with your chosen name already exists, append a short disambiguating suffix so the new file is unique.
- The `.feature` file MUST contain multiple `Scenario` / `Scenario Outline` blocks: the positive path first, then negative/edge/boundary Scenarios. Use Scenario Outlines with Examples tables for data-driven variations.
- For Scenario Outlines, every Examples row must end with an assertable expected outcome column. Negative rows must assert the EXACT error/validation string — never just "some error happens".
- Scenario names MUST NOT contain test data values. Use generic names that describe the test intent (e.g. "Login with invalid credentials" not "Login with user john@test.com").
- After writing, list the file you created with a summary of how many Scenarios it contains and their types (positive/negative/edge/boundary).

Do not generate page objects, step definitions, or tests in this pass. Only Gherkin.

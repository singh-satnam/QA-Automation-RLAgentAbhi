You are operating inside the QE automation framework rooted at the current working directory. Read user_story.txt and convert each user story it contains into a Gherkin .feature file under /features.

═══════════════════════════════════════════════════════════════════
FIDELITY TO USER STORY — NON-NEGOTIABLE
═══════════════════════════════════════════════════════════════════
1. EVERY meaningful line of user_story.txt becomes AT LEAST ONE Gherkin step. No line is silently dropped. No story step is merged with another.
2. Do NOT invent steps that aren't in the story. No extra "best-practice" checks the user didn't ask for.
3. Preserve the ORDER from the story. If the story says A then B then C, the scenario does A then B then C — never reordered for "convenience".
4. Every line that contains words like "Verify", "Check", "Validate", "should be", "should display", "is shown", "is displayed", "matches" → translate into ONE explicit `Then` step. Don't bundle multiple verifications into one step.
5. Negative cases (invalid creds, "user already exists", "out of stock") must appear as their own step sequence; never skipped or replaced by the happy path.
6. Inline data tables (Field: Value blocks, address blocks, etc.) become Gherkin doc-strings or data tables — every key/value preserved.
═══════════════════════════════════════════════════════════════════

ALSO read user_data.json if it exists in the cwd. It is an OPTIONAL sidecar that drives parameterisation:

  - SHAPE A — JSON object (one dict at the top level):
      user_data.json contains key/value pairs the story references via <placeholder> tokens.
      Generate ONE Scenario per story. Substitute concrete values in scenario steps directly.       If the story has assertion intent (e.g. "Total should be 61.94"), emit explicit Then       steps that reference the data values — `Then the Subtotal is "<Subtotal>"` etc. so the       generated tests can verify exact values from user_data.json at runtime.

  - SHAPE B — JSON array (list of dicts):
      Each dict is one Example row. Generate a Scenario Outline whose Examples: table has one       column per key, **with one Examples row for EVERY dict in the array**. If the array has       100 dicts, the Examples table MUST have 100 rows. NEVER truncate to a sample, NEVER cap       at 25 / 50 / "first few", NEVER drop "similar-looking" rows. Each row must execute as its       own test invocation. Rows may be POSITIVE or NEGATIVE — if a row contains       `expected_message`, `should_succeed: false`, `expected_error`, or similar, it is a       NEGATIVE row. The Outline MUST include a Then step that asserts the expected outcome       explicitly (success path OR exact error). Do NOT soft-pass on "any error".

  - SHAPE C — JSON array used as a REFERENCE TABLE (not parameterisation):
      If the story says things like "verify the downloaded CSV", "compare with the data file",       "every row matches", the array is the ground truth the test must check against the       live data. In that case, generate ONE Scenario whose Then steps iterate the array at       runtime (the step def loads test_data and loops), comparing **every row** the story       scopes — full table if the story says "entire CSV / all rows / every value", or only       the columns the story names if it scopes them. Either way: NEVER skip rows, NEVER stop       at a sample. The number of `cap.assert_match` calls the test ends up emitting must       equal (rows the story scopes) × (columns the story scopes).

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
- EXACTLY ONE .feature file per distinct user story. If user_story.txt has N stories, write   EXACTLY N .feature files — no more, no fewer.
- Stories are separated by blank lines or numbered headings ("1.", "2.", "Story 1:"). If a single   continuous flow has no separator, treat it as ONE story.
- Before writing, delete any existing .feature files in /features that don't correspond to the   current stories — the final state of /features must contain only the files for the current run.
- Filenames: features/story_<n>_<short_slug>.feature.
- Use clear Given/When/Then phrasing. Include URL/credentials as scenario context if specified.
- For Scenario Outlines, every row in Examples must end up with an assertable expected outcome.   Negative rows must assert the EXACT error message string from user_data.json — never just   "some error happens".
- After writing, list every file you created with one-line summaries.

Do not generate page objects, step definitions, or tests in this pass. Only Gherkin.

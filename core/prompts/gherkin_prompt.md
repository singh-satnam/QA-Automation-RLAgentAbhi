You are operating inside the QE automation framework rooted at the current working directory (a single project folder). Read the user story file user_story/{{STORY_FILE}} and convert it into a single  .feature file under feature/.
═══════════════════════════════════════════════════════════════════ DUPLICATE STORY DETECTION — RUN FIRST, BEFORE ANY GENERATION ═══════════════════════════════════════════════════════════════════ BEFORE generating any Gherkin, you MUST check for duplicate user stories:
Read the new user story file user_story/{{STORY_FILE}}.


Read EVERY OTHER file in user_story/ (skip the new file itself).


For each existing story, compare at the STEP level:


Extract the action steps from both stories (navigate to X, click Y, enter Z, verify W — ignore preamble/description text).
If 80%+ of the action steps in the new story match an existing story (same actions on the same targets, even if worded differently), the stories are DUPLICATES.
"Match" means the same functional intent: "click Sign In" matches "press the Sign In button"; "enter email" matches "type the email address". Minor phrasing differences do not make steps different.
IF FULL DUPLICATE (80%+ steps match):


DO NOT generate any .feature file.
Find the existing .feature file that corresponds to the matched story (check feature/ for a file whose scenarios cover those steps).
OUTPUT to the user: a. Which existing story file matched and why (list the matching steps). b. The full content of the existing .feature file. c. State: "Skipping generation — this story is already covered."
STOP. Do not proceed to Gherkin generation.
IF PARTIAL OVERLAP (some steps match but new story has additional steps):


Find the existing .feature file for the overlapping story.
OUTPUT to the user: a. Which existing story partially matches (list the overlapping steps). b. The full content of the existing .feature file. c. List the NEW steps that are NOT covered by the existing feature. d. State: "Partial overlap detected — the following steps are new: [list]. Generating a new .feature file for the full story."
PROCEED with Gherkin generation for the new story (generate the complete .feature file including all steps, not just the delta).
IF NO MATCH — proceed directly to Gherkin generation. ═══════════════════════════════════════════════════════════════════


═══════════════════════════════════════════════════════════════════ FIDELITY TO USER STORY — NON-NEGOTIABLE ═══════════════════════════════════════════════════════════════════
EVERY meaningful line of the user story file becomes AT LEAST ONE Gherkin step. No line is silently dropped. No story step is merged with another.
The user story is the BASELINE — generate it faithfully as the first Scenario (the positive/happy path). Then ADDITIONALLY generate negative, edge-case, boundary-value, and the extended scenario families to ensure the requirement works as expected (see COMPREHENSIVE SCENARIO GENERATION below).
Preserve the ORDER from the story. If the story says A then B then C, the scenario does A then B then C — never reordered for "convenience".
Every line that contains words like "Verify", "Check", "Validate", "should be", "should display", "is shown", "is displayed", "matches" → translate into ONE explicit Then step. Don't bundle multiple verifications into one step.
Negative cases explicitly stated in the story (invalid creds, "user already exists", "out of stock") must appear as their own step sequence; never skipped or replaced by the happy path.
Inline data tables (Field: Value blocks, address blocks, etc.) become Gherkin doc-strings or data tables — every key/value preserved. ═══════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════ COMPREHENSIVE SCENARIO GENERATION — REFERENCE GUIDELINES ═══════════════════════════════════════════════════════════════════ GOAL: after generating the positive-path Scenario from the story, analyse every user interaction, input field, action, assertion, and state transition in the story and generate ADDITIONAL Scenarios so the requirement is thoroughly covered.
HOW TO USE THE CATEGORIES BELOW: The categories A–I (Negative, Edge, Boundary, Positive-variations, UI-state, Session/Navigation, Workflow, Data/List, Role/Permission) are a REFERENCE PALETTE and a THINKING AID — not a rigid fill-every-cell checklist. Use them the way an experienced QA engineer uses a heuristics cheat-sheet: read down the list, and for each interaction in the story ask "does this heuristic surface a scenario that is genuinely relevant here?"
· Apply judgment. Generate the scenarios that ARE relevant to the story's actual behaviour; do not manufacture a scenario for a category that does not apply just to tick a box. · The bullet points inside each category are EXAMPLES of the kinds of checks that category inspires — they are illustrative, not a mandatory list to reproduce verbatim. Pick the ones that fit; add sensible ones of your own in the same spirit if the story warrants them. · Aim for COMPLETE coverage of the story's real behaviour — every field, action, and assertion that could plausibly fail or vary should be exercised. "Reference" means flexible about WHICH heuristics apply, not permission to skip meaningful scenarios. · Stay in scope (see SCOPE below): the guidelines inspire scenarios for what the story contains, never for invented features.
────────────────────────────────────────────────────────────────── A. NEGATIVE SCENARIOS — functional failures a QA engineer would test [@negative] · Empty/missing required fields (e.g. empty email, empty password) · Wrong/invalid values (e.g. incorrect password, non-existent user) · Invalid formats (e.g. malformed email "userexample.com", too-short password) · Mismatched dependent fields (e.g. password ≠ confirm-password) · Business-rule violations (e.g. insufficient balance, out of stock, quantity exceeds available, action not allowed in current state) · Duplicate / conflicting submission (e.g. "user already exists", "email already registered") · Unauthorised access (e.g. expired session, revoked permissions, accessing a page without login) · Each negative scenario MUST assert the EXACT expected error/validation message or behaviour (e.g. "Invalid email or password" is displayed). · Do NOT include security testing (XSS, SQL injection, CSRF, etc.).
B. EDGE CASES — unusual but valid situations [@edge] · Leading/trailing whitespace in inputs · Special characters in text fields (quotes, ampersands, unicode, emoji) · Maximum-length input values · Actions performed twice (double-click, double-submit, rapid re-tap) · Network-dependent states (slow load, element not yet visible, timeout) · Pasted vs typed input / browser autofill where the story implies entry
C. BOUNDARY VALUES — limits of valid/invalid input [@boundary] · Minimum and maximum allowed lengths for text fields · Numeric fields at their min, max, min-1, max+1 values · Zero, negative, and very-large numeric values where numbers are entered · Date fields at boundary dates if applicable (today, past, future, limits)
D. POSITIVE VARIATIONS — alternate valid paths to the same outcome [@positive] · Required-fields-only submission vs all-fields (including optional) filled · Alternate valid input formats the story permits (e.g. phone with/without country code, name with middle name) · Multiple valid ways to reach the same result (button vs Enter key, link vs menu) — ONLY if the story mentions more than one path · Each variation asserts the same successful outcome explicitly.
E. UI STATE & FEEDBACK — visible state the story implies [@ui] · Element visibility / enabled-vs-disabled states (e.g. Submit disabled until required fields filled) — only where the story describes it · Loading / spinner / progress state during an async action · Success confirmation message or toast after a successful action · Field-level inline validation feedback (red border, helper text) · State transition of a control (e.g. "Add to cart" → "Added")
F. STATE, SESSION & NAVIGATION — persistence across interruptions [@state] · Page refresh mid-flow (entered data persists or is cleared as specified) · Browser back / forward navigation returns to the correct state · Session persistence after successful action; session expiry / re-login · Data persistence after reload (cart, saved draft, filters) · Direct-URL / deep-link access to a page (allowed or redirected to login) · Generate ONLY when the story involves login, saved data, carts, or multi-step flows where interruption is meaningful.
G. WORKFLOW & INTERACTION — mid-action control [@workflow] · Cancel / discard mid-action (changes are not saved) · Retry after a failure recovers correctly (the story's negative recovery) · Confirmation / cancellation dialogs (confirm proceeds, cancel aborts) · Sequential dependent actions where one gates the next · Generate ONLY when the story has cancel buttons, dialogs, or multi-step dependent actions.
H. DATA-DRIVEN & LIST BEHAVIOUR — collections, search, results [@data] · Empty state (no results / no data / empty cart) with the exact empty message the story specifies · Single result vs multiple results · Large result set → pagination / scroll / "load more" if mentioned · Sorting and filtering produce the correct ordered/filtered set · Search: exact match, partial match, no-match, case sensitivity — only the variants the story's search implies · Generate ONLY when the story involves lists, tables, search, or catalogs.
I. ROLE & PERMISSION — access varies by user type [@permission] · Each authorised role can perform the action (one row/scenario per role) · Unauthorised role is blocked with the exact denial message/behaviour · Permission boundary (e.g. manager can delete, standard user cannot) · Generate ONLY when the story names roles, permissions, or user types.
────────────────────────────────────────────────────────────────── GROUPING RULES: · Group related variations of the SAME behaviour into a SINGLE Scenario Outline with an Examples table. E.g. all login-failure variations (empty email, empty password, wrong password, malformed email) become ONE Scenario Outline with one row per variation and columns for input + expected_error. · Use a separate Scenario (not Outline) when the BEHAVIOUR is fundamentally different (e.g. double-submit has different steps than wrong-password; cancel-mid-flow differs from a validation failure). · Every Scenario Outline row MUST include an expected outcome column (expected_error, expected_message, expected_result) so the step def can assert the specific result for that row.
SCOPE (unchanged and strictly enforced): · Generate negatives/edges/extended families ONLY for interactions, fields, pages, and controls that appear IN the story. Do NOT fabricate entirely new features, pages, roles, fields, or flows the story does not mention. Categories D–I are conditional — trigger only on the signals named in each. · The positive Scenario comes FIRST, followed by the other Scenarios. · Tag each scenario with its category tag: @positive, @negative, @edge, @boundary, @ui, @state, @workflow, @data, @permission. A scenario may carry more than one tag if it legitimately spans families. ═══════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════ COVERAGE SELF-REVIEW — RUN AFTER DRAFTING, BEFORE WRITING FILE ═══════════════════════════════════════════════════════════════════ Use this as a review pass to confirm you have not missed anything meaningful. It is a guideline for checking your own thoroughness, not a rigid form to fill. After you have drafted the Scenarios but BEFORE writing the .feature file:
Build a COVERAGE MATRIX as a review aid. List every distinct interaction/ field/action/assertion extracted from the story down the rows. Across the columns put the nine reference categories A–I. For each cell mark: ✓ COVERED → name the Scenario/row that covers it N/A → one-line reason the category is not relevant here The matrix is a lens to spot gaps — the value is finding relevant scenarios you missed, not producing an entry for every combination.


Sanity checks (apply judgment, these are the ones that usually matter): · Each input field that is REQUIRED generally warrants a positive path plus its relevant failure cases (empty, invalid value/format) — include the ones that make sense for that field. · Fields with a length / numeric / date limit generally warrant boundary coverage. · Every assertion in the story ("should display", "should be", "matches") should map to at least one explicit Then step in some Scenario. This one is firm — story assertions must not be dropped.


If the review surfaces a RELEVANT scenario you have not yet covered, add it before writing the file. If a category is genuinely not relevant, mark it N/A and move on — do not invent scenarios to fill it.


Output the COVERAGE MATRIX to the user alongside the file summary so the coverage is auditable. Keep it compact (a table is fine). ═══════════════════════════════════════════════════════════════════


ALSO read the test-data JSON file referenced by the story (if present in the project folder). It is an OPTIONAL sidecar that drives parameterisation:
SHAPE A — JSON object (one dict at the top level): user_data.json contains key/value pairs the story references via <placeholder> tokens. Generate ONE Scenario per story. Substitute concrete values in scenario steps directly. If the story has assertion intent (e.g. "Total should be 61.94"), emit explicit Then steps that reference the data values — Then the Subtotal is "<Subtotal>" etc. so the generated tests can verify exact values from user_data.json at runtime.


SHAPE B — JSON array (list of dicts): Each dict is one Example row. Generate a Scenario Outline whose Examples: table has one column per key, with one Examples row for EVERY dict in the array. If the array has 100 dicts, the Examples table MUST have 100 rows. NEVER truncate to a sample, NEVER cap at 25 / 50 / "first few", NEVER drop "similar-looking" rows. Each row must execute as its own test invocation. Rows may be POSITIVE or NEGATIVE — if a row contains expected_message, should_succeed: false, expected_error, or similar, it is a NEGATIVE row. The Outline MUST include a Then step that asserts the expected outcome explicitly (success path OR exact error). Do NOT soft-pass on "any error".


SHAPE C — JSON array used as a REFERENCE TABLE (not parameterisation): If the story says things like "verify the downloaded CSV", "compare with the data file", "every row matches", the array is the ground truth the test must check against the live data. In that case, generate ONE Scenario whose Then steps iterate the array at runtime (the step def loads test_data and loops), comparing every row the story scopes — full table if the story says "entire CSV / all rows / every value", or only the columns the story names if it scopes them. Either way: NEVER skip rows, NEVER stop at a sample. The number of cap.assert_match calls the test ends up emitting must equal (rows the story scopes) × (columns the story scopes).


NO user_data.json: Generate the positive-path Scenario from the story (no parameters), plus the negative/edge/boundary and extended-family Scenarios per COMPREHENSIVE SCENARIO GENERATION, driven by the COVERAGE SELF-AUDIT.


NEGATIVE STEPS INLINE IN THE STORY (no JSON needed)
The user may write negative-path steps directly in the user story file, e.g.: "enter the below invalid login details" "User should not be logged in" "Invalid email or password validation message should be displayed" "Clear the fields and enter the below valid login details"
Detect these inline negative attempts by these signals:
Words like "invalid", "wrong", "incorrect", "bad", "expired" preceding credentials/values
Negative assertions like "should not be", "should fail", "should be rejected"
Validation/error messages: "validation message should be displayed", "error message should appear", "should show invalid", "should show error"
When present, the .feature MUST include the negative attempt as its OWN explicit step sequence BEFORE the positive one: Examples (literal, illustrative): When the user enters email "invalid@myyahoo.com" and password "wrongpass" Then the "Invalid email or password" validation message is displayed And the user is not logged in When the user clears the email and password fields And the user enters email "qauto@myyahoo.com" and password "passw0rd"
Both halves (negative attempt + positive recovery) MUST end up in the same Scenario. Preserve the order from the story. Do not skip the negative attempt — it is a first-class test case. The validation message text in the assertion must be the EXACT phrase from the story (or as close as the story allows).
MISSING-DATA INTENT (when the story expects items but some may not exist live):
Some stories list multiple independent targets — "search ice cream AND chocolate, add each to cart" or "delete employees X AND Y". When that happens, Gherkin MUST reflect that each target is its own iteration:
· Prefer a Scenario Outline whose Examples table lists each target on its own row. pytest-bdd then runs one test per row. Missing items affect ONLY that row's verdict, not the others. · OR an explicit per-item And-chain so each Then is independently assertable: When the user searches for "ice cream" Then the result for "ice cream" is recorded (found or not found) When the user searches for "chocolate" Then the result for "chocolate" is recorded (found or not found) And the cart contains every product that WAS found
When the story has a BLOCKING prerequisite (e.g. "log in as manager 503 then …"), the very first Then after the login MUST explicitly check it succeeded: When the manager submits credentials Then the manager is logged in ← this becomes assert_prerequisite at step-def time
Never collapse a "search A and search B" story into one step "search the catalog". Each named target needs its own step so missing items can be individually reported.
Hard rules:
Write EXACTLY ONE .feature file per user story into feature/. Name it after the FEATURE under test — a short snake_case slug, e.g. feature/login_validation.feature. This single file contains ALL Scenarios (positive, negative, edge, boundary, and any applicable extended families) for that story.
NEVER delete or overwrite an existing .feature file. If a file with your chosen name already exists, append a short disambiguating suffix so the new file is unique.
The .feature file MUST contain multiple Scenario / Scenario Outline blocks: the positive path first, then the negative/edge/boundary and applicable extended-family Scenarios. Use Scenario Outlines with Examples tables for data-driven variations.
For Scenario Outlines, every Examples row must end with an assertable expected outcome column. Negative rows must assert the EXACT error/validation string — never just "some error happens".
Scenario names MUST NOT contain test data values. Use generic names that describe the test intent (e.g. "Login with invalid credentials" not "Login with user john@test.com").
Run the COVERAGE SELF-REVIEW before writing the file, and add any RELEVANT scenario the review surfaces. The reference categories are guidelines — use judgment on which apply; do not manufacture scenarios for categories that don't fit the story.
After writing, list the file you created with: (a) how many Scenarios it contains and their types/tags (positive/negative/edge/boundary/ui/state/workflow/data/permission), and (b) the COVERAGE MATRIX showing each story interaction against the nine reference categories.
Do not generate page objects, step definitions, or tests in this pass. Only Gherkin.


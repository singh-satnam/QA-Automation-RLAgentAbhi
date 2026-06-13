# QE Agent — Project-Scoped Workspace Layout

**Date:** 2026-06-13
**Status:** Approved (design), pending implementation plan

## Problem

The current agent derives the "project" identity from the **URL inside a user
story**, generates artifacts into a *flat workspace inside `core/`*, then
archives each story into its own `workspace/projects/<app_id>/<slug>__<digest>/`
folder. It also maintains a `_shared/` reuse folder plus cross-project
fork/promote/restore machinery and a legacy-folder migration.

This conflicts with the desired model:

- `core/` must contain **only agent code** — no user stories, feature files,
  step defs, pytest config, reports, or any client-specific data.
- A "project" is identified by the **filename prefix** of the uploaded user
  story (`RLRG_login.txt` → `RLRG`), not by a URL.
- All stories of a project share **one flat set of folders**; there are no
  per-story subfolders and no `_shared/` reuse layer.

## Goals

1. Identify the project from the uploaded story filename (or an explicit field
   when pasting).
2. Keep `core/` pure agent code.
3. Lay every project out as a single flat folder tree under `workspace/`.
4. Never destroy a user's existing stories, features, or framework components;
   only add.
5. Detect duplicate stories by filename and short-circuit with a clear UI
   message.
6. Generate artifacts directly into the project folder (agent subprocess runs
   there), not into `core/`.

## Non-goals

- Preserving the old `ra_demo_*` example data (wiped — start clean).
- Keeping the `_shared/` **folder** and the cross-folder copy machinery (fork,
  promote, restore, legacy-migration) — all removed. The reuse *goal* is
  retained and strengthened (see "Reuse and efficiency"); only the redundant
  copy layer goes away.
- Cross-project similarity / "fork a prior project" suggestions (removed).

## Decisions (locked during brainstorming)

| Topic | Decision |
|---|---|
| Project name source | Filename prefix before the first `_`. |
| No-prefix filename | **Reject** the upload with a UI error. |
| Architecture | **Full replace** of per-story / `_shared` / fork model. |
| Duplicate detection | By **filename** within `user_story/`. |
| Reports | Timestamped run folders; UI shows current run's test(s) plus per-test history. |
| Paste path | Keep paste, with a required **Project name** field + **Story filename** field. |
| Stories per file | **One file = one story** (one feature file per story; drop blank-line splitting). |
| Folder names | Follow the spec diagram exactly: singular `feature`, `test`, `report`. |
| Existing data | Wipe and start clean. |
| pytest.ini / conftest.py | **Per-project generated files** inside `workspace/<project>/`. |
| Reuse layer | **No `_shared/` folder.** The flat project folders ARE the shared layer. Reuse is enforced behaviorally via read-before-generate, the delta prompt, and a maintained `reuse_index.json`. |

## Design

### Project identity

- **Upload:** filename must match `‹project›_‹rest›.txt`. Project = text before
  the **first** underscore. A filename with no underscore is rejected with:
  *"Filename must be `‹project›_‹name›.txt` so the project can be identified."*
- **Paste:** a required **Project name** text field and a required **Story
  filename** field (must end in `.txt`). The pasted text is saved under that
  filename in `user_story/`.

### Folder layout

```
workspace/‹project›/
  user_story/          one .txt per story (never overwritten/deleted)
  feature/             unique .feature per feature (never overwritten/deleted)
  step_defs/
  pages/
  test/
  mcp-selectors/
  report/‹timestamp›/  one folder per test run
  reuse_index.json     known flows / page-methods / selectors -> file (reuse map)
  pytest.ini           generated once per project (base_url from story URL)
  conftest.py          generated once per project (fixtures / setup / teardown)
```

Folder names follow the diagram exactly (singular `feature`, `test`,
`report`). The repo-level `workspace/` directory holds one such tree per
project; there is no intermediate `projects/` directory and no per-story
subfolder. There is **no `_shared/` subfolder** — see "Reuse and efficiency".

### Removed components

- Per-story `‹slug›__‹digest›/` archive folders.
- `_shared/` reuse folder. (`flow_index.json`'s role is replaced by the
  per-project `reuse_index.json` described in "Reuse and efficiency".)
- `promote_to_shared`, `restore_from_shared`, `fork_project_into_workspace`,
  `find_similar_projects`, `_score_similarity`, `_extract_flow_signals`,
  `_migrate_legacy_folders`, `_is_app_folder`, and the URL-derived
  `_extract_app_id` / `app_id_for_story_id` / `app_shared_has_work` logic.
- The "flat workspace inside `core/`" pattern (`archive_artifacts` /
  `restore_artifacts` copy cycle).
- Stray data files in `core/`: `user_story.txt`, `user_data.json`,
  `features/`, `pages/`, `step_defs/`, `tests/`, `conftest.py`, `pytest.ini`,
  `mcp-selectors/`, `reports/`, `generation_log.txt`, `.playwright-mcp/`,
  `.pytest_cache/`.
- Existing `workspace/projects/ra_demo_*` content (wiped).

After cleanup, `core/` retains only: `agent_ui.py`, `prompts/`,
`requirements.txt`, `.streamlit/`.

### Upload / duplicate flow

1. Derive the project from the filename (or the paste fields).
2. Create only the missing `workspace/‹project›/…` subfolders. If the project
   folder already exists, reuse it — do not recreate or clear it.
3. If `user_story/‹filename›` **already exists**, stop and show:
   *"same user story exists. Proceed to execute the test."* Generate nothing.
4. Otherwise write the new story file into `user_story/`; leave every other
   story file untouched.

### Generation (agent subprocess)

- The agent subprocess runs with **`cwd = workspace/‹project›/`**. Prompts use
  relative paths so artifacts land directly in the project. `core/` is never
  written to during generation.
- **Discovery (Playwright MCP scouts):** write into `‹project›/mcp-selectors/`;
  create the folder if missing, append files, never wipe.
- **Gherkin:** read the *specific* uploaded story file, write a **new
  uniquely-named** `.feature` into `feature/`, named after the feature under
  test. Never delete or overwrite existing features. Cover positive, negative,
  and boundary scenarios; emit a Scenario Outline + Examples when the story
  references a JSON test-data file.
- **Framework (`framework_prompt`):** build `step_defs/`, `pages/` (POM +
  `base_page.py`), `test/`, and generate `conftest.py` / `pytest.ini` the first
  time for the project. POM, base page, and fixtures follow industry-standard
  BDD structure.
- **Framework delta (`framework_delta_prompt`):** when the project already has
  framework components, add **only** the new feature's pages / step defs /
  tests. Do not duplicate `base_page.py`, fixtures, or `conftest.py`.

### Reuse and efficiency

A project will accumulate many stories over time. Reuse must be aggressive:
no duplicate code, logic, files, or repeated MCP discovery. This is achieved
**without** a separate `_shared/` folder — the project's own flat folders are
the shared store — through three mechanisms:

1. **The flat project folders are the shared assets.** Every story writes into
   the same `pages/`, `step_defs/`, `mcp-selectors/`. Nothing is copied between
   stories because nothing is siloed.
2. **`reuse_index.json` at the project root** maps what already exists — known
   flows, page-object methods, and discovered selectors → the file that
   provides them. The agent greps this index *before* any MCP discovery or new
   POM/step authoring, so it can answer "do I already have this?" cheaply (low
   token cost). The index is refreshed after each successful framework /
   discovery pass.
3. **Read-before-generate per phase:**
   - **Discovery:** read existing `mcp-selectors/locators.json` + the reuse
     index first; run Playwright MCP **only for screens/elements not already
     mapped**. Known pages are never re-crawled.
   - **Framework:** for any story *after the first* in a project, the agent
     uses `framework_delta_prompt` by default — it extends existing POMs and
     adds new step defs, and **never** regenerates `base_page.py`,
     `conftest.py`, fixtures, or duplicates an existing page method. The full
     `framework_prompt` runs only when the project has no framework yet.

The agent must always prefer reusing an existing selector / page method / step
def over creating a new one; it creates new artifacts only for genuinely new
flows the project has not seen.

### Prompt edits

Update every prompt `.md` so it:

- Uses the singular folder names (`feature`, `test`, `report`, `mcp-selectors`).
- Reads the target story file rather than assuming a single `user_story.txt`
  at the cwd root.
- Never deletes or overwrites existing features or framework components.

Specifically, remove the rule in `gherkin_prompt.md` that says *"delete any
existing .feature files in /features"* and replace it with the create-only
rule.

### Reports

Each test run writes into `report/‹timestamp›/`. pytest's HTML and Allure
output paths point at that timestamped folder. The UI:

- Shows the report for the test(s) just run.
- For each such test, surfaces prior runs (history).
- When a group of tests runs, shows fresh results for what ran and historical
  results for the rest.

## Affected code (high level)

- `core/agent_ui.py` — module-level path constants, project-derivation helpers,
  upload/paste handlers, `clean_artifacts`, subprocess `cwd`, report paths,
  removal of archive/shared/fork machinery, and the sidebar UI.
- `core/prompts/*.md` — folder names, story-file reading, create-only rules.
- `core/` filesystem cleanup (delete stray artifacts).
- `workspace/` reset to clean slate.

## Open questions

None outstanding. (pytest.ini/conftest location resolved: per-project
generated files.)

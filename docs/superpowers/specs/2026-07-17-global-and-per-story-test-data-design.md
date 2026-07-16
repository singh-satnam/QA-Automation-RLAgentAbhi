# Global + Per-Story Test Data (`test_data/` folder) — Design

**Date:** 2026-07-17
**Branch:** feature/version10
**Status:** Approved for planning

## Problem

The QE Agent pipeline needs two tiers of externalised test data:

1. **Global project data** — URL, username, password and other values shared by
   most tests in a project. Defined once, used many times.
2. **Per-story test data** — data specific to one user story (product ids,
   employee names, parameterised rows).

Today there is only a single home: an uploaded JSON/CSV/XLSX is converted to
`user_data.json` at the project root, and the conftest `test_data` fixture reads
only that file. There is no global-vs-story separation, no `.env`, and the base
URL is scraped from the story text with a brittle regex.

This design introduces a `test_data/` folder per project holding a global `.env`
and per-story JSON files, a second UI uploader ("Global_Project_Data"), rewired
conftest fixtures, and updated LLM prompts — while keeping existing generated
projects (e.g. `ResGate`) working unchanged.

## Requirements Covered

- **Req 8** — new UI upload field "Global_Project_Data" (JSON).
- **Req 9** — on upload to staging, create `test_data/` and save as `test_data/.env`.
- **Req 10** — tests read global URL/username/password from `.env` (define once, use many).
- **Req 12** — existing "Test Data" upload creates `test_data/` and saves the JSON
  named after the user-story filename (`test_data/<storyname>.json`).
- **Req 13** — the runtime fixtures consume these files.

## Decisions (confirmed with user)

1. **`.env` format** — convert the uploaded JSON to standard dotenv `KEY=VALUE`
   lines (not JSON saved verbatim). The raw JSON is preserved alongside.
2. **Per-story data** — save to `test_data/<storyname>.json`; the `test_data`
   fixture reads the story-matching file, falling back to legacy project-root
   `user_data.json` so existing projects keep working.
3. **URL precedence** — `.env` URL wins over the story/pytest.ini URL.
4. **Key precedence** — for a given test, per-story JSON keys override `.env`
   keys, EXCEPT the URL, where the global `.env` is the single source.
5. **Code organisation** — the two uploaders + data ingestion move into a new
   pure-Python module `core/test_data_io.py` (Streamlit-free, unit-testable),
   mirroring how `step_report.py` is split out.

## Architecture

### Folder layout (per project, staging and workspace)

```
temp_workspace/<Project>/
  test_data/
    .env                       # global KEY=VALUE (from Global_Project_Data)
    global_project_data.json   # raw uploaded global JSON, preserved
    <storyname>.json           # per-story data (from "Test data" uploader)
    <storyname>.<ext>          # original non-JSON per-story upload, preserved
```

### New module: `core/test_data_io.py`

Pure functions, no Streamlit import. Unit-tested directly.

- `flatten_json_to_dotenv(data: dict | list) -> str`
  - Top-level scalar keys → `KEY=value`.
  - Non-scalar values (nested dict/array) → `KEY={compact-json}` on one line.
  - Keys upper-cased, spaces → `_`.
  - Values containing newline / `#` / leading-trailing space → double-quoted,
    inner `"` and `\` escaped.
  - A top-level array (no keys) is an error surfaced to the UI: global data must
    be a JSON object.
- `parse_dotenv(text: str) -> dict[str, str]`
  - Skip blank lines and lines starting with `#`.
  - Split on the first `=`; strip surrounding whitespace; unquote if quoted.
- `write_global_env(project_dir: Path, raw_json_text: str) -> tuple[bool, str]`
  - Validate JSON is an object, flatten, write `test_data/.env`, preserve
    `test_data/global_project_data.json`. Returns (ok, message/error).
- `write_story_data(project_dir: Path, story_stem: str, filename: str,
  raw_bytes: bytes) -> tuple[bool, str]`
  - Reuse `convert_uploaded_to_json` output; write `test_data/<story_stem>.json`;
    preserve original as `test_data/<story_stem>.<ext>` for non-json.
- `resolve_story_data_file(test_data_dir: Path, slug: str) -> Path | None`
  - Match a `*.json` in `test_data/` whose stem relates to the running test slug
    (exact, then substring either direction), excluding `global_project_data.json`.

`convert_uploaded_to_json` (currently in `agent_ui.py`) moves into this module so
both the module and the UI share one implementation.

### UI changes (`core/agent_ui.py`)

Both uploaders call into `test_data_io`. The UI keeps only Streamlit glue.

1. **"Global_Project_Data" uploader** (new sidebar block).
   - `type=["json"]`, label exactly `Global_Project_Data`.
   - On upload with an active project + staging: call `write_global_env`,
     show the resulting `.env` preview, `st.rerun()`.
   - If no active project: warn.

2. **"Test data" uploader** (existing block, retargeted).
   - Save to `test_data/<active_story_stem>.json` via `write_story_data`
     instead of project-root `user_data.json`.
   - Requires an **active story** (not just a project); warn if none selected.
   - The inline JSON text-area editor edits the same `test_data/<story>.json`.

`user_data_path()` / `_read_user_data_text()` remain for reading legacy data and
the editor's back-compat path, but new writes go to `test_data/`.

### `workspace.py` changes

- Append `"test_data"` to `PROJECT_SUBDIRS` (additive; appending to the tail does
  not disturb existing name-dependent downstream code). `ensure_project_dirs`,
  `staging_file_summary`, and promotion pick it up for free.
- No change to `promote_to_workspace` (already recurses — `.env` and per-story
  JSON promote automatically), `clean_artifacts` (never touches `test_data`), or
  `write_pytest_ini`.

### conftest fixture changes (`core/templates/conftest.py`)

This file is copied verbatim into every NEW project. Existing projects keep their
old conftest until regenerated; the fallback path guarantees they still work.

- Add `_parse_env(path)` — hand-rolled dotenv parser (no new dependency).
- New session fixture `global_data` → dict from `test_data/.env` (or `{}`), also
  pushed into `os.environ` (only for keys not already set) so step defs may use
  `os.getenv("PASSWORD")`.
- Rewrite `test_data` fixture to **function scope**, taking `request`:
  1. Start from a copy of `global_data`.
  2. Derive slug from the running test module name (`test_<slug>.py` → `<slug>`);
     `resolve_story_data_file` finds the per-story JSON; overlay its keys
     (per-story wins) — but never overwrite the resolved URL key.
  3. If no `test_data/` JSON matches and `test_data/.env` is absent, fall back to
     legacy project-root `user_data.json`.
- `base_url` fixture: resolve `.env` `URL`/`BASE_URL` (case-insensitive) first,
  then `pytest.ini`, then `""`.

`base_page.py` is unchanged.

### Prompt changes

- `framework_prompt.md` and `framework_delta_prompt.md`: replace the
  "read `user_data.json` via the `test_data` fixture" instructions (reqs 6, 73)
  with:
  - Global URL / username / password come from the `test_data` fixture (which now
    merges `.env`) or the `global_data` fixture — read at runtime, never hardcoded.
  - Per-story data comes from the same `test_data` fixture.
  - Shared login/navigation steps in `common_steps.py` read credentials from the
    fixture so every feature reuses them ("define once, use many").

### Security

`test_data/` holds credentials. Add `test_data/` and `**/.env` to `.gitignore`.
Never commit `.env` or per-story data files. This upholds the project's standing
credential-security rule.

## Data Flow

```
Global_Project_Data upload (JSON)
   -> test_data_io.write_global_env
   -> test_data/.env  +  test_data/global_project_data.json
        -> conftest global_data fixture -> os.environ + test_data fixture (base)
             -> base_url fixture (URL key)
             -> step defs (USERNAME/PASSWORD)

Test data upload (JSON/CSV/XLSX, active story = RLRG_login.txt)
   -> convert_uploaded_to_json -> test_data_io.write_story_data
   -> test_data/RLRG_login.json
        -> conftest test_data fixture overlays onto global_data for test_login.py
```

## Error Handling

- Global upload that is not a JSON object → UI error, nothing written.
- Test-data upload with no active story → UI warning, nothing written.
- Malformed CSV/XLSX → existing `convert_uploaded_to_json` error surfaced.
- Missing `.env` / missing per-story JSON → fixtures degrade gracefully (empty
  dict / legacy fallback), tests still run.
- Per-story slug matches nothing → `test_data` returns global-only data.

## Testing

Extend `tests/test_workspace.py` and add coverage for the new module:

- `PROJECT_SUBDIRS` includes `test_data`; `ensure_project_dirs` creates it.
- `flatten_json_to_dotenv`: scalars, nested object/array, key normalisation,
  value quoting, non-object input rejected.
- `parse_dotenv`: comments, blank lines, quoted values, first-`=` split, round-trip.
- `write_global_env`: `.env` + raw JSON written; invalid input rejected.
- `write_story_data`: `test_data/<stem>.json` naming; original preserved for csv.
- `resolve_story_data_file`: exact and substring slug matching; excludes
  `global_project_data.json`.
- Fixture behaviour is verified by running the app (conftest is not unit-tested),
  plus a small standalone test of `_parse_env` logic if extracted.

## Out of Scope

- Removing `user_data.json` entirely (kept as legacy fallback; retire later once
  all projects regenerate).
- Encrypting `.env` at rest (gitignore + never-commit is the boundary here).
- Multi-environment `.env` files (dev/stage/prod) — single `.env` per project.

## Files Touched

- `core/test_data_io.py` — NEW pure module.
- `core/agent_ui.py` — two uploaders call the module; `convert_uploaded_to_json`
  moves out.
- `core/workspace.py` — append `test_data` to `PROJECT_SUBDIRS`.
- `core/templates/conftest.py` — `global_data` fixture, `test_data` rewrite,
  `base_url` `.env` precedence, `_parse_env`.
- `core/prompts/framework_prompt.md`, `core/prompts/framework_delta_prompt.md`.
- `.gitignore` — `test_data/`, `**/.env`.
- `tests/test_workspace.py` + new `tests/test_test_data_io.py`.

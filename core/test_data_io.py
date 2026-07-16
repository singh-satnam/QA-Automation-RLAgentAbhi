"""Pure (Streamlit-free) test-data I/O for the QE Agent.

Owns the conversion between uploaded files and the on-disk test_data/ layout:
  * global data  -> test_data/.env  (dotenv KEY=VALUE)  + raw JSON preserved
  * per-story    -> test_data/<storyname>.json  (+ original non-json preserved)

Kept import-light so it can be unit-tested without Streamlit. The multi-format
ingestion (json/csv/tsv/xlsx -> canonical JSON text) lives here too, so both the
UI and this module share one implementation.
"""
from __future__ import annotations

import json
from pathlib import Path

TEST_DATA_DIRNAME = "test_data"
GLOBAL_RAW_NAME = "global_project_data.json"
ENV_NAME = ".env"

USER_DATA_SUPPORTED_EXTENSIONS = ("json", "csv", "tsv", "xlsx", "xls")


# ---------------------------------------------------------------------------
# JSON <-> dotenv
# ---------------------------------------------------------------------------
def _dotenv_key(key: str) -> str:
    return str(key).strip().upper().replace(" ", "_")


def _dotenv_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        raw = str(value)
    needs_quote = (
        raw != raw.strip()
        or "\n" in raw
        or "#" in raw
        or '"' in raw
    )
    if needs_quote:
        escaped = raw.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return raw


def flatten_json_to_dotenv(data: dict) -> str:
    """Flatten a JSON object to dotenv text. Nested values are JSON-encoded.
    Raises ValueError if `data` is not a dict (global data must be an object)."""
    if not isinstance(data, dict):
        raise ValueError("Global_Project_Data must be a JSON object, not an array.")
    lines = [f"{_dotenv_key(k)}={_dotenv_value(v)}" for k, v in data.items()]
    return "\n".join(lines) + "\n"


def parse_dotenv(text: str) -> dict[str, str]:
    """Minimal dotenv parser: skips blanks/`#`, splits on first `=`, unquotes."""
    out: dict[str, str] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("\"", "'"):
            val = val[1:-1].replace('\\n', "\n").replace('\\"', '"').replace("\\\\", "\\")
        out[key] = val
    return out


# ---------------------------------------------------------------------------
# Multi-format ingestion (moved from agent_ui.py)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Writers + per-story resolver
# ---------------------------------------------------------------------------
def write_global_env(project_dir: Path, raw_json_text: str) -> tuple[bool, str]:
    """Validate the raw JSON is an object, flatten to .env, and persist both the
    .env and the raw JSON under test_data/. Returns (ok, message)."""
    try:
        data = json.loads(raw_json_text)
    except ValueError as exc:
        return False, f"Not valid JSON: {exc}"
    if not isinstance(data, dict):
        return False, "Global_Project_Data must be a JSON object (key/value), not an array."
    try:
        env_text = flatten_json_to_dotenv(data)
    except ValueError as exc:
        return False, str(exc)
    td = project_dir / TEST_DATA_DIRNAME
    td.mkdir(parents=True, exist_ok=True)
    (td / ENV_NAME).write_text(env_text, encoding="utf-8")
    (td / GLOBAL_RAW_NAME).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return True, f"Wrote {len(data)} key(s) to test_data/.env"


def write_story_data(project_dir: Path, story_stem: str, filename: str,
                     raw_bytes: bytes) -> tuple[bool, str]:
    """Convert an uploaded per-story file to JSON and save it as
    test_data/<story_stem>.json. Non-JSON originals are preserved alongside."""
    json_text, msg = convert_uploaded_to_json(filename, raw_bytes)
    if json_text is None:
        return False, msg or "Could not convert file."
    td = project_dir / TEST_DATA_DIRNAME
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{story_stem}.json").write_text(json_text, encoding="utf-8")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext and ext != "json":
        try:
            (td / f"{story_stem}.{ext}").write_bytes(raw_bytes)
        except OSError:
            pass
    return True, msg or f"Saved test_data/{story_stem}.json"


def resolve_story_data_file(test_data_dir: Path, slug: str) -> Path | None:
    """Find the per-story JSON whose stem relates to `slug` (exact, then
    substring either direction). Excludes the global raw JSON. None if no match."""
    if not test_data_dir.exists():
        return None
    candidates = [
        p for p in sorted(test_data_dir.glob("*.json"))
        if p.name != GLOBAL_RAW_NAME
    ]
    for p in candidates:
        if p.stem == slug:
            return p
    for p in candidates:
        if slug and (slug in p.stem or p.stem in slug):
            return p
    return None

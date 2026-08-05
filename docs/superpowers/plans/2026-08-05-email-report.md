# Email Report Feature — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a pytest run, if `--email` is passed, send both `story_coverage.html` and `report.html` to recipients defined in the project-level `email_config.json`.

**Architecture:** Email logic lives inline in `conftest.py` (stdlib only — no external deps, no path fragility). `agent_ui.py` appends `--email` to the pytest command when a UI checkbox is ticked. A `pytest_addoption` hook registers the flag; `pytest_sessionfinish` reads config and sends after the session.

**Tech Stack:** Python stdlib (`smtplib`, `email.mime`, `json`, `pathlib`), Streamlit checkbox, pytest hooks.

## Global Constraints

- Stdlib only in `conftest.py` — no pip dependencies beyond what already exists
- Email send failures must NEVER change pytest exit code — always catch and warn
- `email_config.json` is gitignored — never committed
- `smtp_port` 587 = STARTTLS; 465 = SSL; anything else = STARTTLS fallback
- Subject prefix defaults to `[QE Agent]` if not in config
- Both attachments are optional — skip silently if file doesn't exist

---

### Task 1: Add email hook to conftest.py template

**Files:**
- Modify: `core/templates/conftest.py` (lines 503–515 — `pytest_sessionfinish` + add `pytest_addoption`)

**Interfaces:**
- Produces: `pytest_addoption` registers `--email` flag; `pytest_sessionfinish` calls `_send_run_report(session)` after writing JSON files

- [ ] **Step 1: Add imports at top of conftest.py template**

Open `core/templates/conftest.py`. After the existing imports block (after `from pathlib import Path`), add:

```python
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
```

- [ ] **Step 2: Add `pytest_addoption` hook**

Add this function after the `pytest_plugins = ()` line (around line 28):

```python
def pytest_addoption(parser):
    parser.addoption(
        "--email",
        action="store_true",
        default=False,
        help="Email story_coverage.html + report.html after the test session",
    )
```

- [ ] **Step 3: Add `_send_run_report` helper function**

Add this function just before `pytest_sessionfinish` (before line 503):

```python
def _send_run_report(session) -> None:
    """Read email_config.json and send both run reports. Never raises."""
    config_path = PROJECT_ROOT / "email_config.json"
    if not config_path.exists():
        print(f"\n[email-report] email_config.json not found at {config_path} — skipping email.")
        return

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"\n[email-report] Could not read email_config.json: {exc} — skipping email.")
        return

    smtp_host = config.get("smtp_host", "")
    smtp_port = int(config.get("smtp_port", 587))
    smtp_user = config.get("smtp_user", "")
    smtp_password = config.get("smtp_password", "")
    from_addr = config.get("from", smtp_user)
    to_addrs = config.get("to", [])
    subject_prefix = config.get("subject_prefix", "[QE Agent]")

    if not smtp_host or not to_addrs:
        print("\n[email-report] smtp_host or to addresses missing in email_config.json — skipping email.")
        return

    # Read verdict from latest story_coverage.json
    verdict = "UNKNOWN"
    summary_line = ""
    coverage_json_candidates = sorted(REPORT_DIR.glob("*/story_coverage.json"), reverse=True)
    if coverage_json_candidates:
        try:
            data = json.loads(coverage_json_candidates[0].read_text(encoding="utf-8"))
            verdict = data.get("verdict", "UNKNOWN")
            counts = data.get("counts") or {}
            passed = counts.get("passed", "?")
            failed = counts.get("failed", "?")
            assertions = counts.get("assertions", "?")
            summary_line = f"{passed} passed · {failed} failed · {assertions} assertions"
        except Exception:
            pass

    project_name = PROJECT_ROOT.name
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    subject = f"{subject_prefix} {project_name} — {verdict} | {summary_line} — {timestamp}"

    body_text = (
        f"Project:    {project_name}\n"
        f"Verdict:    {verdict}\n"
        f"Ran:        {timestamp}\n"
        f"\n"
        f"Results:    {summary_line}\n"
        f"\nAttachments: story_coverage.html, report.html (if present)\n"
        f"\n-- QE Agent\n"
    )

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain"))

    # Attach story_coverage.html and report.html from newest run dir
    report_dirs = sorted(REPORT_DIR.glob("*/"), reverse=True)
    run_dir = report_dirs[0] if report_dirs else None

    for filename in ("story_coverage.html", "report.html"):
        filepath = (run_dir / filename) if run_dir else None
        if filepath and filepath.exists():
            try:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(filepath.read_bytes())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={filename}")
                msg.attach(part)
            except Exception as exc:
                print(f"\n[email-report] Could not attach {filename}: {exc}")
        else:
            body_text_note = f"\n[email-report] {filename} not found — not attached."
            print(body_text_note)

    try:
        if smtp_port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(from_addr, to_addrs, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(from_addr, to_addrs, msg.as_string())
        print(f"\n[email-report] Report emailed to {', '.join(to_addrs)} — verdict: {verdict}")
    except Exception as exc:
        print(f"\n[email-report] Failed to send email: {exc}")
```

- [ ] **Step 4: Update `pytest_sessionfinish` to call `_send_run_report`**

The existing `pytest_sessionfinish` (lines 503–514) writes JSON files. Append the email call at the end:

```python
def pytest_sessionfinish(session, exitstatus):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        (REPORT_DIR / "captured_values.json").write_text(
            json.dumps(_CAPTURES, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass
    try:
        (REPORT_DIR / "step_trace.json").write_text(
            json.dumps(_STEP_TRACE, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass
    if session.config.getoption("--email", default=False):
        _send_run_report(session)
```

- [ ] **Step 5: Verify conftest.py parses without error**

```bash
python -c "import ast; ast.parse(open('core/templates/conftest.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add core/templates/conftest.py
git commit -m "feat(email-report): add --email pytest flag + SMTP send in conftest template"
```

---

### Task 2: Propagate conftest changes to active project

**Files:**
- Modify: `temp_workspace/ResGate/conftest.py` (mirror Task 1 changes)

The template is the source of truth. Active projects get a copy — apply the same changes.

- [ ] **Step 1: Apply identical edits to `temp_workspace/ResGate/conftest.py`**

Repeat all four edits from Task 1 Steps 1–4 on `temp_workspace/ResGate/conftest.py`.

- [ ] **Step 2: Verify**

```bash
python -c "import ast; ast.parse(open('temp_workspace/ResGate/conftest.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add temp_workspace/ResGate/conftest.py
git commit -m "feat(email-report): propagate --email hook to ResGate project conftest"
```

---

### Task 3: Update `agent_ui.py` — cmd flag + UI checkbox

**Files:**
- Modify: `core/agent_ui.py:71-84` — `pytest_headed_cmd`
- Modify: `core/agent_ui.py:2031-2037` — Run Tests tab (add checkbox above Run All button)
- Modify: `core/agent_ui.py:3076` — call site passes `email` flag

**Interfaces:**
- Consumes: `pytest_headed_cmd(project, run_dir, target, email)` — `email: bool = False`
- Produces: checkbox state in `st.session_state["email_report"]`; `--email` appended to cmd when True

- [ ] **Step 1: Update `pytest_headed_cmd` signature**

Replace lines 71–84 in `core/agent_ui.py`:

```python
def pytest_headed_cmd(project: str, run_dir: Path, target: str | None = None, email: bool = False) -> list[str]:
    """Build the pytest --headed command writing HTML+Allure into run_dir.
    target is relative to the project dir (e.g. 'test/test_login.py')."""
    cmd = [
        sys.executable, "-m", "pytest", "-v", "--headed",
        f"--html={run_dir / 'report.html'}",
        "--self-contained-html",
        f"--alluredir={run_dir / 'allure-results'}",
    ]
    if email:
        cmd.append("--email")
    if target:
        cmd.append(target)
    else:
        cmd.append("test")
    return cmd
```

- [ ] **Step 2: Add email checkbox to Run Tests tab**

Find lines 2031–2037 in `core/agent_ui.py` (the `runner-actions` div with Run All button). Add the checkbox **before** the `runner-actions` div:

```python
    # Email report checkbox — persisted in session state across runs
    email_after_run = st.checkbox(
        "📧 Email report after run",
        value=st.session_state.get("email_report", False),
        key="email_report",
        help="Sends story_coverage.html + report.html via SMTP. Requires email_config.json in project root.",
    )

    st.markdown('<div class="runner-actions">', unsafe_allow_html=True)
    cols = st.columns([1, 5])
    with cols[0]:
        if st.button("▶▶ Run All", key=f"runall_{story_id}", type="primary",
                     use_container_width=True, help="Run every test for this story (headed)"):
            clicked = "all"
    st.markdown('</div>', unsafe_allow_html=True)

    return clicked
```

Note: `email_after_run` is read via `st.session_state["email_report"]` at the call site — Streamlit checkbox key and session state key are the same.

- [ ] **Step 3: Pass email flag at pytest call site**

Find line ~3076 in `core/agent_ui.py`:

```python
cmd = pytest_headed_cmd(project, run_dir, target)
```

Replace with:

```python
email_flag = st.session_state.get("email_report", False)
cmd = pytest_headed_cmd(project, run_dir, target, email=email_flag)
```

- [ ] **Step 4: Verify agent_ui.py parses**

```bash
python -c "import ast; ast.parse(open('core/agent_ui.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add core/agent_ui.py
git commit -m "feat(email-report): add email checkbox to Run Tests tab + --email flag in pytest cmd"
```

---

### Task 4: Add email_config.json template + gitignore entry

**Files:**
- Create: `email_config.example.json` (repo root — committed as reference)
- Modify: `.gitignore` — ignore `email_config.json` everywhere

- [ ] **Step 1: Create example config**

Create `email_config.example.json` at repo root:

```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "sender@example.com",
  "smtp_password": "your-app-password-here",
  "from": "QE Agent <sender@example.com>",
  "to": ["team@example.com", "manager@example.com"],
  "subject_prefix": "[QE Agent]"
}
```

- [ ] **Step 2: Add gitignore entry**

Open `.gitignore` (repo root). Add:

```
# Email report credentials — never commit
email_config.json
**/email_config.json
```

- [ ] **Step 3: Commit**

```bash
git add email_config.example.json .gitignore
git commit -m "chore(email-report): add email_config example + gitignore entry"
```

---

### Task 5: Smoke test end-to-end

**Goal:** Verify `--email` flag is accepted by pytest, config-missing path warns cleanly, and Streamlit checkbox appears without crash.

- [ ] **Step 1: Verify pytest accepts --email without config**

```bash
cd temp_workspace/ResGate
pytest test/test_researcher_login.py --collect-only --email
```

Expected: collection output + `[email-report] email_config.json not found` warning printed. No crash, exit code 0 or 4 (collection only).

- [ ] **Step 2: Verify --email with a dummy config sends (or fails gracefully)**

Create `temp_workspace/ResGate/email_config.json` with invalid SMTP credentials:

```json
{
  "smtp_host": "smtp.example.invalid",
  "smtp_port": 587,
  "smtp_user": "test@example.com",
  "smtp_password": "wrong",
  "from": "test@example.com",
  "to": ["dev@example.com"]
}
```

Run one test with `--email`:

```bash
cd temp_workspace/ResGate
pytest test/test_researcher_login.py --email -v 2>&1 | tail -20
```

Expected: test runs normally, then `[email-report] Failed to send email: ...` warning printed. pytest exit code reflects test result only (0 = pass, 1 = fail) — NOT affected by email failure.

- [ ] **Step 3: Start Streamlit and verify checkbox renders**

```bash
cd core
streamlit run agent_ui.py
```

Open `http://localhost:8501`. Navigate to Run Tests tab. Verify `📧 Email report after run` checkbox is visible above the Run All button. No Python errors in terminal.

- [ ] **Step 4: Remove dummy email_config.json**

```bash
del temp_workspace\ResGate\email_config.json
```

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "test(email-report): smoke test verified, dummy config removed"
```

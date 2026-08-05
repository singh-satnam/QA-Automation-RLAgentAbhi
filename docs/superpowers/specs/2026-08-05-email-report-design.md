# Email Report Feature — Design Spec

**Date:** 2026-08-05
**Status:** Approved

## Summary

After a test run, if `--email` is passed to pytest, the conftest sends both
`story_coverage.html` and `report.html` to the recipients defined in the
project-level `email_config.json`. A checkbox in the Streamlit Run Tests tab
appends `--email` to the pytest command automatically.

---

## 1. email_config.json (per project)

Location: `<project_root>/email_config.json`

```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "sender@example.com",
  "smtp_password": "app-password-here",
  "from": "QE Agent <sender@example.com>",
  "to": ["team@example.com", "manager@example.com"],
  "subject_prefix": "[QE Agent]"
}
```

- `smtp_port` 587 = STARTTLS (default); 465 = SSL
- `subject_prefix` optional, defaults to `[QE Agent]`
- File is gitignored — edit any time, read fresh each run
- Missing file + `--email` = warning logged, run continues unaffected

---

## 2. conftest.py changes (core/templates/conftest.py)

### pytest_addoption

```python
def pytest_addoption(parser):
    parser.addoption(
        "--email", action="store_true", default=False,
        help="Email run reports after test session completes",
    )
```

### pytest_sessionfinish

Fires after all tests complete:

1. Check `session.config.getoption("--email")` — return early if False
2. Read `email_config.json` from project root (sibling of `conftest.py`)
3. Read verdict + counts from `report/<run_ts>/story_coverage.json`
4. Build multipart email (plain text body + HTML body)
5. Attach `story_coverage.html` and `report.html` if they exist in `run_dir`
6. Send via `smtplib` — STARTTLS for port 587, SSL for port 465
7. Any failure logs a warning to stdout — never raises, never changes exit code

---

## 3. agent_ui.py changes

### pytest_headed_cmd signature

```python
def pytest_headed_cmd(project, run_dir, target=None, email=False):
    cmd = [...existing flags...]
    if email:
        cmd.append("--email")
    return cmd
```

### UI checkbox (Run Tests tab)

```python
email_flag = st.checkbox(
    "📧 Email report after run",
    value=st.session_state.get("email_report", False),
    help="Requires email_config.json in project root",
    key="email_report",
)
```

Call site passes `email=email_flag` to `pytest_headed_cmd`.

---

## 4. Email format

**Subject:**
`[QE Agent] <ProjectName> — <VERDICT> | <N> passed <M> failed — <YYYY-MM-DD HH:MM>`

**Body:**
```
Project:    <project name>
Verdict:    PASS / FAIL / PARTIAL
Ran:        <timestamp>

Results:    N passed · M failed · K skipped
Assertions: X captured · Y matched

Attachments:
  - story_coverage.html
  - report.html

-- QE Agent
```

**Attachments:** `story_coverage.html` + `report.html` from the run dir.
Missing files are skipped silently and noted in the body.

---

## Error handling

| Condition | Behaviour |
|---|---|
| `email_config.json` missing | Warning to stdout, skip send |
| SMTP auth failure | Warning to stdout, skip send |
| Report file missing | Skip that attachment, note in body |
| Any exception | Caught, logged as warning, exit code unchanged |

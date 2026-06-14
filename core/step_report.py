"""Pure rendering of the per-step Test-results report (no Streamlit).

Consumes a list of step records (the new step_trace.json schema) produced by the
generated conftest's pytest-bdd hooks. Kept dependency-free so it is unit-testable
in isolation, mirroring core/workspace.py.
"""

from __future__ import annotations

import html as _html


def _esc(value) -> str:
    return _html.escape("" if value is None else str(value), quote=True)


def step_summary(steps: list[dict]) -> dict:
    """Aggregate counts across every step in the run."""
    tests = {s.get("test") for s in steps if s.get("test")}
    return {
        "tests": len(tests),
        "passed": sum(1 for s in steps if s.get("status") == "passed"),
        "failed": sum(1 for s in steps if s.get("status") == "failed"),
        "skipped": sum(1 for s in steps if s.get("status") == "skipped"),
        "total_steps": len(steps),
    }


# status -> (marker, css class, label)
_STATUS_META = {
    "passed":  ("✓", "stp-pass", "PASS"),   # green tick
    "failed":  ("✗", "stp-fail", "FAIL"),   # red cross
    "skipped": ("⊘", "stp-skip", "SKIP"),   # dark-blue circle-slash
}

STEP_REPORT_CSS = """
.sr-section{margin-top:1.5rem}
.sr-cards{display:flex;gap:0.75rem;flex-wrap:wrap;margin:0.5rem 0 1rem}
.sr-card{flex:1;min-width:120px;border:1px solid #e2e8f0;border-radius:10px;
  padding:0.75rem 1rem;background:#f8fafc;text-align:center}
.sr-card .sr-num{font-size:1.6rem;font-weight:700;color:#0f172a}
.sr-card .sr-lbl{font-size:0.8rem;color:#475569}
.sr-card.sr-pass .sr-num{color:#16a34a}
.sr-card.sr-fail .sr-num{color:#dc2626}
.sr-card.sr-skip .sr-num{color:#1e3a8a}
.sr-filters{margin:0.5rem 0}
.sr-fbtn{border:1px solid #cbd5e1;background:#fff;border-radius:6px;
  padding:0.25rem 0.7rem;margin-right:0.4rem;cursor:pointer;font-size:0.85rem}
.sr-fbtn.active{background:#0f172a;color:#fff;border-color:#0f172a}
.sr-table{width:100%;border-collapse:collapse;font-size:0.9rem}
.sr-table th,.sr-table td{border-bottom:1px solid #eef2f7;padding:0.4rem 0.6rem;
  text-align:left;vertical-align:top}
.sr-table .sr-i{color:#94a3b8;width:2rem}
.sr-table .sr-kw{font-weight:600;color:#334155;white-space:nowrap}
.sr-pill{display:inline-block;border-radius:999px;padding:0.1rem 0.55rem;
  font-size:0.78rem;font-weight:700;white-space:nowrap}
.sr-pill.stp-pass{background:#dcfce7;color:#16a34a}
.sr-pill.stp-fail{background:#fee2e2;color:#dc2626}
.sr-pill.stp-skip{background:#dbeafe;color:#1e3a8a}
.sr-gtitle{margin-top:1.25rem;font-size:1rem;color:#dc2626}
.sr-gallery{display:flex;flex-direction:column;gap:0.75rem}
.sr-fcard{border:1px solid #fecaca;border-radius:10px;overflow:hidden}
.sr-fhead{background:#fef2f2;color:#991b1b;font-weight:600;padding:0.5rem 0.75rem}
.sr-fbody{display:flex;gap:0.75rem;padding:0.75rem;align-items:flex-start}
.sr-shot{max-width:360px;border:1px solid #e2e8f0;border-radius:6px}
.sr-noshot{color:#94a3b8;font-style:italic;padding:1rem;border:1px dashed #e2e8f0;
  border-radius:6px}
.sr-err{flex:1;margin:0;background:#0f172a;color:#e2e8f0;border-radius:6px;
  padding:0.6rem;font-size:0.8rem;white-space:pre-wrap;overflow:auto}
"""

_FILTER_SCRIPT = (
    "<script>function srFilter(b){"
    "var f=b.getAttribute('data-f');"
    "var btns=b.parentNode.querySelectorAll('.sr-fbtn');"
    "btns.forEach(function(x){x.classList.remove('active')});"
    "b.classList.add('active');"
    "document.querySelectorAll('.sr-row').forEach(function(r){"
    "var show=(f=='all')||r.classList.contains('stp-'+f.slice(0,4));"
    "r.style.display=show?'':'none';});}</script>"
)


def render_step_report(steps: list[dict], img_resolver=None) -> str:
    """Return the Template-C report section (summary cards + filterable status
    table + failure gallery). `img_resolver(rel_path) -> data-uri-or-empty` inlines
    failure screenshots; pass None to skip image embedding."""
    if not steps:
        return ""
    summ = step_summary(steps)

    cards = (
        '<div class="sr-cards">'
        f'<div class="sr-card"><div class="sr-num">{summ["tests"]}</div>'
        '<div class="sr-lbl">Tests ran</div></div>'
        f'<div class="sr-card sr-pass"><div class="sr-num">{summ["passed"]}</div>'
        '<div class="sr-lbl">Passed steps</div></div>'
        f'<div class="sr-card sr-fail"><div class="sr-num">{summ["failed"]}</div>'
        '<div class="sr-lbl">Failed steps</div></div>'
        f'<div class="sr-card sr-skip"><div class="sr-num">{summ["skipped"]}</div>'
        '<div class="sr-lbl">Skipped steps</div></div>'
        '</div>'
    )

    rows = []
    for i, s in enumerate(steps, start=1):
        mark, cls, lbl = _STATUS_META.get(s.get("status", ""), ("—", "", ""))
        rows.append(
            f'<tr class="sr-row {cls}">'
            f'<td class="sr-i">{i}</td>'
            f'<td class="sr-test">{_esc(s.get("test", ""))}</td>'
            f'<td class="sr-kw">{_esc(s.get("keyword", ""))}</td>'
            f'<td>{_esc(s.get("name", ""))}</td>'
            f'<td><span class="sr-pill {cls}">{mark} {lbl}</span></td>'
            '</tr>'
        )
    table = (
        '<div class="sr-filters">'
        '<button class="sr-fbtn active" data-f="all" onclick="srFilter(this)">All</button>'
        '<button class="sr-fbtn" data-f="failed" onclick="srFilter(this)">Failed</button>'
        '<button class="sr-fbtn" data-f="skipped" onclick="srFilter(this)">Skipped</button>'
        '</div>'
        '<table class="sr-table"><thead><tr>'
        '<th>#</th><th>Test</th><th>Keyword</th><th>Step</th><th>Status</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table>'
    )

    failures = [s for s in steps if s.get("status") == "failed"]
    gallery = ""
    if failures:
        fcards = []
        for s in failures:
            uri = img_resolver(s.get("screenshot", "")) if img_resolver else ""
            shot = (
                f'<a href="{uri}" target="_blank">'
                f'<img class="sr-shot" src="{uri}" alt="failure screenshot"></a>'
                if uri else '<div class="sr-noshot">(no screenshot)</div>'
            )
            err = _esc(s.get("error", "")) or "(no error captured)"
            fcards.append(
                '<div class="sr-fcard">'
                f'<div class="sr-fhead">✗ {_esc(s.get("test", ""))} · '
                f'{_esc(s.get("keyword", ""))} {_esc(s.get("name", ""))}</div>'
                f'<div class="sr-fbody">{shot}<pre class="sr-err">{err}</pre></div>'
                '</div>'
            )
        gallery = (
            f'<h3 class="sr-gtitle">Failures ({len(failures)})</h3>'
            f'<div class="sr-gallery">{"".join(fcards)}</div>'
        )

    return (
        '<section class="sr-section"><h2>Step-by-step results</h2>'
        f'{cards}{table}{gallery}{_FILTER_SCRIPT}</section>'
    )

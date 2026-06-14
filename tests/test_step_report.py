import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
import step_report  # noqa: E402

SAMPLE = [
    {"test": "test_a", "feature": "a.feature", "index": 1, "keyword": "Given",
     "name": "login", "status": "passed"},
    {"test": "test_a", "feature": "a.feature", "index": 2, "keyword": "Then",
     "name": "created", "status": "failed",
     "error": "AssertionError: boom\nline2\nline3", "screenshot": "screenshots/x.png"},
    {"test": "test_a", "feature": "a.feature", "index": 3, "keyword": "And",
     "name": "appears", "status": "skipped"},
    {"test": "test_b", "feature": "b.feature", "index": 1, "keyword": "Given",
     "name": "open", "status": "passed"},
]


def test_step_summary_counts_and_distinct_tests():
    s = step_report.step_summary(SAMPLE)
    assert s["tests"] == 2
    assert s["passed"] == 2
    assert s["failed"] == 1
    assert s["skipped"] == 1
    assert s["total_steps"] == 4


def test_step_summary_empty():
    s = step_report.step_summary([])
    assert s == {"tests": 0, "passed": 0, "failed": 0, "skipped": 0, "total_steps": 0}


def test_render_empty_returns_empty_string():
    assert step_report.render_step_report([]) == ""


def test_render_includes_summary_table_and_failure_gallery():
    html = step_report.render_step_report(
        SAMPLE, img_resolver=lambda p: "data:image/png;base64,Zm9v" if p else "")
    assert "Tests ran" in html and "Passed steps" in html
    assert html.count('class="sr-row') == 4          # one row per step
    assert "Failures (1)" in html                    # one failed step
    assert "AssertionError: boom" in html            # error text shown
    assert 'data-f="failed"' in html                 # filter button present
    assert "stp-fail" in html and "stp-skip" in html  # status classes


def test_render_failed_step_without_screenshot_shows_placeholder():
    html = step_report.render_step_report(SAMPLE, img_resolver=lambda p: "")
    assert "(no screenshot)" in html

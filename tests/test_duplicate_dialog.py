import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

import agent_ui


def test_generate_anyway_persists_override_and_force():
    eff = agent_ui.duplicate_dialog_next("generate_anyway")
    assert eff["set"] == {"dup_override": True, "force_gherkin": True}
    assert eff["clear"] == ["pending_dup"]
    assert eff["rerun"] is True


def test_cancel_clears_pending_only():
    eff = agent_ui.duplicate_dialog_next("cancel")
    assert eff["set"] == {}
    assert eff["clear"] == ["pending_dup"]
    assert eff["rerun"] is True


def test_view_existing_is_noop_keeps_dialog():
    eff = agent_ui.duplicate_dialog_next("view_existing")
    assert eff["set"] == {}
    assert eff["clear"] == []
    assert eff["rerun"] is False


def test_none_choice_is_noop():
    eff = agent_ui.duplicate_dialog_next(None)
    assert eff == {"set": {}, "clear": [], "rerun": False}

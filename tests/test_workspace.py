import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
import workspace  # noqa: E402
import pytest  # noqa: E402


def test_derive_project_name_takes_prefix_before_first_underscore():
    assert workspace.derive_project_name("RLRG_login.txt") == "RLRG"
    assert workspace.derive_project_name("saucedemo_checkout_flow.txt") == "saucedemo"
    assert workspace.derive_project_name("caedu_a_b_c.txt") == "caedu"  # only first '_'


def test_derive_project_name_rejects_missing_prefix():
    with pytest.raises(workspace.ProjectNameError):
        workspace.derive_project_name("login.txt")


def test_sanitize_filename_forces_txt_and_strips_unsafe_chars():
    assert workspace.sanitize_filename("RLRG login flow") == "RLRG_login_flow.txt"
    assert workspace.sanitize_filename("RLRG_login.txt") == "RLRG_login.txt"
    with pytest.raises(workspace.ProjectNameError):
        workspace.sanitize_filename("   ")


def test_ensure_project_dirs_creates_all_canonical_subfolders(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    pd = workspace.ensure_project_dirs("RLRG")
    assert pd == tmp_path / "RLRG"
    for sub in workspace.PROJECT_SUBDIRS:
        assert (pd / sub).is_dir()


def test_ensure_project_dirs_is_idempotent_and_non_destructive(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    keep = tmp_path / "RLRG" / "feature" / "keep.feature"
    keep.write_text("Feature: keep", encoding="utf-8")
    workspace.ensure_project_dirs("RLRG")  # second call must not wipe
    assert keep.exists()


def test_add_story_writes_new_and_refuses_duplicate(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    created, path = workspace.add_story("RLRG", "RLRG_login.txt", "story body")
    assert created is True
    assert path.read_text(encoding="utf-8") == "story body"
    assert workspace.story_exists("RLRG", "RLRG_login.txt") is True
    created2, path2 = workspace.add_story("RLRG", "RLRG_login.txt", "DIFFERENT")
    assert created2 is False
    assert path2.read_text(encoding="utf-8") == "story body"


def test_list_projects_and_stories(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.add_story("RLRG", "RLRG_a.txt", "a")
    workspace.add_story("RLRG", "RLRG_b.txt", "b")
    workspace.add_story("saucedemo", "saucedemo_x.txt", "x")
    assert workspace.list_projects() == ["RLRG", "saucedemo"]
    names = [p.name for p in workspace.list_stories("RLRG")]
    assert names == ["RLRG_a.txt", "RLRG_b.txt"]


def test_extract_base_url():
    assert workspace.extract_base_url("go to https://saucedemo.com/login now") == "https://saucedemo.com/login"
    assert workspace.extract_base_url("no url here") == ""


def test_write_pytest_ini_sets_base_url_and_testpaths(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    ini = workspace.write_pytest_ini("RLRG", "https://saucedemo.com")
    text = ini.read_text(encoding="utf-8")
    assert "base_url = https://saucedemo.com" in text
    assert "testpaths = test" in text
    workspace.write_pytest_ini("RLRG", "https://other.com")
    text2 = ini.read_text(encoding="utf-8")
    assert text2.count("base_url =") == 1
    assert "https://other.com" in text2


def test_new_report_run_dir_is_unique_and_listed_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    d1 = workspace.new_report_run_dir("RLRG", run_id="2026-06-13_10-00-00")
    d2 = workspace.new_report_run_dir("RLRG", run_id="2026-06-13_11-00-00")
    assert d1.is_dir() and d2.is_dir()
    runs = workspace.report_runs("RLRG")
    assert [r.name for r in runs] == ["2026-06-13_11-00-00", "2026-06-13_10-00-00"]


def test_report_runs_empty_when_none(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    assert workspace.report_runs("RLRG") == []


def test_rebuild_reuse_index_maps_page_methods_steps_and_selectors(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    pd = tmp_path / "RLRG"
    (pd / "pages" / "page_login.py").write_text(
        "class LoginPage:\n"
        "    def open(self): ...\n"
        "    def submit_credentials(self): ...\n"
        "    def _private(self): ...\n",
        encoding="utf-8",
    )
    (pd / "step_defs" / "login_steps.py").write_text(
        "def given_user_on_login(): ...\n", encoding="utf-8",
    )
    (pd / "mcp-selectors" / "locators.json").write_text(
        '{"login_button": "#login", "username": "#user"}', encoding="utf-8",
    )
    idx = workspace.rebuild_reuse_index("RLRG")
    assert idx["page_methods"]["open"] == "page_login.py"
    assert idx["page_methods"]["submit_credentials"] == "page_login.py"
    assert "_private" not in idx["page_methods"]
    assert idx["step_defs"]["given_user_on_login"] == "login_steps.py"
    assert idx["selectors"]["login_button"] == "locators.json"
    loaded = workspace.load_reuse_index("RLRG")
    assert loaded == idx


def test_load_reuse_index_default_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    idx = workspace.load_reuse_index("RLRG")
    assert idx == {"page_methods": {}, "step_defs": {}, "selectors": {}, "flows": {}}


def test_project_dir_staging_resolves_to_temp_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    assert workspace.project_dir("RLRG") == tmp_path / "workspace" / "RLRG"
    assert workspace.project_dir("RLRG", staging=True) == tmp_path / "temp_workspace" / "RLRG"


def test_ensure_project_dirs_staging_creates_in_temp(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    pd = workspace.ensure_project_dirs("RLRG", staging=True)
    assert pd == tmp_path / "temp_workspace" / "RLRG"
    for sub in workspace.PROJECT_SUBDIRS:
        assert (pd / sub).is_dir()
    assert not (tmp_path / "workspace" / "RLRG").exists()


def test_add_story_staging_writes_to_temp(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    created, path = workspace.add_story("RLRG", "RLRG_login.txt", "story body", staging=True)
    assert created is True
    assert "temp_workspace" in str(path)
    assert path.read_text(encoding="utf-8") == "story body"
    assert not (tmp_path / "workspace" / "RLRG" / "user_story" / "RLRG_login.txt").exists()


def test_story_exists_staging_checks_temp(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    workspace.add_story("RLRG", "RLRG_login.txt", "body", staging=True)
    assert workspace.story_exists("RLRG", "RLRG_login.txt", staging=True) is True
    assert workspace.story_exists("RLRG", "RLRG_login.txt", staging=False) is False


def test_copy_scaffolding_staging(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    written = workspace.copy_scaffolding("RLRG", staging=True)
    assert len(written) > 0
    assert (tmp_path / "temp_workspace" / "RLRG" / "conftest.py").exists()
    assert not (tmp_path / "workspace" / "RLRG" / "conftest.py").exists()


def test_write_pytest_ini_staging(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    workspace.ensure_project_dirs("RLRG", staging=True)
    ini = workspace.write_pytest_ini("RLRG", "https://example.com", staging=True)
    assert "temp_workspace" in str(ini)
    assert ini.exists()
    assert "base_url = https://example.com" in ini.read_text(encoding="utf-8")


def test_is_staged_detects_temp_workspace_content(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    assert workspace.is_staged("RLRG") is False
    workspace.add_story("RLRG", "RLRG_login.txt", "body", staging=True)
    assert workspace.is_staged("RLRG") is True


def test_is_staged_false_for_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    (tmp_path / "temp_workspace" / "RLRG").mkdir(parents=True)
    assert workspace.is_staged("RLRG") is False


def test_promote_to_workspace_additive_merge(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    # Create a file in workspace that already exists
    workspace.ensure_project_dirs("RLRG", staging=False)
    (tmp_path / "workspace" / "RLRG" / "pages" / "page_login.py").write_text("existing", encoding="utf-8")
    # Create staging files — one overlapping, one new
    workspace.ensure_project_dirs("RLRG", staging=True)
    (tmp_path / "temp_workspace" / "RLRG" / "pages" / "page_login.py").write_text("staged", encoding="utf-8")
    (tmp_path / "temp_workspace" / "RLRG" / "pages" / "page_dashboard.py").write_text("new", encoding="utf-8")
    (tmp_path / "temp_workspace" / "RLRG" / "feature" / "login.feature").write_text("Feature: login", encoding="utf-8")
    result = workspace.promote_to_workspace("RLRG")
    # page_login.py was skipped (already exists), page_dashboard.py and login.feature were copied
    assert "pages/page_dashboard.py" in result["copied"]
    assert "feature/login.feature" in result["copied"]
    assert "pages/page_login.py" in result["skipped"]
    assert result["failed"] == []
    # Workspace file was NOT overwritten
    assert (tmp_path / "workspace" / "RLRG" / "pages" / "page_login.py").read_text(encoding="utf-8") == "existing"
    # New file was copied
    assert (tmp_path / "workspace" / "RLRG" / "pages" / "page_dashboard.py").read_text(encoding="utf-8") == "new"
    # Staging folder is gone
    assert not (tmp_path / "temp_workspace" / "RLRG").exists()


def test_promote_creates_workspace_dirs_if_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    workspace.ensure_project_dirs("RLRG", staging=True)
    (tmp_path / "temp_workspace" / "RLRG" / "feature" / "login.feature").write_text("Feature: login", encoding="utf-8")
    result = workspace.promote_to_workspace("RLRG")
    assert "feature/login.feature" in result["copied"]
    assert (tmp_path / "workspace" / "RLRG" / "feature" / "login.feature").exists()


def test_discard_staging_removes_temp_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    workspace.add_story("RLRG", "RLRG_login.txt", "body", staging=True)
    assert workspace.is_staged("RLRG") is True
    workspace.discard_staging("RLRG")
    assert workspace.is_staged("RLRG") is False
    assert not (tmp_path / "temp_workspace" / "RLRG").exists()


def test_list_staged_projects(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    workspace.add_story("RLRG", "RLRG_a.txt", "a", staging=True)
    workspace.add_story("saucedemo", "saucedemo_x.txt", "x", staging=True)
    assert workspace.list_staged_projects() == ["RLRG", "saucedemo"]


def test_list_projects_includes_staging(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    workspace.add_story("RLRG", "RLRG_a.txt", "a", staging=False)
    workspace.add_story("NewProj", "NewProj_b.txt", "b", staging=True)
    projects = workspace.list_projects()
    assert "RLRG" in projects
    assert "NewProj" in projects


def test_list_stories_includes_staging(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    workspace.add_story("RLRG", "RLRG_a.txt", "a", staging=False)
    workspace.add_story("RLRG", "RLRG_b.txt", "b", staging=True)
    stories = workspace.list_stories("RLRG")
    names = [p.name for p in stories]
    assert "RLRG_a.txt" in names
    assert "RLRG_b.txt" in names


def test_promote_to_workspace_failed_key_present(tmp_path, monkeypatch):
    """promote_to_workspace result always contains a 'failed' key."""
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    workspace.ensure_project_dirs("RLRG", staging=True)
    (tmp_path / "temp_workspace" / "RLRG" / "feature" / "login.feature").write_text("Feature: login", encoding="utf-8")
    result = workspace.promote_to_workspace("RLRG")
    assert "failed" in result
    assert result["failed"] == []


def test_staging_file_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    workspace.ensure_project_dirs("RLRG", staging=True)
    pd = tmp_path / "temp_workspace" / "RLRG"
    (pd / "feature" / "login.feature").write_text("Feature: login", encoding="utf-8")
    (pd / "feature" / "signup.feature").write_text("Feature: signup", encoding="utf-8")
    (pd / "pages" / "page_login.py").write_text("class LoginPage: ...", encoding="utf-8")
    summary = workspace.staging_file_summary("RLRG")
    assert summary["feature"] == 2
    assert summary["pages"] == 1

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
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
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


# ---------------------------------------------------------------------------
# Duplicate story detection
# ---------------------------------------------------------------------------

STORY_LOGIN_LAUNCH = """\
Navigate to the login page "https://example.com/login"
Enter valid credentials:
  Email: user@example.com
  Password: Pass@123
Click on the Sign In button
Verify landing on the "My Projects" page
Click on the "Automation Testing" project
Verify the "Automation Testing" page is displayed
Click on the My Products tab
Verify "Demo-RD-001" is available
Click on "Demo-RD-001"
Click on "Remote Desktop" under "CONNECT"
Verify a new browser tab is opened
"""

STORY_LOGIN_STOP = """\
Navigate to the login page "https://example.com/login"
Enter valid credentials:
  Email: user@example.com
  Password: Pass@123
Click on the Sign In button
Verify landing on the "My Projects" page
Click on the "Automation Testing" project
Verify the "Automation Testing" page is displayed
Click on the "My Products" tab
Verify "Demo-RD-001" is available
Click on "Demo-RD-001"
Verify the product details page is displayed
Click on "Stop" under "CONNECT"
Verify the stop process initiated successfully
Verify the "Start" option is available under "CONNECT"
Click on the refresh button to update status
Verify the instance status changes to "Stopped"
"""

STORY_COMPLETELY_DIFFERENT = """\
Navigate to the admin dashboard "https://example.com/admin"
Click on the "Users" section
Search for user "john@example.com"
Verify user details are displayed
Delete the user
Verify the user is removed from the list
"""

STORY_EXACT_DUPLICATE = """\
Navigate to the login page "https://example.com/login"
Enter valid credentials:
  Email: user@example.com
  Password: Pass@123
Click on the Sign In button
Verify landing on the "My Projects" page
Click on the "Automation Testing" project
Verify the "Automation Testing" page is displayed
Click on the My Products tab
Verify "Demo-RD-001" is available
Click on "Demo-RD-001"
Click on "Remote Desktop" under "CONNECT"
Verify a new browser tab is opened
"""


def test_extract_action_lines_filters_and_normalises():
    lines = workspace._extract_action_lines(STORY_LOGIN_LAUNCH)
    assert len(lines) > 0
    assert all(isinstance(l, str) for l in lines)
    assert all(l == l.lower() for l in lines)
    for line in lines:
        assert "https://" not in line


def test_extract_action_lines_skips_comments_and_short_lines():
    text = "# this is a comment\nHello\nClick on the Sign In button\n"
    lines = workspace._extract_action_lines(text)
    assert len(lines) == 1
    assert "sign in" in lines[0]


def test_extract_action_lines_empty_input():
    assert workspace._extract_action_lines("") == []
    assert workspace._extract_action_lines("# only comments\n") == []


def test_step_similarity_identical_stories():
    lines = workspace._extract_action_lines(STORY_LOGIN_LAUNCH)
    ratio = workspace._step_similarity(lines, lines)
    assert ratio == 1.0


def test_step_similarity_completely_different():
    lines_a = workspace._extract_action_lines(STORY_LOGIN_LAUNCH)
    lines_b = workspace._extract_action_lines(STORY_COMPLETELY_DIFFERENT)
    ratio = workspace._step_similarity(lines_a, lines_b)
    assert ratio < 0.50


def test_step_similarity_partial_overlap():
    lines_a = workspace._extract_action_lines(STORY_LOGIN_LAUNCH)
    lines_b = workspace._extract_action_lines(STORY_LOGIN_STOP)
    ratio = workspace._step_similarity(lines_a, lines_b)
    assert 0.50 <= ratio < 1.0


def test_step_similarity_empty_input():
    assert workspace._step_similarity([], ["click sign in"]) == 0.0
    assert workspace._step_similarity(["click sign in"], []) == 0.0
    assert workspace._step_similarity([], []) == 0.0


def test_matching_steps_returns_common_steps():
    lines_a = workspace._extract_action_lines(STORY_LOGIN_LAUNCH)
    lines_b = workspace._extract_action_lines(STORY_LOGIN_STOP)
    matched = workspace._matching_steps(lines_a, lines_b)
    assert len(matched) > 0
    assert len(matched) < len(lines_a)


def test_new_steps_returns_delta():
    lines_new = workspace._extract_action_lines(STORY_LOGIN_STOP)
    lines_existing = workspace._extract_action_lines(STORY_LOGIN_LAUNCH)
    delta = workspace._new_steps(lines_new, lines_existing)
    assert len(delta) > 0
    assert any("stop" in s for s in delta)


def test_new_steps_empty_when_identical():
    lines = workspace._extract_action_lines(STORY_LOGIN_LAUNCH)
    delta = workspace._new_steps(lines, lines)
    assert delta == []


def _setup_project(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path)
    workspace.ensure_project_dirs("RLRG")
    return tmp_path / "RLRG"


def test_check_duplicate_story_full_match(tmp_path, monkeypatch):
    pd = _setup_project(tmp_path, monkeypatch)
    (pd / "user_story" / "RLRG_login_launch.txt").write_text(
        STORY_LOGIN_LAUNCH, encoding="utf-8")
    (pd / "user_story" / "RLRG_login_launch_v2.txt").write_text(
        STORY_EXACT_DUPLICATE, encoding="utf-8")
    (pd / "feature" / "login_launch.feature").write_text(
        "Feature: Login and Launch\n  Scenario: Login\n    Given something",
        encoding="utf-8")

    result = workspace.check_duplicate_story("RLRG", "RLRG_login_launch_v2.txt")
    assert result is not None
    assert result["match_type"] == "full"
    assert result["ratio"] >= 0.80
    assert result["matched_story_file"] == "RLRG_login_launch.txt"
    assert len(result["matching_steps"]) > 0
    assert result["feature_content"] != ""


def test_check_duplicate_story_partial_match(tmp_path, monkeypatch):
    pd = _setup_project(tmp_path, monkeypatch)
    (pd / "user_story" / "RLRG_login_launch.txt").write_text(
        STORY_LOGIN_LAUNCH, encoding="utf-8")
    (pd / "user_story" / "RLRG_login_stop.txt").write_text(
        STORY_LOGIN_STOP, encoding="utf-8")

    result = workspace.check_duplicate_story("RLRG", "RLRG_login_stop.txt")
    assert result is not None
    assert result["match_type"] == "partial"
    assert 0.50 <= result["ratio"] < 0.80
    assert len(result["new_steps"]) > 0


def test_check_duplicate_story_no_match(tmp_path, monkeypatch):
    pd = _setup_project(tmp_path, monkeypatch)
    (pd / "user_story" / "RLRG_login_launch.txt").write_text(
        STORY_LOGIN_LAUNCH, encoding="utf-8")
    (pd / "user_story" / "RLRG_admin.txt").write_text(
        STORY_COMPLETELY_DIFFERENT, encoding="utf-8")

    result = workspace.check_duplicate_story("RLRG", "RLRG_admin.txt")
    assert result is None


def test_check_duplicate_story_single_story(tmp_path, monkeypatch):
    pd = _setup_project(tmp_path, monkeypatch)
    (pd / "user_story" / "RLRG_login.txt").write_text(
        STORY_LOGIN_LAUNCH, encoding="utf-8")

    result = workspace.check_duplicate_story("RLRG", "RLRG_login.txt")
    assert result is None


def test_check_duplicate_story_nonexistent_file(tmp_path, monkeypatch):
    _setup_project(tmp_path, monkeypatch)
    result = workspace.check_duplicate_story("RLRG", "RLRG_nonexistent.txt")
    assert result is None


def test_check_duplicate_story_finds_feature_file(tmp_path, monkeypatch):
    pd = _setup_project(tmp_path, monkeypatch)
    (pd / "user_story" / "RLRG_login_launch.txt").write_text(
        STORY_LOGIN_LAUNCH, encoding="utf-8")
    (pd / "user_story" / "RLRG_login_dup.txt").write_text(
        STORY_EXACT_DUPLICATE, encoding="utf-8")
    feature_text = "Feature: Login\n  Scenario: Login flow\n    Given the user logs in"
    (pd / "feature" / "login_launch.feature").write_text(
        feature_text, encoding="utf-8")

    result = workspace.check_duplicate_story("RLRG", "RLRG_login_dup.txt")
    assert result is not None
    assert result["feature_file"] is not None
    assert result["feature_file"].name == "login_launch.feature"
    assert result["feature_content"] == feature_text


def test_check_duplicate_story_no_feature_file(tmp_path, monkeypatch):
    pd = _setup_project(tmp_path, monkeypatch)
    (pd / "user_story" / "RLRG_login_launch.txt").write_text(
        STORY_LOGIN_LAUNCH, encoding="utf-8")
    (pd / "user_story" / "RLRG_login_dup.txt").write_text(
        STORY_EXACT_DUPLICATE, encoding="utf-8")

    result = workspace.check_duplicate_story("RLRG", "RLRG_login_dup.txt")
    assert result is not None
    assert result["feature_content"] == ""


def test_check_duplicate_story_staging(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    workspace.ensure_project_dirs("RLRG", staging=True)
    pd = tmp_path / "temp_workspace" / "RLRG"
    (pd / "user_story" / "RLRG_login_launch.txt").write_text(
        STORY_LOGIN_LAUNCH, encoding="utf-8")
    (pd / "user_story" / "RLRG_login_dup.txt").write_text(
        STORY_EXACT_DUPLICATE, encoding="utf-8")

    result = workspace.check_duplicate_story("RLRG", "RLRG_login_dup.txt", staging=True)
    assert result is not None
    assert result["match_type"] == "full"


def test_check_duplicate_story_across_workspace_and_staging(tmp_path, monkeypatch):
    """New story in staging should detect duplicate in workspace (same project)."""
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(workspace, "TEMP_WORKSPACE_DIR", tmp_path / "temp_workspace")
    # Existing story in workspace
    workspace.ensure_project_dirs("RLRG", staging=False)
    ws_pd = tmp_path / "workspace" / "RLRG"
    (ws_pd / "user_story" / "RLRG_login.txt").write_text(
        STORY_LOGIN_LAUNCH, encoding="utf-8")
    (ws_pd / "feature" / "login.feature").write_text(
        "Feature: Login\n  Scenario: Login\n    Given something",
        encoding="utf-8")
    # New story in staging (same project)
    workspace.ensure_project_dirs("RLRG", staging=True)
    stg_pd = tmp_path / "temp_workspace" / "RLRG"
    (stg_pd / "user_story" / "RLRG_login_v2.txt").write_text(
        STORY_EXACT_DUPLICATE, encoding="utf-8")

    result = workspace.check_duplicate_story("RLRG", "RLRG_login_v2.txt", staging=True)
    assert result is not None
    assert result["match_type"] == "full"
    assert result["matched_story_file"] == "RLRG_login.txt"
    assert result["feature_content"] != ""

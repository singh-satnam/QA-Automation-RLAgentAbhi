from pytest_bdd import when, then

from pages.page_common import MyProjectsPage
from pages.page_project_creation import CreateProjectPage
from pages.page_project_details import ProjectDetailsPage


@when("the user ensures the Use Project Storage checkbox is unchecked")
def ensure_storage_unchecked(page, captured_values):
    cap = captured_values
    CreateProjectPage(page).ensure_storage_unchecked()
    cap.add("Use Project Storage checkbox", "unchecked")



@when("the user searches for the project using the project name from the test data")
def search_project_in_table(page, captured_values, scenario_context):
    cap = captured_values
    project_name = scenario_context.get("project_name", "")
    MyProjectsPage(page).search_project_in_table(project_name)
    cap.add("Searched project name", project_name)


@when("the user clicks on the matching project link")
def click_project_link_in_table(page, captured_values, scenario_context):
    cap = captured_values
    project_name = scenario_context.get("project_name", "")
    MyProjectsPage(page).click_project_link_in_table(project_name)
    ProjectDetailsPage(page).wait_for_page()
    cap.assert_prerequisite(
        "Project details page loaded after table click",
        condition="/project-details/" in page.url,
        reason=f"Expected URL to contain /project-details/, got: {page.url}",
        evidence=page.url,
    )


@then("the following options are present on the Project Details tab")
def verify_project_details_options(page, datatable, captured_values):
    cap = captured_values
    details = ProjectDetailsPage(page)
    for row in datatable[1:]:
        field_name = row[0]
        is_visible = details.is_field_visible(field_name)
        passed = cap.assert_match(
            f"Option '{field_name}' present on Project Details tab",
            expected=field_name,
            actual=field_name if is_visible else "(not found)",
        )
        assert passed, f"Field '{field_name}' not visible on Project Details tab"


@when("the user clicks the Archive option")
def click_archive_option(page, captured_values):
    cap = captured_values
    ProjectDetailsPage(page).click_action_button("Archive")
    cap.add("Archive option clicked", "true")


@then("the Archive project pop up is displayed")
def verify_archive_dialog_visible(page, captured_values):
    cap = captured_values
    details = ProjectDetailsPage(page)
    visible = details.is_archive_dialog_visible()
    cap.add("Archive dialog visible", str(visible))
    assert visible, "Archive project dialog not displayed"


@when("the user clicks the available check box in the Archive pop up")
def click_archive_checkbox(page, captured_values):
    cap = captured_values
    ProjectDetailsPage(page).click_archive_dialog_checkbox()
    cap.add("Archive dialog checkbox", "checked")


@when("the user clicks the Archive button")
def click_archive_button(page, captured_values):
    cap = captured_values
    ProjectDetailsPage(page).click_archive_dialog_button()
    cap.add("Archive button clicked", "true")


@then('a confirmation pop up is displayed on the top right with a message containing "Archiving project started"')
def verify_archive_toast(page, captured_values):
    cap = captured_values
    details = ProjectDetailsPage(page)
    toast_text = details.get_archive_toast_message()
    cap.add("Archive toast message", toast_text)
    passed = cap.assert_match(
        "Archive confirmation toast displayed",
        expected="Archiving project started",
        actual=toast_text,
    )
    assert passed or "Archiving project started" in toast_text, (
        f"Expected toast containing 'Archiving project started', got: {toast_text!r}"
    )

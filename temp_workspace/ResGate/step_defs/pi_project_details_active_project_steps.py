from playwright.sync_api import expect
from pytest_bdd import when, then

from pages.page_project_details import ProjectDetailsPage


@when("the user searches for a project card with an Active button")
def search_active_project_card(page, captured_values):
    cap = captured_values
    active_badge = page.locator("span.status-text:has-text('Active')").first
    expect(active_badge).to_be_visible(timeout=10000)
    cap.add("Active project card found", "true")


@when("the user clicks the Active button on the project card")
def click_active_button(page, captured_values):
    cap = captured_values
    page.locator("span.status-text:has-text('Active')").first.click()
    cap.add("Active button clicked", "true")


@then("the project details page is displayed")
def verify_project_details_page(page, captured_values):
    cap = captured_values
    ProjectDetailsPage(page).wait_for_page()
    cap.assert_prerequisite(
        "Project details page loaded",
        condition="/project-details/" in page.url,
        reason=f"Expected URL to contain /project-details/, got: {page.url}",
        evidence=page.url,
    )
    cap.add("Project details URL", page.url)


@then("the following tabs are displayed on the page")
def verify_tabs_displayed(page, datatable, captured_values):
    cap = captured_values
    details = ProjectDetailsPage(page)
    visible_tabs = details.get_visible_tabs()
    cap.add("Visible tabs", str(visible_tabs))
    for row in datatable[1:]:  # skip header row
        tab_name = row[0]
        found = any(tab_name in t for t in visible_tabs)
        passed = cap.assert_match(
            f"Tab '{tab_name}' displayed",
            expected=tab_name,
            actual=tab_name if found else "(not found)",
        )
        assert passed, f"Tab '{tab_name}' not in visible tabs: {visible_tabs}"


@when("the user clicks the Project Details tab")
def click_project_details_tab(page, captured_values):
    cap = captured_values
    ProjectDetailsPage(page).click_tab("Project Details")
    cap.add("Project Details tab clicked", "true")


@then("the following fields are displayed and have a value")
def verify_fields_displayed(page, datatable, captured_values):
    cap = captured_values
    details = ProjectDetailsPage(page)
    for row in datatable[1:]:  # skip header row
        field_name = row[0]
        is_visible = details.is_field_visible(field_name)
        passed = cap.assert_match(
            f"Field '{field_name}' displayed",
            expected=field_name,
            actual=field_name if is_visible else "(not found)",
        )
        assert passed, f"Field '{field_name}' not visible on Project Details tab"


@then("the Actions section is displayed on the right side of the page")
def verify_actions_section(page, captured_values):
    cap = captured_values
    details = ProjectDetailsPage(page)
    visible = details.is_actions_section_visible()
    cap.add("Actions section visible", str(visible))
    assert visible, "ACTIONS section not visible on project details page"


@then("the following options are displayed under Actions")
def verify_action_options(page, datatable, captured_values):
    cap = captured_values
    details = ProjectDetailsPage(page)
    for row in datatable[1:]:  # skip header row
        option = row[0]
        visible = details.is_action_button_visible(option)
        passed = cap.assert_match(
            f"Action option '{option}' displayed",
            expected=option,
            actual=option if visible else "(not found)",
        )
        assert passed, f"Action button '{option}' not visible in Actions section"

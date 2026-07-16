from pytest_bdd import when, then, parsers
from pages.page_common import MyProjectsPage
from pages.page_pi_project_creation_no_catalog import ProjectCreationPage

_FIELD_DISPATCH = {
    "Project Name": "fill_project_name",
    "Project Description": "fill_project_description",
    "Budget Available": "fill_budget",
}


@then('the PI lands on the "My Projects" page successfully')
def pi_lands_on_my_projects(page, captured_values):
    my_projects_page = MyProjectsPage(page)
    heading_text = my_projects_page.get_heading_text()
    captured_values.add("Page heading after login", heading_text)
    passed = captured_values.assert_match(
        "My Projects page displayed",
        expected="My Projects",
        actual=heading_text,
    )
    assert passed, (
        f"Expected heading 'My Projects' but got {heading_text!r}. "
        f"Current URL: {page.url}"
    )


@when('the user clicks the "Add New" button')
def click_add_new_button(page, captured_values):
    my_projects_page = MyProjectsPage(page)
    my_projects_page.click_add_new()
    captured_values.add("Add New button clicked", "true")


@then('the "Create Project" page is displayed')
def create_project_page_is_displayed(page, captured_values):
    project_page = ProjectCreationPage(page)
    is_displayed = project_page.is_displayed()
    captured_values.add("Create Project page displayed", str(is_displayed))
    captured_values.assert_prerequisite(
        "Create Project page loaded",
        condition=is_displayed,
        reason="Create Project page heading not visible",
        evidence=f"url={page.url}",
    )


@when(parsers.parse('the user fills in "{field}" with "{value}"'))
def fill_field_with_value(page, captured_values, field, value):
    project_page = ProjectCreationPage(page)
    method_name = _FIELD_DISPATCH.get(field)
    if method_name is None:
        pytest_fail_msg = f"Unknown field '{field}' — no POM method mapped"
        captured_values.add(f"Fill {field}", f"ERROR: {pytest_fail_msg}")
        raise AssertionError(pytest_fail_msg)
    getattr(project_page, method_name)(value)
    captured_values.add(f"Filled {field}", value)


@when(parsers.parse('the user selects account "{account_name}" from the list'))
def select_account_from_list(page, captured_values, account_name):
    project_page = ProjectCreationPage(page)
    project_page.select_account(account_name)
    captured_values.add("Account selected", account_name)


@when('the user clicks the "Create Project" button')
def click_create_project_button(page, captured_values):
    project_page = ProjectCreationPage(page)
    project_page.click_create_project()
    captured_values.add("Create Project button clicked", "true")


@then(parsers.parse('the user is taken to the "{page_name}" page'))
def user_is_taken_to_page(page, captured_values, page_name):
    my_projects_page = MyProjectsPage(page)
    heading_text = my_projects_page.get_heading_text()
    captured_values.add("Page heading after creation", heading_text)
    passed = captured_values.assert_match(
        f"Redirected to {page_name} page",
        expected=page_name,
        actual=heading_text,
    )
    assert passed, (
        f"Expected page '{page_name}' but got heading {heading_text!r}. "
        f"Current URL: {page.url}"
    )


@then(parsers.parse('a new project with name "{project_name}" is displayed'))
def new_project_with_name_displayed(page, captured_values, project_name):
    my_projects_page = MyProjectsPage(page)
    found = my_projects_page.find_project_by_name(project_name)
    captured_values.add("Expected project name", project_name)
    passed = captured_values.assert_match(
        "New project visible in My Projects",
        expected=True,
        actual=found,
    )
    assert passed, (
        f"Project '{project_name}' not found in My Projects. "
        f"Current URL: {page.url}"
    )

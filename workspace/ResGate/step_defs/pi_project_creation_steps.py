from pytest_bdd import when, then, parsers
from pages.page_common import MyProjectsPage
from pages.page_project_creation import ProjectCreationPage

_FIELD_TO_KEY = {
    "Project Name": "projectName",
    "Project Description": "projectDescription",
    "Budget Available": "budgetAvailable",
}

_CATALOG_TYPE_TO_KEY = {
    "Create standard catalog": "Select Create standard catalog type from the list",
    "Bring your own catalog": "Select Bring your own catalog type from the list",
}


@when('the user clicks the "Add New" button')
def click_add_new_button(page, captured_values):
    project_page = ProjectCreationPage(page)
    project_page.click_add_new()
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


@when(parsers.parse('the user fills in "{field}" from the test data'))
def fill_field_from_test_data(page, test_data, captured_values, run_id, field):
    project_page = ProjectCreationPage(page)
    user_data = test_data.get("PI_Project_Creation", {})
    key = _FIELD_TO_KEY.get(field, field)
    value = user_data.get(key, "")
    if field == "Project Name":
        value = f"{value}{run_id}"
    dispatch = {
        "Project Name": project_page.fill_project_name,
        "Project Description": project_page.fill_project_description,
        "Budget Available": project_page.fill_budget,
    }
    dispatch.get(field, project_page.fill_project_name)(value)
    captured_values.add(f"Filled {field}", value)


@when("the user selects an account from the list using the test data")
def select_account_from_test_data(page, test_data, captured_values):
    project_page = ProjectCreationPage(page)
    user_data = test_data.get("PI_Project_Creation", {})
    account_name = user_data.get("Select an account from the list", "")
    project_page.select_account(account_name)
    captured_values.add("Account selected", account_name)


@when("the user selects a user from the list using the test data")
def select_user_from_test_data(page, test_data, captured_values):
    project_page = ProjectCreationPage(page)
    user_data = test_data.get("PI_Project_Creation", {})
    user_label = user_data.get("Select users from the list", "")
    project_page.select_user(user_label)
    captured_values.add("User selected", user_label)


@when(parsers.parse('the user selects "{catalog_type}" type from the list using the test data'))
def select_catalog_type_from_test_data(page, test_data, captured_values, catalog_type):
    project_page = ProjectCreationPage(page)
    user_data = test_data.get("PI_Project_Creation", {})
    key = _CATALOG_TYPE_TO_KEY.get(catalog_type, "")
    label_text = user_data.get(key, "")
    project_page.select_catalog_type(label_text)
    captured_values.add(f"Catalog type selected ({catalog_type})", label_text)


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
        f"{page_name} page displayed after creation",
        expected=page_name,
        actual=heading_text,
    )
    assert passed, (
        f"Expected '{page_name}' heading but got {heading_text!r}. "
        f"Current URL: {page.url}"
    )


@then('a new project with name matching "Project Name" from the test data is displayed')
def new_project_displayed(page, test_data, captured_values, run_id):
    my_projects_page = MyProjectsPage(page)
    user_data = test_data.get("PI_Project_Creation", {})
    project_name = f"{user_data.get('projectName', '')}{run_id}"
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

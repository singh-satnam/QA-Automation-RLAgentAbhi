from pytest_bdd import when, then

from pages.page_common import MyProjectsPage
from pages.page_project_creation import CreateProjectPage
from utils import unique_suffix


@when("the user clicks the Add New button")
def click_add_new(page, captured_values):
    cap = captured_values
    my_projects = MyProjectsPage(page)
    my_projects.click_add_new()
    cap.add("Add New clicked", "true")


@then("the Create Project page is displayed")
def verify_create_project_page(page, captured_values):
    cap = captured_values
    create_pg = CreateProjectPage(page)
    create_pg.wait_for_page()
    cap.assert_prerequisite(
        "Create Project page loaded",
        condition="/addProject" in page.url,
        reason=f"Expected URL to contain /addProject, got: {page.url}",
        evidence=page.url,
    )


@when("the user fills in the Project Name from the test data")
def fill_project_name(page, test_data, captured_values, scenario_context):
    cap = captured_values
    name = f"{test_data['projectName']} {unique_suffix()}"
    scenario_context["project_name"] = name
    CreateProjectPage(page).fill_project_name(name)
    cap.add("Project Name", name)


@when("the user fills in the Project Description from the test data")
def fill_project_description(page, test_data, captured_values):
    cap = captured_values
    desc = test_data["projectDescription"]
    CreateProjectPage(page).fill_project_description(desc)
    cap.add("Project Description", desc)


@when("the user fills in the Budget Available from the test data")
def fill_budget(page, test_data, captured_values):
    cap = captured_values
    budget = test_data["budgetAvailable"]
    CreateProjectPage(page).fill_budget(budget)
    cap.add("Budget Available", budget)


@when("the user selects an account from the test data")
def select_account(page, test_data, captured_values):
    cap = captured_values
    account = test_data["Select an account from the list"]
    CreateProjectPage(page).select_account(account)
    cap.add("Account selected", account)


@when("the user selects a user from the test data")
def select_user(page, test_data, captured_values):
    cap = captured_values
    user = test_data["Select users from the list"]
    CreateProjectPage(page).select_user(user)
    cap.add("User selected", user)


@when("the user selects the Create standard catalog type from the test data")
def select_standard_catalog(page, test_data, captured_values):
    cap = captured_values
    catalog = test_data["Select Create standard catalog type from the list"]
    CreateProjectPage(page).select_catalog_type(catalog)
    cap.add("Standard catalog selected", catalog)


@when("the user selects the Bring your own catalog type from the test data")
def select_byoc_catalog(page, test_data, captured_values):
    cap = captured_values
    catalog = test_data["Select Bring your own catalog type from the list"]
    CreateProjectPage(page).select_catalog_type(catalog)
    cap.add("BYOC catalog selected", catalog)


@when("the user ensures the Use Project Storage checkbox is unchecked")
def ensure_storage_unchecked(page, captured_values):
    cap = captured_values
    CreateProjectPage(page).ensure_storage_unchecked()
    cap.add("Use Project Storage checkbox", "unchecked")


@when("the user clicks the Create Project button")
def click_create_project(page, captured_values):
    cap = captured_values
    CreateProjectPage(page).click_create_project()
    cap.add("Create Project clicked", "true")


@then("the user is taken to the My Projects page")
def verify_redirected_to_my_projects(page, captured_values):
    cap = captured_values
    MyProjectsPage(page).wait_for_pi_page()
    cap.assert_prerequisite(
        "Redirected to My Projects after creation",
        condition="/principal" in page.url,
        reason=f"Expected URL to contain /principal, got: {page.url}",
        evidence=page.url,
    )


@then("the new project with the project name from the test data is displayed")
def verify_new_project_visible(page, test_data, captured_values, scenario_context):
    cap = captured_values
    project_name = scenario_context.get("project_name", test_data["projectName"])
    my_projects = MyProjectsPage(page)
    my_projects.wait_for_project_visible(project_name)
    project_names = my_projects.get_project_names()
    cap.add("Project names on page", str(project_names))
    found = project_name in project_names
    passed = cap.assert_match(
        "New project visible in My Projects",
        expected=project_name,
        actual=project_name if found else "(not found)",
    )
    assert passed, f"Project {project_name!r} not in project list: {project_names}"

from pytest_bdd import given, when, then

from pages.page_common import LoginPage, MyProjectsPage


@given("the user is on the Research Gateway login page")
def navigate_to_login(page, base_url, test_data, captured_values):
    cap = captured_values
    url = base_url or test_data.get("URL", "")
    login = LoginPage(page)
    login.navigate(url)
    cap.add("Login page URL", url)


@when("the user signs in as a Researcher")
def sign_in_as_researcher(page, test_data, captured_values):
    cap = captured_values
    email = test_data["RES_USER"]
    password = test_data["RES_PWD"]
    login = LoginPage(page)
    login.enter_email(email)
    login.enter_password(password)
    cap.add("RES email entered", email)


@given("the user clicks Sign In")
@when("the user clicks Sign In")
def click_sign_in(page, captured_values):
    cap = captured_values
    login = LoginPage(page)
    login.click_sign_in()
    cap.add("Sign In action", "clicked")


@then("the researcher lands on the My Projects page with only their assigned projects displayed")
def verify_my_projects_page(page, captured_values):
    cap = captured_values
    my_projects = MyProjectsPage(page)

    my_projects.wait_for_page()

    cap.assert_prerequisite(
        "Researcher My Projects page",
        condition="/researcher" in page.url,
        reason=f"Expected URL to contain /researcher, got: {page.url}",
        evidence=page.url,
    )

    breadcrumb_text = my_projects.get_breadcrumb_text()
    cap.add("Breadcrumb text", breadcrumb_text)
    assert cap.assert_match(
        "My Projects page title displayed",
        expected="My Projects",
        actual=breadcrumb_text,
    ), f"Expected 'My Projects' in breadcrumb, got: {breadcrumb_text!r}"

    project_count = my_projects.get_project_count()
    cap.add("Assigned project count", project_count)

    for name in my_projects.get_project_names():
        cap.add_component("Assigned project", name, group="researcher_projects")

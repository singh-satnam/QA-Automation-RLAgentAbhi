from pytest_bdd import when, then

from pages.page_common import LoginPage, MyProjectsPage


@when("the user signs in as a PI")
def sign_in_as_pi(page, test_data, captured_values):
    cap = captured_values
    email = test_data["PI_USER"]
    password = test_data["PI_PWD"]
    login = LoginPage(page)
    login.enter_email(email)
    login.enter_password(password)
    cap.add("PI email entered", email)


@then("the PI lands on the My Projects page successfully")
def verify_pi_my_projects_page(page, captured_values):
    cap = captured_values
    my_projects = MyProjectsPage(page)

    my_projects.wait_for_pi_page()

    cap.assert_prerequisite(
        "PI My Projects page",
        condition="/principal" in page.url,
        reason=f"Expected URL to contain /principal, got: {page.url}",
        evidence=page.url,
    )

    breadcrumb_text = my_projects.get_breadcrumb_text()
    cap.add("Breadcrumb text", breadcrumb_text)
    assert cap.assert_match(
        "My Projects page title displayed",
        expected="My Projects",
        actual=breadcrumb_text,
    ), f"Expected 'My Projects' in breadcrumb, got: {breadcrumb_text!r}"

    project_count = my_projects.get_pi_project_count()
    cap.add("PI project count", project_count)

    for name in my_projects.get_project_names():
        cap.add_component("PI project", name, group="pi_projects")

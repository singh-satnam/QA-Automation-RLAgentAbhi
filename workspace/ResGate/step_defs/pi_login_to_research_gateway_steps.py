from pytest_bdd import given, then
from pages.page_common import LoginPage, MyProjectsPage


@given("the user navigates to the Research Gateway login page")
def navigate_to_login_page(page, test_data, captured_values):
    login_url = test_data.get("config", {}).get("login_url") or ""
    login_page = LoginPage(page)
    login_page.navigate(login_url)
    login_page.dismiss_session_expired_alert()
    captured_values.add("Login URL", login_url)
    captured_values.assert_prerequisite(
        "Login page loaded",
        condition=login_page.is_visible(login_page.loc["login"]["email_input"], timeout=15000),
        reason="Email input not visible — login page did not load",
        evidence=f"url={page.url}",
    )


@given("the user clicks the Sign In button")
def click_sign_in_button(page, captured_values):
    login_page = LoginPage(page)
    login_page.click_sign_in()
    error_text = login_page.get_error_text()
    captured_values.add("Sign-in server response", error_text or "<none>")
    captured_values.assert_prerequisite(
        "Sign In accepted",
        condition=not error_text,
        reason=f"Login rejected — server returned: {error_text or '<unknown error>'}",
        evidence=f"url={page.url}",
    )


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

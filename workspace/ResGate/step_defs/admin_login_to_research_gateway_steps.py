import pytest
from pytest_bdd import given, when, then
from pages.page_common import LoginPage, MyOrganizationsPage


@given("the Research Gateway login page is open")
def open_login_page(page, test_data, captured_values):
    login_url = test_data["config"]["login_url"]
    login_page = LoginPage(page)
    login_page.navigate(login_url)
    login_page.dismiss_session_expired_alert()
    captured_values.add("Login URL", login_url)
    cap = captured_values
    cap.assert_prerequisite(
        "Login page loaded",
        condition=login_page.is_visible(login_page.loc["login"]["email_input"], timeout=15000),
        reason="Email input not visible — login page did not load",
        evidence=f"url={page.url}",
    )


@when("the admin enters valid admin credentials")
def admin_enters_credentials(page, credentials, captured_values):
    creds = credentials.get("admin", {})
    login_page = LoginPage(page)
    login_page.enter_email(creds["email"])
    login_page.enter_password(creds["password"])
    captured_values.add("Admin email used", creds["email"])


@when("the admin clicks Sign In")
def admin_clicks_sign_in(page, captured_values):
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


@then("the admin lands on the My Organizations page")
def admin_lands_on_my_organizations(page, captured_values):
    orgs_page = MyOrganizationsPage(page)
    heading_text = orgs_page.get_heading_text()
    captured_values.add("Page heading after login", heading_text)
    passed = captured_values.assert_match(
        "My Organizations page displayed",
        expected="My Organizations",
        actual=heading_text,
    )
    assert passed, (
        f"Expected heading 'My Organizations' but got {heading_text!r}. "
        f"Current URL: {page.url}"
    )

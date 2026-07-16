from pytest_bdd import given, when, then, parsers
from pages.page_common import LoginPage, HeaderNavPage, LogoutPage


@given("the user opens the RG login page")
def open_rg_login_page(page, test_data, captured_values):
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


@when("the user clicks Sign In")
def click_sign_in(page, captured_values):
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


@when("the user clicks the user name in the header")
def click_user_name_in_header(page, captured_values):
    header_nav = HeaderNavPage(page)
    header_nav.click_user_menu()
    captured_values.add("User menu opened", "true")


@when("the user clicks Sign Out")
def click_sign_out(page, captured_values):
    header_nav = HeaderNavPage(page)
    header_nav.click_sign_out()
    captured_values.add("Sign Out clicked", "true")


@then(parsers.parse('the user is redirected to the login screen with button "{button_text}"'))
def verify_redirected_to_logout_screen(page, captured_values, button_text):
    logout_page = LogoutPage(page)
    is_displayed = logout_page.is_displayed()
    actual_url = page.url
    captured_values.add("Post-logout URL", actual_url)
    actual_btn_text = logout_page.get_button_text() if is_displayed else ""
    captured_values.add("Logout page button text", actual_btn_text)
    passed = captured_values.assert_match(
        "Logout page displayed with expected button",
        expected=button_text.lower(),
        actual=actual_btn_text.lower(),
    )
    assert passed, (
        f"Expected logout screen button '{button_text}' but got '{actual_btn_text}'. "
        f"Current URL: {actual_url}"
    )

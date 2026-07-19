from pytest_bdd import when, then

from pages.page_common import HeaderNav, LogoutPage


@when("the user clicks the username in the header")
def click_username_in_header(page, captured_values):
    cap = captured_values
    header = HeaderNav(page)
    header.click_username_in_header()
    cap.add("Username menu", "clicked")


@when("the user clicks Sign Out")
def click_sign_out(page, captured_values):
    cap = captured_values
    header = HeaderNav(page)
    header.click_sign_out()
    cap.add("Sign Out action", "clicked")


@then('the user is redirected to the login screen with the "Click here to Login" button')
def verify_redirected_to_login_screen(page, captured_values):
    cap = captured_values
    logout_page = LogoutPage(page)

    logout_page.wait_for_page()

    cap.assert_prerequisite(
        "Redirected to logout screen",
        condition="/logout" in page.url,
        reason=f"Expected URL to contain /logout, got: {page.url}",
        evidence=page.url,
    )

    is_visible = logout_page.is_login_button_visible()
    cap.add("Click here to login button visible", is_visible)
    assert cap.assert_match(
        "Click here to login button displayed",
        expected=True,
        actual=is_visible,
    ), "Expected 'Click here to login' button to be visible on logout screen"

from playwright.sync_api import expect
from pytest_bdd import given, parsers, when, then

from pages.page_common import LoginPage, MyProjectsPage, HeaderNav, LogoutPage
from pages.page_project_details import ProjectDetailsPage


@when(parsers.re(r'the user searches for the project card "(?P<project_name>[^"]+)" and clicks on it'))
def search_and_click_project_card(page, captured_values, project_name):
    cap = captured_values
    mp = MyProjectsPage(page)
    mp.wait_for_project_visible(project_name, timeout=15000)
    mp.click_project(project_name)
    cap.add("Project card clicked", project_name)


@then(parsers.re(r'the "(?P<user_name>[^"]+)" user checkbox is unchecked'))
def ensure_user_checkbox_unchecked(page, captured_values, user_name):
    cap = captured_values
    details = ProjectDetailsPage(page)
    is_checked = details.is_user_checkbox_checked(user_name)
    if is_checked:
        details.click_user_checkbox_by_name(user_name)
        page.wait_for_timeout(500)
        cap.add(f"'{user_name}' checkbox was checked — unchecked to reset", "true")
    else:
        cap.add(f"'{user_name}' checkbox already unchecked", "true")
    assert not details.is_user_checkbox_checked(user_name), \
        f"'{user_name}' checkbox still checked after reset attempt"


@when(parsers.re(r'the user selects the "(?P<user_name>[^"]+)" user checkbox and clicks the Update button'))
def select_user_and_update(page, captured_values, user_name):
    cap = captured_values
    details = ProjectDetailsPage(page)
    details.click_user_checkbox_by_name(user_name)
    cap.add(f"'{user_name}' checkbox selected", "true")
    details.click_update_assigned_users()
    cap.add("Update button clicked", "true")
    details.wait_for_success_toast()
    details.wait_for_toast_gone()


@then(parsers.re(r'the Assigned Users section displays "(?P<user_name>[^"]+)"'))
def verify_assigned_user_displayed(page, captured_values, user_name):
    cap = captured_values
    details = ProjectDetailsPage(page)
    is_assigned = details.is_user_assigned(user_name)
    cap.add(f"'{user_name}' shown in Assigned Users", str(is_assigned))
    passed = cap.assert_match(
        f"Assigned Users displays '{user_name}'",
        expected="True",
        actual=str(is_assigned),
    )
    assert passed, f"Expected '{user_name}' to appear in Assigned Users section"


@when("the user clicks the username on the top right and selects Sign out")
def click_username_and_sign_out(page, test_data, captured_values):
    cap = captured_values
    header = HeaderNav(page)
    header.click_username_in_header()
    header.click_sign_out()
    # If interstitial "Click here to login" button is absent, navigate directly to login URL
    login_btn = page.locator("button:has-text('Click here to login')")
    try:
        login_btn.wait_for(state="visible", timeout=5000)
        login_btn.click()
    except Exception:
        url = test_data.get("URL", "")
        LoginPage(page).navigate(url)
    cap.add("Sign out", "clicked")


@given("the user signs in as a RESPRJ")
@when("the user signs in as a RESPRJ")
def sign_in_as_resprj(page, test_data, captured_values):
    cap = captured_values
    email = test_data["RESPRJ_USER"]
    password = test_data["RESPRJ_PWD"]
    login = LoginPage(page)
    login.enter_email(email)
    login.enter_password(password)
    cap.add("RESPRJ email entered", email)


@when("the user signs in as a RESBOT")
def sign_in_as_resbot(page, test_data, captured_values):
    cap = captured_values
    email = test_data["RESBOT_USER"]
    password = test_data["RESBOT_PWD"]
    login = LoginPage(page)
    login.enter_email(email)
    login.enter_password(password)
    cap.add("RESBOT email entered", email)


@then("the user lands on the My Projects page successfully")
def verify_user_lands_on_my_projects(page, captured_values):
    cap = captured_values
    page.wait_for_selector(
        "h1:has-text('My Projects'), h3:has-text('My Projects')",
        timeout=20000,
    )
    cap.assert_prerequisite(
        "My Projects page loaded",
        condition="/researcher" in page.url or "/principal" in page.url,
        reason=f"Expected researcher or principal URL, got: {page.url}",
        evidence=page.url,
    )
    cap.add("My Projects URL", page.url)


@then(parsers.re(r'the project card "(?P<project_name>[^"]+)" is displayed'))
def verify_project_card_displayed(page, captured_values, project_name):
    cap = captured_values
    card = page.locator(f"h3:has-text('{project_name}')").first
    expect(card).to_be_visible(timeout=10000)
    cap.add(f"Project card '{project_name}' visible", "true")
    passed = cap.assert_match(
        f"Project card '{project_name}' displayed",
        expected=project_name,
        actual=project_name,
    )
    assert passed


@then(parsers.re(r'the "(?P<user_name>[^"]+)" user checkbox is selected'))
def verify_user_checkbox_selected(page, captured_values, user_name):
    cap = captured_values
    details = ProjectDetailsPage(page)
    is_checked = details.is_user_checkbox_checked(user_name)
    cap.add(f"'{user_name}' checkbox checked", str(is_checked))
    passed = cap.assert_match(
        f"'{user_name}' checkbox is selected",
        expected="True",
        actual=str(is_checked),
    )
    assert passed, f"Expected '{user_name}' checkbox to be checked but it was unchecked"


@when(parsers.re(r'the user deselects the "(?P<user_name>[^"]+)" user checkbox and clicks the Update button'))
def deselect_user_and_update(page, captured_values, user_name):
    cap = captured_values
    details = ProjectDetailsPage(page)
    details.click_user_checkbox_by_name(user_name)
    cap.add(f"'{user_name}' checkbox deselected", "true")
    details.click_update_assigned_users()
    cap.add("Update button clicked", "true")
    details.wait_for_success_toast()
    details.wait_for_toast_gone()


@then(parsers.re(r'the project card "(?P<project_name>[^"]+)" is not displayed'))
def verify_project_card_not_displayed(page, captured_values, project_name):
    cap = captured_values
    page.wait_for_timeout(2000)
    cards = page.locator(f"h3:has-text('{project_name}')").all()
    visible = [c for c in cards if c.is_visible()]
    cap.add(f"Project card '{project_name}' visible count", str(len(visible)))
    passed = cap.assert_match(
        f"Project card '{project_name}' not displayed",
        expected="0",
        actual=str(len(visible)),
    )
    assert passed, f"Expected '{project_name}' card to NOT be visible but found {len(visible)}"

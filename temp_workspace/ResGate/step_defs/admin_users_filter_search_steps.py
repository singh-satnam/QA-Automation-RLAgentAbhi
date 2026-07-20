from pytest_bdd import given, when, then, parsers

from pages.page_common import LoginPage, HeaderNav
from pages.page_users import UsersPage


@given("the user is on the ResGate login page")
def navigate_to_resgate_login(page, base_url, test_data, captured_values):
    cap = captured_values
    url = base_url or test_data.get("URL", "")
    LoginPage(page).navigate(url)
    cap.add("Login page URL", url)


@when("the user signs in as an Admin")
def sign_in_as_admin_full(page, test_data, captured_values):
    cap = captured_values
    email = test_data["ADMIN_USER"]
    password = test_data["ADMIN_PWD"]
    login = LoginPage(page)
    login.enter_email(email)
    login.enter_password(password)
    login.click_sign_in()
    cap.add("Admin signed in", email)


@when(parsers.parse('the user clicks on the hamburger menu and selects "{nav_item}"'))
def click_hamburger_and_select(page, nav_item, captured_values):
    cap = captured_values
    page.wait_for_selector(
        "button[aria-label='Open navigation menu']", state="visible", timeout=15000
    )
    nav = HeaderNav(page)
    nav.click_hamburger_menu()
    page.wait_for_timeout(400)
    nav.click_nav_item(nav_item)
    page.wait_for_timeout(600)
    # Angular SPA may not reset component state on same-route navigation.
    # Explicitly clear the search input so subsequent filter steps start clean.
    search_inp = page.locator("input#searchKeyForUser")
    try:
        if search_inp.is_visible(timeout=2000):
            current_val = search_inp.input_value(timeout=1000)
            if current_val:
                search_inp.fill("")
                search_inp.dispatch_event("input")
                page.wait_for_timeout(500)
    except Exception:
        pass
    cap.add("Hamburger nav selected", nav_item)


@then("the Users page is displayed")
def verify_users_page_displayed(page, captured_values):
    cap = captured_values
    UsersPage(page).wait_for_page()
    cap.assert_prerequisite(
        "Users page loaded",
        condition="/users" in page.url,
        reason=f"Expected URL to contain /users, got: {page.url}",
        evidence=page.url,
    )
    cap.add("Users page URL", page.url)


@then("the search bar is present on the Users page")
def verify_search_bar_present(page, captured_values):
    cap = captured_values
    visible = UsersPage(page).is_search_bar_visible()
    cap.add("Search bar visible", str(visible))
    assert visible, "Search bar not visible on Users page"


@then(parsers.parse('the "{element_label}" button is present on the Users page'))
def verify_button_present(page, element_label, captured_values):
    cap = captured_values
    users_pg = UsersPage(page)
    if element_label == "Add New Select":
        visible = users_pg.is_add_new_visible()
    else:
        visible = users_pg.is_reset_filters_visible()
    cap.add(f'"{element_label}" button visible', str(visible))
    assert visible, f'"{element_label}" button not visible on Users page'


@then(parsers.parse('the "{filter_label}" filter option is present on the Users page'))
def verify_filter_option_present(page, filter_label, captured_values):
    cap = captured_values
    visible = UsersPage(page).is_filter_trigger_visible(filter_label)
    cap.add(f'"{filter_label}" filter option visible', str(visible))
    assert visible, f'"{filter_label}" filter option not visible on Users page'


@then(parsers.parse('the "{toggle_label}" toggle is present on the Users page'))
def verify_toggle_present(page, toggle_label, captured_values):
    cap = captured_values
    visible = UsersPage(page).is_toggle_visible()
    cap.add(f'"{toggle_label}" toggle visible', str(visible))
    assert visible, f'"{toggle_label}" toggle not visible on Users page'


@when(parsers.parse('the user searches for "{search_text}" in the search bar'))
def search_in_search_bar(page, search_text, captured_values):
    cap = captured_values
    UsersPage(page).search(search_text)
    cap.add("Search term entered", search_text)


@then(parsers.parse('users containing the text "{search_text}" are shown on the page'))
def verify_search_results(page, search_text, captured_values):
    cap = captured_values
    names = UsersPage(page).get_visible_user_names()
    cap.add("Visible user names after search", str(names))
    assert len(names) > 0, f"No users shown after searching for '{search_text}'"
    for name in names:
        assert search_text.lower() in name.lower(), (
            f"User '{name}' does not contain search text '{search_text}'"
        )


@when(parsers.parse('the user clicks on "{dropdown}" and selects "{option}"'))
def click_filter_and_select_option(page, dropdown, option, captured_values):
    cap = captured_values
    users_pg = UsersPage(page)
    users_pg.click_filter_dropdown(dropdown)
    users_pg.select_filter_option(option)
    cap.add(f'"{dropdown}" option selected', option)


@then(parsers.parse('"{expected_value}" is present in the results'))
def verify_value_in_org_results(page, expected_value, captured_values):
    cap = captured_values
    orgs = UsersPage(page).get_visible_user_orgs()
    cap.add("Visible user orgs after OU filter", str(orgs))
    assert len(orgs) > 0, f"No results shown after filtering by OU '{expected_value}'"
    assert all(expected_value in org for org in orgs), (
        f"Not all results contain '{expected_value}': {orgs}"
    )


@when('the user clicks the "Reset Filters" button')
def click_reset_filters_btn(page, captured_values):
    cap = captured_values
    UsersPage(page).click_reset_filters()
    cap.add("Reset Filters clicked", "true")


@then(parsers.parse('the results contain the text "{expected_text}"'))
def verify_results_contain_text(page, expected_text, captured_values):
    cap = captured_values
    roles = UsersPage(page).get_visible_user_roles()
    cap.add("Visible user roles after role filter", str(roles))
    assert len(roles) > 0, f"No results shown after filtering by role '{expected_text}'"
    assert all(expected_text in role for role in roles), (
        f"Not all results contain '{expected_text}': {roles}"
    )


@then("the results are updated")
def verify_results_updated(page, captured_values):
    cap = captured_values
    card_count = UsersPage(page).get_visible_card_count()
    cap.add("Card count after sort", card_count)
    assert card_count > 0, "No user cards visible after applying Sort By"


@when('the user clicks the "Active Users" toggle')
def click_active_users_toggle(page, captured_values):
    cap = captured_values
    UsersPage(page).click_active_users_toggle()
    cap.add("Active Users toggle clicked", "true")


@then('the results show only users with "Active" status')
def verify_only_active_users(page, captured_values):
    cap = captured_values
    statuses = UsersPage(page).get_visible_statuses()
    cap.add("Visible user statuses after toggle", str(statuses))
    assert len(statuses) > 0, "No users visible after toggling Active Users"
    assert all(s == "Active" for s in statuses), (
        f"Non-Active users found in results: {statuses}"
    )

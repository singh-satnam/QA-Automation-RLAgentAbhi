from pytest_bdd import when, then, parsers

from pages.page_common import MyOrganizationsPage, HeaderNav
from pages.page_org import CreateOrganizationPage
from pages.page_users import UsersPage


@then("the user is taken to the My Organizations page")
def verify_taken_to_my_organizations_page(page, captured_values):
    cap = captured_values
    orgs_page = MyOrganizationsPage(page)
    orgs_page.wait_for_page()
    cap.assert_prerequisite(
        "My Organizations page loaded",
        condition="/admin" in page.url,
        reason=f"Expected URL to contain /admin, got: {page.url}",
        evidence=page.url,
    )
    cap.add("My Organizations page URL", page.url)


@when("the user clicks the hamburger menu to display menu items")
def click_hamburger_menu_to_display(page, captured_values):
    cap = captured_values
    page.wait_for_selector(
        "button[aria-label='Open navigation menu']", state="visible", timeout=15000
    )
    HeaderNav(page).click_hamburger_menu()
    page.wait_for_timeout(400)
    cap.add("Hamburger menu opened", "true")


@when(parsers.parse('the user clicks on "{nav_item}"'))
def click_nav_item_in_menu(page, nav_item, captured_values):
    cap = captured_values
    HeaderNav(page).click_nav_item(nav_item)
    page.wait_for_timeout(600)
    cap.add("Nav item clicked", nav_item)


@when('the user clicks the "+ Add New" button and selects "Add New User"')
def click_add_new_and_select_add_user(page, captured_values):
    cap = captured_values
    UsersPage(page).click_add_new_user_option()
    cap.add("Add New User option selected", "true")


@then("the Add User popup is displayed")
def verify_add_user_popup_displayed(page, captured_values):
    cap = captured_values
    visible = CreateOrganizationPage(page).is_add_user_dialog_visible()
    cap.add("Add User popup visible", str(visible))
    assert visible, "Add User popup not visible"


@when("the user fills in the new user details")
def fill_new_user_details(page, test_data, captured_values, scenario_context):
    cap = captured_values
    email = test_data.get("ADD_USER_EMAIL", "auto_pw@yopmail.com")
    role = test_data.get("ADD_USER_ROLE", "Researcher")
    first_name = test_data.get("ADD_USER_FIRST_NAME", "Auto")
    last_name = test_data.get("ADD_USER_LAST_NAME", "skills")
    scenario_context["added_user_email"] = email
    add_user = CreateOrganizationPage(page)
    add_user.fill_new_user_email(email)
    add_user.select_new_user_role(role)
    add_user.fill_new_user_first_name(first_name)
    add_user.fill_new_user_last_name(last_name)
    cap.add("New user email", email)
    cap.add("New user role", role)
    cap.add("New user first name", first_name)
    cap.add("New user last name", last_name)


@when('the user clicks the "Add User" button')
def click_add_user_button(page, captured_values):
    cap = captured_values
    CreateOrganizationPage(page).click_add_user_in_dialog()
    page.wait_for_timeout(2000)
    cap.add("Add User button clicked", "true")


@when(parsers.parse('the user clicks in the Search bar and types "{email}" and presses Enter'))
def search_user_in_search_bar(page, email, captured_values, scenario_context):
    cap = captured_values
    search_email = scenario_context.get("added_user_email", email)
    UsersPage(page).search_and_submit(search_email)
    cap.add("User searched", search_email)


@then(parsers.parse('the user card for "{email}" is displayed'))
def verify_user_card_displayed(page, email, captured_values, scenario_context):
    cap = captured_values
    search_email = scenario_context.get("added_user_email", email)
    users_pg = UsersPage(page)
    users_pg.wait_for_user_card(search_email)
    visible = users_pg.is_user_card_visible(search_email)
    cap.add("User card visible for", search_email)
    assert visible, f"User card for '{search_email}' not visible"


@when("the user clicks the three-dot Actions menu on the user card")
def click_user_card_actions_menu(page, captured_values, scenario_context):
    cap = captured_values
    email = scenario_context.get("added_user_email", "")
    UsersPage(page).click_user_card_actions(email)
    cap.add("Actions menu clicked for", email)


@when('the user selects "Delete User"')
def select_delete_user_option(page, captured_values, scenario_context):
    cap = captured_values
    email = scenario_context.get("added_user_email", "")
    UsersPage(page).click_delete_user_option(email)
    cap.add("Delete User option selected for", email)


@then("the Delete User popup is displayed")
def verify_delete_user_popup_displayed(page, captured_values):
    cap = captured_values
    visible = UsersPage(page).is_delete_user_dialog_visible()
    cap.add("Delete User popup visible", str(visible))
    assert visible, "Delete User popup not visible"


@when('the user clicks the "Delete User" button')
def click_delete_user_confirm_button(page, captured_values):
    cap = captured_values
    UsersPage(page).click_delete_user_confirm()
    cap.add("Delete User button clicked", "true")


@then("the user is deleted")
def verify_user_is_deleted(page, captured_values, scenario_context):
    cap = captured_values
    email = scenario_context.get("added_user_email", "")
    users_pg = UsersPage(page)
    users_pg.wait_for_user_card_gone(email)
    visible = users_pg.is_user_card_visible(email)
    cap.add("User card visible after delete", str(visible))
    assert not visible, f"User '{email}' still visible after deletion"

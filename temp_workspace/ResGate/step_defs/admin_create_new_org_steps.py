from pytest_bdd import step, parsers

from pages.page_org import CreateOrganizationPage, OrgManagementPage
from utils import unique_suffix


@step("the Create Organization page is displayed")
def verify_create_org_page(page, captured_values):
    cap = captured_values
    create_pg = CreateOrganizationPage(page)
    create_pg.wait_for_page()
    cap.assert_prerequisite(
        "Create Organization page loaded",
        condition="/addOrganization" in page.url,
        reason=f"Expected URL to contain /addOrganization, got: {page.url}",
        evidence=page.url,
    )


@step("the user enters a unique organization name in the Organization Name field")
def enter_unique_org_name(page, test_data, captured_values, scenario_context):
    cap = captured_values
    prefix = test_data.get("orgNamePrefix", "RL-01_Researcher")
    name = f"{prefix}-{unique_suffix()}"
    scenario_context["org_name"] = name
    CreateOrganizationPage(page).fill_org_name(name)
    cap.add("Organization name entered", name)


@step(parsers.parse("the user enters '{description}' in the Organization Description field"))
def enter_org_description(page, description, captured_values):
    cap = captured_values
    CreateOrganizationPage(page).fill_org_description(description)
    cap.add("Organization description entered", description)


@step("the user clicks the Add Users dropdown")
def click_add_users_dropdown(page, captured_values):
    cap = captured_values
    CreateOrganizationPage(page).click_add_users_dropdown()
    cap.add("Add Users dropdown clicked", "true")


@step("a pop-up box with Add User is displayed")
def verify_add_user_popup_visible(page, captured_values):
    cap = captured_values
    visible = CreateOrganizationPage(page).is_add_user_dialog_visible()
    cap.add("Add User dialog visible", str(visible))
    assert visible, "Add User dialog not visible after clicking Add Users dropdown"


@step("the user enters a valid new user email in the Email input box")
def enter_new_user_email(page, test_data, captured_values, scenario_context):
    cap = captured_values
    email_base = test_data.get("newUserEmailBase", "rgate1")
    email = f"{email_base}+{unique_suffix()}@yopmail.com"
    scenario_context["new_user_email"] = email
    CreateOrganizationPage(page).fill_new_user_email(email)
    cap.add("New user email entered", email)


@step(parsers.parse("the user enters '{first_name}' in the FirstName input box"))
def enter_new_user_first_name(page, first_name, captured_values):
    cap = captured_values
    CreateOrganizationPage(page).fill_new_user_first_name(first_name)
    cap.add("New user first name entered", first_name)


@step(parsers.parse("the user enters '{last_name}' in the LastName input box"))
def enter_new_user_last_name(page, last_name, captured_values):
    cap = captured_values
    CreateOrganizationPage(page).fill_new_user_last_name(last_name)
    cap.add("New user last name entered", last_name)


@step(parsers.parse("the user clicks the Role dropdown and selects '{role}'"))
def select_new_user_role(page, role, captured_values):
    cap = captured_values
    CreateOrganizationPage(page).select_new_user_role(role)
    cap.add("New user role selected", role)


@step("the user clicks the Add User button")
def click_add_user_in_dialog(page, captured_values):
    cap = captured_values
    CreateOrganizationPage(page).click_add_user_in_dialog()
    cap.add("Add User dialog submitted", "true")


@step("the user selects the newly added user checkbox from the Select Users from the list")
def select_new_user_checkbox(page, captured_values, scenario_context):
    cap = captured_values
    email = scenario_context.get("new_user_email", "")
    CreateOrganizationPage(page).select_user_checkbox_by_email(email)
    cap.add("New user checkbox selected", email)


@step("the user clicks the Create Organization button")
def click_create_org_btn(page, captured_values):
    cap = captured_values
    CreateOrganizationPage(page).click_create_org()
    cap.add("Create Organization clicked", "true")


@step(parsers.parse("the organization with a name containing '{org_fragment}' is present on the page"))
def verify_org_visible_on_page(page, org_fragment, captured_values, scenario_context):
    cap = captured_values
    org_name = scenario_context.get("org_name", org_fragment)
    org_pg = OrgManagementPage(page)
    org_pg.wait_for_page()
    org_pg.wait_for_org_visible(org_fragment)
    visible = org_pg.is_org_visible(org_fragment)
    cap.add("Org name searched for", org_fragment)
    cap.add("Full org name created", org_name)
    passed = cap.assert_match(
        f"Organization containing '{org_fragment}' visible",
        expected="visible",
        actual="visible" if visible else "not visible",
    )
    assert passed, f"Organization with name containing '{org_fragment}' not found on page"


@step(parsers.parse("the user clicks Actions for the organization with a name containing '{org_fragment}' and selects Delete"))
def click_org_actions_and_select_delete(page, org_fragment, captured_values):
    cap = captured_values
    org_pg = OrgManagementPage(page)
    org_pg.click_actions_for_org(org_fragment)
    org_pg.click_delete_option()
    cap.add("Actions > Delete clicked for org containing", org_fragment)


@step(parsers.parse("the user selects the confirmation checkbox '{checkbox_text}' and clicks the Delete button"))
def confirm_and_click_delete(page, checkbox_text, captured_values):
    cap = captured_values
    org_pg = OrgManagementPage(page)
    org_pg.check_delete_confirmation_checkbox()
    cap.add("Delete confirmation checkbox selected", checkbox_text)
    org_pg.click_delete_confirm_button()
    cap.add("Delete confirm button clicked", "true")


@step(parsers.parse("the confirmation message '{message}' is displayed on the top right side"))
def verify_delete_success_toast(page, message, captured_values):
    cap = captured_values
    org_pg = OrgManagementPage(page)
    toast_text = org_pg.get_success_toast_text()
    cap.add("Delete confirmation toast text", toast_text)
    actual_for_assert = message if message.lower() in toast_text.lower() else toast_text
    passed = cap.assert_match(
        f"Confirmation message '{message}' displayed",
        expected=message,
        actual=actual_for_assert,
    )
    assert passed, f"Expected toast containing '{message}', got: {toast_text!r}"

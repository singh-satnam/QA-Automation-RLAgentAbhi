from pytest_bdd import when, then

from pages.page_common import HeaderNav
from pages.page_key_pairs import KeyPairsPage
from utils import unique_suffix


@when("the user clicks the hamburger menu and selects Key Pairs")
def click_hamburger_and_select_key_pairs(page, captured_values):
    cap = captured_values
    page.wait_for_selector(
        "button[aria-label='Open navigation menu']", state="visible", timeout=15000
    )
    nav = HeaderNav(page)
    nav.click_hamburger_menu()
    page.wait_for_timeout(400)
    nav.click_nav_item("Key Pairs")
    page.wait_for_timeout(600)
    cap.add("Hamburger nav selected", "Key Pairs")


@when("the user clicks the +Create New button")
def click_create_new_button(page, captured_values):
    cap = captured_values
    kp = KeyPairsPage(page)
    kp.wait_for_page()
    kp.click_create_new()
    cap.add("+Create New clicked", "true")


@then("the Create Key Pair dialog box appears")
def verify_create_key_pair_dialog(page, captured_values):
    cap = captured_values
    visible = KeyPairsPage(page).is_create_dialog_visible()
    cap.add("Create Key Pair dialog visible", str(visible))
    assert visible, "Create Key Pair dialog is not visible"


@when("the user clicks the Project dropdown and selects the second project")
def select_second_project(page, captured_values):
    cap = captured_values
    project_name = KeyPairsPage(page).select_project_by_index(2)
    cap.add("Project selected (2nd)", project_name)


@when("the user fills the Name input box with a valid name")
def fill_key_pair_name(page, test_data, captured_values, scenario_context):
    cap = captured_values
    prefix = test_data.get("keyPairNamePrefix", "myauto")
    name = f"{prefix}{unique_suffix()}"
    scenario_context["key_pair_name"] = name
    KeyPairsPage(page).fill_key_pair_name(name)
    cap.add("Key pair name", name)


@when("the user clicks the File format dropdown and selects pem")
def select_file_format_pem(page, captured_values):
    cap = captured_values
    KeyPairsPage(page).select_file_format_pem()
    cap.add("File format selected", "pem")


@when("the user clicks Create Key Pair")
def click_create_key_pair(page, captured_values):
    cap = captured_values
    KeyPairsPage(page).click_create_key_pair_button()
    cap.add("Create Key Pair clicked", "true")


@then("the created key pair appears on the Key Pairs page")
def verify_key_pair_on_page(page, captured_values, scenario_context):
    cap = captured_values
    name = scenario_context.get("key_pair_name", "")
    kp = KeyPairsPage(page)
    kp.wait_for_key_pair_row(name)
    visible = kp.is_key_pair_visible(name)
    cap.add("Key pair visible in table", str(visible))
    assert visible, f"Key pair '{name}' not visible on Key Pairs page"


@when("the user clicks the three dots menu on the created key pair")
def click_three_dots_on_key_pair(page, captured_values, scenario_context):
    cap = captured_values
    name = scenario_context.get("key_pair_name", "")
    KeyPairsPage(page).click_actions_for_key_pair(name)
    cap.add("Three dots menu clicked for", name)


@when("the user clicks the Delete button")
def click_delete_option(page, captured_values):
    cap = captured_values
    KeyPairsPage(page).click_delete_option()
    cap.add("Delete option clicked", "true")


@then("the Delete key pair modal appears")
def verify_delete_modal(page, captured_values):
    cap = captured_values
    visible = KeyPairsPage(page).is_delete_modal_visible()
    cap.add("Delete key pair modal visible", str(visible))
    assert visible, "Delete key pair modal is not visible"


@when("the user clicks the Delete button to confirm")
def click_confirm_delete(page, captured_values):
    cap = captured_values
    KeyPairsPage(page).click_confirm_delete()
    cap.add("Delete confirmed", "true")


@then("the Deleted keypair successfully message is displayed")
def verify_delete_success_toast(page, captured_values):
    cap = captured_values
    toast_text = KeyPairsPage(page).get_toast_text()
    cap.add("Delete success toast", toast_text)
    assert "deleted" in toast_text.lower() or "keypair" in toast_text.lower(), (
        f"Expected delete success message, got: {toast_text!r}"
    )

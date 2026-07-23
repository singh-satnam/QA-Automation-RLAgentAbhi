from pytest_bdd import when, then, parsers

from pages.page_study import StudiesPage, StudyDetailsPage


@when(parsers.parse('the user searches for "{search_term}"'))
def search_for_study(page, search_term, captured_values):
    cap = captured_values
    studies = StudiesPage(page)
    studies.wait_for_page()
    studies.search_study(search_term)
    cap.add("Study search term", search_term)


@when(parsers.parse('the user clicks the card whose name starts with "{prefix}"'))
def click_study_card_by_prefix(page, prefix, captured_values):
    cap = captured_values
    StudiesPage(page).click_study_card_by_prefix(prefix)
    cap.add("Study card clicked", prefix)


@then(parsers.parse('the "{tab_name}" tab is present'))
def verify_tab_present(page, tab_name, captured_values):
    cap = captured_values
    details = StudyDetailsPage(page)
    assert details.is_tab_present(tab_name), f"Tab '{tab_name}' not found on study details page"
    cap.add(f"Tab present: {tab_name}", "true")


@when(parsers.parse('the user clicks the "{tab_name}" tab'))
def click_study_tab(page, tab_name, captured_values):
    cap = captured_values
    StudyDetailsPage(page).click_tab(tab_name)
    cap.add("Tab clicked", tab_name)


@then(parsers.parse('the Assigned Projects list includes "{project_name}"'))
def verify_assigned_projects_include(page, project_name, captured_values):
    cap = captured_values
    value = StudyDetailsPage(page).get_field_value("Assigned Projects")
    cap.add("Assigned Projects value", value)
    assert project_name in value, (
        f"Expected '{project_name}' in Assigned Projects, got: {value!r}"
    )


@then(parsers.parse('the Bucket Name equals "{expected_bucket}"'))
def verify_bucket_name(page, expected_bucket, captured_values):
    cap = captured_values
    value = StudyDetailsPage(page).get_field_value("Bucket Name")
    cap.add("Bucket Name value", value)
    assert expected_bucket in value, f"Expected bucket '{expected_bucket}', got: {value!r}"


@when('the user clicks the "Delete" button')
def click_delete_button(page, captured_values):
    cap = captured_values
    StudyDetailsPage(page).click_delete_action()
    cap.add('"Delete" action clicked', "true")


@then("a new popup is displayed")
def verify_delete_popup_visible(page, captured_values):
    cap = captured_values
    details = StudyDetailsPage(page)
    assert details.is_delete_dialog_visible(), "Delete confirmation dialog not visible"
    cap.add("Delete popup visible", "true")


@when("the user selects the checkbox in the popup")
def select_popup_checkbox(page, captured_values):
    cap = captured_values
    StudyDetailsPage(page).check_delete_confirmation_checkbox()
    cap.add("Delete confirmation checkbox", "checked")


@when('the user clicks the "Delete" button in the popup')
def click_delete_in_popup(page, captured_values):
    cap = captured_values
    StudyDetailsPage(page).click_delete_in_dialog()
    cap.add('"Delete" in popup clicked', "true")


@then("a confirmation popup is displayed in the top right corner")
def verify_confirmation_popup(page, captured_values):
    cap = captured_values
    toast_text = StudyDetailsPage(page).get_confirmation_toast_text()
    cap.add("Confirmation popup text", toast_text)
    assert toast_text, "No confirmation toast appeared after delete"

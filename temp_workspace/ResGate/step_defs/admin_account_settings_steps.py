from pytest_bdd import when, then

from pages.page_account_settings import AccountSettingsPage


@when("the user clicks the Account icon and selects Settings")
def click_account_icon_and_select_settings(page, captured_values):
    cap = captured_values
    AccountSettingsPage(page).click_account_icon_and_select_settings()
    cap.add("Account icon → Settings clicked", "true")


@then("the user is taken to the Back to Organization page")
def verify_back_to_org_page(page, captured_values):
    cap = captured_values
    settings_pg = AccountSettingsPage(page)
    settings_pg.wait_for_page()
    cap.assert_prerequisite(
        "Account Settings page loaded",
        condition="/setting" in page.url,
        reason=f"Expected URL to contain /setting, got: {page.url}",
        evidence=page.url,
    )
    cap.add("Settings page URL", page.url)


@then("the Project Accounts table is displayed")
def verify_project_accounts_table_visible(page, captured_values):
    cap = captured_values
    visible = AccountSettingsPage(page).is_project_accounts_table_visible()
    cap.add("Project Accounts table visible", str(visible))
    assert visible, "Project Accounts table not visible on Settings page"


@then("the Project Accounts table displays the following column headings:")
def verify_project_accounts_column_headings(page, captured_values):
    cap = captured_values
    expected = ["Account Name", "Region", "Account Number", "Organization", "Created On", "SRE"]
    actual_headers = AccountSettingsPage(page).get_project_accounts_table_headers()
    cap.add("Project Accounts table headers found", str(actual_headers))
    for col in expected:
        found = any(col.lower() in h.lower() for h in actual_headers)
        passed = cap.assert_match(
            f"Column '{col}' displayed",
            expected=col,
            actual=col if found else f"NOT FOUND in {actual_headers}",
        )
        assert passed, f"Column '{col}' not found in table headers: {actual_headers}"


@when("the user clicks the link icon under Account Name")
def click_link_icon_under_account_name(page, captured_values):
    cap = captured_values
    AccountSettingsPage(page).click_link_icon_under_account_name()
    cap.add("Link icon under Account Name clicked", "true")


@then("the StandardAccount popup is displayed")
def verify_standard_account_popup_visible(page, captured_values):
    cap = captured_values
    settings_pg = AccountSettingsPage(page)
    settings_pg.wait_for_popup()
    visible = settings_pg.is_standard_account_popup_visible()
    cap.add("StandardAccount popup visible", str(visible))
    assert visible, "StandardAccount popup not visible after clicking link icon"


@then("the popup displays the following fields:")
def verify_popup_field_labels(page, captured_values):
    cap = captured_values
    expected = ["Project Name", "Created On", "Project Owner"]
    actual_fields = AccountSettingsPage(page).get_popup_field_labels()
    cap.add("Popup field labels found", str(actual_fields))
    for field in expected:
        found = any(field.lower() in f.lower() for f in actual_fields)
        passed = cap.assert_match(
            f"Popup field '{field}' displayed",
            expected=field,
            actual=field if found else f"NOT FOUND in {actual_fields}",
        )
        assert passed, f"Popup field '{field}' not found: {actual_fields}"


@when("the user clicks the X icon to close the popup")
def click_close_popup(page, captured_values):
    cap = captured_values
    AccountSettingsPage(page).click_close_popup()
    cap.add("Popup X icon closed", "true")

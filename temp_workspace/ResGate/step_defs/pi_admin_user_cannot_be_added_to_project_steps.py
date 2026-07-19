from pytest_bdd import when, then

from pages.page_project_details import ProjectDetailsPage


@when("the user clicks Manage next to Assigned Users")
def click_manage_assigned_users(page, captured_values):
    cap = captured_values
    ProjectDetailsPage(page).click_manage_assigned_users()
    cap.add("Manage Assigned Users clicked", "true")


@then("the admin user is not displayed in the Assigned Users list")
def verify_admin_not_in_assigned_users(page, test_data, captured_values):
    cap = captured_values
    admin_email = test_data["ADMIN_USER"]
    details = ProjectDetailsPage(page)
    users_list = details.get_assigned_users_list()
    cap.add("Assigned Users list", str(users_list))
    cap.add("Admin user email checked", admin_email)
    admin_in_list = any(admin_email in user_text for user_text in users_list)
    passed = cap.assert_match(
        "Admin user not in Assigned Users list",
        expected="not present",
        actual="not present" if not admin_in_list else f"found: {admin_email}",
    )
    assert passed, f"Admin user '{admin_email}' should NOT be in Assigned Users list but was found"


@when("the user clicks the Cancel button")
def click_cancel_button(page, captured_values):
    cap = captured_values
    ProjectDetailsPage(page).click_cancel_assigned_users()
    cap.add("Cancel button clicked", "true")

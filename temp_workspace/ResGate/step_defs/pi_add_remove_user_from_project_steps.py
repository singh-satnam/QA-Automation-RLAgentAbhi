from pytest_bdd import then, when

from pages.page_project_details import ProjectDetailsPage


@then('the "Select users from the list" panel is displayed')
def verify_select_users_panel_visible(page, captured_values):
    cap = captured_values
    visible = ProjectDetailsPage(page).is_assigned_users_panel_visible()
    cap.add("Select users panel visible", str(visible))
    assert visible, "'Select users from the list' panel not visible after clicking Manage"


@when("the user selects the last option from the list")
def select_last_user_from_list(page, captured_values):
    cap = captured_values
    label = ProjectDetailsPage(page).select_last_user_from_list()
    cap.add("Last user selected", label)

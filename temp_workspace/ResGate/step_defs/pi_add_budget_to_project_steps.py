import re

from pytest_bdd import parsers, when, then

from pages.page_project_details import ProjectDetailsPage


@then("the user reads the current value of the Budget field")
def read_budget_value(page, captured_values, scenario_context):
    cap = captured_values
    details = ProjectDetailsPage(page)
    budget_text = details.get_budget_value_text()
    scenario_context["budget_before_text"] = budget_text
    match = re.search(r'USD\s+([\d,]+)', budget_text)
    scenario_context["budget_before_amount"] = int(match.group(1).replace(',', '')) if match else 0
    cap.add("Budget before", budget_text)


@when("the user clicks Add Budget")
def click_add_budget(page, captured_values):
    cap = captured_values
    ProjectDetailsPage(page).click_action_button("Add Budget")
    cap.add("Add Budget clicked", "true")


@when(parsers.re(r'the user enters "(?P<amount>[^"]+)" in the "(?P<field_label>[^"]+)" field'))
def enter_amount_in_field(page, amount, field_label, captured_values):
    cap = captured_values
    ProjectDetailsPage(page).fill_add_budget_amount(amount)
    cap.add(f"Amount entered in '{field_label}'", amount)


@when("the user clicks Submit")
def click_submit(page, captured_values):
    cap = captured_values
    ProjectDetailsPage(page).click_dialog_submit()
    cap.add("Submit clicked", "true")


@then(parsers.re(r'the success message "(?P<expected_message>[^"]+)" is displayed in the top right corner and disappears'))
def verify_success_toast(page, expected_message, captured_values):
    cap = captured_values
    details = ProjectDetailsPage(page)
    actual_message = details.wait_for_success_toast()
    cap.add("Expected success message", expected_message)
    cap.add("Actual success message", actual_message)
    assert "budget" in actual_message.lower() and any(
        kw in actual_message.lower() for kw in ("success", "updated", "added")
    ), f"Toast did not indicate budget success: '{actual_message}'"
    details.wait_for_toast_gone()
    cap.add("Success toast disappeared", "true")


@then("the Budget field displays the updated value equal to the previous budget value plus 1")
def verify_budget_updated(page, captured_values, scenario_context):
    cap = captured_values
    details = ProjectDetailsPage(page)
    new_budget_text = details.get_budget_value_text()
    cap.add("Budget after", new_budget_text)
    before_amount = scenario_context.get("budget_before_amount", 0)
    match = re.search(r'USD\s+([\d,]+)', new_budget_text)
    new_amount = int(match.group(1).replace(',', '')) if match else 0
    cap.add("Budget before (numeric)", str(before_amount))
    cap.add("Budget after (numeric)", str(new_amount))
    expected = before_amount + 1
    passed = cap.assert_match(
        "Budget updated by 1",
        expected=str(expected),
        actual=str(new_amount),
    )
    assert passed, f"Budget not updated correctly: expected {expected}, got {new_amount}"

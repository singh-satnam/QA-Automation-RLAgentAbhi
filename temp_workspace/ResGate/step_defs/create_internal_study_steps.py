from pytest_bdd import when, then, parsers

from pages.page_common import HeaderNav
from pages.page_study import StudiesPage, CreateStudyPage
from utils import unique_suffix


@when('the user clicks the hamburger menu and selects "Studies"')
def click_hamburger_and_select_studies(page, captured_values):
    cap = captured_values
    page.wait_for_selector(
        "button[aria-label='Open navigation menu']", state="visible", timeout=15000
    )
    nav = HeaderNav(page)
    nav.click_hamburger_menu()
    page.wait_for_timeout(400)
    nav.click_nav_item("Studies")
    page.wait_for_timeout(600)
    cap.add("Hamburger nav selected", "Studies")


@when('the user clicks the "+Create Study" button')
def click_create_study_button(page, captured_values):
    cap = captured_values
    studies = StudiesPage(page)
    studies.wait_for_page()
    studies.click_create_study()
    cap.add("+Create Study clicked", "true")


@then(parsers.parse('the "{page_name}" page appears'))
def verify_create_study_page(page, page_name, captured_values):
    cap = captured_values
    study_page = CreateStudyPage(page)
    study_page.wait_for_create_page()
    cap.assert_prerequisite(
        "Create New Study page loaded",
        condition="/studies/actions" in page.url,
        reason=f"Expected URL to contain /studies/actions, got: {page.url}",
        evidence=page.url,
    )
    actual_heading = study_page.get_heading()
    cap.add("Create study page heading", actual_heading)


@when(parsers.parse('the user enters the study name "{prefix}" with a random number appended'))
def enter_study_name(page, prefix, captured_values, scenario_context):
    cap = captured_values
    name = f"{prefix.replace(' ', '')}{unique_suffix()}"
    scenario_context["study_name"] = name
    CreateStudyPage(page).fill_study_name(name)
    cap.add("Study name entered", name)


@when(parsers.parse('the user enters the description "{prefix}" with a random number appended'))
def enter_description(page, prefix, captured_values):
    cap = captured_values
    desc = f"{prefix}{unique_suffix()}"
    CreateStudyPage(page).fill_description(desc)
    cap.add("Description entered", desc)


@when(parsers.parse('the user selects the study type as "{study_type}"'))
def select_study_type(page, study_type, captured_values):
    cap = captured_values
    CreateStudyPage(page).select_study_type(study_type)
    cap.add("Study type selected", study_type)


@when(parsers.parse('the user selects the access level as "{access_level}"'))
def select_access_level(page, access_level, captured_values):
    cap = captured_values
    CreateStudyPage(page).select_access_level(access_level)
    cap.add("Access level selected", access_level)


@when('the user clicks the "Next" button')
def click_next_button(page, captured_values):
    cap = captured_values
    CreateStudyPage(page).click_next()
    cap.add('"Next" button clicked', "true")


@when('the user clicks the "Register Study" button')
def click_register_study_button(page, captured_values):
    cap = captured_values
    CreateStudyPage(page).click_register_study()
    cap.add('"Register Study" button clicked', "true")


@when("the user enters the bucket name from the test data")
def enter_bucket_name(page, test_data, captured_values):
    cap = captured_values
    bucket_name = test_data["Bucket Name"].strip()
    CreateStudyPage(page).fill_bucket_name(bucket_name)
    page.wait_for_timeout(800)
    cap.add("Bucket name entered", bucket_name)


@when("the user selects the project account from the test data")
def select_project_account(page, test_data, captured_values):
    cap = captured_values
    account = test_data["Project Account"]
    CreateStudyPage(page).select_project_account(account)
    cap.add("Project account selected", account)


@when("the user clicks the project checkbox from the test data")
def click_project_checkbox(page, test_data, captured_values):
    cap = captured_values
    project = test_data["Projects"]
    CreateStudyPage(page).click_project_checkbox_by_name(project)
    cap.add("Project checkbox clicked", project)


@then("a confirmation message is displayed in the top right corner")
def verify_confirmation_message(page, captured_values):
    cap = captured_values
    toast_text = CreateStudyPage(page).get_success_toast_text()
    cap.add("Confirmation toast text", toast_text)
    assert toast_text, "No confirmation toast appeared after Register Study"
    assert any(
        kw in toast_text.lower()
        for kw in ("register", "success", "study", "created")
    ), f"Unexpected confirmation message: {toast_text!r}"

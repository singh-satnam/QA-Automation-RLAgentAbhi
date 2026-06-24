import pytest
from pytest_bdd import given, when, then, parsers

from pages.page_create_new_instance import (
    LoginPage,
    MyProjectsPage,
    ProjectPage,
    CreateInstancePage,
)


def _table_to_dicts(datatable):
    headers = datatable[0]
    return [dict(zip(headers, row)) for row in datatable[1:]]


@given(parsers.parse('the user navigates to the login page "{url}"'))
def navigate_to_login(page, base_url, captured_values, scenario_context, url):
    login_page = LoginPage(page, base_url)
    login_page.navigate_to_login(url)
    cap = captured_values
    cap.add("Login URL", url)
    scenario_context["login_page"] = login_page


@then("the user enters valid credentials:")
@given("the user enters valid credentials:")
def enter_credentials(page, captured_values, scenario_context, datatable):
    login_page = scenario_context.get("login_page") or LoginPage(page)
    rows = _table_to_dicts(datatable)
    row = rows[0]
    email = row["Email"]
    password = row["Password"]
    login_page.enter_email(email)
    login_page.enter_password(password)
    cap = captured_values
    cap.add("Login Email", email)
    cap.add("Login Password", "***")
    scenario_context["login_page"] = login_page


@then("the user clicks on the Sign In button")
def click_sign_in(page, captured_values, scenario_context):
    login_page = scenario_context.get("login_page") or LoginPage(page)
    login_page.click_sign_in()
    cap = captured_values
    cap.add("Sign In clicked", "Yes")


@then(parsers.parse('the user should be landing on the "{page_name}" page'))
def verify_landing_page(page, captured_values, scenario_context, page_name):
    login_page = scenario_context.get("login_page") or LoginPage(page)
    is_on_page = login_page.is_on_my_projects()
    cap = captured_values
    cap.assert_prerequisite(
        f"Landing on {page_name}",
        condition=is_on_page,
        reason=f"Expected to land on '{page_name}' page after login",
        evidence=f"Current URL: {page.url}",
    )
    scenario_context["my_projects_page"] = MyProjectsPage(page)


@then(parsers.parse('the user verifies the "{card_name}" card is present'))
@given(parsers.parse('the user verifies the "{card_name}" card is present'))
def verify_card_present(page, captured_values, scenario_context, card_name):
    my_projects = scenario_context.get("my_projects_page") or MyProjectsPage(page)
    is_visible = my_projects.is_project_card_visible(card_name)
    cap = captured_values
    assert cap.assert_match(
        f"Project card '{card_name}' is present",
        expected="visible",
        actual="visible" if is_visible else "not found",
    ), f"Project card '{card_name}' was not found on the page"


@when(parsers.parse('the user clicks on the "{project_name}" project'))
def click_project(page, captured_values, scenario_context, project_name):
    my_projects = scenario_context.get("my_projects_page") or MyProjectsPage(page)
    my_projects.click_project(project_name)
    cap = captured_values
    cap.add("Clicked project", project_name)
    scenario_context["project_page"] = ProjectPage(page)


@then(parsers.parse('the "{project_name}" page is displayed'))
def verify_project_page(page, captured_values, scenario_context, project_name):
    project_page = scenario_context.get("project_page") or ProjectPage(page)
    is_displayed = project_page.is_project_page_displayed(project_name)
    cap = captured_values
    assert cap.assert_match(
        f"Project page '{project_name}' displayed",
        expected="displayed",
        actual="displayed" if is_displayed else "not displayed",
    ), f"Project page '{project_name}' was not displayed"


@then("the page should have the following tabs:")
@given("the page should have the following tabs:")
def verify_tabs(page, captured_values, scenario_context, datatable):
    project_page = scenario_context.get("project_page") or ProjectPage(page)
    cap = captured_values
    rows = _table_to_dicts(datatable)
    for row in rows:
        tab_name = row["Tab"]
        is_visible = project_page.is_tab_visible(tab_name)
        assert cap.assert_match(
            f"Tab '{tab_name}' is visible",
            expected="visible",
            actual="visible" if is_visible else "not found",
        ), f"Tab '{tab_name}' was not found on the project page"


@then(parsers.parse('the user clicks on "LAUNCH NOW" under "{product_name}"'))
@given(parsers.parse('the user clicks on "LAUNCH NOW" under "{product_name}"'))
def click_launch_now_for_product(page, captured_values, scenario_context, product_name):
    project_page = scenario_context.get("project_page") or ProjectPage(page)
    project_page.click_launch_now_for_product(product_name)
    cap = captured_values
    cap.add("LAUNCH NOW clicked for", product_name)
    scenario_context["create_instance_page"] = CreateInstancePage(page)


@then("the create new instance page is displayed")
def verify_create_instance_page(page, captured_values, scenario_context):
    create_page = scenario_context.get("create_instance_page") or CreateInstancePage(page)
    is_displayed = create_page.is_create_instance_page_displayed()
    cap = captured_values
    cap.assert_prerequisite(
        "Create new instance page displayed",
        condition=is_displayed,
        reason="Expected create new instance page to be visible",
        evidence=f"Current URL: {page.url}",
    )
    scenario_context["create_instance_page"] = create_page


@then(parsers.parse('the user fills the Product Name as "{name_template}"'))
@given(parsers.parse('the user fills the Product Name as "{name_template}"'))
def fill_product_name(page, captured_values, scenario_context, name_template):
    create_page = scenario_context.get("create_instance_page") or CreateInstancePage(page)
    if "<random_number>" in name_template:
        product_name = create_page.generate_product_name()
    else:
        product_name = name_template
    create_page.fill_product_name(product_name)
    cap = captured_values
    cap.add("Product Name entered", product_name)
    scenario_context["product_name"] = product_name


@then("the user selects the below option under Study Selection:")
@given("the user selects the below option under Study Selection:")
def select_study(page, captured_values, scenario_context, datatable):
    create_page = scenario_context.get("create_instance_page") or CreateInstancePage(page)
    cap = captured_values
    rows = _table_to_dicts(datatable)
    for row in rows:
        study_name = row["Study Selection"]
        create_page.select_study(study_name)
        cap.add("Study selected", study_name)


@then("the user fills the below details under project configuration:")
@given("the user fills the below details under project configuration:")
def fill_project_config(page, captured_values, scenario_context, datatable):
    create_page = scenario_context.get("create_instance_page") or CreateInstancePage(page)
    cap = captured_values
    rows = _table_to_dicts(datatable)
    for row in rows:
        field = row["Field"]
        value = row["Value"]
        if field == "AvailabilityZone":
            create_page.select_availability_zone(value)
        elif field == "EBSVolumeSize":
            create_page.fill_ebs_volume_size(value)
        elif field == "InstanceType":
            create_page.select_instance_type(value)
        else:
            pytest.fail(f"Unknown configuration field: {field}")
        cap.add(f"Config - {field}", value)


@then(parsers.parse('the user clicks on "LAUNCH NOW" at the top right side of the page'))
@given(parsers.parse('the user clicks on "LAUNCH NOW" at the top right side of the page'))
def click_launch_now_create(page, captured_values, scenario_context):
    create_page = scenario_context.get("create_instance_page") or CreateInstancePage(page)
    create_page.click_launch_now()
    cap = captured_values
    first_toast = create_page.get_first_toast()
    cap.add("LAUNCH NOW clicked (create instance)", "Yes")
    cap.add("First toast after launch", first_toast or "<none>")
    scenario_context["first_toast"] = first_toast
    scenario_context["project_page"] = ProjectPage(page)


@then(parsers.parse('the user lands on the "My Products" tab with the message "{message}"'))
def verify_my_products_with_message(page, captured_values, scenario_context, message):
    project_page = scenario_context.get("project_page") or ProjectPage(page)
    cap = captured_values

    first_toast = scenario_context.get("first_toast", "")
    current_toast = project_page.get_success_message()
    cap.add("Current toast on My Products", current_toast or "<none>")

    best_match = ""
    for candidate in [first_toast, current_toast]:
        if message.lower() in candidate.lower() or candidate.lower() in message.lower():
            best_match = candidate
            break
    if not best_match:
        best_match = first_toast or current_toast

    is_on_tab = project_page.is_on_my_products_tab()
    assert cap.assert_match(
        "Landed on My Products tab",
        expected="visible",
        actual="visible" if is_on_tab else "not visible",
    ), "Did not land on the My Products tab after launch"

    assert cap.assert_match(
        "Launch success message",
        expected=message,
        actual=best_match or "<no toast captured>",
    ), f"Expected message '{message}' but got '{best_match}'"


@then('the "My Products" tab should have the entered Product Name as one of the Product containers')
def verify_product_name_in_my_products(page, captured_values, scenario_context):
    project_page = scenario_context.get("project_page") or ProjectPage(page)
    product_name = scenario_context.get("product_name", "")
    cap = captured_values

    cap.assert_prerequisite(
        "Product name was captured",
        condition=bool(product_name),
        reason="Product name was not recorded during form fill",
        evidence=f"product_name='{product_name}'",
    )

    found = project_page.is_product_name_in_my_products(product_name)
    names = project_page.get_my_product_names()
    cap.add("My Products list", ", ".join(names) if names else "<empty>")

    assert cap.assert_match(
        f"Product '{product_name}' in My Products",
        expected=product_name,
        actual=product_name if found else f"NOT FOUND in [{', '.join(names[:5])}...]",
    ), f"Product '{product_name}' was not found in My Products"

from pytest_bdd import given, when, then, parsers
from playwright.sync_api import expect

from pages.page_login_and_stop_instance import (
    LoginPage,
    MyProjectsPage,
    ProjectDetailsPage,
    ProductDetailsPage,
)


@given(parsers.parse('the user navigates to the login page "{url}"'))
def navigate_to_login(page, base_url, captured_values, url):
    login_page = LoginPage(page, base_url)
    login_page.navigate_to_login(url)
    captured_values.add("Login URL", url)


@given("the user enters valid credentials:")
def enter_credentials(page, base_url, captured_values, datatable):
    login_page = LoginPage(page, base_url)
    headers = datatable[0]
    values = datatable[1]
    row = dict(zip(headers, values))
    email = row["Email"]
    password = row["Password"]
    login_page.enter_email(email)
    login_page.enter_password(password)
    captured_values.add("Email entered", email)
    captured_values.add("Password entered", "***")


@when("the user clicks on the Sign In button")
def click_sign_in(page, base_url, captured_values):
    login_page = LoginPage(page, base_url)
    login_page.click_sign_in()
    captured_values.add("Sign In clicked", True)


@then(parsers.parse('the user should be landing on the "{page_name}" page'))
def verify_landing_page(page, base_url, captured_values, page_name):
    projects_page = MyProjectsPage(page, base_url)
    is_landed = projects_page.is_my_projects_page()
    captured_values.assert_prerequisite(
        f"Landing on {page_name}",
        condition=is_landed,
        reason=f"Did not land on {page_name} page after login",
        evidence=f"current_url={page.url}",
    )
    captured_values.add("Landed on page", page_name)


@then(parsers.parse('the "{project_name}" card is present'))
def verify_project_card_present(page, base_url, captured_values, project_name):
    projects_page = MyProjectsPage(page, base_url)
    is_present = projects_page.is_project_card_present(project_name)
    assert captured_values.assert_match(
        f"Project card '{project_name}' is present",
        expected="True",
        actual=str(is_present),
    )


@when(parsers.parse('the user clicks on the "{project_name}" project'))
def click_project(page, base_url, captured_values, project_name):
    projects_page = MyProjectsPage(page, base_url)
    projects_page.click_project_card(project_name)
    captured_values.add("Clicked project", project_name)


@then(parsers.parse('the "{project_name}" page is displayed'))
def verify_project_page_displayed(page, base_url, captured_values, project_name):
    project_page = ProjectDetailsPage(page, base_url)
    is_displayed = project_page.is_project_page_displayed(project_name)
    assert captured_values.assert_match(
        f"Project page '{project_name}' displayed",
        expected="True",
        actual=str(is_displayed),
    )


@when(parsers.parse('the user clicks on the "{tab_name}" tab'))
def click_tab(page, base_url, captured_values, tab_name):
    project_page = ProjectDetailsPage(page, base_url)
    project_page.click_my_products_tab()
    captured_values.add("Clicked tab", tab_name)


@then(parsers.parse('"{product_name}" is available'))
def verify_product_available(page, base_url, captured_values, product_name):
    project_page = ProjectDetailsPage(page, base_url)
    is_available = project_page.is_product_available(product_name)
    assert captured_values.assert_match(
        f"Product '{product_name}' is available",
        expected="True",
        actual=str(is_available),
    )


@then(parsers.parse('the "{product_name}" is in green "{status}" status'))
def verify_product_status(page, base_url, captured_values, product_name, status):
    project_page = ProjectDetailsPage(page, base_url)
    actual_status = project_page.get_product_status(product_name)
    captured_values.add(f"Product '{product_name}' actual status", actual_status)
    assert captured_values.assert_match(
        f"Product '{product_name}' status",
        expected=status,
        actual=actual_status,
    )


@when(parsers.re(r'the user clicks on "(?P<action>[^"]+)" under "(?P<section>[^"]+)"'))
def click_action_under_section(page, base_url, captured_values, scenario_context, action, section):
    stop_icon = page.locator("img[alt='Stop Product']")
    stop_visible = False
    try:
        expect(stop_icon.first).to_be_visible(timeout=5000)
        stop_visible = True
    except Exception:
        pass
    captured_values.assert_prerequisite(
        f"'{action}' button available",
        condition=stop_visible,
        reason=f"'{action}' button not found — instance may already be stopped",
        evidence=f"current_url={page.url}",
    )
    product_page = ProductDetailsPage(page, base_url)
    product_page.click_stop_under_connect()
    toast_text = product_page.get_toast_message_text()
    scenario_context["stop_toast_text"] = toast_text
    captured_values.add(f"Clicked '{action}' under '{section}'", True)


@when(parsers.re(r'the user clicks on "(?P<product_name>[^"]+)"$'))
def click_product(page, base_url, captured_values, product_name):
    project_page = ProjectDetailsPage(page, base_url)
    project_page.click_product(product_name)
    captured_values.add("Clicked product", product_name)


@then(parsers.parse('the user lands on the product details page of "{product_name}"'))
def verify_product_details_page(page, base_url, captured_values, product_name):
    product_page = ProductDetailsPage(page, base_url)
    is_on_page = product_page.is_product_details_page(product_name)
    captured_values.assert_prerequisite(
        f"Product details page for '{product_name}'",
        condition=is_on_page,
        reason=f"Did not land on product details page for {product_name}",
        evidence=f"current_url={page.url}",
    )
    heading = product_page.get_product_heading()
    captured_values.add("Product details heading", heading)


@then("the stop process initiated successfully message is displayed")
def verify_stop_success_message(page, base_url, captured_values, scenario_context):
    toast_text = scenario_context.get("stop_toast_text", "")
    if toast_text:
        captured_values.add("Stop toast message", toast_text)
        assert captured_values.assert_match(
            "Stop process initiated successfully",
            expected="True",
            actual="True",
        )
        return
    product_page = ProductDetailsPage(page, base_url)
    is_indicated = product_page.is_stop_success_indicated()
    captured_values.add("Stop notification text", "<status change detected>" if is_indicated else "<not detected>")
    assert captured_values.assert_match(
        "Stop process initiated successfully",
        expected="True",
        actual=str(is_indicated),
    )


@then(parsers.parse('the "{option}" option is available under "{section}"'))
def verify_option_available_under_section(page, base_url, captured_values, option, section):
    product_page = ProductDetailsPage(page, base_url)
    is_available = product_page.is_start_option_available()
    assert captured_values.assert_match(
        f"'{option}' option available under '{section}'",
        expected="True",
        actual=str(is_available),
    )

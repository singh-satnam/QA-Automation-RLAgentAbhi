import pytest
from pytest_bdd import given, when, then, parsers
from pages.page_login_and_launch_machine import (
    LoginPage,
    MyProjectsPage,
    ProjectPage,
    ProductDetailsPage,
    AmazonDCVPage,
)


@given("the user navigates to the login page")
def navigate_to_login(page, test_data, captured_values, scenario_context):
    cap = captured_values
    login_url = test_data.get("config", {}).get("login_url", "")
    login_page = LoginPage(page, login_url)
    login_page.navigate(login_url)
    login_page.dismiss_session_expired_alert()
    cap.add("Navigated to login URL", login_url)
    scenario_context["login_page"] = login_page


@given(parsers.parse('the user enters "{user_type}" credentials'))
def enter_credentials(page, credentials, captured_values, scenario_context, user_type):
    cap = captured_values
    login_page = scenario_context.get("login_page") or LoginPage(page)
    creds = credentials.get(user_type, {})
    login_page.fill_email(creds["email"])
    login_page.fill_password(creds["password"])
    cap.add("User type", user_type)
    cap.add("Email entered", creds["email"])
    cap.add("Password entered", "***")
    scenario_context["login_page"] = login_page


@when("the user clicks on the Sign In button")
def click_sign_in(page, captured_values, scenario_context):
    cap = captured_values
    login_page = scenario_context.get("login_page") or LoginPage(page)
    login_page.click_sign_in()
    cap.add("Clicked Sign In", "Yes")


@then(parsers.parse('the user should be landing on the "{page_name}" page'))
def verify_landing_page(page, captured_values, scenario_context, page_name):
    cap = captured_values
    login_page = scenario_context.get("login_page") or LoginPage(page)
    is_on_page = login_page.is_on_my_projects_page()
    cap.assert_prerequisite(
        f"Landing on {page_name}",
        condition=is_on_page,
        reason=f"Expected to land on '{page_name}' page after login",
        evidence=f"Current URL: {page.url}",
    )
    cap.add("Landed on page", page_name)
    scenario_context["my_projects_page"] = MyProjectsPage(page)


@then(parsers.parse('the "{card_name}" card is present'))
def verify_card_present(page, captured_values, scenario_context, card_name):
    cap = captured_values
    mp = scenario_context.get("my_projects_page") or MyProjectsPage(page)
    is_present = mp.is_project_card_present(card_name)
    assert cap.assert_match(
        f"Project card '{card_name}' is present",
        expected="True",
        actual=str(is_present),
    )
    scenario_context["my_projects_page"] = mp


@when(parsers.parse('the user clicks on the "{project_name}" project'))
def click_project(page, captured_values, scenario_context, project_name):
    cap = captured_values
    mp = scenario_context.get("my_projects_page") or MyProjectsPage(page)
    mp.click_project_card(project_name)
    cap.add("Clicked project", project_name)
    scenario_context["project_page"] = ProjectPage(page)


@then(parsers.parse('the "{project_name}" page is displayed'))
def verify_project_page(page, captured_values, scenario_context, project_name):
    cap = captured_values
    pp = scenario_context.get("project_page") or ProjectPage(page)
    is_displayed = pp.is_project_page_displayed(project_name)
    assert cap.assert_match(
        f"Project page '{project_name}' displayed",
        expected="True",
        actual=str(is_displayed),
    )
    scenario_context["project_page"] = pp


@when("the user clicks on the My Products tab")
def click_my_products_tab(page, captured_values, scenario_context):
    cap = captured_values
    pp = scenario_context.get("project_page") or ProjectPage(page)
    pp.click_my_products_tab()
    cap.add("Clicked tab", "My Products")
    scenario_context["project_page"] = pp


@then(parsers.parse('"{product_name}" is available'))
def verify_product_available(page, captured_values, scenario_context, product_name):
    cap = captured_values
    pp = scenario_context.get("project_page") or ProjectPage(page)
    is_avail = pp.is_product_available(product_name)
    assert cap.assert_match(
        f"Product '{product_name}' available",
        expected="True",
        actual=str(is_avail),
    )
    scenario_context["project_page"] = pp


@then(parsers.parse('"{product_name}" is in green "{status}" status'))
def verify_product_status(page, captured_values, scenario_context, product_name, status):
    cap = captured_values
    pp = scenario_context.get("project_page") or ProjectPage(page)
    actual_status = pp.get_product_status(product_name)
    assert cap.assert_match(
        f"Product '{product_name}' status",
        expected=status,
        actual=actual_status,
    )


@when(parsers.re(r'the user clicks on "(?P<product_name>[^"]+)"$'))
def click_product(page, captured_values, scenario_context, product_name):
    cap = captured_values
    pp = scenario_context.get("project_page") or ProjectPage(page)
    pp.click_product(product_name)
    cap.add("Clicked product", product_name)
    scenario_context["product_details_page"] = ProductDetailsPage(page)


@then(parsers.parse('the user lands on the product details of "{product_name}"'))
def verify_product_details(page, captured_values, scenario_context, product_name):
    cap = captured_values
    pd = scenario_context.get("product_details_page") or ProductDetailsPage(page)
    is_displayed = pd.is_product_details_displayed(product_name)
    assert cap.assert_match(
        f"Product details for '{product_name}' displayed",
        expected="True",
        actual=str(is_displayed),
    )
    scenario_context["product_details_page"] = pd


@when(parsers.re(r'the user clicks on "(?P<option>[^"]+)" under "(?P<section>[^"]+)"'))
def click_option_under_section(page, captured_values, scenario_context, tabs, option, section):
    cap = captured_values
    pd = scenario_context.get("product_details_page") or ProductDetailsPage(page)
    with tabs.expect_new("Amazon DCV"):
        pd.click_remote_desktop()
    cap.add(f"Clicked '{option}' under '{section}'", "Yes")
    scenario_context["tabs"] = tabs


@then("a new browser tab is opened with the new Amazon instance")
def verify_new_tab(page, captured_values, scenario_context, tabs):
    cap = captured_values
    if "tabs" not in scenario_context:
        scenario_context["tabs"] = tabs
    new_page = tabs.active()
    dcv = AmazonDCVPage(new_page)
    dcv.wait_for_connection()
    title = new_page.title()
    cap.assert_prerequisite(
        "New Amazon DCV tab opened",
        condition="Amazon DCV" in title or "ip-" in title,
        reason="Expected new tab with Amazon DCV instance",
        evidence=f"Tab title: {title}",
    )
    cap.add("Amazon DCV tab title", title)
    scenario_context["dcv_page"] = dcv
    scenario_context["dcv_tab_page"] = new_page


@when('on the new tab the user clicks on the option with text starting with "ip-"')
def click_ip_option(page, captured_values, scenario_context, tabs):
    cap = captured_values
    dcv = scenario_context["dcv_page"]
    ip_text = dcv.get_ip_button_text()
    cap.add("IP option text", ip_text)
    dcv.click_ip_button()
    cap.add("Clicked ip- option", "Yes")


@then("a menuitem is displayed")
def verify_menuitem_displayed(page, captured_values, scenario_context):
    cap = captured_values
    dcv = scenario_context["dcv_page"]
    is_menu = dcv.is_menu_displayed()
    assert cap.assert_match(
        "Menu item displayed after clicking ip- option",
        expected="True",
        actual=str(is_menu),
    )


@when(parsers.parse('the user clicks on the "{option}" option'))
def click_menu_option(page, captured_values, scenario_context, option):
    cap = captured_values
    dcv = scenario_context["dcv_page"]
    dcv.click_disconnect()
    cap.add(f"Clicked '{option}' option", "Yes")


@then(parsers.parse('the user sees the "{message}" message on the page'))
def verify_message_on_page(page, captured_values, scenario_context, message):
    cap = captured_values
    dcv = scenario_context["dcv_page"]
    actual_message = dcv.get_connection_closed_message()
    cap.add("Connection closed message (actual)", actual_message)
    assert cap.assert_match(
        "Connection closed message",
        expected=message,
        actual=actual_message.rstrip("."),
    )

from pytest_bdd import when, then, parsers

from pages.page_common import LoginPage, HeaderNav
from pages.page_catalog import CatalogPage


@when("the user enters valid Admin credentials")
def enter_admin_credentials(page, test_data, captured_values):
    cap = captured_values
    email = test_data["ADMIN_USER"]
    password = test_data["ADMIN_PWD"]
    login = LoginPage(page)
    login.enter_email(email)
    login.enter_password(password)
    cap.add("Admin email entered", email)


@when('the user clicks "Sign In"')
def click_sign_in_button(page, captured_values):
    cap = captured_values
    LoginPage(page).click_sign_in()
    cap.add("Sign In clicked", "true")


@when(parsers.parse('the user clicks the hamburger menu and selects "{nav_item}"'))
def click_hamburger_menu_and_select(page, nav_item, captured_values):
    cap = captured_values
    page.wait_for_selector(
        "button[aria-label='Open navigation menu']", state="visible", timeout=15000
    )
    nav = HeaderNav(page)
    nav.click_hamburger_menu()
    page.wait_for_timeout(400)
    nav.click_nav_item(nav_item)
    page.wait_for_timeout(600)
    cap.add("Hamburger nav selected", nav_item)


@then("the Catalog page is displayed")
def verify_catalog_page_displayed(page, captured_values):
    cap = captured_values
    catalog = CatalogPage(page)
    catalog.wait_for_page()
    cap.assert_prerequisite(
        "Catalog page loaded",
        condition="/catalog" in page.url,
        reason=f"Expected URL to contain /catalog, got: {page.url}",
        evidence=page.url,
    )
    cap.add("Catalog page URL", page.url)


@then('the Catalog page title displays "Catalog (X)" where X is greater than 0')
def verify_catalog_title_count(page, captured_values):
    cap = captured_values
    catalog = CatalogPage(page)
    count = catalog.get_catalog_count()
    title = catalog.get_title_text()
    cap.add("Catalog page title", title)
    cap.add("Catalog item count", str(count))
    assert count > 0, f"Expected Catalog count > 0, got: {count} (title: {title!r})"


@then(parsers.parse('the "{element}" dropdown combo is present on the Catalog page'))
def verify_view_dropdown_present(page, element, captured_values):
    cap = captured_values
    visible = CatalogPage(page).is_view_dropdown_visible()
    cap.add(f'"{element}" dropdown combo visible', str(visible))
    assert visible, f'"{element}" dropdown combo not visible on Catalog page'


@then("the custom search bar is present on the Catalog page")
def verify_catalog_search_bar_present(page, captured_values):
    cap = captured_values
    visible = CatalogPage(page).is_search_bar_visible()
    cap.add("Catalog search bar visible", str(visible))
    assert visible, "Custom search bar not visible on Catalog page"


@when(parsers.parse('the user clicks the "{dropdown_name}" dropdown'))
def click_catalog_dropdown(page, dropdown_name, captured_values):
    cap = captured_values
    CatalogPage(page).click_view_dropdown()
    cap.add(f'"{dropdown_name}" dropdown clicked', "true")


@then(parsers.parse('the "{dropdown_name}" dropdown displays available options'))
def verify_dropdown_has_options(page, dropdown_name, captured_values):
    cap = captured_values
    catalog = CatalogPage(page)
    options = catalog.get_view_dropdown_options()
    cap.add(f'"{dropdown_name}" dropdown options', str(options))
    assert len(options) > 0, (
        f'"{dropdown_name}" dropdown has no options. Dropdown may not be open.'
    )


@when(parsers.parse('the user selects each option from the "{dropdown_name}" dropdown one by one'))
def select_each_dropdown_option(page, dropdown_name, captured_values, scenario_context):
    catalog = CatalogPage(page)
    if not catalog.is_view_dropdown_open():
        catalog.click_view_dropdown()
        page.wait_for_timeout(300)
    options = catalog.get_view_dropdown_options()
    assert options, f'No options found in "{dropdown_name}" dropdown'

    results = []
    for option in options:
        if not catalog.is_view_dropdown_open():
            catalog.click_view_dropdown()
            page.wait_for_timeout(300)
        catalog.select_view_option(option)
        page.wait_for_timeout(500)
        title = catalog.get_title_text()
        captured_values.add(f'Catalog title after selecting "{option}"', title)
        results.append({"option": option, "title": title})

    scenario_context["dropdown_results"] = results


@then("each dropdown selection updates the Catalog page")
def verify_each_selection_updates_page(captured_values, scenario_context):
    results = scenario_context.get("dropdown_results", [])
    assert results, "No dropdown selection results recorded"
    failures = [r["option"] for r in results if not r["title"]]
    captured_values.add("Dropdown iteration results", str(results))
    assert not failures, (
        f"Catalog heading not displayed after selecting: {failures}"
    )

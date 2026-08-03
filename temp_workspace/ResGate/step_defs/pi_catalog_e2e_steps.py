from pytest_bdd import when, then, parsers

from pages.page_common import LoginPage, MyProjectsPage, HeaderNav
from pages.page_catalog import CatalogPage
from pages.page_project_details import ProjectDetailsPage


@when("the user enters valid PI credentials")
def enter_pi_credentials(page, test_data, captured_values):
    cap = captured_values
    email = test_data["PI_USER"]
    password = test_data["PI_PWD"]
    login = LoginPage(page)
    login.enter_email(email)
    login.enter_password(password)
    cap.add("PI email entered", email)


@then("the PI is on the My Projects page")
def pi_is_on_my_projects_page(page, captured_values):
    cap = captured_values
    my_projects = MyProjectsPage(page)
    my_projects.wait_for_pi_page()
    cap.assert_prerequisite(
        "PI My Projects page",
        condition="/principal" in page.url,
        reason=f"Expected URL to contain /principal, got: {page.url}",
        evidence=page.url,
    )
    cap.add("PI landing URL", page.url)


@when("the user clicks the hamburger menu and selects Catalog")
def click_hamburger_and_select_catalog(page, captured_values):
    cap = captured_values
    page.wait_for_selector(
        "button[aria-label='Open navigation menu']", state="visible", timeout=15000
    )
    nav = HeaderNav(page)
    nav.click_hamburger_menu()
    page.wait_for_timeout(400)
    nav.click_nav_item("Catalog")
    page.wait_for_timeout(600)
    cap.add("Hamburger nav selected", "Catalog")


@then(parsers.parse('the View dropdown displays "{expected_label}"'))
def verify_view_dropdown_label(page, expected_label, captured_values):
    cap = captured_values
    catalog = CatalogPage(page)
    catalog.wait_for_page()
    label = catalog.get_selected_filter()
    cap.add("View dropdown label", label)
    assert expected_label in label, (
        f"Expected View dropdown to show '{expected_label}', got: {label!r}"
    )


@then("the Search with Category Filter is displayed")
def verify_search_and_category_filter(page, captured_values):
    cap = captured_values
    catalog = CatalogPage(page)
    search_visible = catalog.is_search_bar_visible()
    filter_visible = catalog.is_category_filter_visible()
    cap.add("Search bar visible", str(search_visible))
    cap.add("Category filter visible", str(filter_visible))
    assert search_visible, "Search bar not visible on Catalog page"
    assert filter_visible, "Category filter not visible on Catalog page"


@when(parsers.parse('the user clicks the "{category}" Category Filter option'))
@then(parsers.parse('the user clicks the "{category}" Category Filter option'))
def click_category_filter(page, category, captured_values):
    cap = captured_values
    CatalogPage(page).click_category_filter(category)
    cap.add("Category filter clicked", category)


@when("clears the text from the Category Filter option")
@then("clears the text from the Category Filter option")
def clear_category_filter_text(page, captured_values):
    CatalogPage(page).clear_search()
    captured_values.add("Search text cleared", "true")


@when(parsers.parse('the user searches for "{query}"'))
def search_catalog(page, query, captured_values, scenario_context):
    cap = captured_values
    CatalogPage(page).search_catalog(query)
    scenario_context["last_search_query"] = query
    cap.add("Search query", query)
    page.wait_for_timeout(5000)



@then(parsers.parse('the message "{expected_message}" is displayed'))
def verify_empty_search_message(page, expected_message, captured_values):
    cap = captured_values
    msg = CatalogPage(page).get_empty_search_message()
    cap.add("Empty search message", msg)
    assert expected_message in msg, (
        f"Expected '{expected_message}', got: {msg!r}"
    )
   


@then("matching products are displayed")
def verify_matching_products(page, captured_values):
    cap = captured_values
    count = CatalogPage(page).get_product_card_count()
    cap.add("Matching product count", str(count))
    assert count > 0, f"No products displayed after search, got: {count}"


@when(parsers.parse('the user selects "{product_name}" by clicking its checkbox'))
def select_product_checkbox(page, product_name, captured_values):
    cap = captured_values
    CatalogPage(page).select_product_by_name(product_name)
    cap.add("Product selected", product_name)


@when("the user clicks Assign Selected to Project")
def click_assign_selected(page, captured_values):
    cap = captured_values
    CatalogPage(page).click_assign_selected()
    cap.add("Assign Selected to Project clicked", "true")


@then("the Assign to a Project modal is displayed")
def verify_assign_modal(page, captured_values):
    cap = captured_values
    visible = CatalogPage(page).is_assign_modal_visible()
    cap.add("Assign modal visible", str(visible))
    assert visible, "Assign to a Project modal not displayed"


@when(parsers.parse('the user selects "{project_name}" from the Choose a project from the list dropdown'))
def select_project_in_assign_modal(page, project_name, captured_values):
    cap = captured_values
    CatalogPage(page).select_project_in_modal(project_name)
    cap.add("Project selected in modal", project_name)


@when("the user clicks Assign")
def click_assign_in_modal(page, captured_values):
    cap = captured_values
    CatalogPage(page).click_assign_in_modal()
    cap.add("Assign clicked in modal", "true")


@then(parsers.parse('the confirmation message "{expected_message}" is displayed'))
def verify_confirmation_message(page, expected_message, captured_values):
    cap = captured_values
    msg = CatalogPage(page).get_confirmation_toast()
    cap.add("Confirmation message", msg)
    key = expected_message.split(".")[0].strip()
    assert key in msg, (
        f"Expected confirmation containing '{key}', got: {msg!r}"
    )


@when("the user clicks the hamburger menu and selects My Projects")
def click_hamburger_and_select_my_projects(page, captured_values):
    cap = captured_values
    page.wait_for_selector(
        "button[aria-label='Open navigation menu']", state="visible", timeout=15000
    )
    nav = HeaderNav(page)
    nav.click_hamburger_menu()
    page.wait_for_timeout(400)
    nav.click_nav_item("My Projects")
    page.wait_for_timeout(800)
    cap.add("Hamburger nav selected", "My Projects")


@when(parsers.parse("click on the project with name '{project_name}'"))
def click_project_by_name(page, project_name, captured_values):
    cap = captured_values
    my_projects = MyProjectsPage(page)
    my_projects.wait_for_pi_page()
    my_projects.click_project(project_name)
    page.wait_for_timeout(600)
    cap.add("Project clicked", project_name)


@when("click on Events link")
def click_events_tab(page, captured_values):
    cap = captured_values
    proj = ProjectDetailsPage(page)
    proj.wait_for_page()
    proj.click_tab("Events")
    page.wait_for_timeout(1000)
    cap.add("Events tab clicked", "true")


@then(parsers.parse("verify on the Events page '{field1}' '{field2}' fields are not blank"))
def verify_events_fields_not_blank(page, field1, field2, captured_values):
    cap = captured_values
    proj = ProjectDetailsPage(page)
    for field in [field1, field2]:
        values = proj.get_events_column_values(field)
        cap.add(f"Events {field} values", str(values))
        assert values, f"Expected '{field}' column to have non-blank values, found none"

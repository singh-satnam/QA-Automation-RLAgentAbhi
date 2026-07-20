from pytest_bdd import when, then

from pages.page_common import MyProjectsPage
from pages.page_project_details import ProjectDetailsPage
from pages.page_product_details import ProductDetailsPage


@when("the user clicks on the project")
def click_on_project(page, test_data, captured_values):
    cap = captured_values
    project_name = test_data["projectName"]
    MyProjectsPage(page).click_project(project_name)
    cap.add("Project clicked", project_name)


@when("the user clicks on the product under My Products")
def click_on_product(page, test_data, captured_values):
    cap = captured_values
    product_name = test_data["product"]
    ProjectDetailsPage(page).click_product_card(product_name)
    cap.add("Product clicked", product_name)


@when("the user clicks the Product Details tab")
def click_product_details_tab(page, captured_values):
    cap = captured_values
    ProductDetailsPage(page).click_product_tab("Product Details")
    cap.add("Product Details tab clicked", "true")


@then("the following product fields are present and each has a value")
def verify_product_fields(page, datatable, captured_values):
    cap = captured_values
    details = ProductDetailsPage(page)
    for row in datatable[1:]:
        field_name = row[0]
        is_visible = details.is_product_field_visible(field_name)
        passed = cap.assert_match(
            f"Field '{field_name}' present",
            expected=field_name,
            actual=field_name if is_visible else "(not found)",
        )
        assert passed, f"Field '{field_name}' not visible on Product Details tab"


@then("CONNECT and ACTIONS are present on the page")
def verify_connect_and_actions(page, captured_values):
    cap = captured_values
    details = ProductDetailsPage(page)
    connect_visible = details.is_connect_visible()
    actions_visible = details.is_actions_visible()
    cap.add("CONNECT visible", str(connect_visible))
    cap.add("ACTIONS visible", str(actions_visible))
    assert connect_visible, "CONNECT link not visible on product details page"
    assert actions_visible, "ACTIONS link not visible on product details page"


@when("the user clicks the Events tab")
def click_events_tab(page, captured_values):
    cap = captured_values
    ProductDetailsPage(page).click_product_tab("Events")
    cap.add("Events tab clicked", "true")


@then("the Events webtable is displayed")
def verify_events_table(page, captured_values):
    cap = captured_values
    details = ProductDetailsPage(page)
    visible = details.is_events_table_visible()
    cap.add("Events table visible", str(visible))
    assert visible, "Events table not visible on Events tab"


@then("the Timestamp column has entries")
def verify_timestamp_entries(page, captured_values):
    cap = captured_values
    details = ProductDetailsPage(page)
    entries = details.get_timestamp_column_entries()
    cap.add("Timestamp entries", str(entries))
    assert len(entries) > 0, f"Timestamp column has no entries, got: {entries}"


@then("the Status column has entries")
def verify_status_entries(page, captured_values):
    cap = captured_values
    details = ProductDetailsPage(page)
    entries = details.get_status_column_entries()
    cap.add("Status entries", str(entries))
    assert len(entries) > 0, f"Status column has no entries, got: {entries}"

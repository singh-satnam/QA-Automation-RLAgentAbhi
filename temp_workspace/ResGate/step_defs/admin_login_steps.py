from pytest_bdd import when, then

from pages.page_common import LoginPage, MyOrganizationsPage


@when("the user signs in as an Admin")
def sign_in_as_admin(page, test_data, captured_values):
    cap = captured_values
    email = test_data["ADMIN_USER"]
    password = test_data["ADMIN_PWD"]
    login = LoginPage(page)
    login.enter_email(email)
    login.enter_password(password)
    cap.add("ADMIN email entered", email)


@then("the admin lands on the My Organizations page")
def verify_my_organizations_page(page, captured_values):
    cap = captured_values
    my_orgs = MyOrganizationsPage(page)

    my_orgs.wait_for_page()

    cap.assert_prerequisite(
        "Admin My Organizations page",
        condition="/admin" in page.url,
        reason=f"Expected URL to contain /admin, got: {page.url}",
        evidence=page.url,
    )

    heading_text = my_orgs.get_heading_text()
    cap.add("Page heading text", heading_text)
    assert cap.assert_match(
        "My Organizations heading displayed",
        expected="My Organizations",
        actual=heading_text,
    ), f"Expected 'My Organizations' in heading, got: {heading_text!r}"

    org_count = my_orgs.get_org_count()
    cap.add("Organization count", org_count)

    for name in my_orgs.get_org_names():
        cap.add_component("Organization", name, group="admin_organizations")

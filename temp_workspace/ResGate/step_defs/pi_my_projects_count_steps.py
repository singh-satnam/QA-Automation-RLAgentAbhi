from pytest_bdd import then

from pages.page_common import MyProjectsPage


@then("the My Projects header displays a project count greater than zero")
def verify_pi_project_count_greater_than_zero(page, captured_values):
    cap = captured_values
    my_projects = MyProjectsPage(page)
    count = my_projects.get_pi_project_count()
    cap.add("PI project count from header", count)
    assert cap.assert_match(
        "My Projects count > 0",
        expected=True,
        actual=count > 0,
    ), f"Expected project count > 0, got: {count}"

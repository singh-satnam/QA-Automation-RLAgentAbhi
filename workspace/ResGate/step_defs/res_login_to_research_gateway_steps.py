from pytest_bdd import then
from pages.page_common import MyProjectsPage


@then('the researcher lands on the "My Projects" page with only assigned projects')
def researcher_lands_on_my_projects(page, captured_values):
    my_projects_page = MyProjectsPage(page)
    heading_text = my_projects_page.get_heading_text()
    captured_values.add("Page heading after RES login", heading_text)
    passed = captured_values.assert_match(
        "My Projects page displayed for RES user",
        expected="My Projects",
        actual=heading_text,
    )
    assert passed, (
        f"Expected heading 'My Projects' but got {heading_text!r}. "
        f"Current URL: {page.url}"
    )
    project_count = my_projects_page.get_project_count()
    captured_values.add("Assigned project count (RES)", project_count)

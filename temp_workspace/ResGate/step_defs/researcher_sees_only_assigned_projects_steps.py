from pytest_bdd import parsers, then

from pages.page_common import MyProjectsPage


@then("the user lands on the My Projects page successfully")
def user_lands_on_my_projects(page, captured_values):
    cap = captured_values
    my_projects = MyProjectsPage(page)
    my_projects.wait_for_page()
    cap.add("My Projects page URL", page.url)


@then(parsers.parse('the project card "{project_name}" is displayed'))
def project_card_displayed(page, project_name, captured_values):
    cap = captured_values
    my_projects = MyProjectsPage(page)
    my_projects.wait_for_project_visible(project_name)
    cap.add("Project card displayed", project_name)

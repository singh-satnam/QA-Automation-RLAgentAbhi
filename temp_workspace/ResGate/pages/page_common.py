import re

from playwright.sync_api import expect

from pages.base_page import BasePage


class LoginPage(BasePage):
    def navigate(self, url):
        self.goto(url)
        self.wait_visible(self.loc["login"]["email_input"])

    def enter_email(self, email):
        self.page.locator(self.loc["login"]["email_input"]).fill(email)

    def enter_password(self, password):
        self.page.locator(self.loc["login"]["password_input"]).fill(password)

    def click_sign_in(self):
        self.page.locator(self.loc["login"]["sign_in_btn"]).click()


class MyOrganizationsPage(BasePage):
    def wait_for_page(self, timeout=20000):
        self.wait_visible(self.loc["my_organizations"]["page_heading"], timeout=timeout)

    def get_heading_text(self):
        el = self.page.locator(self.loc["my_organizations"]["page_heading"]).first
        return el.inner_text(timeout=10000).strip()

    def get_org_count(self):
        import re
        count_el = self.page.locator(self.loc["my_organizations"]["org_count_heading"]).first
        count_text = count_el.inner_text(timeout=10000)
        match = re.search(r'\d+', count_text)
        return int(match.group()) if match else 0

    def get_org_names(self):
        all_h3 = self.page.locator("h3").all()
        names = []
        for h in all_h3:
            try:
                text = h.inner_text(timeout=2000).strip()
                if text and "My Organizations" not in text:
                    names.append(text)
            except Exception:
                pass
        return names


class MyProjectsPage(BasePage):
    def wait_for_page(self, timeout=20000):
        self.wait_visible(self.loc["my_projects"]["page_heading"], timeout=timeout)

    def get_breadcrumb_text(self):
        el = self.page.locator(self.loc["my_projects"]["breadcrumb_item"]).first
        return el.inner_text(timeout=10000).strip()

    def get_project_count(self):
        heading = self.page.locator(self.loc["my_projects"]["page_heading"]).first
        heading_text = heading.inner_text(timeout=10000)
        match = re.search(r'\(\s*(\d+)\s*\)', heading_text)
        if match:
            return int(match.group(1))
        return len(self.get_project_names())

    def get_project_names(self):
        all_h3 = self.page.locator("h3").all()
        names = []
        for h in all_h3:
            try:
                text = h.inner_text(timeout=2000).strip()
                if text and "My Projects" not in text and not re.fullmatch(
                    r'\(\s*\d+\s*\)', text
                ):
                    names.append(text)
            except Exception:
                pass
        return names

    def click_add_new(self):
        import re
        # Matches both native <button> (PI page) and <div role="button"> (Admin page)
        self.page.get_by_role("button", name=re.compile(r"Add New", re.IGNORECASE)).first.click()

    def wait_for_project_visible(self, project_name, timeout=30000):
        self.wait_visible(f"h3:has-text('{project_name}')", timeout=timeout)

    def click_project(self, project_name):
        self.page.locator(f"h3:has-text('{project_name}')").click()

    def wait_for_pi_page(self, timeout=20000):
        self.wait_visible(self.loc["pi_my_projects"]["page_heading"], timeout=timeout)

    def get_pi_project_count(self):
        heading = self.page.locator(self.loc["pi_my_projects"]["page_heading"]).first
        heading_text = heading.inner_text(timeout=10000)
        match = re.search(r'\(\s*(\d+)\s*\)', heading_text)
        if match:
            return int(match.group(1))
        return len(self.get_project_names())


class HeaderNav(BasePage):
    def click_username_in_header(self):
        self.page.locator(self.loc["logout"]["username_menu_btn"]).click()

    def click_sign_out(self):
        self.page.locator(self.loc["logout"]["sign_out_item"]).click()

    def click_hamburger_menu(self):
        self.page.locator(self.loc["admin_nav"]["hamburger_btn"]).click()

    def click_nav_item(self, label):
        self.page.locator(f"nav button:has-text('{label}')").click()


class LogoutPage(BasePage):
    def wait_for_page(self, timeout=15000):
        self.wait_visible(self.loc["logout"]["click_here_login_btn"], timeout=timeout)

    def is_login_button_visible(self):
        return self.page.locator(self.loc["logout"]["click_here_login_btn"]).is_visible()

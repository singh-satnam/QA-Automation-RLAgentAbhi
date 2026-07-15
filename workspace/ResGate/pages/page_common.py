from playwright.sync_api import expect
from pages.base_page import BasePage


class LoginPage(BasePage):
    def navigate(self, url):
        self.goto(url, timeout=60000)

    def dismiss_session_expired_alert(self):
        close_btn = self.page.locator(self.loc["login"]["error_close"])
        try:
            expect(close_btn.first).to_be_visible(timeout=5000)
            close_btn.first.click()
        except Exception:
            pass

    def enter_email(self, email):
        el = self.page.locator(self.loc["login"]["email_input"])
        expect(el).to_be_visible(timeout=15000)
        el.fill(email)

    def enter_password(self, password):
        el = self.page.locator(self.loc["login"]["password_input"])
        expect(el).to_be_visible(timeout=15000)
        el.fill(password)

    def click_sign_in(self):
        btn = self.page.locator(self.loc["login"]["sign_in_button"])
        expect(btn).to_be_visible(timeout=10000)
        btn.click()

    def get_error_text(self):
        alert = self.page.locator(self.loc["login"]["error_alert"])
        try:
            expect(alert.first).to_be_visible(timeout=5000)
            return alert.first.inner_text().strip()
        except Exception:
            return ""


class MyOrganizationsPage(BasePage):
    def is_displayed(self):
        heading = self.page.locator(self.loc["my_organizations"]["page_heading_partial"])
        try:
            expect(heading.first).to_be_visible(timeout=20000)
            return True
        except Exception:
            return False

    def get_heading_text(self):
        heading = self.page.locator(self.loc["my_organizations"]["page_heading_partial"])
        expect(heading.first).to_be_visible(timeout=20000)
        return heading.first.inner_text().strip()

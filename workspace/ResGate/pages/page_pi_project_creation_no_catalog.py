from playwright.sync_api import expect
from pages.base_page import BasePage


class ProjectCreationPage(BasePage):
    def is_displayed(self):
        heading = self.page.locator(self.loc["create_project"]["page_heading"])
        try:
            expect(heading.first).to_be_visible(timeout=20000)
            return True
        except Exception:
            return False

    def fill_project_name(self, value):
        el = self.page.locator(self.loc["create_project"]["project_name_input"])
        expect(el).to_be_visible(timeout=15000)
        el.fill(value)

    def fill_project_description(self, value):
        el = self.page.locator(self.loc["create_project"]["project_description_input"])
        expect(el).to_be_visible(timeout=15000)
        el.fill(value)

    def fill_budget(self, value):
        el = self.page.locator(self.loc["create_project"]["budget_input"])
        expect(el).to_be_visible(timeout=15000)
        el.fill(str(value))

    def select_account(self, account_name):
        # Angular custom radio: actual <input> is off-screen; trigger via JS click
        radio = self.page.get_by_role("radio", name=account_name, exact=True)
        radio.wait_for(state="attached", timeout=15000)
        radio.evaluate("el => el.click()")

    def click_create_project(self):
        btn = self.page.locator(self.loc["create_project"]["submit_button"])
        expect(btn).to_be_enabled(timeout=30000)
        btn.click()

import re

from playwright.sync_api import expect

from pages.base_page import BasePage


class CreateProjectPage(BasePage):
    def wait_for_page(self, timeout=20000):
        self.wait_visible(self.loc["create_project"]["page_heading"], timeout=timeout)

    def fill_project_name(self, name):
        self.page.locator(self.loc["create_project"]["project_name_input"]).fill(name)

    def fill_project_description(self, description):
        self.page.locator(self.loc["create_project"]["project_description_input"]).fill(description)

    def fill_budget(self, budget):
        self.page.locator(self.loc["create_project"]["budget_input"]).fill(str(budget))

    def select_account(self, account_name):
        # Radio input is CSS-hidden; click the visible label.
        # Desktop labels use for="accountRadio<n>"; mobile labels use random Angular IDs.
        self.page.locator("label[for^='accountRadio']").filter(has_text=account_name).click()

    def select_user(self, user_display):
        # Two checkbox sets rendered (desktop + mobile). Desktop labels use for="userCheckbox<n>".
        # Mobile labels use for="<email>". Scoping to [for^='userCheckbox'] targets desktop only.
        self.page.locator("label[for^='userCheckbox']").filter(has_text=user_display).click()

    def select_catalog_type(self, catalog_partial):
        # Strip dynamic count segment ("- N products are available.") so the
        # match is stable regardless of how many products the env exposes.
        stable = re.split(r'\s*-\s*\d+\s', catalog_partial)[0].strip()
        self.page.locator("label.selection-label").filter(has_text=stable).first.click()

    def click_create_project(self, timeout=15000):
        btn = self.page.locator(self.loc["create_project"]["create_project_btn"])
        # Angular's change detection needs a cycle after the last label/checkbox interaction
        # before the form validity propagates to the button's disabled state.
        self.page.wait_for_timeout(500)
        expect(btn).to_be_enabled(timeout=timeout)
        btn.click()

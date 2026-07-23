import re

from pages.base_page import BasePage


class StudiesPage(BasePage):
    def wait_for_page(self, timeout=20000):
        self.wait_visible(self.loc["studies_page"]["page_heading"], timeout=timeout)

    def click_create_study(self):
        btn = self.page.get_by_role(
            "button", name=re.compile(r"create\s*(new\s*)?study", re.IGNORECASE)
        )
        btn.wait_for(state="visible", timeout=10000)
        btn.click()


class CreateStudyPage(BasePage):
    def wait_for_create_page(self, timeout=20000):
        self.wait_visible(self.loc["create_study_form"]["page_heading"], timeout=timeout)

    def get_heading(self):
        return (
            self.page.locator(self.loc["create_study_form"]["page_heading"])
            .inner_text(timeout=10000)
            .strip()
        )

    def fill_study_name(self, name):
        self.page.locator(self.loc["create_study_form"]["study_name_input"]).fill(name)

    def fill_description(self, description):
        self.page.locator(self.loc["create_study_form"]["description_input"]).fill(description)

    def select_study_type(self, study_type):
        self.page.locator(self.loc["create_study_form"]["study_type_select"]).select_option(
            label=study_type
        )

    def select_access_level(self, access_level):
        self.page.locator(self.loc["create_study_form"]["access_level_select"]).select_option(
            label=access_level
        )

    def click_next(self):
        btn = self.page.locator("button:has-text('Next'):visible:not([disabled])")
        btn.wait_for(state="visible", timeout=10000)
        btn.click()

    def fill_bucket_name(self, bucket_name):
        self.page.locator(self.loc["create_study_form"]["bucket_name_input"]).fill(bucket_name)

    def select_project_account(self, account_name):
        select = self.page.locator(self.loc["create_study_form"]["project_account_select"])
        select.wait_for(state="visible", timeout=15000)
        self.page.wait_for_timeout(1500)
        select.select_option(label=account_name)
        self.page.wait_for_timeout(1200)

    def click_project_checkbox_by_name(self, project_name):
        label = self.page.locator(
            f'{self.loc["create_study_form"]["project_checkbox_label"]}:has-text("{project_name}")'
        )
        label.wait_for(state="visible", timeout=15000)
        label.click()

    def click_register_study(self):
        btn = self.page.locator(self.loc["create_study_form"]["register_study_btn"])
        btn.wait_for(state="visible", timeout=10000)
        btn.click()

    def get_success_toast_text(self, timeout=15000):
        alert = self.page.locator(self.loc["success_toast"]["alert"])
        alert.wait_for(state="visible", timeout=timeout)
        return alert.inner_text(timeout=5000).strip()

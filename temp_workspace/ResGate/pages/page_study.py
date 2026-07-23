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

    def search_study(self, query):
        search = self.page.locator(self.loc["study_details_page"]["search_input"])
        search.wait_for(state="visible", timeout=10000)
        search.fill(query)
        self.page.wait_for_timeout(800)

    def click_study_card_by_prefix(self, prefix):
        card = self.page.locator(
            f"div[aria-label*='Open study: {prefix}']"
        ).first
        card.wait_for(state="visible", timeout=15000)
        card.click()
        self.page.wait_for_timeout(800)


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


class StudyDetailsPage(BasePage):
    def is_tab_present(self, tab_name):
        return self.is_visible(f"[role='tab']:has-text('{tab_name}')")

    def click_tab(self, tab_name):
        tab = self.page.locator(f"[role='tab']:has-text('{tab_name}')")
        tab.wait_for(state="visible", timeout=10000)
        tab.click()
        self.page.wait_for_timeout(600)

    def get_field_value(self, field_label):
        value_el = self.page.locator(
            f"[role='tabpanel'].active label.product-key-txt:has-text('{field_label}') + *"
        )
        value_el.wait_for(state="visible", timeout=10000)
        return value_el.inner_text(timeout=5000).strip()

    def click_delete_action(self):
        btn = self.page.locator(self.loc["study_details_page"]["delete_action_btn"])
        btn.wait_for(state="visible", timeout=10000)
        btn.click()
        self.page.wait_for_timeout(600)

    def is_delete_dialog_visible(self):
        return self.is_visible(self.loc["study_details_page"]["delete_dialog"])

    def check_delete_confirmation_checkbox(self):
        cb = self.page.locator(self.loc["study_details_page"]["delete_dialog_checkbox"])
        cb.wait_for(state="visible", timeout=10000)
        cb.check()

    def click_delete_in_dialog(self):
        btn = self.page.locator(self.loc["study_details_page"]["delete_dialog_btn"])
        btn.wait_for(state="visible", timeout=10000)
        btn.click()

    def get_confirmation_toast_text(self, timeout=15000):
        alert = self.page.locator(self.loc["success_toast"]["alert"])
        alert.wait_for(state="visible", timeout=timeout)
        return alert.inner_text(timeout=5000).strip()

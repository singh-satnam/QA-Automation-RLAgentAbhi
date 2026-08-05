import re

from pages.base_page import BasePage


class CreateOrganizationPage(BasePage):
    def wait_for_page(self, timeout=15000):
        self.wait_visible(self.loc["create_organization"]["page_heading"], timeout=timeout)

    def fill_org_name(self, name):
        self.page.locator(self.loc["create_organization"]["org_name_input"]).fill(name)

    def fill_org_description(self, desc):
        self.page.locator(self.loc["create_organization"]["org_description_input"]).fill(desc)

    def click_add_users_dropdown(self):
        self.page.locator("div.add-new-btn-trigger").filter(
            has_text=re.compile(r"^Add Users$")
        ).first.click()

    def is_add_user_dialog_visible(self):
        return self.is_visible(self.loc["add_user_dialog"]["heading"])

    def fill_new_user_email(self, email):
        self.page.locator(self.loc["add_user_dialog"]["email_input"]).fill(email)

    def fill_new_user_first_name(self, name):
        self.page.locator(self.loc["add_user_dialog"]["first_name_input"]).fill(name)

    def fill_new_user_last_name(self, name):
        self.page.locator(self.loc["add_user_dialog"]["last_name_input"]).fill(name)

    def select_new_user_role(self, role):
        self.page.locator(self.loc["add_user_dialog"]["role_select"]).select_option(role)

    def click_add_user_in_dialog(self):
        self.page.locator(self.loc["add_user_dialog"]["add_user_btn"]).click()

    def select_user_checkbox_by_email(self, email):
        # Angular hides native checkbox; click label to trigger selection
        self.page.locator("label.selection-label").filter(has_text=email).first.click()

    def click_create_org(self):
        self.page.locator(self.loc["create_organization"]["create_org_btn"]).click()


class OrgManagementPage(BasePage):
    def wait_for_page(self, timeout=20000):
        self.wait_visible(self.loc["my_organizations"]["page_heading"], timeout=timeout)

    def is_org_visible(self, org_name_fragment):
        return self.is_visible(f"div.organization-card h3:has-text('{org_name_fragment}')")

    def wait_for_org_visible(self, org_name_fragment, timeout=30000):
        self.wait_visible(
            f"div.organization-card h3:has-text('{org_name_fragment}')",
            timeout=timeout,
        )

    def click_actions_for_org(self, org_name_fragment):
        self.page.locator("div.organization-card").filter(
            has_text=org_name_fragment
        ).locator("button.org-card-menu-trigger").first.click()

    def click_delete_option(self):
        self.page.locator(self.loc["org_card"]["delete_option"]).click()

    def check_delete_confirmation_checkbox(self):
        self.page.locator(self.loc["delete_org_dialog"]["confirm_checkbox"]).check()

    def click_delete_confirm_button(self):
        self.page.locator(self.loc["delete_org_dialog"]["delete_btn"]).click()

    def get_success_toast_text(self, timeout=10000):
        el = self.wait_visible(self.loc["success_toast"]["alert"], timeout=timeout)
        return el.inner_text(timeout=5000).strip()

    def wait_for_fresh_toast(self, timeout=20000):
        """Wait for any existing toast to clear, then wait for the next one."""
        toast_loc = self.page.locator("[role='alert'], div.toast-title").first
        try:
            toast_loc.wait_for(state="hidden", timeout=8000)
        except Exception:
            pass
        toast_loc.wait_for(state="visible", timeout=timeout)
        return toast_loc.inner_text(timeout=5000).strip()

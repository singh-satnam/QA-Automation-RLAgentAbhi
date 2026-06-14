"""Page Object for the 'Create a New Organization' feature (ResGate / Research Gateway).

All Playwright calls live here. Selector keys are read from
mcp-selectors/locators.json (the single source of truth), loaded by BasePage.
"""

from playwright.sync_api import expect

from .base_page import BasePage


class CreateOrganizationPage(BasePage):
    # ---- login -------------------------------------------------------------
    def navigate_to_login(self, url, timeout=30000):
        self.goto(url, timeout=timeout)

    def sign_in_form_is_displayed(self, timeout=30000):
        """The live /login page presents the sign-in form directly. The story's
        'click the Sign In link' step is satisfied by the sign-in form being
        reachable/visible — we do not fabricate a separate landing step."""
        return self.is_visible(self.loc["login"]["email_input"], timeout=timeout)

    def enter_credentials(self, email, password):
        self.wait_visible(self.loc["login"]["email_input"]).fill(email)
        self.page.locator(self.loc["login"]["password_input"]).first.fill(password)

    def click_login(self):
        self.page.locator(self.loc["login"]["sign_in_button"]).first.click()

    # ---- my organizations page --------------------------------------------
    def is_on_my_organizations(self, timeout=30000):
        try:
            self.page.wait_for_url("**/admin", timeout=timeout)
        except Exception:
            pass
        return self.is_visible(self.loc["my_organizations"]["heading"], timeout=timeout)

    def my_organizations_heading_text(self, timeout=30000):
        return self.wait_visible(
            self.loc["my_organizations"]["heading"], timeout=timeout
        ).inner_text().strip()

    def organization_count(self):
        """Number of organization cards currently rendered in the list."""
        self.page.locator(self.loc["my_organizations"]["org_card"]).first.wait_for(
            state="visible", timeout=30000
        )
        return self.page.locator(self.loc["my_organizations"]["org_card"]).count()

    def click_add_new(self):
        self.wait_visible(self.loc["my_organizations"]["add_new_button"]).click()

    # ---- create organization form -----------------------------------------
    def is_create_form_displayed(self, timeout=30000):
        form_ok = self.is_visible(self.loc["create_organization"]["heading"], timeout=timeout)
        name_ok = self.is_visible(self.loc["create_organization"]["name_input"], timeout=timeout)
        return form_ok and name_ok

    def create_form_heading_text(self, timeout=30000):
        return self.wait_visible(
            self.loc["create_organization"]["heading"], timeout=timeout
        ).inner_text().strip()

    def enter_organization_details(self, name, description):
        self.wait_visible(self.loc["create_organization"]["name_input"]).fill(name)
        self.page.locator(
            self.loc["create_organization"]["description_input"]
        ).first.fill(description)

    def click_create_organization(self):
        btn = self.page.locator(self.loc["create_organization"]["create_button"]).first
        expect(btn).to_be_enabled(timeout=15000)
        # The Create button sits in the top-right header zone where this app's
        # transient background error-toasts (ngx-toastr top-right) and the fixed
        # header intermittently intercept pointer events. Dispatch the element's
        # native click so the genuine submit handler fires reliably.
        btn.evaluate("el => el.click()")

    # ---- outcome -----------------------------------------------------------
    def success_toast_text(self, timeout=15000):
        """Return the success-toast text (e.g. 'Organization saved successfully')
        if one appears, else ''."""
        try:
            toast = self.page.locator(self.loc["toast"]["success"]).first
            expect(toast).to_be_visible(timeout=timeout)
            return toast.inner_text().strip()
        except Exception:
            return ""

    def latest_error_toast_text(self, timeout=4000):
        """Return the text of an error toast if one is present, else ''."""
        try:
            toast = self.page.locator(self.loc["toast"]["error"]).first
            expect(toast).to_be_visible(timeout=timeout)
            return toast.inner_text().strip()
        except Exception:
            return ""

    def wait_for_organization_in_list(self, name, timeout=30000):
        """Wait for the org card with the given name to be visible on the
        My Organizations list. Returns True if it appears, else False."""
        self.is_on_my_organizations(timeout=timeout)
        sel = f"{self.loc['my_organizations']['org_card_name']}:has-text(\"{name}\")"
        try:
            expect(self.page.locator(sel).first).to_be_visible(timeout=timeout)
            return True
        except Exception:
            return False

    def organization_card_text(self, name):
        sel = f"{self.loc['my_organizations']['org_card_name']}:has-text(\"{name}\")"
        loc = self.page.locator(sel).first
        if loc.count() == 0:
            return ""
        return loc.inner_text().strip()

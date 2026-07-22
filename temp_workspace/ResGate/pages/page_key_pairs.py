import re

from pages.base_page import BasePage


class KeyPairsPage(BasePage):
    def wait_for_page(self, timeout=20000):
        self.wait_visible(self.loc["key_pairs"]["page_heading"], timeout=timeout)

    def click_create_new(self):
        self.page.get_by_role(
            "button", name=re.compile("create new key pair", re.IGNORECASE)
        ).click()

    def is_create_dialog_visible(self):
        return self.is_visible(self.loc["create_key_pair_dialog"]["heading"])

    def select_project_by_index(self, index):
        """Select the nth non-disabled project option (1-based). Returns option text."""
        select = self.page.locator(self.loc["create_key_pair_dialog"]["project_select"])
        options = select.evaluate(
            "el => Array.from(el.options)"
            ".filter(o => !o.disabled)"
            ".map(o => ({value: o.value, text: o.text.trim()}))"
        )
        target = options[index - 1] if len(options) >= index else options[-1]
        select.select_option(value=target["value"])
        return target["text"]

    def fill_key_pair_name(self, name):
        self.page.locator(self.loc["create_key_pair_dialog"]["name_input"]).fill(name)

    def select_file_format_pem(self):
        self.page.locator(
            self.loc["create_key_pair_dialog"]["file_format_select"]
        ).select_option(label="pem ( For use with OpenSSH )")

    def click_create_key_pair_button(self):
        from playwright.sync_api import expect
        btn = self.page.get_by_role("button", name="Create Key Pair")
        expect(btn).to_be_enabled(timeout=10000)
        btn.click()

    def wait_for_key_pair_row(self, name, timeout=30000):
        self.wait_visible(
            f"table tbody tr td:first-child:has-text('{name}')", timeout=timeout
        )

    def is_key_pair_visible(self, name):
        return self.is_visible(f"table tbody tr td:first-child:has-text('{name}')")

    def click_actions_for_key_pair(self, name):
        row = self.page.locator("table tbody tr").filter(has_text=name)
        row.locator(self.loc["key_pairs"]["actions_btn"]).click()

    def click_delete_option(self):
        self.page.locator(self.loc["key_pairs"]["delete_menuitem"]).click()

    def is_delete_modal_visible(self):
        return self.is_visible(self.loc["delete_key_pair_dialog"]["heading"])

    def click_confirm_delete(self):
        self.page.get_by_role("button", name="Delete").click()

    def get_toast_text(self):
        toast = self.page.locator(self.loc["success_toast"]["alert"])
        toast.wait_for(state="visible", timeout=15000)
        return toast.inner_text().strip()

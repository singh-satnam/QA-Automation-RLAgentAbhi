from pages.base_page import BasePage


class AccountSettingsPage(BasePage):
    def click_account_icon_and_select_settings(self):
        self.page.locator(self.loc["logout"]["username_menu_btn"]).click()
        self.page.locator(self.loc["account_settings"]["settings_menu_item"]).click()

    def wait_for_page(self, timeout=20000):
        self.wait_visible(self.loc["account_settings"]["back_to_orgs_link"], timeout=timeout)

    def wait_for_popup(self, timeout=10000):
        self.wait_visible(self.loc["account_settings"]["popup_container"], timeout=timeout)

    def is_project_accounts_table_visible(self, timeout=15000):
        try:
            self.wait_visible(self.loc["account_settings"]["project_accounts_table"], timeout=timeout)
            return self.page.locator(self.loc["account_settings"]["project_accounts_table"]).is_visible()
        except Exception:
            return False

    def get_project_accounts_table_headers(self):
        headers = self.page.locator(self.loc["account_settings"]["table_headers"]).all()
        result = []
        for h in headers:
            try:
                text = h.inner_text(timeout=2000).strip()
                if text:
                    result.append(text)
            except Exception:
                pass
        return result

    def click_link_icon_under_account_name(self):
        self.page.locator(self.loc["account_settings"]["account_name_link_icon"]).first.click()

    def is_standard_account_popup_visible(self):
        return self.page.locator(self.loc["account_settings"]["popup_container"]).is_visible()

    def get_popup_field_labels(self):
        self.wait_visible(self.loc["account_settings"]["popup_table_headers"], timeout=10000)
        headers = self.page.locator(self.loc["account_settings"]["popup_table_headers"]).all()
        result = []
        for h in headers:
            try:
                text = h.inner_text(timeout=2000).strip()
                if text:
                    result.append(text)
            except Exception:
                pass
        return result

    def click_close_popup(self):
        self.page.locator(self.loc["account_settings"]["popup_close_btn"]).click()

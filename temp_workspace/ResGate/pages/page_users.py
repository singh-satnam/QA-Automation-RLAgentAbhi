from pages.base_page import BasePage


class UsersPage(BasePage):
    def wait_for_page(self, timeout=20000):
        self.wait_visible(self.loc["users_page"]["page_heading"], timeout=timeout)

    def is_search_bar_visible(self):
        return self.page.locator(self.loc["users_page"]["search_input"]).is_visible()

    def is_add_new_visible(self):
        return self.page.locator(self.loc["users_page"]["add_new_trigger"]).is_visible()

    def is_filter_trigger_visible(self, label):
        return self.page.locator(f".filter-dropdown-trigger:has-text('{label}')").is_visible()

    def is_reset_filters_visible(self):
        return self.page.locator(self.loc["users_page"]["reset_filters_btn"]).is_visible()

    def is_toggle_visible(self):
        return self.page.locator(self.loc["users_page"]["active_users_toggle"]).is_visible()

    def search(self, text):
        inp = self.page.locator(self.loc["users_page"]["search_input"])
        inp.click()
        inp.press_sequentially(text, delay=50)
        self.page.wait_for_timeout(1000)

    def get_visible_user_names(self):
        els = self.page.locator(self.loc["users_page"]["user_name_text"]).all()
        names = []
        for el in els:
            try:
                names.append(el.inner_text(timeout=2000).strip())
            except Exception:
                pass
        return names

    def click_filter_dropdown(self, label):
        self.page.locator(f".filter-dropdown-trigger:has-text('{label}')").click()
        self.page.wait_for_timeout(400)

    def select_filter_option(self, option_text):
        self.page.locator(f"span.filter-dropdown-option:has-text('{option_text}')").first.click()
        self.page.wait_for_timeout(800)

    def click_reset_filters(self):
        self.page.locator(self.loc["users_page"]["reset_filters_btn"]).click()
        self.page.wait_for_timeout(500)

    def get_visible_user_orgs(self):
        els = self.page.locator(self.loc["users_page"]["user_org"]).all()
        orgs = []
        for el in els:
            try:
                orgs.append(el.inner_text(timeout=2000).strip())
            except Exception:
                pass
        return orgs

    def get_visible_user_roles(self):
        els = self.page.locator(self.loc["users_page"]["user_role"]).all()
        roles = []
        for el in els:
            try:
                roles.append(el.inner_text(timeout=2000).strip())
            except Exception:
                pass
        return roles

    def get_visible_statuses(self):
        try:
            self.page.wait_for_selector(
                self.loc["users_page"]["user_active_txt"], state="visible", timeout=8000
            )
        except Exception:
            pass
        els = self.page.locator(self.loc["users_page"]["user_active_txt"]).all()
        statuses = []
        for el in els:
            try:
                statuses.append(el.inner_text(timeout=2000).strip())
            except Exception:
                pass
        return statuses

    def get_visible_card_count(self):
        return self.page.locator(self.loc["users_page"]["user_card"]).count()

    def click_active_users_toggle(self):
        self.page.locator(self.loc["users_page"]["active_users_toggle"]).click()
        self.page.wait_for_timeout(2000)

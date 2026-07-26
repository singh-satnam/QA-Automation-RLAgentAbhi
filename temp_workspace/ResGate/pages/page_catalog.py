import re

from pages.base_page import BasePage

_MENU = ".mat-mdc-menu-panel.filter-dd"
_ITEM_TEXT = f"{_MENU} [role='menuitem'] span.mat-mdc-menu-item-text"


class CatalogPage(BasePage):
    def wait_for_page(self, timeout=20000):
        self.wait_visible(self.loc["catalog"]["page_heading"], timeout=timeout)

    def get_title_text(self):
        el = self.page.locator(self.loc["catalog"]["page_heading"]).first
        return el.inner_text(timeout=10000).strip()

    def get_catalog_count(self):
        text = self.get_title_text()
        match = re.search(r'\(\s*(\d+)\s*\)', text)
        return int(match.group(1)) if match else 0

    def is_view_dropdown_visible(self):
        return self.page.locator(self.loc["catalog"]["view_dropdown_trigger"]).is_visible()

    def is_search_bar_visible(self):
        return self.page.locator(self.loc["catalog"]["search_input"]).is_visible()

    def click_view_dropdown(self):
        self.page.locator(self.loc["catalog"]["view_dropdown_trigger"]).click()
        self.page.wait_for_selector(_MENU, state="visible", timeout=5000)

    def is_view_dropdown_open(self):
        trigger = self.page.locator(self.loc["catalog"]["view_dropdown_trigger"])
        return trigger.get_attribute("aria-expanded") == "true"

    def get_view_dropdown_options(self):
        items = self.page.locator(_ITEM_TEXT).all()
        return [item.inner_text().strip() for item in items if item.inner_text().strip()]

    def is_view_option_present(self, option):
        return self.page.locator(f"{_MENU} [role='menuitem']:has-text('{option}')").count() > 0

    def select_view_option(self, option):
        self.page.locator(f"{_MENU} [role='menuitem']:has-text('{option}')").click()

    def get_selected_filter(self):
        text = self.page.locator(self.loc["catalog"]["current_filter_label"]).inner_text(timeout=5000).strip()
        if "View :" in text:
            return text.split("View :")[1].strip().split("\n")[0].strip()
        return text

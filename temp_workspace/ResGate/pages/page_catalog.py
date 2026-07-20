import re

from pages.base_page import BasePage


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

    def is_view_dropdown_open(self):
        return self.page.locator("div.custom-options").evaluate(
            "el => window.getComputedStyle(el).display !== 'none'"
        )

    def get_view_dropdown_options(self):
        options = self.page.locator("span.custom-option").all()
        return [opt.get_attribute("title") for opt in options if opt.get_attribute("title")]

    def is_view_option_present(self, option):
        return self.page.locator(f"span.custom-option[title='{option}']").count() > 0

    def select_view_option(self, option):
        self.page.locator(f"span.custom-option[title='{option}']").click()

    def get_selected_filter(self):
        el = self.page.locator(self.loc["catalog"]["current_filter_label"])
        return el.get_attribute("title") or el.inner_text(timeout=5000).strip()

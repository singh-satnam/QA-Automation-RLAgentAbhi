from playwright.sync_api import expect

from pages.base_page import BasePage


class ProductDetailsPage(BasePage):
    def _active_panel(self):
        return self.page.locator(self.loc["product_details_product_page"]["active_panel"])

    def click_product_tab(self, tab_name):
        self.page.locator(
            f"{self.loc['product_details_product_page']['tab_btn']}:has-text('{tab_name}')"
        ).click()

    def is_product_field_visible(self, field_name):
        try:
            panel = self._active_panel()
            el = panel.get_by_text(field_name, exact=False).first
            expect(el).to_be_visible(timeout=5000)
            return True
        except Exception:
            return False

    def is_connect_visible(self):
        return self.is_visible(self.loc["product_details_product_page"]["connect_link"])

    def is_actions_visible(self):
        return self.is_visible(self.loc["product_details_product_page"]["actions_link"])

    def is_events_table_visible(self):
        return self.is_visible(self.loc["product_details_product_page"]["events_table"])

    def get_timestamp_column_entries(self):
        cells = self.page.locator(
            self.loc["product_details_product_page"]["timestamp_cells"]
        ).all()
        result = []
        for c in cells:
            try:
                text = c.inner_text(timeout=3000).strip()
                if text:
                    result.append(text)
            except Exception:
                pass
        return result

    def get_status_column_entries(self):
        cells = self.page.locator(
            self.loc["product_details_product_page"]["status_cells"]
        ).all()
        result = []
        for c in cells:
            try:
                text = c.inner_text(timeout=3000).strip()
                if text:
                    result.append(text)
            except Exception:
                pass
        return result

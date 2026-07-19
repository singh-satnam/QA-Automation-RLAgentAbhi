import re

from playwright.sync_api import expect

from pages.base_page import BasePage


class ProjectDetailsPage(BasePage):
    def wait_for_page(self, timeout=20000):
        self.wait_visible(self.loc["project_details_page"]["project_status_text"], timeout=timeout)

    def _primary_tablist(self):
        return self.page.locator(self.loc["project_details_page"]["tab_list"]).first

    def get_visible_tabs(self):
        tabs = self._primary_tablist().locator("[role='tab']").all()
        result = []
        for t in tabs:
            try:
                text = re.sub(r"\s+", " ", t.inner_text(timeout=2000)).strip()
                if text:
                    result.append(text)
            except Exception:
                pass
        return result

    def click_tab(self, tab_name):
        self._primary_tablist().locator(f"[role='tab']:has-text('{tab_name}')").click()

    def is_field_visible(self, field_name):
        try:
            panel = self.page.locator(".mat-mdc-tab-body-active")
            el = panel.get_by_text(field_name, exact=False).first
            expect(el).to_be_visible(timeout=5000)
            return True
        except Exception:
            return False

    def is_actions_section_visible(self):
        return self.is_visible(self.loc["project_details_page"]["actions_heading"])

    def is_action_button_visible(self, action_name):
        try:
            btn = self.page.locator(
                f"{self.loc['project_details_page']['action_link_btn']}:has-text('{action_name}')"
            ).first
            expect(btn).to_be_visible(timeout=5000)
            return True
        except Exception:
            return False

    def click_action_button(self, action_name):
        self.page.locator(
            f"{self.loc['project_details_page']['action_link_btn']}:has-text('{action_name}')"
        ).first.click()

    def get_budget_value_text(self):
        self.page.wait_for_timeout(500)
        result = self.page.evaluate("""() => {
            const panels = document.querySelectorAll('.mat-mdc-tab-body-active');
            for (const panel of panels) {
                const divs = Array.from(panel.querySelectorAll('div'));
                for (const div of divs) {
                    const children = Array.from(div.children);
                    if (children.length >= 2 &&
                            children[0].textContent.trim() === 'Budget') {
                        return children[children.length - 1].textContent.trim();
                    }
                }
            }
            return '';
        }""")
        if not result:
            raise AssertionError("Budget field value not found in active tab panel")
        return result

    def fill_add_budget_amount(self, amount):
        input_el = self.page.locator(self.loc["add_budget_dialog"]["amount_input"])
        input_el.click()
        input_el.press("Control+a")
        input_el.press("Delete")
        input_el.press_sequentially(str(amount))

    def click_dialog_submit(self):
        self.page.locator(self.loc["add_budget_dialog"]["submit_btn"]).click()

    def wait_for_success_toast(self, timeout=10000):
        alert_loc = self.page.locator(self.loc["success_toast"]["alert"])
        expect(alert_loc).to_be_visible(timeout=timeout)
        return alert_loc.inner_text(timeout=5000).strip()

    def wait_for_toast_gone(self, timeout=30000):
        alert_loc = self.page.locator(self.loc["success_toast"]["alert"])
        try:
            expect(alert_loc).to_be_hidden(timeout=timeout)
        except Exception:
            close_btn = self.page.locator("button.toast-close-button, button[aria-label='Close'], .toast-close-button").first
            if close_btn.is_visible():
                close_btn.click()
            expect(alert_loc).to_be_hidden(timeout=5000)

    def click_manage_assigned_users(self):
        panel = self.page.locator(".mat-mdc-tab-body-active")
        panel.locator(self.loc["assigned_users_section"]["manage_btn"]).first.click()

    def get_assigned_users_list(self):
        panel = self.page.locator(".mat-mdc-tab-body-active")
        items = panel.locator(self.loc["assigned_users_section"]["user_selection_label"]).all()
        result = []
        for item in items:
            try:
                result.append(item.inner_text(timeout=3000).strip())
            except Exception:
                pass
        return result

    def click_cancel_assigned_users(self):
        panel = self.page.locator(".mat-mdc-tab-body-active")
        panel.locator(self.loc["assigned_users_section"]["cancel_btn"]).first.click()

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
        btn = self.page.locator(self.loc["assigned_users_section"]["manage_btn"]).first
        btn.wait_for(state="visible", timeout=10000)
        btn.click()
        self.page.locator(self.loc["assigned_users_section"]["select_users_text"]).first.wait_for(
            state="visible", timeout=10000
        )

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

    def is_assigned_users_panel_visible(self):
        try:
            panel = self.page.locator(".mat-mdc-tab-body-active")
            el = panel.get_by_text("Select users from the list", exact=False).first
            expect(el).to_be_visible(timeout=5000)
            return True
        except Exception:
            return False

    def select_last_user_from_list(self):
        panel = self.page.locator(".mat-mdc-tab-body-active")
        all_labels = panel.locator(self.loc["assigned_users_section"]["user_selection_label"]).all()
        visible_labels = [l for l in all_labels if l.is_visible()]
        if not visible_labels:
            raise AssertionError("No visible users found in selection list")
        last_label = visible_labels[-1]
        label_text = last_label.inner_text(timeout=3000).strip()
        last_label.click()
        return label_text

    def _get_user_checkbox_wrapper(self, user_name):
        panel = self.page.locator(".mat-mdc-tab-body-active")
        return panel.locator(
            f"div.selection:has(label.selection-label:has-text('{user_name}'))"
        ).first

    def is_user_checkbox_checked(self, user_name):
        cb = self._get_user_checkbox_wrapper(user_name).locator("input[type='checkbox']").first
        return cb.is_checked()

    def click_user_checkbox_by_name(self, user_name):
        panel = self.page.locator(".mat-mdc-tab-body-active")
        panel.locator(f"label.selection-label:has-text('{user_name}')").first.click()

    def click_update_assigned_users(self):
        panel = self.page.locator(".mat-mdc-tab-body-active")
        panel.locator(self.loc["assigned_users_section"]["update_btn"]).first.click()

    def is_user_assigned(self, user_name):
        panel = self.page.locator(".mat-mdc-tab-body-active")
        self.page.wait_for_timeout(500)
        try:
            el = panel.get_by_text(user_name, exact=False).first
            expect(el).to_be_visible(timeout=8000)
            return True
        except Exception:
            return False

    def is_archive_dialog_visible(self, timeout=10000):
        try:
            el = self.page.locator("mat-dialog-container").first
            expect(el).to_be_visible(timeout=timeout)
            return True
        except Exception:
            return False

    def click_archive_dialog_checkbox(self):
        self.page.locator(self.loc["archive_project_dialog"]["checkbox"]).first.check()

    def click_archive_dialog_button(self):
        self.page.locator(self.loc["archive_project_dialog"]["archive_btn"]).first.click()

    def get_archive_toast_message(self, timeout=15000):
        msg_loc = self.page.locator(self.loc["success_toast"]["message"])
        try:
            expect(msg_loc).to_be_visible(timeout=timeout)
            return msg_loc.inner_text(timeout=5000).strip()
        except Exception:
            # fall back to toast title
            return self.wait_for_success_toast(timeout=timeout)

    def click_product_card(self, product_name):
        prefix = product_name.split("-")[0]
        self.page.locator(
            f"{self.loc['my_products_tab']['product_card']}:has-text('{prefix}')"
        ).first.click()

    def get_events_column_values(self, column_name, timeout=15000):
        table = self.page.locator(self.loc["project_details_page"]["events_table"])
        table.wait_for(state="visible", timeout=timeout)
        # Headers live in sibling divs outside the table — no <thead> exists
        header_spans = self.page.locator(
            self.loc["project_details_page"]["events_header_labels"]
        ).all()
        col_idx = None
        for i, h in enumerate(header_spans):
            try:
                if column_name.strip().lower() in h.inner_text(timeout=2000).strip().lower():
                    col_idx = i + 1
                    break
            except Exception:
                pass
        if col_idx is None:
            return []
        cells = table.locator(f"tbody td:nth-child({col_idx})").all()
        values = []
        for c in cells:
            try:
                text = c.inner_text(timeout=2000).strip()
                if text:
                    values.append(text)
            except Exception:
                pass
        return values

import random
import re

from playwright.sync_api import expect

from pages.base_page import BasePage


class LoginPage(BasePage):
    def navigate_to_login(self, url):
        self.goto(url, timeout=60000)
        self._dismiss_session_expired()

    def _dismiss_session_expired(self):
        close_btn = self.page.locator(self.loc["login"]["session_expired_close"])
        try:
            expect(close_btn.first).to_be_visible(timeout=3000)
            close_btn.first.click()
        except Exception:
            pass

    def enter_email(self, email):
        el = self.page.locator(self.loc["login"]["email_input"])
        expect(el).to_be_visible(timeout=15000)
        el.fill(email)

    def enter_password(self, password):
        el = self.page.locator(self.loc["login"]["password_input"])
        expect(el).to_be_visible(timeout=10000)
        el.fill(password)

    def click_sign_in(self):
        btn = self.page.locator(self.loc["login"]["sign_in_button"])
        expect(btn).to_be_visible(timeout=10000)
        btn.click()

    def is_on_my_projects(self):
        heading = self.page.locator(self.loc["my_projects"]["page_heading"])
        try:
            expect(heading.first).to_be_visible(timeout=20000)
            return True
        except Exception:
            return False

    def get_page_heading_text(self):
        heading = self.page.locator(self.loc["my_projects"]["page_heading"])
        expect(heading.first).to_be_visible(timeout=15000)
        return heading.first.inner_text()


class MyProjectsPage(BasePage):
    def _find_project_card(self, project_name, timeout=15000):
        """Scan all project cards and return the one whose h3 heading matches."""
        cards = self.page.locator(self.loc["my_projects"]["all_project_cards"])
        cards.first.wait_for(state="visible", timeout=timeout)
        count = cards.count()
        for i in range(count):
            card = cards.nth(i)
            heading = card.locator(self.loc["my_projects"]["project_card_name"])
            if heading.count() > 0:
                text = heading.first.inner_text().strip()
                if text == project_name:
                    return card
        return None

    def is_project_card_visible(self, project_name):
        card = self._find_project_card(project_name)
        return card is not None

    def click_project(self, project_name):
        card = self._find_project_card(project_name)
        assert card is not None, f"Project card '{project_name}' not found among project cards"
        heading = card.locator(self.loc["my_projects"]["project_card_name"]).first
        heading.click()
        self.page.wait_for_load_state("domcontentloaded", timeout=15000)


class ProjectPage(BasePage):
    def _wait_for_project_page_ready(self, timeout=20000):
        """Wait until the project page is fully loaded by checking for the
        first tab to become visible — tabs only render after the API response."""
        first_tab = self.page.locator(self.loc["project_page"]["tab_project_details"])
        try:
            expect(first_tab).to_be_visible(timeout=timeout)
            return True
        except Exception:
            return False

    def is_project_page_displayed(self, project_name):
        if not self._wait_for_project_page_ready():
            return False
        breadcrumb = self.page.locator(f"li:has-text('{project_name}')")
        try:
            expect(breadcrumb.first).to_be_visible(timeout=10000)
            return True
        except Exception:
            return False

    def get_visible_tabs(self):
        self._wait_for_project_page_ready()
        tabs = []
        for tab_name in ["Project Details", "Available Products", "My Products", "Shared Services"]:
            selector = self.loc["project_page"]["tab_by_name"].replace("{tab_name}", tab_name)
            tab_el = self.page.locator(selector)
            try:
                expect(tab_el).to_be_visible(timeout=5000)
                tabs.append(tab_name)
            except Exception:
                pass
        return tabs

    def is_tab_visible(self, tab_name):
        self._wait_for_project_page_ready()
        selector = self.loc["project_page"]["tab_by_name"].replace("{tab_name}", tab_name)
        tab_el = self.page.locator(selector)
        try:
            expect(tab_el).to_be_visible(timeout=5000)
            return True
        except Exception:
            return False

    def click_launch_now_for_product(self, product_name):
        product_card = self.page.locator(
            f"div:has(div:has-text('{product_name}')) >> button:has-text('LAUNCH NOW')"
        )
        try:
            expect(product_card.first).to_be_visible(timeout=10000)
            product_card.first.click()
            return
        except Exception:
            pass
        cards = self.page.locator("button:has-text('LAUNCH NOW')")
        all_cards = self.page.locator("div:has(> div img[alt*='Available Product'])").all()
        for i, card in enumerate(all_cards):
            text = card.inner_text()
            if product_name in text:
                cards.nth(i).click()
                return
        raise AssertionError(f"Could not find LAUNCH NOW for product: {product_name}")

    def click_my_products_tab(self):
        selector = self.loc["project_page"]["my_products_tab"]
        tab = self.page.locator(selector)
        expect(tab).to_be_visible(timeout=10000)
        tab.click()
        self.page.wait_for_timeout(2000)

    def is_on_my_products_tab(self):
        heading = self.page.locator(self.loc["project_page"]["my_products_heading"])
        try:
            expect(heading.first).to_be_visible(timeout=15000)
            return True
        except Exception:
            return False

    def get_success_message(self):
        """Scan all visible toast notifications and return the one containing
        'successfully launched'. Checks every element matched by each selector
        in locators.json common.success_toast."""
        self.page.wait_for_timeout(3000)
        selectors = self.loc["common"]["success_toast"].split(", ")
        for sel in selectors:
            loc = self.page.locator(sel.strip())
            count = loc.count()
            for i in range(count):
                try:
                    el = loc.nth(i)
                    if not el.is_visible(timeout=2000):
                        continue
                    text = _clean_toast(el.inner_text())
                    if "successfully" in text.lower():
                        return text
                except Exception:
                    continue
        return ""

    def get_my_product_names(self):
        name_labels = self.page.locator("label.product-name")
        count = name_labels.count()
        names = []
        for i in range(count):
            el = name_labels.nth(i)
            name = el.get_attribute("title") or el.inner_text()
            name = name.strip()
            if name:
                names.append(name)
        return names

    def is_product_name_in_my_products(self, product_name, timeout=15000):
        deadline = timeout // 1000
        for _ in range(deadline):
            names = self.get_my_product_names()
            if product_name in names:
                return True
            self.page.wait_for_timeout(1000)
        return False


def _clean_toast(text: str) -> str:
    return re.sub(r"^[×x]\s*", "", text.replace("\n", " ")).strip()


class CreateInstancePage(BasePage):
    def is_create_instance_page_displayed(self):
        heading = self.page.locator(self.loc["create_instance"]["page_heading"])
        try:
            expect(heading.first).to_be_visible(timeout=15000)
            return True
        except Exception:
            return False

    def fill_product_name(self, name):
        inp = self.page.locator(self.loc["create_instance"]["product_name_input"])
        expect(inp).to_be_visible(timeout=10000)
        inp.fill(name)

    def generate_product_name(self):
        rand_num = random.randint(1000, 9999)
        return f"Demo-RD-{rand_num}"

    def select_study(self, study_name):
        selector = self.loc["create_instance"]["study_selection_item"].replace("{study_name}", study_name)
        study_el = self.page.locator(selector)
        try:
            expect(study_el.first).to_be_visible(timeout=10000)
            checkbox = study_el.first.locator("xpath=ancestor-or-self::*[@role='checkbox' or contains(@class,'checkbox') or contains(@class,'mat-pseudo-checkbox')]")
            if checkbox.count() > 0:
                checkbox.first.click()
            else:
                study_el.first.click()
        except Exception:
            mat_checkbox = self.page.locator(f"mat-checkbox:has-text('{study_name}'), label:has-text('{study_name}'), div:has-text('{study_name}') >> nth=0")
            expect(mat_checkbox.first).to_be_visible(timeout=10000)
            mat_checkbox.first.click()

    def is_study_selected(self, study_name):
        study_el = self.page.locator(f"text='{study_name}'")
        try:
            expect(study_el.first).to_be_visible(timeout=5000)
            parent = study_el.first.locator("xpath=ancestor::*[contains(@class,'selected') or contains(@class,'checked') or @aria-checked='true']")
            return parent.count() > 0
        except Exception:
            return False

    def select_availability_zone(self, zone):
        dropdown = self.page.locator(self.loc["create_instance"]["availability_zone_dropdown"])
        expect(dropdown).to_be_visible(timeout=10000)
        dropdown.select_option(label=zone)

    def fill_ebs_volume_size(self, size):
        inp = self.page.locator(self.loc["create_instance"]["ebs_volume_size_input"])
        expect(inp).to_be_visible(timeout=10000)
        inp.fill("")
        inp.fill(str(size))

    def select_instance_type(self, instance_type):
        dropdown = self.page.locator(self.loc["create_instance"]["instance_type_dropdown"])
        expect(dropdown).to_be_visible(timeout=10000)
        dropdown.select_option(label=instance_type)

    def click_launch_now(self):
        btn = self.page.locator(self.loc["create_instance"]["launch_now_button"])
        expect(btn.first).to_be_visible(timeout=10000)
        btn.first.click()
        self._first_toast = self._capture_first_toast()

    def _capture_first_toast(self):
        selectors = self.loc["common"]["success_toast"].split(", ")
        for sel in selectors:
            loc = self.page.locator(sel.strip())
            try:
                expect(loc.first).to_be_visible(timeout=8000)
                return _clean_toast(loc.first.inner_text())
            except Exception:
                continue
        try:
            loc = self.page.locator("text=/successfully/i")
            expect(loc.first).to_be_visible(timeout=5000)
            return _clean_toast(loc.first.inner_text())
        except Exception:
            pass
        return ""

    def get_first_toast(self):
        return getattr(self, "_first_toast", "")

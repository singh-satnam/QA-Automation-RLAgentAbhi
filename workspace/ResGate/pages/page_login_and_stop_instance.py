from playwright.sync_api import expect

from pages.base_page import BasePage


class LoginPage(BasePage):
    def navigate_to_login(self, url):
        self.page.goto(url, wait_until="commit", timeout=60000)
        self.page.wait_for_selector(
            self.loc["login"]["email_input"], state="visible", timeout=30000
        )
        self._dismiss_session_expired_alert()

    def _dismiss_session_expired_alert(self):
        close_btn = self.page.locator(self.loc["login"]["session_expired_close"])
        try:
            expect(close_btn.first).to_be_visible(timeout=3000)
            close_btn.first.click()
        except Exception:
            pass

    def enter_email(self, email):
        field = self.page.locator(self.loc["login"]["email_input"])
        expect(field).to_be_visible(timeout=10000)
        field.fill(email)

    def enter_password(self, password):
        field = self.page.locator(self.loc["login"]["password_input"])
        expect(field).to_be_visible(timeout=10000)
        field.fill(password)

    def click_sign_in(self):
        btn = self.page.locator(self.loc["login"]["sign_in_button"])
        expect(btn).to_be_visible(timeout=10000)
        btn.click()

    def is_sign_in_page(self):
        return self.is_visible(self.loc["login"]["sign_in_button"])


class MyProjectsPage(BasePage):
    def is_my_projects_page(self):
        return self.is_visible(self.loc["my_projects"]["page_heading"], timeout=15000)

    def get_page_heading_text(self):
        heading = self.page.locator(self.loc["my_projects"]["page_heading"])
        expect(heading).to_be_visible(timeout=15000)
        return heading.inner_text()

    def is_project_card_present(self, name):
        card = self.page.get_by_role("heading", name=name, exact=True)
        try:
            expect(card.first).to_be_visible(timeout=10000)
            return True
        except Exception:
            return False

    def click_project_card(self, name):
        card = self.page.get_by_role("heading", name=name, exact=True)
        expect(card.first).to_be_visible(timeout=10000)
        card.first.click()


class ProjectDetailsPage(BasePage):
    def is_project_page_displayed(self, name):
        self.page.wait_for_timeout(3000)
        breadcrumb = self.page.locator(f"nav[aria-label='breadcrumb'] li:has-text('{name}')")
        try:
            expect(breadcrumb.first).to_be_visible(timeout=15000)
            return True
        except Exception:
            return name.replace(" ", "%20") in self.page.url or name in self.page.url

    def click_my_products_tab(self):
        tab = self.page.locator(self.loc["project_page"]["my_products_tab"])
        expect(tab).to_be_visible(timeout=10000)
        tab.click()
        self.page.locator(self.loc["project_page"]["my_products_heading"]).first.wait_for(
            state="visible", timeout=15000
        )

    def is_product_available(self, name):
        card = self._find_product_card(name)
        return card is not None

    def get_product_status(self, name):
        tab_panel = self.page.get_by_role("tabpanel", name="My Products")
        expect(tab_panel.get_by_text(name, exact=True).first).to_be_visible(timeout=15000)
        return self.page.evaluate("""(productName) => {
            const label = document.querySelector('label.product-name[title="' + productName + '"]');
            if (!label) return 'Unknown';
            const card = label.closest('.my-product-card');
            if (!card) return 'Unknown';
            const statusEl = card.querySelector('span.status-text');
            return statusEl ? statusEl.textContent.trim() : 'Unknown';
        }""", name)

    def click_product(self, name):
        card = self._find_product_card(name)
        if card:
            card.click()
        else:
            self.page.locator(f"label.product-name[title='{name}']").first.click()

    def _find_product_card(self, name):
        cards = self.page.locator(self.loc["my_projects"]["all_project_cards"])
        tab_panel = self.page.get_by_role("tabpanel", name="My Products")
        product = tab_panel.locator(f"label.product-name[title='{name}']")
        try:
            expect(product.first).to_be_visible(timeout=10000)
            return product.first.locator("xpath=ancestor::div[contains(@class,'my-product-card')]")
        except Exception:
            return None


class ProductDetailsPage(BasePage):
    def is_product_details_page(self, name):
        heading = self.page.get_by_role("heading", name=name, level=4)
        try:
            expect(heading.first).to_be_visible(timeout=15000)
            return True
        except Exception:
            return name in self.page.url

    def get_product_heading(self):
        heading = self.page.get_by_role("heading", level=4)
        expect(heading.first).to_be_visible(timeout=10000)
        return heading.first.inner_text().strip()

    def click_stop_under_connect(self):
        stop_icon = self.page.locator("img[alt='Stop Product']")
        expect(stop_icon.first).to_be_visible(timeout=10000)
        stop_icon.first.click()
        toast = self.page.locator(self.loc["common"]["success_toast"])
        try:
            expect(toast.first).to_be_visible(timeout=15000)
            self._last_toast_text = toast.first.inner_text().strip()
        except Exception:
            self._last_toast_text = ""

    def get_toast_message_text(self):
        return getattr(self, "_last_toast_text", "")

    def is_stop_success_indicated(self):
        msg = self.get_toast_message_text()
        if msg and "stop" in msg.lower():
            return True
        if msg:
            return True
        status_el = self.page.locator("div:text-matches('^(Stopping|Stopped|Transitioning)$')")
        try:
            expect(status_el.first).to_be_visible(timeout=15000)
            return True
        except Exception:
            pass
        start_icon = self.page.locator("img[alt='Start Product']")
        try:
            expect(start_icon.first).to_be_visible(timeout=15000)
            return True
        except Exception:
            return False

    def is_start_option_available(self):
        start_icon = self.page.locator("img[alt='Start Product']")
        for attempt in range(6):
            try:
                expect(start_icon.first).to_be_visible(timeout=30000)
                return True
            except Exception:
                refresh = self.page.locator("img[alt='Provisioned Product Status Refresh'][title='Refresh']")
                try:
                    refresh.first.click()
                    self.page.wait_for_timeout(3000)
                except Exception:
                    self.page.wait_for_timeout(5000)
        return False

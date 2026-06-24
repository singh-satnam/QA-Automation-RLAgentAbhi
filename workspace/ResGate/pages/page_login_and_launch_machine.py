from playwright.sync_api import expect
from pages.base_page import BasePage


class LoginPage(BasePage):
    def navigate(self, url):
        self.goto(url, timeout=60000)

    def dismiss_session_expired_alert(self):
        alert_close = self.page.locator(self.loc["login"]["session_expired_close"])
        try:
            expect(alert_close.first).to_be_visible(timeout=5000)
            alert_close.first.click()
        except Exception:
            pass

    def fill_email(self, email):
        el = self.page.get_by_role("textbox", name="Email *")
        expect(el).to_be_visible(timeout=10000)
        el.fill(email)

    def fill_password(self, password):
        el = self.page.get_by_role("textbox", name="Password *")
        expect(el).to_be_visible(timeout=10000)
        el.fill(password)

    def click_sign_in(self):
        btn = self.page.get_by_role("button", name="Sign In")
        expect(btn).to_be_visible(timeout=10000)
        btn.click()

    def is_on_my_projects_page(self):
        heading = self.page.get_by_role("heading", name="My Projects")
        try:
            expect(heading.first).to_be_visible(timeout=15000)
            return True
        except Exception:
            return False

    def get_page_heading_text(self):
        heading = self.page.get_by_role("heading", name="My Projects")
        expect(heading.first).to_be_visible(timeout=15000)
        return heading.first.inner_text()


class MyProjectsPage(BasePage):
    def is_project_card_present(self, project_name):
        card = self.page.get_by_role("heading", name=project_name, exact=True)
        try:
            expect(card.first).to_be_visible(timeout=15000)
            return True
        except Exception:
            return False

    def click_project_card(self, project_name):
        card = self.page.get_by_role("heading", name=project_name, exact=True)
        expect(card.first).to_be_visible(timeout=15000)
        card.first.click()


class ProjectPage(BasePage):
    def is_project_page_displayed(self, project_name):
        breadcrumb = self.page.locator("nav[aria-label='breadcrumb']").get_by_text(project_name)
        try:
            expect(breadcrumb.first).to_be_visible(timeout=15000)
            return True
        except Exception:
            return False

    def click_my_products_tab(self):
        tab = self.page.get_by_role("tab", name="My Products")
        expect(tab).to_be_visible(timeout=15000)
        tab.click()

    def is_product_available(self, product_name):
        tab_panel = self.page.get_by_role("tabpanel", name="My Products")
        product = tab_panel.get_by_text(product_name, exact=True)
        try:
            expect(product.first).to_be_visible(timeout=15000)
            return True
        except Exception:
            return False

    def get_product_status(self, product_name):
        tab_panel = self.page.get_by_role("tabpanel", name="My Products")
        expect(tab_panel.get_by_text(product_name, exact=True).first).to_be_visible(timeout=15000)
        status = self.page.evaluate("""(productName) => {
            const label = document.querySelector('label.product-name[title="' + productName + '"]');
            if (!label) return '';
            const card = label.closest('.my-product-card');
            if (!card) return '';
            const statusEl = card.querySelector('span.status-text');
            return statusEl ? statusEl.textContent.trim() : '';
        }""", product_name)
        return status

    def click_product(self, product_name):
        tab_panel = self.page.get_by_role("tabpanel", name="My Products")
        product = tab_panel.get_by_text(product_name, exact=True)
        expect(product.first).to_be_visible(timeout=15000)
        product.first.click()


class ProductDetailsPage(BasePage):
    def is_product_details_displayed(self, product_name):
        heading = self.page.get_by_role("heading", name=product_name, level=4)
        try:
            expect(heading.first).to_be_visible(timeout=15000)
            return True
        except Exception:
            return False

    def click_remote_desktop(self):
        rd_link = self.page.locator("div.connect-link.my-enable:visible").filter(
            has_text="Remote Desktop"
        ).first
        expect(rd_link).to_be_visible(timeout=15000)
        rd_link.click()


class AmazonDCVPage(BasePage):
    def wait_for_connection(self):
        connecting = self.page.locator("text='Connecting'")
        try:
            connecting.first.wait_for(state="hidden", timeout=10000)
        except Exception:
            pass

    def click_ip_button(self):
        btn = self.page.locator(self.loc["amazon_dcv"]["ip_button"])
        expect(btn.first).to_be_visible(timeout=15000)
        btn.first.click()

    def get_ip_button_text(self):
        btn = self.page.locator(self.loc["amazon_dcv"]["ip_button"])
        expect(btn.first).to_be_visible(timeout=15000)
        return btn.first.inner_text().strip()

    def is_menu_displayed(self):
        menu = self.page.get_by_role("menuitem", name="Disconnect")
        try:
            expect(menu).to_be_visible(timeout=10000)
            return True
        except Exception:
            return False

    def click_disconnect(self):
        menuitem = self.page.get_by_role("menuitem", name="Disconnect")
        expect(menuitem).to_be_visible(timeout=10000)
        menuitem.click()

    def get_connection_closed_message(self):
        msg = self.page.locator(self.loc["amazon_dcv"]["connection_closed_message"])
        try:
            expect(msg.first).to_be_visible(timeout=15000)
            return msg.first.inner_text().strip()
        except Exception:
            return ""

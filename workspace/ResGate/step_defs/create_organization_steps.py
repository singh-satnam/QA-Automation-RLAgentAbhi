"""Step definitions for feature/create_organization.feature.

One step-def file per feature. Every step calls exactly one Page Object method
(no raw Playwright here). Values the story refers to later are recorded via the
captured_values fixture at the moment they are read; verifications map to one
captured_values assertion each.
"""

from pytest_bdd import given, when, then, parsers

from pages.page_create_organization import CreateOrganizationPage


def _pom(scenario_context, page, base_url):
    pom = scenario_context.get("pom")
    if pom is None:
        pom = CreateOrganizationPage(page, base_url)
        scenario_context["pom"] = pom
    return pom


# ---------------------------------------------------------------------------
# Given the user navigates to the login page "<url>"
# ---------------------------------------------------------------------------
@given(parsers.parse('the user navigates to the login page "{url}"'))
def navigate_to_login(scenario_context, page, base_url, captured_values, url):
    pom = _pom(scenario_context, page, base_url)
    pom.navigate_to_login(url)
    captured_values.add("Login page URL", url)


# ---------------------------------------------------------------------------
# And the user clicks the Sign In link
# The live /login page presents the sign-in form directly — this step confirms
# the sign-in form is reachable (no fabricated landing step).
# ---------------------------------------------------------------------------
@given("the user clicks the Sign In link")
def click_sign_in_link(scenario_context, page, base_url, captured_values):
    pom = _pom(scenario_context, page, base_url)
    visible = pom.sign_in_form_is_displayed()
    captured_values.assert_prerequisite(
        "Sign-in form reachable",
        condition=visible,
        reason="sign-in form (email field) not visible on the login page",
        evidence=f"email selector={pom.loc['login']['email_input']}",
    )


# ---------------------------------------------------------------------------
# And the user enters valid credentials: | Email | Password |
# ---------------------------------------------------------------------------
@given("the user enters valid credentials:")
def enter_valid_credentials(scenario_context, page, base_url, captured_values, datatable):
    pom = _pom(scenario_context, page, base_url)
    headers, row = datatable[0], datatable[1]
    creds = dict(zip([h.strip() for h in headers], [c.strip() for c in row]))
    email, password = creds["Email"], creds["Password"]
    pom.enter_credentials(email, password)
    captured_values.add("Login email", email)


# ---------------------------------------------------------------------------
# When the user clicks the Login button
# ---------------------------------------------------------------------------
@when("the user clicks the Login button")
def click_login_button(scenario_context, page, base_url, captured_values):
    pom = _pom(scenario_context, page, base_url)
    pom.click_login()


# ---------------------------------------------------------------------------
# Then the user should be redirected to the My Organizations page
# ---------------------------------------------------------------------------
@then("the user should be redirected to the My Organizations page")
def redirected_to_my_organizations(scenario_context, page, base_url, captured_values):
    pom = _pom(scenario_context, page, base_url)
    on_page = pom.is_on_my_organizations()
    heading = pom.my_organizations_heading_text() if on_page else page.url
    # Blocking gate: every later step needs this page / session.
    captured_values.assert_prerequisite(
        "Redirected to My Organizations",
        condition=on_page,
        reason="login did not land on the My Organizations page",
        evidence=f"current_url={page.url}; heading={heading}",
    )
    # Record the org count BEFORE creation so we can prove creation later.
    count_before = pom.organization_count()
    scenario_context["count_before"] = count_before
    captured_values.add("Organization count before create", count_before)


# ---------------------------------------------------------------------------
# When the user clicks the Add New button
# ---------------------------------------------------------------------------
@when("the user clicks the Add New button")
def click_add_new_button(scenario_context, page, base_url, captured_values):
    pom = _pom(scenario_context, page, base_url)
    pom.click_add_new()


# ---------------------------------------------------------------------------
# Then the Create Organization form should be displayed
# ---------------------------------------------------------------------------
@then("the Create Organization form should be displayed")
def create_form_displayed(scenario_context, page, base_url, captured_values):
    pom = _pom(scenario_context, page, base_url)
    heading = pom.create_form_heading_text() if pom.is_create_form_displayed() else "<not displayed>"
    assert captured_values.assert_match(
        "Create Organization form displayed",
        expected="Create Organization",
        actual=heading,
    )


# ---------------------------------------------------------------------------
# When the user enters the organization details: | Name | Description |
# ---------------------------------------------------------------------------
@when("the user enters the organization details:")
def enter_organization_details(scenario_context, page, base_url, captured_values, datatable):
    pom = _pom(scenario_context, page, base_url)
    headers, row = datatable[0], datatable[1]
    details = dict(zip([h.strip() for h in headers], [c.strip() for c in row]))
    name = details["Organization Name"]
    description = details["Organization Description"]
    pom.enter_organization_details(name, description)
    scenario_context["org_name"] = name
    scenario_context["org_description"] = description
    captured_values.add("Organization name entered", name)
    captured_values.add("Organization description entered", description)


# ---------------------------------------------------------------------------
# And the user clicks the Create Organization button
# ---------------------------------------------------------------------------
@when("the user clicks the Create Organization button")
def click_create_organization_button(scenario_context, page, base_url, captured_values):
    pom = _pom(scenario_context, page, base_url)
    pom.click_create_organization()


# ---------------------------------------------------------------------------
# Then a new organization should be created successfully
# ---------------------------------------------------------------------------
@then("a new organization should be created successfully")
def organization_created_successfully(scenario_context, page, base_url, captured_values):
    pom = _pom(scenario_context, page, base_url)
    name = scenario_context["org_name"]
    count_before = scenario_context.get("count_before") or 0

    # Success must be proven BY THIS RUN: the app's own success toast
    # ("Organization saved successfully") and/or the new card appearing with the
    # count incrementing. This demo throws unrelated background error-toasts, so
    # an error is only reported when the positive signal is ABSENT (otherwise we
    # would fail on noise that has nothing to do with the creation).
    success_toast = pom.success_toast_text()
    pom.is_on_my_organizations()
    appeared = pom.wait_for_organization_in_list(name)
    count_after = pom.organization_count()
    scenario_context["count_after"] = count_after

    positive = ("saved successfully" in success_toast.lower()) or \
               (appeared and count_after == count_before + 1)
    error_text = "" if positive else pom.latest_error_toast_text()

    captured_values.add("Create — success toast", success_toast or "<none>")
    captured_values.add("Organization count after create", count_after)
    captured_values.assert_action_succeeded(
        "Organization created",
        error_text=error_text,
        positive_signal=positive,
        reason="no success toast and the org count did not increment — creation not confirmed",
        evidence=f"count_before={count_before} count_after={count_after} "
                 f"card_appeared={appeared} success_toast={success_toast!r}",
    )


# ---------------------------------------------------------------------------
# And the organization named "<name>" should be displayed in the list ...
# ---------------------------------------------------------------------------
@then(parsers.parse('the organization named "{name}" should be displayed in '
                    'the list of organizations on the My Organizations page'))
def organization_displayed_in_list(scenario_context, page, base_url, captured_values, name):
    pom = _pom(scenario_context, page, base_url)
    pom.wait_for_organization_in_list(name)
    actual = pom.organization_card_text(name)
    assert captured_values.assert_match(
        f'Organization "{name}" displayed in list',
        expected=name,
        actual=actual,
    )

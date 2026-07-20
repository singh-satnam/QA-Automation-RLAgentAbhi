Feature: Admin Users Page Filter and Search

  Scenario: Admin verifies Users page elements and uses search, filter, and sort features

    Given the user is on the ResGate login page
    When the user signs in as an Admin
    And the user clicks on the hamburger menu and selects "Users"
    Then the Users page is displayed
    And the search bar is present on the Users page
    And the "Add New Select" button is present on the Users page
    And the "Filter By OU" filter option is present on the Users page
    And the "Filter By Role" filter option is present on the Users page
    And the "Sort By" filter option is present on the Users page
    And the "Reset Filters" button is present on the Users page
    And the "Toggle Active Users" toggle is present on the Users page
    When the user searches for "Swayam" in the search bar
    Then users containing the text "Swayam" are shown on the page
    When the user clicks on the hamburger menu and selects "Users"
    And the user clicks on "Filter By OU" and selects "test-auto-use"
    Then "test-auto-use" is present in the results
    When the user clicks the "Reset Filters" button
    And the user clicks on "Filter By Role" and selects "Principal Investigator"
    Then the results contain the text "Principal Investigator"
    When the user clicks the "Reset Filters" button
    And the user clicks on "Sort By" and selects "Username"
    Then the results are updated
    When the user clicks the "Active Users" toggle
    Then the results show only users with "Active" status

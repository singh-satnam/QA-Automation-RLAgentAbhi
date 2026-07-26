Feature: Admin User Catalog

  Scenario: Admin views and filters the Catalog page
    Given the user is on the ResGate login page
    When the user enters valid Admin credentials
    And the user clicks "Sign In"
    And the user clicks the hamburger menu and selects "Catalog"
    Then the Catalog page is displayed
    And the Catalog page title displays "Catalog (X)" where X is greater than 0
    And the "View" dropdown combo is present on the Catalog page
    And the custom search bar is present on the Catalog page
    When the user clicks the "View" dropdown
    Then the "View" dropdown displays available options
    When the user selects each option from the "View" dropdown one by one
    Then each dropdown selection updates the Catalog page

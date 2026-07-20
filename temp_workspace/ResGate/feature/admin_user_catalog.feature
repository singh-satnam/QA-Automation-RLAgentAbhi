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
    Then the "View" dropdown displays the option "Research"
    And the "View" dropdown displays the option "Secure"
    And the "View" dropdown displays the option "RA Standard"
    When the user selects "RA Standard" from the "View" dropdown
    Then the Catalog page displays results for "RA Standard"

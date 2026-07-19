Feature: Logout via Sign Out

  Scenario: Admin logs out via Sign Out and is redirected to the login screen
    Given the user is on the Research Gateway login page
    When the user signs in as an Admin
    And the user clicks Sign In
    And the user clicks the username in the header
    And the user clicks Sign Out
    Then the user is redirected to the login screen with the "Click here to Login" button

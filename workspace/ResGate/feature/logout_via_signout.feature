Feature: Logout via Sign Out

  Scenario: Admin logs out via Sign Out in header
    Given the user opens the RG login page
    And the user enters "admin" credentials
    When the user clicks Sign In
    And the user clicks the user name in the header
    And the user clicks Sign Out
    Then the user is redirected to the login screen with button "Click here to Login"

Feature: Admin Login to Research Gateway

  Scenario: Admin logs in with valid credentials and lands on My Organizations
    Given the user is on the Research Gateway login page
    When the user signs in as an Admin
    And the user clicks Sign In
    Then the admin lands on the My Organizations page

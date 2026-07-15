Feature: Admin login to Research Gateway
  As an admin user
  I want to log in to Research Gateway
  So that I can access the My Organizations page

  Scenario: Admin logs in with valid credentials and lands on My Organizations page
    Given the Research Gateway login page is open
    When the admin enters valid admin credentials
    And the admin clicks Sign In
    Then the admin lands on the My Organizations page

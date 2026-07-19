Feature: PI Login to Research Gateway

  Scenario: PI logs in with valid credentials and lands on My Projects
    Given the user is on the Research Gateway login page
    When the user signs in as a PI
    And the user clicks Sign In
    Then the PI lands on the My Projects page successfully

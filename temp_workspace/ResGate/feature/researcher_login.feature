Feature: RES Login to Research Gateway

  Scenario: Researcher logs in with valid credentials and lands on My Projects
    Given the user is on the Research Gateway login page
    When the user signs in as a Researcher
    And the user clicks Sign In
    Then the researcher lands on the My Projects page with only their assigned projects displayed

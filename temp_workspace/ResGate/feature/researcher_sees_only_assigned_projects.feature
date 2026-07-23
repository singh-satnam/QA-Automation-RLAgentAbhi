Feature: Researcher Sees Only Assigned Projects on My Projects Page

  Scenario: Researcher logs in and verifies assigned project card is displayed on My Projects page
    Given the user is on the Research Gateway login page
    When the user signs in as a Researcher
    And the user clicks Sign In
    Then the user lands on the My Projects page successfully
    And the project card "AutomationProjDonotTouch" is displayed

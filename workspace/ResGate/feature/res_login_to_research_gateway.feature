Feature: RES Login to Research Gateway

  Scenario: Researcher logs in and lands on My Projects page with only assigned projects
    Given the user navigates to the Research Gateway login page
    And the user enters "res" credentials
    And the user clicks the Sign In button
    Then the researcher lands on the "My Projects" page with only assigned projects

Feature: PI Login to Research Gateway

  Scenario: PI logs in and lands on My Projects page
    Given the user navigates to the Research Gateway login page
    And the user enters "PI" credentials
    And the user clicks the Sign In button
    Then the PI lands on the "My Projects" page successfully

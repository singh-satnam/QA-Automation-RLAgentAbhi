Feature: Login and stop the instance
  As a user of ResGate, I want to log in, navigate to a project product,
  and stop a running instance so that the instance transitions from Active to Stopped.

  Scenario: Login and stop the instance
    Given the user navigates to the login page
    And the user enters "res" credentials
    When the user clicks on the Sign In button
    Then the user should be landing on the "My Projects" page
    And the "Automation Testing" card is present
    When the user clicks on the "Automation Testing" project
    Then the "Automation Testing" page is displayed
    When the user clicks on the "My Products" tab
    Then "Demo-RD-9227" is available
    And the "Demo-RD-9227" is in green "Active" status
    When the user clicks on "Demo-RD-9227"
    Then the user lands on the product details page of "Demo-RD-9227"
    When the user clicks on "Stop" under "CONNECT"
    Then the stop process initiated successfully message is displayed
    And the "Start" option is available under "CONNECT"

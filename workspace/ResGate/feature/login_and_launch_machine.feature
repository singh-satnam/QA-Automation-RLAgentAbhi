@resgate @login @remote_desktop
Feature: Login and Launch Remote Desktop Machine
  As a user of ResGate
  I want to log in, navigate to a project product, and launch a remote desktop connection
  So that I can connect to and disconnect from an Amazon instance

  Scenario: Login navigate to project product and launch remote desktop
    Given the user navigates to the login page "https://ra-demo.rlcatalyst.com/login"
    And the user enters valid credentials:
      | Email                                  | Password |
      | piyusha.varshney+r@relevancelab.com    | Pass@123 |
    When the user clicks on the Sign In button
    Then the user should be landing on the "My Projects" page
    And the "Automation Testing" card is present
    When the user clicks on the "Automation Testing" project
    Then the "Automation Testing" page is displayed
    When the user clicks on the My Products tab
    Then "Demo-RD-9227" is available
    And "Demo-RD-9227" is in green "Active" status
    When the user clicks on "Demo-RD-9227"
    Then the user lands on the product details of "Demo-RD-9227"
    When the user clicks on "Remote Desktop" under "CONNECT"
    Then a new browser tab is opened with the new Amazon instance
    When on the new tab the user clicks on the option with text starting with "ip-"
    Then a menuitem is displayed
    When the user clicks on the "Disconnect" option
    Then the user sees the "The connection has been closed" message on the page

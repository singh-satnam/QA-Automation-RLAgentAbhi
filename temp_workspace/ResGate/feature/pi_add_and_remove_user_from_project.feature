Feature: PI Add and Remove User from Project

  Scenario: PI adds RESBOT user to project verifies access then removes user and verifies loss of access
    Given the user is on the Research Gateway login page
    When the user signs in as a PI
    And the user clicks Sign In
    Then the PI lands on the My Projects page successfully
    When the user searches for the project card "AutomationProjDonotTouch" and clicks on it
    Then the project details page is displayed
    And the following tabs are displayed on the page
      | Tab Name           |
      | Project Details    |
      | Events             |
      | Available Products |
      | My Products        |
      | All Products       |
      | Shared Services    |
    When the user clicks the Project Details tab
    And the user clicks Manage next to Assigned Users
    Then the "Anthropic bot" user checkbox is unchecked
    When the user selects the "Anthropic bot" user checkbox and clicks the Update button
    Then the Assigned Users section displays "Anthropic bot"
    When the user clicks the username on the top right and selects Sign out
    And the user clicks the "Click here to login" button
    And the user signs in as a RESBOT
    And the user clicks Sign In
    Then the user lands on the My Projects page successfully
    And the project card "AutomationProjDonotTouch" is displayed
    When the user clicks the username on the top right and selects Sign out
    And the user clicks the "Click here to login" button
    And the user signs in as a PI
    And the user clicks Sign In
    Then the PI lands on the My Projects page successfully
    When the user searches for the project card "AutomationProjDonotTouch" and clicks on it
    Then the project details page is displayed
    When the user clicks the Project Details tab
    And the user clicks Manage next to Assigned Users
    Then the "Anthropic bot" user checkbox is selected
    When the user deselects the "Anthropic bot" user checkbox and clicks the Update button
    And the user clicks the username on the top right and selects Sign out
    And the user clicks the "Click here to login" button
    And the user signs in as a RESBOT
    And the user clicks Sign In
    Then the user lands on the My Projects page successfully
    And the project card "AutomationProjDonotTouch" is not displayed

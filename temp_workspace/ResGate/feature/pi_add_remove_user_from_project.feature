Feature: PI Add User to Project from Assigned Users

  Scenario: PI selects a user from the assigned users list of an active project
    Given the user is on the Research Gateway login page
    When the user signs in as a PI
    And the user clicks Sign In
    Then the PI lands on the My Projects page successfully
    When the user searches for a project card with an Active button
    And the user clicks the Active button on the project card
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
    Then the "Select users from the list" panel is displayed
    When the user selects the last option from the list

Feature: Admin User Cannot Be Added to Project

  Scenario: PI verifies admin user cannot be added to assigned users of an active project
    Given the user is on the Research Gateway login page
    When the user signs in as a PI
    And the user clicks Sign In
    Then the PI lands on the My Projects page successfully
    When the user searches for a project card with an Active button
    And the user clicks the Active button on the project card
    Then the project details page is displayed
    And the following tabs are displayed on the page
      | Tab Name          |
      | Project Details   |
      | Events            |
      | Available Products |
      | My Products       |
      | All Products      |
      | Shared Services   |
    When the user clicks the Project Details tab
    Then the following fields are displayed and have a value
      | Field               |
      | Project Name        |
      | Project Description |
      | Project Owner       |
      | Created On          |
      | Project Type        |
      | Account Details     |
      | Budget              |
      | Project Tags        |
      | Assigned Users      |
      | Linked Studies      |
      | Add Products        |
    When the user clicks Manage next to Assigned Users
    Then the admin user is not displayed in the Assigned Users list
    When the user clicks the Cancel button

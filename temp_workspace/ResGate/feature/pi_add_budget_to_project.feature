Feature: PI Add Budget to Project

  Scenario: PI adds budget to an active project and verifies the updated budget
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
    Then the following fields are displayed and have a value
      | Field               |
      | Project Name        |
      | Project Description |
      | Project Owner       |
      | Created On          |
      | Project Type        |
      | Account Details     |
      | Budget              |
    And the user reads the current value of the Budget field
    And the Actions section is displayed on the right side of the page
    And the following options are displayed under Actions
      | Option     |
      | Pause      |
      | Stop       |
      | Sync       |
      | Add Budget |
      | Archive    |
    When the user clicks Add Budget
    And the user enters "1" in the "Enter the amount you would like to add to the current project budget" field
    And the user clicks Submit
    Then the success message "The Budget has been added successfully" is displayed in the top right corner and disappears
    And the Budget field displays the updated value equal to the previous budget value plus 1

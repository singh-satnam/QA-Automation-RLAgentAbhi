Feature: PI creates a project without storage and archives it

  Scenario: PI creates a project without storage, validates project details, and archives the project
    Given the user is on the Research Gateway login page
    When the user signs in as a PI
    And the user clicks Sign In
    Then the PI lands on the My Projects page successfully
    When the user clicks the Add New button
    Then the Create Project page is displayed
    When the user fills in the Project Name from the test data
    And the user fills in the Project Description from the test data
    And the user fills in the Budget Available from the test data
    And the user selects an account from the test data
    And the user selects a user from the test data
    And the user ensures the Use Project Storage checkbox is unchecked
    And the user clicks the Create Project button
    Then the user is taken to the My Projects page
    And the new project with the project name from the test data is displayed
    When the user searches for the project using the project name from the test data
    And the user clicks on the matching project link
    When the user clicks the Project Details tab
    Then the following options are present on the Project Details tab
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
    When the user clicks the Archive option
    Then the Archive project pop up is displayed
    When the user clicks the available check box in the Archive pop up
    And the user clicks the Archive button
    Then a confirmation pop up is displayed on the top right with a message containing "Archiving project started"

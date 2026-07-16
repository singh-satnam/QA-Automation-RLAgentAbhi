Feature: PI Project Creation in Research Gateway

  Scenario: PI creates a new project with details from test data
    Given the user navigates to the Research Gateway login page
    And the user enters "PI" credentials
    And the user clicks the Sign In button
    Then the PI lands on the "My Projects" page successfully
    When the user clicks the "Add New" button
    Then the "Create Project" page is displayed
    When the user fills in "Project Name" from the test data
    And the user fills in "Project Description" from the test data
    And the user fills in "Budget Available" from the test data
    And the user selects an account from the list using the test data
    And the user selects a user from the list using the test data
    And the user selects "Create standard catalog" type from the list using the test data
    And the user selects "Bring your own catalog" type from the list using the test data
    And the user clicks the "Create Project" button
    Then the user is taken to the "My Projects" page
    And a new project with name matching "Project Name" from the test data is displayed

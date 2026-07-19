Feature: PI Project Creation in ResGate

  Scenario: PI creates a new project with details from test data
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
    And the user selects the Create standard catalog type from the test data
    And the user selects the Bring your own catalog type from the test data
    And the user clicks the Create Project button
    Then the user is taken to the My Projects page
    And the new project with the project name from the test data is displayed

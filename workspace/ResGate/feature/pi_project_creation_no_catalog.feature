Feature: PI Project Creation Without Catalog in Research Gateway

  Scenario: PI creates a new project without catalog selection
    Given the user navigates to the Research Gateway login page
    And the user enters "pi" credentials
    And the user clicks the Sign In button
    Then the PI lands on the "My Projects" page successfully
    When the user clicks the "Add New" button
    Then the "Create Project" page is displayed
    When the user fills in "Project Name" with "Auto Demo"
    And the user fills in "Project Description" with "PW-Demo"
    And the user fills in "Budget Available" with "10"
    And the user selects account "StandardAccount" from the list
    And the user clicks the "Create Project" button
    Then the user is taken to the "My Projects" page
    And a new project with name "Auto Demo" is displayed

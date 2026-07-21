Feature: PI My Projects Count

  Scenario: PI verifies My Projects count is greater than zero
    Given the user is on the Research Gateway login page
    When the user signs in as a PI
    And the user clicks Sign In
    Then the PI lands on the My Projects page successfully
    And the My Projects header displays a project count greater than zero

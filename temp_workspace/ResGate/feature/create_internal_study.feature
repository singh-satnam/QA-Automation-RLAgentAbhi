Feature: Create Internal Study

  Scenario: PI creates an internal study

    Given the user is on the ResGate login page
    When the user signs in as a PI
    And the user clicks Sign In
    Then the PI lands on the My Projects page successfully
    When the user clicks the hamburger menu and selects "Studies"
    And the user clicks the "+Create Study" button
    Then the "Create Key Study" page appears
    When the user enters the study name "Automation Demo Study" with a random number appended
    And the user enters the description "This-is-script" with a random number appended
    And the user selects the study type as "Internal Study"
    And the user selects the access level as "Read Only"
    And the user clicks the "Next" button
    And the user enters the bucket name from the test data
    And the user clicks the "Next" button
    And the user selects the project account from the test data
    And the user clicks the project checkbox from the test data
    And the user clicks the "Register Study" button
    Then a confirmation message is displayed in the top right corner

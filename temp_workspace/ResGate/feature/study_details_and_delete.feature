Feature: Verify Study Link to Project and Delete Study

  Scenario: PI verifies study details and assigned project then deletes the study

    Given the user is on the ResGate login page
    When the user signs in as a PI
    And the user clicks Sign In
    Then the PI lands on the My Projects page successfully
    When the user clicks the hamburger menu and selects "Studies"
    And the user searches for "AutomationDemoStudy"
    And the user clicks the card whose name starts with "AutomationDemoStudy"
    Then the "Study Details" tab is present
    And the "Resource Details" tab is present
    When the user clicks the "Study Details" tab
    Then the Assigned Projects list includes "AutomationProjDonotTouch"
    When the user clicks the "Resource Details" tab
    Then the Bucket Name equals "rg-healthsciencesp-studytest3-285"
    When the user clicks the "Delete" button
    Then a new popup is displayed
    When the user selects the checkbox in the popup
    And the user clicks the "Delete" button in the popup
    Then a confirmation popup is displayed in the top right corner

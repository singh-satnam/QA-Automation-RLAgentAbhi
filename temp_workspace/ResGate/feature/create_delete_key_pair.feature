Feature: Create and Delete Key Pair

  Scenario: PI creates a key pair and then deletes it
    Given the user is on the Research Gateway login page
    When the user signs in as a PI
    And the user clicks Sign In
    Then the PI lands on the My Projects page successfully
    When the user clicks the hamburger menu and selects Key Pairs
    And the user clicks the +Create New button
    Then the Create Key Pair dialog box appears
    When the user clicks the Project dropdown and selects the second project
    And the user fills the Name input box with a valid name
    And the user clicks the File format dropdown and selects pem
    And the user clicks Create Key Pair
    Then the created key pair appears on the Key Pairs page
    When the user clicks the three dots menu on the created key pair
    And the user clicks the Delete button
    Then the Delete key pair modal appears
    When the user clicks the Delete button to confirm
    Then the Deleted keypair successfully message is displayed

Feature: Admin Create and Delete Organization

  Scenario: Admin creates a new organization with a new user and then deletes it
    Given the user is on the Research Gateway login page
    When the user signs in as an Admin
    And the user clicks Sign In
    Then the admin lands on the My Organizations page
    When the user clicks the Add New button
    Then the Create Organization page is displayed
    When the user enters a unique organization name in the Organization Name field
    And the user enters 'Automation demo work' in the Organization Description field
    And the user clicks the Add Users dropdown
    Then a pop-up box with Add User is displayed
    And the user enters a valid new user email in the Email input box
    And the user enters 'Swayamshree' in the FirstName input box
    And the user enters 'Nayak' in the LastName input box
    And the user clicks the Role dropdown and selects 'Principal Investigator'
    And the user clicks the Add User button
    And the user selects the newly added user checkbox from the Select Users from the list
    When the user clicks the Create Organization button
    Then the organization with a name containing 'RL-01_Researcher' is present on the page
    When the user clicks Actions for the organization with a name containing 'RL-01_Researcher' and selects Delete
    And the user selects the confirmation checkbox 'Yes, I want to permanently delete this organization and all its data' and clicks the Delete button
    Then the confirmation message 'Organization Deleted Successfully' is displayed on the top right side

Feature: Add User to an Organization
  As a logged-in user
  I want to add a new user to an organization from the Users page
  So that the new user appears in the users list with the assigned role

  Scenario: Successfully add a new user to an organization
    Given the user navigates to the login page "https://ra-demo.rlcatalyst.com/login"
    And the user enters the following credentials:
      | Email                              | Password      |
      | sundeep.mallya+a@relevancelab.com  | Relevance@123 |
    When the user clicks the Sign In button
    Then the Organizations page should be displayed
    When the user clicks the Menu icon in the top-left corner
    And the user selects Users
    Then the user should be redirected to the Users page
    When the user clicks Add New
    And the user selects Add New User from the available options
    Then the Add User modal should be displayed
    When the user enters the following details:
      | Email             | Role       | First Name | Last Name | Organization Unit |
      | skumar77@gmail.com | Researcher | Ravi       | Selva     | Anthropic Org     |
    And the user clicks the Add User button
    Then the user should be created successfully
    And the Users page should be displayed
    And the newly created user "skumar77@gmail.com" should appear in the users list
    And the user should have the "Researcher" role

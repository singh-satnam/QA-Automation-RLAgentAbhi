Feature: Create a New Organization
  As a logged-in user
  I want to create a new organization from the My Organizations page
  So that the new organization appears in my list of organizations

  Scenario: Successfully create a new organization
    Given the user navigates to the login page "https://ra-demo.rlcatalyst.com/login"
    And the user clicks the Sign In link
    And the user enters valid credentials:
      | Email                                  | Password       |
      | sundeep.mallya+a@relevancelab.com      | Relevance@123  |
    When the user clicks the Login button
    Then the user should be redirected to the My Organizations page
    When the user clicks the Add New button
    Then the Create Organization form should be displayed
    When the user enters the organization details:
      | Organization Name | Organization Description        |
      | Anthropic Org     | Providing IT services globally  |
    And the user clicks the Create Organization button
    Then a new organization should be created successfully
    And the organization named "Anthropic Org" should be displayed in the list of organizations on the My Organizations page

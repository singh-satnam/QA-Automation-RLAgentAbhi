Feature: Admin Account Settings - Project Accounts

  Scenario: Admin navigates to Account Settings and validates Project Accounts table and popup
    Given the user is on the Research Gateway login page
    When the user signs in as an Admin
    And the user clicks Sign In
    And the user clicks the Account icon and selects Settings
    Then the user is taken to the Back to Organization page
    And the Project Accounts table is displayed
    And the Project Accounts table displays the following column headings:
      | Column Heading |
      | Account Name   |
      | Region         |
      | Account Number |
      | Organization   |
      | Created On     |
      | SRE            |
    When the user clicks the link icon under Account Name
    Then the StandardAccount popup is displayed
    And the popup displays the following fields:
      | Field         |
      | Project Name  |
      | Created On    |
      | Project Owner |
    When the user clicks the X icon to close the popup

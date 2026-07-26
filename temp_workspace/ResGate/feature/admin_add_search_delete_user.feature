Feature: Admin Add User, Search Added User, and Delete User

  Scenario: Admin adds a new user, searches for the added user, and deletes the user
    Given the user is on the ResGate login page
    When the user signs in as an Admin
    Then the user is taken to the My Organizations page
    When the user clicks the hamburger menu to display menu items
    And the user clicks on "Users"
    Then the Users page is displayed
    When the user clicks the "+ Add New" button and selects "Add New User"
    Then the Add User popup is displayed
    When the user fills in the new user details
      | Field      | Value               |
      | Email      | auto_pw@yopmail.com |
      | Role       | Researcher          |
      | First Name | Auto                |
      | Last Name  | skills              |
    And the user clicks the "Add User" button
    When the user clicks in the Search bar and types "auto_pw@yopmail.com" and presses Enter
    Then the user card for "auto_pw@yopmail.com" is displayed
    When the user clicks the three-dot Actions menu on the user card
    And the user selects "Delete User"
    Then the Delete User popup is displayed
    When the user clicks the "Delete User" button
    Then the user is deleted

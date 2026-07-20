Feature: PI Product Details for Project

  Scenario: PI views product details and events for a project
    Given the user is on the Research Gateway login page
    When the user signs in as a PI
    And the user clicks Sign In
    Then the PI lands on the My Projects page successfully
    When the user clicks on the project
    And the user clicks on the product under My Products
    And the user clicks the Product Details tab
    Then the following product fields are present and each has a value
      | Field            |
      | Description      |
      | Created On       |
      | EnableS3Files    |
      | Advanced Details |
      | Bucket Name      |
    And CONNECT and ACTIONS are present on the page
    When the user clicks the Events tab
    Then the Events webtable is displayed
    And the Timestamp column has entries
    And the Status column has entries

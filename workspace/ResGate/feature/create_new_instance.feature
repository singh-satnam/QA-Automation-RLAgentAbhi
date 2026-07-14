Feature: Create New Standard Linux Remote Desktop Instance
  As a user of the ResGate platform
  I want to launch a new Standard Linux Remote Desktop instance
  So that I can use it for my project work

  Scenario: Launch a Standard Linux Remote Desktop instance with project configuration
    Given the user navigates to the login page
    And the user enters "res" credentials
    Then the user clicks on the Sign In button
    Then the user should be landing on the "My Projects" page
    And the user verifies the "Automation Testing" card is present
    When the user clicks on the "Automation Testing" project
    Then the "Automation Testing" page is displayed
    And the page should have the following tabs:
      | Tab                 |
      | Project Details     |
      | Available Products  |
      | My Products         |
      | Shared Services     |
    And the user clicks on "LAUNCH NOW" under "Standard Linux Remote Desktop"
    Then the create new instance page is displayed
    And the user fills the Product Name as "Demo-RD+<random_number>"
    And the user selects the below option under Study Selection:
      | Study Selection                          |
      | GenomicsStudyData(read-only, Internal)   |
    And the user fills the below details under project configuration:
      | Field            | Value       |
      | AvailabilityZone | us-east-2a  |
      | EBSVolumeSize    | 80          |
      | InstanceType     | t3.small    |
    And the user clicks on "LAUNCH NOW" at the top right side of the page
    Then the user lands on the "My Products" tab with the message "Standard Linux Remote Desktop launched successfully!"
    And the "My Products" tab should have the entered Product Name as one of the Product containers

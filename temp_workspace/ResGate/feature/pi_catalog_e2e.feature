Feature: PI Catalog End-to-End Product Assignment

  Scenario: PI searches catalog with filters and assigns products to a project
    Given the user is on the ResGate login page
    When the user enters valid PI credentials
    And the user clicks Sign In
    Then the PI is on the My Projects page

    When the user clicks the hamburger menu and selects Catalog
    Then the View dropdown displays "O.U. Catalog"
    And the Search with Category Filter is displayed

    When the user clicks the "All" Category Filter option
    And the user clicks the "Research" Category Filter option
    And the user clicks the "Secure" Category Filter option
    And the user clicks the "RA Standard" Category Filter option

    When the user searches for "zzz"
    Then the message "We could not find any products that matched your search." is displayed

    And the user clicks the "All" Category Filter option
    And clears the text from the Category Filter option

    When the user searches for "EC2"
    Then matching products are displayed

    When the user selects "Amazon EC2 Linux" by clicking its checkbox
    And clears the text from the Category Filter option

    When the user searches for "JupyterLab"
    Then matching products are displayed  

    When the user selects "JupyterLab" by clicking its checkbox
    And the user clicks Assign Selected to Project
    Then the Assign to a Project modal is displayed

    When the user selects "AutomationProjDonotTouch" from the Choose a project from the list dropdown
    And the user clicks Assign
    Then the confirmation message "The selected products are being updated to your project. This can take some time to complete. You can monitor the progress in the events tab of the project." is displayed

# mobile-auto export: source=mobile/scenarios/EXAMPLE-1/scenarios.json source_sha256=c885ef1862fc9bf6c4561915cf0963f5dbe8c56ef61c1c5b8c4a6bffaf359254 content_sha256=c69c666d56a71221800124391292835f5ced7bf528bb448ae8291e2fa1441585
@EXAMPLE-1
Feature: Example: buy foreign currency in a banking app
  EXAMPLE-1: https://jira.example.com/browse/EXAMPLE-1

  @positive
  Scenario: Buy 250 EUR within the daily limit
    Given the customer signs in as uat-fx-01
    And the customer opens the foreign exchange screen
    When the customer buys 250 EUR
    Then the confirmation shows 250.00 EUR

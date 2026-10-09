# mobile-auto export: source=mobile/scenarios/EXAMPLE-1/scenarios.json source_sha256=c885ef1862fc9bf6c4561915cf0963f5dbe8c56ef61c1c5b8c4a6bffaf359254 content_sha256=abd00c69ee7626cfbbb45f73d3c441c5d34be25a9ffe600ea42f67ed990fa931
@EXAMPLE-1
Feature: Example: buy foreign currency in a banking app
  EXAMPLE-1: https://jira.example.com/browse/EXAMPLE-1

  @positive
  Scenario: Buy 100 USD within the daily limit
    Given the customer signs in as uat-fx-01
    And the customer opens the foreign exchange screen
    When the customer buys 100 USD
    Then the confirmation shows 100.00 USD

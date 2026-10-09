# mobile-auto export: source=mobile/scenarios/EXAMPLE-1/scenarios.json source_sha256=c885ef1862fc9bf6c4561915cf0963f5dbe8c56ef61c1c5b8c4a6bffaf359254 content_sha256=4896c6aee53e78b2997154f85c0d1ccd370cb16c10298d1d6fe31dacfa968868
@EXAMPLE-1
Feature: Example: buy foreign currency in a banking app
  EXAMPLE-1: https://jira.example.com/browse/EXAMPLE-1

  @negative
  Scenario: Buying 50001 USD over the daily limit is refused
    Given the customer signs in as uat-fx-01
    And the customer opens the foreign exchange screen
    When the customer buys 50001 USD
    Then the message Amount exceeds your daily limit is shown
    And no purchase is confirmed

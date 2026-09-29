# mobile-auto export: source=mobile/scenarios/EXAMPLE-1/scenarios.json source_sha256=ec411ac4bc4ed2b354a47b9844e2489095df23026b5904fcf22f7fccbd8dae1d content_sha256=1a4d58448b7ec9e2f347bb1212e5bfeafa309cd5dd47a8cc0977b0f84297a893
@EXAMPLE-1
Feature: Example: buy foreign currency in a banking app
  EXAMPLE-1: https://jira.example.com/browse/EXAMPLE-1

  Background:
    Given the customer is signed in
    And the customer is on the foreign exchange screen

  @positive
  Scenario Outline: Buy foreign currency within the daily limit
    When the customer buys <amount> <currency>
    Then the confirmation shows <expected_total>

    Examples:
      | example | currency | amount | expected_total |
      | USD     | USD      | 100    | 100.00 USD     |
      | EUR     | EUR      | 250    | 250.00 EUR     |

  @negative
  Scenario Outline: Buying over the daily limit is refused
    When the customer buys <amount> <currency>
    Then the message <expected_message> is shown
    And no purchase is confirmed

    Examples:
      | example   | currency | amount | expected_message                |
      | USD-limit | USD      | 50001  | Amount exceeds your daily limit |

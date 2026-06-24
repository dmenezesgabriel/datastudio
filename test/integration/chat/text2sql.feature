Feature: Text2SQL graph answers natural language questions

  Scenario: Query the NYC taxi dataset
    Given a DuckDB engine seeded with dev data
    And a text2sql graph configured with OpenCode Go settings
    When I ask "How many taxi trips are in the dataset?"
    Then I receive a non-empty natural language answer
    And the answer contains a number

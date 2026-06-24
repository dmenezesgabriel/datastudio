Feature: Language model via OpenCode Go API

  Scenario: Chat model returns a response to a simple prompt
    Given a language model configured with OpenCode Go settings
    When I send the prompt "Say hello in one word"
    Then I receive a non-empty text response

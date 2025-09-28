Feature: DaedalusForge Orchestrator Execution
  As a developer, I want to test the orchestrator's ability to run different process configurations
  to ensure functional correctness and robustness.

  Scenario Outline: Running a process defined in a YAML file
    Given a process configuration defined in "<config_file>"
    And a mock LLM client configured for the "<scenario_name>" scenario
    When the orchestrator runs with the initial context
    Then the final state artifact "<artifact_key>" should exist and contain "<expected_content>"
    And the mock LLM should have been called <call_count> times

    Examples:
      | config_file                     | scenario_name      | artifact_key  | expected_content           | call_count |
      | "configs/process_config.yaml"   | "linear_process"   | "copy_canais" | "Adapted copy for channels"  | 8          |
      | "configs/plan_and_execute.yaml" | "plan_and_execute" | "final_article"  | "The final article content." | 4          |

  Scenario: Running a process with a failing agent
    Given a process configuration defined in "configs/process_config.yaml"
    And a mock LLM client configured for the "failing_agent" scenario
    When the orchestrator runs with the initial context
    Then the final state quality artifact "error" should contain "LLM invocation failed"

  Scenario: Running a process with an invalid agent reference in edges
    Given a process configuration defined in "configs/invalid_edge_config.yaml"
    When the orchestrator is initialized
    Then it should raise a "DSLValidationError"
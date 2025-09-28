Feature: DaedalusForge Orchestrator Execution
  As a developer, I want to test the orchestrator's ability to run different process configurations
  to ensure functional correctness and robustness.

  Scenario Outline: Running a process defined in a YAML file
    Given a process configuration defined in "<config_file>"
    And a mock LLM client configured for the "<scenario_name>" scenario
    When the orchestrator runs with the initial context
    Then the final state artifact "<artifact_key>" should exist
    And the mock LLM should have been called <call_count> times

    Examples:
      | config_file                     | scenario_name      | artifact_key     | call_count |
      | "configs/process_config.yaml"   | "linear_process"   | "copy_principal" | 7          |
      | "configs/plan_and_execute.yaml" | "plan_and_execute" | "final_article"  | 4          |
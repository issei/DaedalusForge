import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from unittest.mock import MagicMock, patch
import json
from typing import Any

from src.orchestrator import Orchestrator
from src.model import GlobalState
from langchain_core.tools import BaseTool

# Define a mock tool that satisfies the BaseTool interface for validation
class MockTool(BaseTool):
    name: str = "mock_tool"
    description: str = "A mock tool for testing"

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        return "Mocked tool output"

# Point pytest-bdd to the feature file
scenarios('../features/orchestrator_execution.feature')

@pytest.fixture
def mock_llm_client():
    """A pytest fixture to create a mock LLM client that handles both regular and structured output calls."""
    client = MagicMock()
    # The structured output mock is a separate object to have its own invoke method
    structured_mock = MagicMock()
    client.with_structured_output.return_value = structured_mock
    return client

@pytest.fixture
def orchestrator_context():
    """A fixture to hold shared state between steps."""
    return {}

@given(parsers.parse('a process configuration defined in "{config_file}"'))
def given_process_config(config_file, orchestrator_context):
    """Loads the YAML and prepares the orchestrator."""
    orchestrator_context['config_path'] = config_file.strip('"')

@given(parsers.parse('a mock LLM client configured for the "{scenario_name}" scenario'))
def given_mock_llm_for_scenario(mock_llm_client, scenario_name, orchestrator_context):
    """Configures the mock LLM with a sequence of responses for a specific scenario."""
    scenario_name = scenario_name.strip('"')

    if scenario_name == "linear_process":
        # This process involves a loop that runs until the critic approves.
        # All agents in this flow use structured output.
        responses = [
            {"dores_promessas": "Initial ideas..."},      # 1. analise
            {"copy_principal": "First draft"},            # 2. geracao_copy
            {"feedback": "REFINAR"},                       # 3. critico_revisor
            {"copy_principal": "Second draft"},           # 4. geracao_copy
            {"feedback": "REFINAR"},                       # 5. critico_revisor
            {"copy_principal": "Final draft"},            # 6. geracao_copy
            {"feedback": "APROVADO"},                      # 7. critico_revisor
        ]
        mock_llm_client.with_structured_output.return_value.invoke.side_effect = responses

    elif scenario_name == "plan_and_execute":
        # This process has a loop controlled by the `updater` agent.
        structured_responses = [
            ["research", "write"],                          # 1. planner
            {"final_article": "The final article content."} # 2. finalizer
        ]
        # The tool-using agent makes regular calls.
        tool_responses = [
            MagicMock(content="Research result"), # 1. executor
            MagicMock(content="Writing result")   # 2. executor
        ]
        mock_llm_client.with_structured_output.return_value.invoke.side_effect = structured_responses
        mock_llm_client.invoke.side_effect = tool_responses

    orchestrator_context['mock_llm'] = mock_llm_client

@when('the orchestrator runs with the initial context')
def when_orchestrator_runs(orchestrator_context, mock_llm_client):
    """Runs the orchestrator and stores the final state."""

    mock_tavily_tool = MockTool(name="tavily_search", description="A mock search tool")

    # The ToolRegistry does not need to be patched as the real implementation is now correct.
    with patch('src.orchestrator.Orchestrator._create_llm_client', return_value=mock_llm_client), \
         patch('src.orchestrator.TavilySearchResults', return_value=mock_tavily_tool):

        orchestrator = Orchestrator(config_path=orchestrator_context['config_path'])

        initial_context = {
            "briefing": {"infoproduto": {"nome": "Test Product"}},
            "user_request": "Test request",
            "topic": "The History of AI"
        }

        final_state = orchestrator.run(initial_context)
        orchestrator_context['final_state'] = final_state

@then(parsers.parse('the final state artifact "{artifact_key}" should exist'))
def then_artifact_exists(artifact_key, orchestrator_context):
    """Checks if a specific artifact was created."""
    final_state = orchestrator_context['final_state']
    clean_artifact_key = artifact_key.strip('"')
    assert clean_artifact_key in final_state.artifacts, \
        f"Artifact '{clean_artifact_key}' not found in {list(final_state.artifacts.keys())}"

@then(parsers.parse('the mock LLM should have been called {call_count:d} times'))
def then_llm_call_count(call_count, mock_llm_client):
    """Checks how many times the mock LLM was invoked."""
    total_calls = (
        mock_llm_client.invoke.call_count +
        mock_llm_client.with_structured_output.return_value.invoke.call_count
    )
    assert total_calls == call_count, \
        f"Expected {call_count} calls, but got {total_calls}"
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

# A dictionary to hold mock responses for different scenarios, promoting clarity and maintainability.
SCENARIO_RESPONSES = {
    "linear_process": {
        "structured_output": [],  # All calls are regular invoke calls
        "regular_output": [
            # 1. analise_dores_promessas
            MagicMock(content={"dores_promessas": "Initial ideas..."}),
            # 2. geracao_copy
            MagicMock(content={"copy_principal": "First draft"}),
            # 3. critico_revisor
            MagicMock(content="REFINAR"),
            # 4. geracao_copy
            MagicMock(content={"copy_principal": "Second draft"}),
            # 5. critico_revisor
            MagicMock(content="REFINAR"),
            # 6. geracao_copy
            MagicMock(content={"copy_principal": "Final draft"}),
            # 7. critico_revisor
            MagicMock(content="APROVADO"),
            # 8. adaptacao_canais
            MagicMock(content={"copy_canais": "Adapted copy for channels"}),
        ]
    },
    "plan_and_execute": {
        "structured_output": [
            ["research", "write"],
            {"final_article": "The final article content."}
        ],
        "regular_output": [
            MagicMock(content="Final Answer: Research result"),
            MagicMock(content="Final Answer: Writing result")
        ]
    },
    "failing_agent": {
        "structured_output": [],
        "regular_output": [Exception("LLM invocation failed")]
    }
}

@given(parsers.parse('a mock LLM client configured for the "{scenario_name}" scenario'))
def given_mock_llm_for_scenario(mock_llm_client, scenario_name, orchestrator_context):
    """Configures the mock LLM with a sequence of responses for a specific scenario."""
    scenario_name = scenario_name.strip('"')
    responses = SCENARIO_RESPONSES.get(scenario_name)

    if not responses:
        raise ValueError(f"Scenario '{scenario_name}' not configured in SCENARIO_RESPONSES.")

    # Configure structured and regular outputs based on the scenario's needs
    if responses.get("structured_output"):
        mock_llm_client.with_structured_output.return_value.invoke.side_effect = responses["structured_output"]
    if responses.get("regular_output"):
        mock_llm_client.invoke.side_effect = responses["regular_output"]

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

@then(parsers.parse('the final state artifact "{artifact_key}" should exist and contain "{expected_content}"'))
def then_artifact_exists_and_contains(artifact_key, expected_content, orchestrator_context):
    """Checks if an artifact exists and its content matches expectations."""
    final_state = orchestrator_context['final_state']
    clean_artifact_key = artifact_key.strip('"')
    clean_expected_content = expected_content.strip('"')

    assert clean_artifact_key in final_state.artifacts, \
        f"Artifact '{clean_artifact_key}' not found in {list(final_state.artifacts.keys())}"

    actual_content = str(final_state.artifacts[clean_artifact_key])
    assert clean_expected_content in actual_content, \
        f"Expected content '{clean_expected_content}' not found in artifact '{clean_artifact_key}'."

@then(parsers.parse('the mock LLM should have been called {call_count:d} times'))
def then_llm_call_count(call_count, mock_llm_client):
    """Checks how many times the mock LLM was invoked."""
    total_calls = (
        mock_llm_client.invoke.call_count +
        mock_llm_client.with_structured_output.return_value.invoke.call_count
    )
    assert total_calls == call_count, \
        f"Expected {call_count} calls, but got {total_calls}"


@then(parsers.parse('the final state quality artifact "{artifact_key}" should contain "{expected_content}"'))
def then_quality_artifact_contains(artifact_key, expected_content, orchestrator_context):
    """Checks if a quality artifact contains a specific string."""
    final_state = orchestrator_context['final_state']
    clean_artifact_key = artifact_key.strip('"')
    clean_expected_content = expected_content.strip('"')

    assert clean_artifact_key in final_state.quality, \
        f"Quality artifact '{clean_artifact_key}' not found in {list(final_state.quality.keys())}"

    actual_content = str(final_state.quality[clean_artifact_key])
    assert clean_expected_content in actual_content, \
        f"Expected content '{clean_expected_content}' not found in quality artifact '{clean_artifact_key}'."


@when('the orchestrator is initialized')
def when_orchestrator_is_initialized(orchestrator_context):
    """Stores the function that should raise an error, to be called in the 'then' step."""
    # This step is designed to be followed by a step that checks for an exception.
    # It prepares a callable that will perform the initialization.
    from src.orchestrator import Orchestrator
    orchestrator_context['init_func'] = lambda: Orchestrator(config_path=orchestrator_context['config_path'])


@then(parsers.parse('it should raise a "{exception_name}"'))
def then_it_should_raise(exception_name, orchestrator_context):
    """Checks if the expected exception was raised during initialization."""
    # Importing here to avoid potential circular dependency issues at module level
    from src.exceptions import DSLValidationError

    clean_exception_name = exception_name.strip('"')

    expected_exception = {"DSLValidationError": DSLValidationError}.get(clean_exception_name)
    if not expected_exception:
        raise ValueError(f"Exception type '{clean_exception_name}' not recognized for testing.")

    with pytest.raises(expected_exception) as excinfo:
        # The 'when' step prepared this function for us to call
        orchestrator_context['init_func']()

    assert excinfo.value is not None, f"Expected exception {clean_exception_name} was not raised."
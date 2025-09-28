from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Callable, Optional, Dict, Any, List

# Tenacity para retentativas robustas
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    RetryError,
)

# LangChain para integração com LLMs e Ferramentas
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
import httpx

from .model import GlobalState, AgentOutput

class BaseAgent(ABC):
    """Contrato base para agentes plugáveis."""
    name: str

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def execute(self, state: GlobalState) -> AgentOutput:
        """Executa o agente e retorna deltas para o estado."""
        raise NotImplementedError

class DeterministicAgent(BaseAgent):
    """
    Agente que executa uma função Python determinística.
    """
    def __init__(self, name: str, function: Callable[[GlobalState], AgentOutput]):
        super().__init__(name)
        self.function = function

    def execute(self, state: GlobalState) -> AgentOutput:
        print(f"Executando DeterministicAgent '{self.name}'...")
        try:
            return self.function(state)
        except Exception as e:
            return AgentOutput(quality={"error": f"Erro ao executar a função em {self.name}: {e}"})


class LLMAgent(BaseAgent):
    """
    Agente que invoca um LLM com um prompt simples.
    """
    def __init__(
        self,
        name: str,
        purpose: str,
        llm_client: BaseChatModel,
        prompt_template: str,
        output_key: str,
        force_json_output: bool = False,
    ):
        super().__init__(name)
        self.purpose = purpose
        self.llm = llm_client
        self.prompt_template = prompt_template
        self.output_key = output_key
        self.force_json_output = force_json_output

    def _render_prompt(self, state: GlobalState) -> str:
        data = {"context": state.context, "artifacts": state.artifacts, "quality": state.quality}
        try:
            return self.prompt_template.format(**data)
        except KeyError as e:
            error_msg = f"Chave ausente no template do prompt: {e}"
            return f"{self.prompt_template}\n\n[AVISO] {error_msg}\n[CTX]{state.context}\n[ART]{list(state.artifacts.keys())}\n[QLT]{state.quality}"

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(3))
    def _invoke_llm(self, prompt: str) -> Any:
        client = self.llm
        try:
            if self.force_json_output:
                # For structured output, we expect the raw dict/list
                return client.with_structured_output().invoke([HumanMessage(content=prompt)])
            else:
                # For regular output, we expect a message object
                response = client.invoke([HumanMessage(content=prompt)])
                return response.content
        except Exception as e:
            print(f"Erro na chamada da API para o LLM: {e}. Tentando novamente...")
            raise

    def execute(self, state: GlobalState) -> AgentOutput:
        prompt = self._render_prompt(state)
        try:
            generated_content = self._invoke_llm(prompt)
            return AgentOutput(artifacts={self.output_key: generated_content})
        except RetryError as e:
            error_message = f"Falha ao invocar o LLM após múltiplas tentativas: {e}"
            return AgentOutput(quality={"error": error_message})


class ToolUsingAgent(BaseAgent):
    """
    Um agente que usa o padrão ReAct para realizar tarefas com ferramentas.
    """
    def __init__(self, name: str, purpose: str, llm: BaseChatModel, prompt_template: str, tools: List[BaseTool], output_key: str):
        super().__init__(name)
        self.purpose = purpose
        self.output_key = output_key

        agent_prompt = ChatPromptTemplate.from_template(prompt_template)
        react_agent = create_react_agent(llm, tools, agent_prompt)
        self.agent_executor = AgentExecutor(agent=react_agent, tools=tools, verbose=True)

    def execute(self, state: GlobalState) -> AgentOutput:
        input_str = f"Contexto: {state.context}\nArtefatos: {state.artifacts}\nQualidade: {state.quality}"
        try:
            result = self.agent_executor.invoke({"input": input_str})
            return AgentOutput(artifacts={self.output_key: result.get("output")})
        except Exception as e:
            error_message = f"Falha ao executar ToolUsingAgent {self.name}: {e}"
            return AgentOutput(quality={"error": error_message})


class ReflectionAgent(BaseAgent): # Changed from JudgeAgent to BaseAgent
    """
    Evolução do JudgeAgent, capaz de gerar feedback textual detalhado.
    """
    def __init__(self, name: str, purpose: str, llm_client: BaseChatModel, prompt_template: str):
        super().__init__(name)
        self.purpose = purpose
        self.prompt_template = prompt_template
        self.llm_agent = LLMAgent(name, purpose, llm_client, prompt_template, output_key="reflection_feedback")

    def execute(self, state: GlobalState) -> AgentOutput:
        print(f"Executando ReflectionAgent '{self.name}'...")
        llm_output = self.llm_agent.execute(state)
        feedback = llm_output.artifacts.get("reflection_feedback", "")

        if "APROVADO" in feedback.upper():
            status = "APROVADO"
        else:
            status = "REFINAR"

        attempts = int(state.quality.get("attempts", 0)) + 1
        return AgentOutput(
            quality={"review_status": status, "feedback": feedback, "attempts": attempts},
            messages=[{"agent": self.name, "kind": "reflection", "feedback": feedback}],
        )


class SupervisorAgent(BaseAgent):
    """
    Orquestra o fluxo decidindo qual agente chamar a seguir.
    """
    def __init__(self, name: str, purpose: str, llm_client: BaseChatModel, prompt_template: str, available_agents: List[str]):
        super().__init__(name)
        self.purpose = purpose
        self.available_agents = available_agents
        self.prompt_template = prompt_template.format(available_agents=str(available_agents + ["FINISH"]))
        self.llm_agent = LLMAgent(name, purpose, llm_client, self.prompt_template, output_key="next_agent")

    def execute(self, state: GlobalState) -> AgentOutput:
        print(f"Executando SupervisorAgent '{self.name}'...")
        llm_output = self.llm_agent.execute(state)
        next_agent = llm_output.artifacts.get("next_agent", "FINISH").strip()

        if next_agent not in self.available_agents + ["FINISH"]:
            print(f"AVISO: Supervisor retornou um agente inválido '{next_agent}'. Finalizando fluxo.")
            next_agent = "FINISH"

        return AgentOutput(quality={"next_agent": next_agent})


class UTCPAgent(BaseAgent):
    """
    Agente que executa chamadas de API diretas com base em manuais UTCP.
    """
    def __init__(self, name: str, purpose: str, llm_client: BaseChatModel, prompt_template: str, utcp_manuals: List[Dict], output_key: str):
        super().__init__(name)
        self.purpose = purpose
        self.utcp_manuals = utcp_manuals
        self.output_key = output_key
        self.llm_agent = LLMAgent(
            name,
            purpose,
            llm_client,
            prompt_template,
            output_key="decision",
            force_json_output=True
        )

    def execute(self, state: GlobalState) -> AgentOutput:
        print(f"Executando UTCPAgent '{self.name}'...")

        prompt_template_com_manuais = f"{self.llm_agent.prompt_template}\n\nManuais de Ferramentas Disponíveis (UTCP):\n{self.utcp_manuals}"

        temp_llm = LLMAgent(
            self.name,
            self.purpose,
            self.llm_agent.llm,
            prompt_template_com_manuais,
            "decision",
            True
        )
        llm_output = temp_llm.execute(state)
        decision = llm_output.artifacts.get("decision", {})

        if not decision or "tool_name" not in decision:
            return AgentOutput(quality={"error": "UTCPAgent não conseguiu decidir qual ferramenta usar."})

        tool_name = decision.get("tool_name")
        parameters = decision.get("parameters", {})

        manual_name, tool_func = tool_name.split('.')
        manual = next((m for m in self.utcp_manuals if m.get("name") == manual_name), None)
        if not manual:
            return AgentOutput(quality={"error": f"Manual UTCP '{manual_name}' não encontrado."})

        tool_spec = next((t for t in manual.get("tools", []) if t.get("name") == tool_func), None)
        if not tool_spec:
            return AgentOutput(quality={"error": f"Ferramenta '{tool_func}' não encontrada no manual '{manual_name}'."})

        config = manual.get("provider_config", {})
        base_url = config.get("base_url", "")
        endpoint = tool_spec.get("endpoint", "")
        method = tool_spec.get("method", "GET").upper()

        api_key_env = config.get("auth", {}).get("secret")
        api_key = os.getenv(api_key_env) if api_key_env else None

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        try:
            with httpx.Client() as client:
                if method == "GET":
                    response = client.get(f"{base_url}{endpoint}", params=parameters, headers=headers)
                elif method == "POST":
                    response = client.post(f"{base_url}{endpoint}", json=parameters, headers=headers)

                response.raise_for_status()
                result = response.json()

            return AgentOutput(artifacts={self.output_key: result})

        except httpx.HTTPStatusError as e:
            return AgentOutput(quality={"error": f"Erro na chamada da API: {e.response.status_code} - {e.response.text}"})
        except Exception as e:
            return AgentOutput(quality={"error": f"Erro inesperado no UTCPAgent: {e}"})
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
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import BaseTool
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from model import GlobalState, AgentOutput

class BaseAgent(ABC):
    """Contrato base para agentes plugáveis."""
    name: str

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def execute(self, state: GlobalState) -> AgentOutput:
        """Executa o agente e retorna deltas para o estado."""
        raise NotImplementedError

class LLMAgent(BaseAgent):
    """
    Agente que invoca um LLM com um prompt simples. (Sem alterações)
    - propósito: Propósito do agente (para auditoria/logs).
    - model_name: Nome do modelo (ex: "gemini-1.5-pro", "gpt-4o").
    - prompt_template: f-string que pode referenciar chaves do state.
    - output_key: Chave de saída em artifacts.
    """
    def __init__(
        self,
        name: str,
        purpose: str,
        model_name: str,
        prompt_template: str,
        output_key: str,
        force_json_output: bool = False,
    ):
        super().__init__(name)
        self.purpose = purpose
        self.model_name = model_name
        self.prompt_template = prompt_template
        self.output_key = output_key
        self.force_json_output = force_json_output

        _google_key = os.getenv("GOOGLE_API_KEY")
        _openai_key = os.getenv("OPENAI_API_KEY")

        self.llm = None
        if "gemini" in self.model_name.lower() and _google_key:
            self.llm = ChatGoogleGenerativeAI(model=self.model_name, temperature=0.0, google_api_key=_google_key)
        elif "gpt" in self.model_name.lower() and _openai_key:
            self.llm = ChatOpenAI(model=self.model_name, temperature=0.0, openai_api_key=_openai_key)

        if not self.llm:
            raise ValueError(f"Nenhum LLM pôde ser inicializado para '{self.model_name}'.")

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
        if self.force_json_output:
            client = client.with_structured_output()
        try:
            response = client.invoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            print(f"Erro na chamada da API para {self.model_name}: {e}. Tentando novamente...")
            raise

    def execute(self, state: GlobalState) -> AgentOutput:
        prompt = self._render_prompt(state)
        try:
            generated_content = self._invoke_llm(prompt)
            return AgentOutput(artifacts={self.output_key: generated_content})
        except RetryError as e:
            error_message = f"Falha ao invocar o LLM {self.model_name} após múltiplas tentativas: {e}"
            return AgentOutput(quality={"error": error_message})


class ToolUsingAgent(BaseAgent):
    """
    **NOVO AGENTE**: Um agente que usa o padrão ReAct para realizar tarefas com ferramentas.
    - Inspirado na Lição 2 e 6 dos notebooks O'Reilly.
    """
    def __init__(self, name: str, purpose: str, model_name: str, prompt_template: str, tools: List[BaseTool], output_key: str):
        super().__init__(name)
        self.purpose = purpose
        self.output_key = output_key

        _google_key = os.getenv("GOOGLE_API_KEY")
        _openai_key = os.getenv("OPENAI_API_KEY")
        llm = None
        if "gemini" in model_name.lower() and _google_key:
            llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.0, google_api_key=_google_key)
        elif "gpt" in model_name.lower() and _openai_key:
            llm = ChatOpenAI(model=model_name, temperature=0.0, openai_api_key=_openai_key)

        if not llm:
            raise ValueError(f"Nenhum LLM pôde ser inicializado para '{model_name}'.")

        # Cria o agente ReAct
        agent_prompt = ChatPromptTemplate.from_template(prompt_template)
        react_agent = create_react_agent(llm, tools, agent_prompt)
        self.agent_executor = AgentExecutor(agent=react_agent, tools=tools, verbose=True)

    def execute(self, state: GlobalState) -> AgentOutput:
        # A entrada para o agente ReAct é uma combinação do estado
        input_str = f"Contexto: {state.context}\nArtefatos: {state.artifacts}\nQualidade: {state.quality}"
        try:
            result = self.agent_executor.invoke({"input": input_str})
            return AgentOutput(artifacts={self.output_key: result.get("output")})
        except Exception as e:
            error_message = f"Falha ao executar ToolUsingAgent {self.name}: {e}"
            return AgentOutput(quality={"error": error_message})


class ReflectionAgent(JudgeAgent):
    """
    **AGENTE MELHORADO**: Evolução do JudgeAgent, capaz de gerar feedback textual detalhado.
    - Inspirado na Lição 7 dos notebooks O'Reilly.
    """
    def __init__(self, name: str, purpose: str, model_name: str, prompt_template: str):
        super().__init__(name=name, purpose=purpose)
        self.model_name = model_name
        self.prompt_template = prompt_template
        # A lógica do LLM é similar ao LLMAgent
        self.llm_agent = LLMAgent(name, purpose, model_name, prompt_template, output_key="reflection_feedback")

    def execute(self, state: GlobalState) -> AgentOutput:
        print(f"Executando ReflectionAgent '{self.name}'...")
        # Usa o LLM para gerar o feedback
        llm_output = self.llm_agent.execute(state)
        feedback = llm_output.artifacts.get("reflection_feedback", "")

        # Determina o status com base no feedback
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
    **NOVO AGENTE**: Orquestra o fluxo decidindo qual agente chamar a seguir.
    - Inspirado na Lição 8 dos notebooks O'Reilly.
    """
    def __init__(self, name: str, purpose: str, model_name: str, prompt_template: str, available_agents: List[str]):
        super().__init__(name)
        self.purpose = purpose
        self.available_agents = available_agents
        # Adiciona 'FINISH' como uma opção válida
        self.prompt_template = prompt_template.format(available_agents=str(available_agents + ["FINISH"]))
        self.llm_agent = LLMAgent(name, purpose, model_name, self.prompt_template, output_key="next_agent")

    def execute(self, state: GlobalState) -> AgentOutput:
        print(f"Executando SupervisorAgent '{self.name}'...")
        llm_output = self.llm_agent.execute(state)
        next_agent = llm_output.artifacts.get("next_agent", "FINISH").strip()

        if next_agent not in self.available_agents + ["FINISH"]:
            print(f"AVISO: Supervisor retornou um agente inválido '{next_agent}'. Finalizando fluxo.")
            next_agent = "FINISH"

        # O resultado é armazenado em `quality` para ser usado na aresta condicional
        return AgentOutput(quality={"next_agent": next_agent})
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Callable, Optional, Dict, Any

# Tenacity para retentativas robustas
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    RetryError,
)

# LangChain para integração com LLMs
from langchain_core.messages import HumanMessage
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
    Agente que invoca um LLM real (Google Gemini ou OpenAI GPT) via LangChain.
    - purpose: Propósito do agente (para auditoria/logs).
    - model_name: Nome do modelo (ex: "gemini-1.5-pro", "gpt-4o").
    - prompt_template: f-string que pode referenciar chaves do state.
    - output_key: Chave de saída em artifacts.
    - force_json_output: Se True, força a saída do LLM para JSON.
    """
    def __init__(
        self,
        name: str,
        purpose: str,
        model_name: str,
        prompt_template: str,
        output_key: str,
        force_json_output: bool = False,
        google_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        super().__init__(name)
        self.purpose = purpose
        self.model_name = model_name
        self.prompt_template = prompt_template
        self.output_key = output_key
        self.force_json_output = force_json_output

        # Carrega chaves de API do ambiente se não forem fornecidas
        _google_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        _openai_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        # Inicializa os clientes dos LLMs
        self.gemini_client = None
        if "gemini" in self.model_name.lower() and _google_key:
            self.gemini_client = ChatGoogleGenerativeAI(
                model=self.model_name,
                temperature=0.0,
                google_api_key=_google_key
            )

        self.openai_client = None
        if "gpt" in self.model_name.lower() and _openai_key:
            self.openai_client = ChatOpenAI(
                model=self.model_name,
                temperature=0.0,
                openai_api_key=_openai_key
            )

        if not self.gemini_client and not self.openai_client:
            raise ValueError(
                f"Nenhum cliente de LLM pôde ser inicializado para o modelo '{self.model_name}'. "
                "Verifique o nome do modelo e se as chaves de API (GOOGLE_API_KEY/OPENAI_API_KEY) "
                "estão configuradas como variáveis de ambiente."
            )

    def _render_prompt(self, state: GlobalState) -> str:
        # Render simples e resiliente (sem falhar por chaves ausentes).
        data = {
            "context": state.context,
            "artifacts": state.artifacts,
            "quality": state.quality,
        }
        try:
            return self.prompt_template.format(**data)
        except KeyError as e:
            # Fallback: inclui dicts serializados e loga um aviso
            error_msg = f"Chave ausente no template do prompt: {e}"
            return f"{self.prompt_template}\n\n[AVISO] {error_msg}\n[CTX]{state.context}\n[ART]{list(state.artifacts.keys())}\n[QLT]{state.quality}"

    # Decorador para retentativas com backoff exponencial (ex: 1s, 2s, 4s)
    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(3))
    def _invoke_llm(self, prompt: str) -> Any:
        """
        Invoca o LLM apropriado com o prompt, aplicando retentativas e
        tratamento de erros.
        """
        client = None
        if "gemini" in self.model_name.lower():
            client = self.gemini_client
        elif "gpt" in self.model_name.lower():
            client = self.openai_client
        else:
            raise ValueError(f"Modelo não suportado ou cliente não inicializado: {self.model_name}")

        if self.force_json_output:
            client = client.with_structured_output()

        try:
            response = client.invoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            # Captura exceções da API e levanta para o `tenacity` tentar novamente
            print(f"Erro na chamada da API para {self.model_name}: {e}. Tentando novamente...")
            raise

    def execute(self, state: GlobalState) -> AgentOutput:
        prompt = self._render_prompt(state)
        
        try:
            generated_content = self._invoke_llm(prompt)
            
            return AgentOutput(
                artifacts={self.output_key: generated_content},
                messages=[{
                    "agent": self.name,
                    "kind": "llm",
                    "model": self.model_name,
                    "purpose": self.purpose,
                    "status": "success",
                }],
            )
        except RetryError as e:
            # Erro final após todas as retentativas falharem
            error_message = f"Falha ao invocar o LLM {self.model_name} após múltiplas tentativas: {e}"
            return AgentOutput(
                quality={"error": error_message},
                messages=[{
                    "agent": self.name,
                    "kind": "llm",
                    "model": self.model_name,
                    "purpose": self.purpose,
                    "status": "error",
                    "detail": str(e),
                }],
            )


class DeterministicAgent(BaseAgent):
    """
    Encapsula lógica determinística arbitrária.
    A função deve receber GlobalState e devolver AgentOutput.
    """
    def __init__(self, name: str, function: Callable[[GlobalState], AgentOutput]):
        super().__init__(name)
        self.function = function

    def execute(self, state: GlobalState) -> AgentOutput:
        out = self.function(state)
        # Padroniza mensagem de auditoria
        msgs = (out.messages or []) + [{"agent": self.name, "kind": "deterministic"}]
        out.messages = msgs
        return out


class JudgeAgent(BaseAgent):
    """

    Avalia artefatos e produz métricas em `quality`.
    Pode operar via regra determinística ou heurística simples.
    """
    def __init__(
        self,
        name: str,
        purpose: str = "Avaliar qualidade final",
        rule: Optional[Callable[[GlobalState], AgentOutput]] = None,
    ):
        super().__init__(name)
        self.purpose = purpose
        self.rule = rule

    def _default_rule(self, state: GlobalState) -> AgentOutput:
        """
        Heurística simples:
          - Se 'copy_principal' existe e tem > 50 chars => APROVADO
          - Caso contrário => REFINAR
          - Incrementa attempts
        """
        copy_text = state.artifacts.get("copy_principal")
        attempts = int(state.quality.get("attempts", 0))
        
        # A heurística foi ajustada para ser mais realista com saídas de LLM
        status = "APROVADO" if (isinstance(copy_text, (str, dict)) and len(str(copy_text)) > 50) else "REFINAR"
        
        return AgentOutput(
            quality={"review_status": status, "attempts": attempts + 1},
            messages=[{"agent": self.name, "kind": "judge", "rule": "default"}],
        )

    def execute(self, state: GlobalState) -> AgentOutput:
        if self.rule:
            out = self.rule(state)
            msgs = (out.messages or []) + [{"agent": self.name, "kind": "judge", "purpose": self.purpose}]
            out.messages = msgs
            return out
        return self._default_rule(state)

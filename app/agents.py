from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional, Dict, Any
from app.model import GlobalState, AgentOutput


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
    Agente LLM (simulado). Em produção, injete um cliente real (OpenAI, etc.).
    - purpose: propósito do agente (para auditoria/logs)
    - model_name: nome do modelo (para metadata/auditoria)
    - prompt_template: f-string que pode referenciar chaves do state (context/artifacts/quality)
    - output_key: chave de saída em artifacts (ex.: "copy_principal")
    """
    def __init__(
        self,
        name: str,
        purpose: str,
        model_name: str,
        prompt_template: str,
        output_key: str,
    ):
        super().__init__(name)
        self.purpose = purpose
        self.model_name = model_name
        self.prompt_template = prompt_template
        self.output_key = output_key

    def _render_prompt(self, state: GlobalState) -> str:
        # Render simples e resiliente (sem falhar por chaves ausentes).
        data = {
            "context": state.context,
            "artifacts": state.artifacts,
            "quality": state.quality,
        }
        try:
            return self.prompt_template.format(**data)
        except KeyError:
            # fallback: inclui dicts serializados
            return f"{self.prompt_template}\n\n[CTX]{state.context}\n[ART]{list(state.artifacts.keys())}\n[QLT]{state.quality}"

    def _simulate_llm(self, prompt: str) -> str:
        # Simulação: Devolve uma "saída" reprodutível e auditável.
        header = f"[LLM:{self.model_name} | agent={self.name} | purpose={self.purpose}]"
        body = prompt[:3000]  # truncate para evitar outputs gigantes
        return f"{header}\n{body}\n\n[SIMULATED_OUTPUT] Conteúdo gerado com base no briefing e contexto."

    def execute(self, state: GlobalState) -> AgentOutput:
        prompt = self._render_prompt(state)
        generated = self._simulate_llm(prompt)
        return AgentOutput(
            artifacts={self.output_key: generated},
            messages=[{"agent": self.name, "kind": "llm", "model": self.model_name, "purpose": self.purpose}],
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
          - Se 'copy_principal' existe e tem > 200 chars => APROVADO
          - Caso contrário => REFINAR
          - Incrementa attempts
        """
        copy_text = state.artifacts.get("copy_principal")
        attempts = int(state.quality.get("attempts", 0))
        status = "APROVADO" if (isinstance(copy_text, str) and len(copy_text) > 200) else "REFINAR"
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

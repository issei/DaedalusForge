from __future__ import annotations

from typing import Optional, Dict, List, Any, Mapping, MutableMapping
from pydantic import BaseModel


def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge profundo, imutável: retorna um NOVO dicionário.
    - Dicionários são mesclados recursivamente.
    - Listas e outros tipos de `b` SEMPRE sobrescrevem os de `a`.
    """
    if a is None:
        a = {}
    if b is None:
        return dict(a)

    # Start with a copy of the base dictionary
    out = dict(a)

    for k, v_b in b.items():
        v_a = out.get(k)
        if isinstance(v_a, dict) and isinstance(v_b, dict):
            # If both are dicts, merge them recursively
            out[k] = deep_merge(v_a, v_b)
        else:
            # For any other type (including lists or mismatched types),
            # the value from `b` overwrites the value from `a`.
            out[k] = v_b
    return out


class GlobalState(BaseModel):
    """
    Estado compartilhado entre nós. Trate como imutável no design:
    cada nó retorna um NOVO estado a partir do anterior + deltas.
    """
    context: Dict[str, Any] = {}
    artifacts: Dict[str, Any] = {}
    quality: Dict[str, Any] = {}
    messages: List[Dict[str, Any]] = []


class AgentOutput(BaseModel):
    """
    Deltas que um agente produz. Serão "merged" no GlobalState.
    - updates -> merge em state.context
    - artifacts -> merge em state.artifacts
    - quality -> merge em state.quality
    - messages -> extend em state.messages
    """
    updates: Optional[Dict[str, Any]] = None
    artifacts: Optional[Dict[str, Any]] = None
    quality: Optional[Dict[str, Any]] = None
    messages: Optional[List[Dict[str, Any]]] = None


def apply_agent_output(prev: GlobalState, delta: AgentOutput) -> GlobalState:
    """Aplica AgentOutput de forma imutável ao GlobalState."""
    next_context = deep_merge(prev.context, delta.updates or {})
    next_artifacts = deep_merge(prev.artifacts, delta.artifacts or {})
    next_quality = deep_merge(prev.quality, delta.quality or {})
    next_messages = list(prev.messages)
    if delta.messages:
        next_messages.extend(delta.messages)

    return GlobalState(
        context=next_context,
        artifacts=next_artifacts,
        quality=next_quality,
        messages=next_messages,
    )

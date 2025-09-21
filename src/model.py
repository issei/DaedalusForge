from __future__ import annotations

from typing import Optional, Dict, List, Any, Mapping, MutableMapping
from pydantic import BaseModel


def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge profundo, imutável: retorna um NOVO dicionário.
    - dicionário + dicionário: merge recursivo
    - lista + lista: concatena (sem deduplicar)
    - tipos primitivos: b sobrescreve a
    """
    if a is None:
        a = {}
    if b is None:
        return dict(a)

    out: Dict[str, Any] = {}
    a_keys = set(a.keys())
    b_keys = set(b.keys())
    for k in a_keys | b_keys:
        av = a.get(k)
        bv = b.get(k)
        if k in a_keys and k not in b_keys:
            out[k] = av
        elif k not in a_keys and k in b_keys:
            out[k] = bv
        else:
            # k in ambos
            if isinstance(av, dict) and isinstance(bv, dict):
                out[k] = deep_merge(av, bv)
            elif isinstance(av, list) and isinstance(bv, list):
                out[k] = list(av) + list(bv)
            else:
                out[k] = bv
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

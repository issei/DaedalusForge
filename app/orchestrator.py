from __future__ import annotations

import yaml
from typing import Dict, Any, Callable, List, Optional, Tuple

# LangGraph é preferencial; se ausente, há fallback sequencial
try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except Exception:
    HAS_LANGGRAPH = False
    StateGraph = None  # type: ignore
    END = "__END__"    # type: ignore

from app.model import GlobalState, AgentOutput, apply_agent_output
from app.agents import BaseAgent, LLMAgent, DeterministicAgent, JudgeAgent
from app.safe_eval import SafeConditionEvaluator


class DSLValidationError(Exception):
    pass


class Orchestrator:
    """
    Carrega o DSL YAML, valida, instancia agentes e constrói o fluxo.
    """
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.dsl = self._load_and_validate_dsl(config_path)
        self.agent_registry: Dict[str, BaseAgent] = self._instantiate_agents(self.dsl)
        self._compiled_graph = self._build_graph(self.dsl, self.agent_registry)

    # ---------- DSL ----------

    def _load_and_validate_dsl(self, config_path: str) -> Dict[str, Any]:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        # Estrutura mínima
        required_top = {"process", "agents", "edges"}
        if not all(k in cfg for k in required_top):
            raise DSLValidationError("DSL deve conter 'process', 'agents' e 'edges'.")

        proc = cfg["process"]
        if "start" not in proc or "name" not in proc:
            raise DSLValidationError("process.start e process.name são obrigatórios.")
        if "done_condition" not in proc:
            # opcional, mas recomendamos
            proc["done_condition"] = ""

        agents = cfg["agents"]
        if not isinstance(agents, dict) or not agents:
            raise DSLValidationError("agents deve ser um mapa não-vazio.")

        # Validação básica dos edges
        edges = cfg["edges"]
        if not isinstance(edges, list) or not edges:
            raise DSLValidationError("edges deve ser uma lista não-vazia.")

        names = set(agents.keys())
        if proc["start"] not in names:
            raise DSLValidationError("process.start deve referenciar um agente existente.")

        for e in edges:
            if "from" not in e or "to" not in e:
                raise DSLValidationError("Cada edge deve conter 'from' e 'to'.")
            if e["from"] not in names:
                raise DSLValidationError(f"Edge.from desconhecido: {e['from']}")
            if e["to"] != "__end__" and e["to"] not in names:
                raise DSLValidationError(f"Edge.to desconhecido: {e['to']}")
            if "condition" in e and not isinstance(e["condition"], str):
                raise DSLValidationError("Edge.condition (se presente) deve ser string.")

        # Done condition validável
        try:
            _ = SafeConditionEvaluator(proc.get("done_condition", ""))
        except Exception as e:
            raise DSLValidationError(f"process.done_condition inválida: {e}") from e

        return cfg

    # ---------- Agents ----------

    def _instantiate_agents(self, cfg: Dict[str, Any]) -> Dict[str, BaseAgent]:
        """
        Constrói instâncias de agentes a partir do DSL.
        Para DeterministicAgent, suporta um registry simples de funções.
        """
        registry: Dict[str, BaseAgent] = {}

        # Funções determinísticas de exemplo (registre as suas aqui)
        def _fn_consolidar_contexto(state: GlobalState) -> AgentOutput:
            briefing = state.context.get("briefing", {})
            dores = state.artifacts.get("dores_promessas", "N/D")
            # Coloca um resumo de contexto consolidado
            return AgentOutput(
                updates={"contexto_consolidado": {"briefing": briefing, "dores_promessas": bool(dores)}},
                messages=[{"note": "Contexto consolidado para geração de copy"}],
            )

        deterministic_functions = {
            "consolidar_contexto": _fn_consolidar_contexto,
        }

        for name, spec in cfg["agents"].items():
            kind = spec.get("kind", "llm")
            purpose = spec.get("purpose", name)
            if kind == "llm":
                model = spec.get("model_name", "gpt-simulado")
                prompt = spec.get("prompt_template", "Gere conteúdo.\nContexto: {context}\nArtefatos: {artifacts}")
                output_key = spec.get("output_key", name)
                registry[name] = LLMAgent(
                    name=name,
                    purpose=purpose,
                    model_name=model,
                    prompt_template=prompt,
                    output_key=output_key,
                )
            elif kind == "deterministic":
                fn_name = spec.get("function")
                if not fn_name or fn_name not in deterministic_functions:
                    raise DSLValidationError(f"Agente determinístico '{name}' requer 'function' conhecida.")
                registry[name] = DeterministicAgent(name=name, function=deterministic_functions[fn_name])
            elif kind == "judge":
                # Judge com regra default simples (você pode plugar outra)
                registry[name] = JudgeAgent(name=name, purpose=purpose)
            else:
                raise DSLValidationError(f"kind de agente não suportado: {kind}")

        return registry

    # ---------- Graph ----------

    def _wrap_node(self, agent: BaseAgent) -> Callable[[GlobalState], GlobalState]:
        def _node_fn(state: GlobalState) -> GlobalState:
            delta = agent.execute(state)
            new_state = apply_agent_output(state, delta)
            return new_state
        return _node_fn

    def _build_graph(
        self,
        cfg: Dict[str, Any],
        registry: Dict[str, BaseAgent],
    ):
        """
        Constrói o grafo. Se LangGraph não estiver disponível, retorna
        um objeto com .invoke() implementado (runner sequencial).
        """
        start_node = cfg["process"]["start"]
        done_expr = cfg["process"].get("done_condition", "")
        done_eval = SafeConditionEvaluator(done_expr)

        # Organiza edges por 'from'
        by_source: Dict[str, List[Dict[str, Any]]] = {}
        for e in cfg["edges"]:
            by_source.setdefault(e["from"], []).append(e)

        if not HAS_LANGGRAPH:
            # -------- Fallback sequencial --------
            class _SeqRunner:
                def __init__(self, orch: Orchestrator):
                    self._orch = orch

                def _pick_next(self, src: str, state: GlobalState) -> Optional[str]:
                    if done_eval.evaluate(state):
                        return "__end__"
                    options = by_source.get(src, [])
                    # 1) Tenta condicionais em ordem
                    for edge in options:
                        cond_str = edge.get("condition")
                        if cond_str:
                            if SafeConditionEvaluator(cond_str).evaluate(state):
                                return edge["to"]
                    # 2) Senão, primeira aresta sem condição (se houver)
                    for edge in options:
                        if "condition" not in edge:
                            return edge["to"]
                    # 3) Sem opções → fim
                    return "__end__"

                def invoke(self, state: GlobalState) -> GlobalState:
                    current = start_node
                    s = state
                    visited_guard = 0
                    while current != "__end__":
                        visited_guard += 1
                        if visited_guard > 1000:
                            # proteção contra loops infinitos
                            break
                        agent = registry[current]
                        s = apply_agent_output(s, agent.execute(s))
                        nxt = self._pick_next(current, s)
                        if nxt == "__end__" or nxt is None:
                            break
                        current = nxt
                    return s

            return _SeqRunner(self)

        # -------- LangGraph --------
        graph = StateGraph(GlobalState)

        # Nós
        for name, agent in registry.items():
            graph.add_node(name, self._wrap_node(agent))

        # Arestas: para cada 'from', criamos uma função de branching
        for src, edges in by_source.items():
            # Constrói estrutura de branching:
            # 1) DONE → END
            # 2) primeiramente edges condicionais (ordem no YAML)
            # 3) fallback: primeira edge sem condição, se existir, senão END
            cond_evals: List[Tuple[str, SafeConditionEvaluator, str]] = []  # (label, evaluator, to)
            fallback_to: Optional[str] = None

            label_idx = 0
            for e in edges:
                if "condition" in e:
                    label = f"C{label_idx}"
                    cond_evals.append((label, SafeConditionEvaluator(e["condition"]), e["to"]))
                    label_idx += 1
                else:
                    if fallback_to is None:
                        fallback_to = e["to"]

            def _branch_fn_factory(
                conds: List[Tuple[str, SafeConditionEvaluator, str]],
                fallback: Optional[str],
            ):
                def _branch(state: GlobalState) -> str:
                    # DONE primeiro
                    if done_eval.evaluate(state):
                        return "END"
                    # Condicionais em ordem
                    for label, evaluator, _to in conds:
                        if evaluator.evaluate(state):
                            return label
                    # Fallback incondicional (se houver)
                    if fallback:
                        return "FALLBACK"
                    return "END"
                return _branch

            mapping = {"END": END}
            for label, _ev, to in cond_evals:
                mapping[label] = to if to != "__end__" else END
            if fallback_to:
                mapping["FALLBACK"] = fallback_to if fallback_to != "__end__" else END

            graph.add_conditional_edges(
                src,
                _branch_fn_factory(cond_evals, fallback_to),
                mapping,
            )

        # Entry
        graph.set_entry_point(start_node)
        return graph.compile()

    # ---------- Exec ----------

    def run(self, initial_context: dict) -> GlobalState:
        init_state = GlobalState(
            context=initial_context or {},
            artifacts={},
            quality={},
            messages=[],
        )
        result = self._compiled_graph.invoke(init_state)

        # LangGraph pode retornar um dict, então normalizamos para GlobalState
        if isinstance(result, dict):
            return GlobalState(**result)
        return result

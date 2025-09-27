from __future__ import annotations
import yaml
from typing import Dict, Any, Callable, List

# LangGraph e dependências
try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False

# LangChain e Ferramentas (exemplos)
from langchain_community.tools import TavilySearchResults
from langchain_experimental.tools import PythonREPLTool

from model import GlobalState, AgentOutput, apply_agent_output
from agents import BaseAgent, LLMAgent, DeterministicAgent, ReflectionAgent, ToolUsingAgent, SupervisorAgent, UTCPAgent
from safe_eval import SafeConditionEvaluator

class DSLValidationError(Exception):
    pass

class ToolRegistry:
    """Um registro simples para funções determinísticas e ferramentas LangChain."""
    def __init__(self):
        self._tools: Dict[str, Any] = {}
        self._register_defaults()

    def _register_defaults(self):
        # Ferramentas LangChain
        self.register("tavily_search", TavilySearchResults(max_results=3))
        self.register("python_repl", PythonREPLTool())

        # Funções determinísticas
        def _fn_consolidar_contexto(state: GlobalState) -> AgentOutput:
            # (mesma implementação de antes)
            briefing = state.context.get("briefing", {})
            dores = state.artifacts.get("dores_promessas", "N/D")
            return AgentOutput(
                updates={"contexto_consolidado": {"briefing": briefing, "dores_promessas": bool(dores)}},
                messages=[{"note": "Contexto consolidado para geração de copy"}],
            )
        self.register("consolidar_contexto", _fn_consolidar_contexto)

    def register(self, name: str, tool_or_func: Any):
        self._tools[name] = tool_or_func

    def get(self, name: str) -> Any:
        if name not in self._tools:
            raise DSLValidationError(f"Ferramenta ou função '{name}' não encontrada no registro.")
        return self._tools[name]

    def get_many(self, names: List[str]) -> List[Any]:
        return [self.get(name) for name in names]


class Orchestrator:
    """Carrega o DSL YAML, valida, instancia agentes e constrói o fluxo."""
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.tool_registry = ToolRegistry()
        self.dsl = self._load_and_validate_dsl(config_path)
        self.utcp_tools = self.dsl.get("tools", {}) # Carrega os manuais UTCP
        self.agent_registry: Dict[str, BaseAgent] = self._instantiate_agents(self.dsl)
        self._compiled_graph = self._build_graph(self.dsl, self.agent_registry)

    # (Função _load_and_validate_dsl permanece a mesma)
    
    def _instantiate_agents(self, cfg: Dict[str, Any]) -> Dict[str, BaseAgent]:
        registry: Dict[str, BaseAgent] = {}
        for name, spec in cfg["agents"].items():
            kind = spec.get("kind", "llm")
            purpose = spec.get("purpose", name)
            model = spec.get("model_name", "gemini-1.5-flash")
            prompt = spec.get("prompt_template", "Contexto: {context}\nArtefatos: {artifacts}")
            output_key = spec.get("output_key", name)

            if kind == "llm":
                registry[name] = LLMAgent(name=name, purpose=purpose, model_name=model, prompt_template=prompt, output_key=output_key)
            elif kind == "deterministic":
                fn_name = spec.get("function")
                registry[name] = DeterministicAgent(name=name, function=self.tool_registry.get(fn_name))
            elif kind == "reflection": # Antigo 'judge'
                registry[name] = ReflectionAgent(name=name, purpose=purpose, model_name=model, prompt_template=prompt)
            elif kind == "tool_using":
                tool_names = spec.get("tools", [])
                tools = self.tool_registry.get_many(tool_names)
                registry[name] = ToolUsingAgent(name=name, purpose=purpose, model_name=model, prompt_template=prompt, tools=tools, output_key=output_key)
            elif kind == "supervisor":
                available_agents = spec.get("available_agents", [])
                registry[name] = SupervisorAgent(name=name, purpose=purpose, model_name=model, prompt_template=prompt, available_agents=available_agents)
            elif kind == "utcp_agent":  # Adicionar este novo bloco
                tool_names = spec.get("tools", [])
                # Garante que os manuais existam antes de passá-los
                utcp_manuals = []
                for t_name in tool_names:
                    manual = self.utcp_tools.get(t_name)
                    if not manual:
                        raise DSLValidationError(f"Manual UTCP '{t_name}' não encontrado na seção 'tools'.")
                    manual['name'] = t_name # Injeta o nome no manual para referência
                    utcp_manuals.append(manual)

                registry[name] = UTCPAgent(
                    name=name,
                    purpose=purpose,
                    model_name=model,
                    prompt_template=prompt,
                    utcp_manuals=utcp_manuals,
                    output_key=output_key
                )
            else:
                raise DSLValidationError(f"Tipo de agente não suportado: {kind}")
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
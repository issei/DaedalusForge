from __future__ import annotations
import yaml
import os
from typing import Dict, Any, Callable, List

# LangGraph e dependências
try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False

# LangChain e Ferramentas
from langchain_community.tools import TavilySearchResults
from langchain_experimental.tools import PythonREPLTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from .model import GlobalState, AgentOutput, apply_agent_output
from .agents import BaseAgent, LLMAgent, ToolUsingAgent, ReflectionAgent, SupervisorAgent, UTCPAgent, DeterministicAgent
from .safe_eval import SafeConditionEvaluator

class DSLValidationError(Exception):
    pass

class ToolRegistry:
    """Um registro simples para funções determinísticas e ferramentas LangChain."""
    def __init__(self):
        self._tools: Dict[str, Any] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register("tavily_search", TavilySearchResults(max_results=3))
        self.register("python_repl", PythonREPLTool())

        def _fn_consolidar_contexto(state: GlobalState) -> AgentOutput:
            briefing = state.context.get("briefing", {})
            dores = state.artifacts.get("dores_promessas", "N/D")
            return AgentOutput(
                updates={"contexto_consolidado": {"briefing": briefing, "dores_promessas": bool(dores)}},
                messages=[{"note": "Contexto consolidado para geração de copy"}],
            )
        self.register("consolidar_contexto", _fn_consolidar_contexto)

        def _fn_update_plan_and_artifacts(state: GlobalState) -> AgentOutput:
            """
            Updates the plan by removing the completed step and appends the
            result to a separate list of step results for final consolidation.
            """
            plan = state.artifacts.get("plan", [])
            step_result = state.artifacts.get("step_result")

            # Archive the result of the completed step
            step_results = state.artifacts.get("step_results", [])
            if step_result:
                step_results.append(step_result)

            return AgentOutput(
                artifacts={
                    "plan": plan[1:] if plan else [],  # Return the rest of the plan
                    "step_results": step_results
                },
                messages=[{"note": f"Completed step. Remaining plan steps: {len(plan) - 1 if plan else 0}"}]
            )
        self.register("update_plan_and_artifacts", _fn_update_plan_and_artifacts)

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
        self.utcp_tools = self.dsl.get("tools", {})
        self.agent_registry: Dict[str, BaseAgent] = self._instantiate_agents(self.dsl)
        self._compiled_graph = self._build_graph(self.dsl, self.agent_registry)

    def _load_and_validate_dsl(self, config_path: str) -> Dict[str, Any]:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            if not isinstance(cfg, dict) or "process" not in cfg or "agents" not in cfg:
                raise DSLValidationError("O arquivo de configuração deve ser um dicionário com as chaves 'process' e 'agents'.")
            return cfg
        except FileNotFoundError:
            raise DSLValidationError(f"Arquivo de configuração não encontrado em: {config_path}")
        except yaml.YAMLError as e:
            raise DSLValidationError(f"Erro ao parsear o arquivo YAML: {e}")

    def _create_llm_client(self, model_name: str) -> BaseChatModel:
        """Cria uma instância de cliente LLM com base no nome do modelo."""
        _google_key = os.getenv("GOOGLE_API_KEY")
        _openai_key = os.getenv("OPENAI_API_KEY")

        if "gemini" in model_name.lower() and _google_key:
            return ChatGoogleGenerativeAI(model=model_name, temperature=0.0, google_api_key=_google_key)
        elif "gpt" in model_name.lower() and _openai_key:
            return ChatOpenAI(model=model_name, temperature=0.0, openai_api_key=_openai_key)

        raise DSLValidationError(f"Nenhum LLM pôde ser inicializado para '{model_name}'. Verifique o nome do modelo e as chaves de API.")

    def _instantiate_agents(self, cfg: Dict[str, Any]) -> Dict[str, BaseAgent]:
        registry: Dict[str, BaseAgent] = {}
        for name, spec in cfg["agents"].items():
            kind = spec.get("kind", "llm")
            purpose = spec.get("purpose", name)
            model = spec.get("model_name", "gemini-1.5-flash")
            prompt = spec.get("prompt_template", "Contexto: {context}\nArtefatos: {artifacts}")
            output_key = spec.get("output_key", name)

            if kind == "llm":
                llm_client = self._create_llm_client(model)
                registry[name] = LLMAgent(name=name, purpose=purpose, llm_client=llm_client, prompt_template=prompt, output_key=output_key)
            elif kind == "deterministic":
                fn_name = spec.get("function")
                if not fn_name:
                    raise DSLValidationError(f"Agente determinístico '{name}' não especificou uma 'function'.")
                registry[name] = DeterministicAgent(name=name, function=self.tool_registry.get(fn_name))
            elif kind == "reflection":
                llm_client = self._create_llm_client(model)
                registry[name] = ReflectionAgent(name=name, purpose=purpose, llm_client=llm_client, prompt_template=prompt)
            elif kind == "tool_using":
                llm_client = self._create_llm_client(model)
                tool_names = spec.get("tools", [])
                tools = self.tool_registry.get_many(tool_names)
                registry[name] = ToolUsingAgent(name=name, purpose=purpose, llm=llm_client, prompt_template=prompt, tools=tools, output_key=output_key)
            elif kind == "supervisor":
                llm_client = self._create_llm_client(model)
                available_agents = spec.get("available_agents", [])
                registry[name] = SupervisorAgent(name=name, purpose=purpose, llm_client=llm_client, prompt_template=prompt, available_agents=available_agents)
            elif kind == "utcp_agent":
                llm_client = self._create_llm_client(model)
                tool_names = spec.get("tools", [])
                utcp_manuals = []
                for t_name in tool_names:
                    manual = self.utcp_tools.get(t_name)
                    if not manual:
                        raise DSLValidationError(f"Manual UTCP '{t_name}' não encontrado na seção 'tools'.")
                    manual['name'] = t_name
                    utcp_manuals.append(manual)

                registry[name] = UTCPAgent(
                    name=name,
                    purpose=purpose,
                    llm_client=llm_client,
                    prompt_template=prompt,
                    utcp_manuals=utcp_manuals,
                    output_key=output_key
                )
            else:
                raise DSLValidationError(f"Tipo de agente não suportado: {kind}")
        return registry

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
        for e in cfg.get("edges", []):
            by_source.setdefault(e["from"], []).append(e)

        if not HAS_LANGGRAPH:
            # This part is a fallback and not essential for the BDD test, but good to keep
            class _SeqRunner:
                def invoke(self, state: GlobalState) -> GlobalState:
                    # Dummy implementation for environments without langgraph
                    print("AVISO: LangGraph não encontrado, usando runner sequencial dummy.")
                    return state
            return _SeqRunner()

        # -------- LangGraph --------
        graph = StateGraph(GlobalState)

        # Nós
        for name, agent in registry.items():
            graph.add_node(name, self._wrap_node(agent))

        # Arestas: para cada 'from', criamos uma função de branching
        for src, edges in by_source.items():
            cond_evals: List[Tuple[str, SafeConditionEvaluator, str]] = []
            fallback_to: Optional[str] = None

            for i, e in enumerate(edges):
                if "condition" in e:
                    label = f"C{i}"
                    cond_evals.append((label, SafeConditionEvaluator(e["condition"]), e["to"]))
                elif fallback_to is None:
                    fallback_to = e["to"]

            def _branch_fn_factory(
                conditions: List[Tuple[str, SafeConditionEvaluator, str]],
                fallback: Optional[str],
            ):
                def _branch(state: GlobalState) -> str:
                    if done_eval.evaluate(state):
                        return "__end__"
                    for label, evaluator, _to in conditions:
                        if evaluator.evaluate(state):
                            return label
                    return fallback if fallback else "__end__"
                return _branch

            mapping = {"__end__": END}
            for label, _ev, to in cond_evals:
                mapping[label] = to
            if fallback_to:
                mapping[fallback_to] = fallback_to

            # Only add conditional edges if there are conditions
            if cond_evals:
                graph.add_conditional_edges(
                    src,
                    _branch_fn_factory(cond_evals, fallback_to),
                    mapping,
                )
            elif fallback_to: # Handle non-conditional edges
                graph.add_edge(src, fallback_to)

        graph.set_entry_point(start_node)

        # Ensure all nodes have an exit point
        all_nodes = set(registry.keys())
        source_nodes = {e["from"] for e in cfg.get("edges", [])}
        terminal_nodes = all_nodes - source_nodes
        for node in terminal_nodes:
            if node != start_node:
                 graph.add_edge(node, END)

        return graph.compile()

    def run(self, initial_context: dict) -> GlobalState:
        init_state = GlobalState(
            context=initial_context or {},
            artifacts={},
            quality={},
            messages=[],
        )
        result = self._compiled_graph.invoke(init_state)

        if isinstance(result, dict):
            return GlobalState(**result)
        return result
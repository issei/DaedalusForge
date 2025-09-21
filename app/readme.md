# Multi-Agent Orchestrator (Python + YAML DSL)

Plataforma genérica e reconfigurável para **orquestração de múltiplos agentes de IA**.
Processos são definidos por **DSL em YAML**; o core é **agnóstico de domínio**. Serve para marketing (ex.: geração de copy), documentação de software (UX/QA/Arquitetura/Segurança), finanças (conciliação), etc.

---

## ✨ Principais recursos

* **Arquitetura em camadas**: Core → SDK de Agentes → DSL/Processos → Infra/Observabilidade.
* **Orquestração por DSL**: descreva nós (agentes), arestas e condições no YAML.
* **Agentes plugáveis**:

  * `LLMAgent` (simulado; trocável por LLM real),
  * `DeterministicAgent` (regras/cálculos),
  * `JudgeAgent` (avalia qualidade e produz métricas).
* **Estado imutável + merge profundo**: previsível, fácil de testar e reexecutar.
* **Condições seguras**: avaliação via AST (sem `eval/exec`) com `and/or/not`, comparações e `is (not) None`.
* **LangGraph opcional**: usa `langgraph.graph.StateGraph` se instalado; caso contrário, tem **fallback sequencial** que preserva a semântica.

---

## 🗂️ Estrutura do projeto

```
.
├─ agents.py            # BaseAgent, LLMAgent, DeterministicAgent, JudgeAgent
├─ model.py             # GlobalState, AgentOutput, deep_merge, apply_agent_output
├─ orchestrator.py      # Carrega/valida DSL, constrói grafo e executa
├─ safe_eval.py         # SafeConditionEvaluator (AST, sem eval/exec)
├─ process_config.yaml  # Processo de exemplo (Geração de Copy)
├─ main.py              # Script de execução do processo
├─ requirements.txt     # Runtime (pydantic, PyYAML, langgraph opcional)
├─ requirements-dev.txt # Dev tools (pytest, ruff, black, mypy, etc.)
├─ pyproject.toml       # Configs de lint/format/typecheck/pytest
├─ .gitignore
├─ .dockerignore
├─ .editorconfig
├─ .env.example
├─ Makefile
└─ LICENSE
```

---

## 🚀 Comece rápido

### 1) Setup (com `make`)

```bash
make install-dev     # venv + deps (runtime + dev) + pre-commit
make test            # roda testes (se houver)
make run             # executa o processo de exemplo (process_config.yaml)
```

### 2) Setup manual

```bash
python -m venv .venv
. .venv/bin/activate
pip install -U pip -r requirements-dev.txt
python main.py --process process_config.yaml
```

> **Nota:** `langgraph` é opcional. Se não estiver instalado, o orquestrador executa o **runner sequencial** interno.

---

## 🧱 Conceitos principais

### GlobalState (imutável)

* `context: dict` — entradas/briefing/dados normalizados
* `artifacts: dict` — saídas nomeadas (ex.: `copy_principal`)
* `quality: dict` — métricas e sinais (ex.: `review_status`, `attempts`)
* `messages: list` — eventos/auditoria

Cada agente retorna um `AgentOutput` (**deltas**) e o core aplica um **merge profundo** para produzir um **novo** `GlobalState`.

### Agentes

* **BaseAgent** → contrato: `execute(state) -> AgentOutput`
* **LLMAgent** → recebe `purpose`, `model_name`, `prompt_template` e escreve em `artifacts` (simulado por padrão).
* **DeterministicAgent** → encapsula uma função Python determinística.
* **JudgeAgent** → avalia artefatos e preenche `quality` (status APROVADO/REFINAR, tentativas, etc.).

### DSL (YAML)

* **process**: `name`, `start`, `done_condition`
* **agents**: definição de cada nó (`kind`, propósito, params)
* **edges**: transições com `from`/`to` e `condition` (opcional)

---

## 🧪 Exemplo de DSL — `process_config.yaml`

```yaml
process:
  name: "geracao-copy-marketing-v1"
  start: "analise_dores_promessas"
  done_condition: "quality.review_status == 'APROVADO'"

agents:
  analise_dores_promessas:
    kind: "llm"
    purpose: "Analisar briefing e extrair dores/promessas."
    model_name: "gpt-simulado"
    prompt_template: |
      Você é um estrategista de marketing. Extraia dores, objeções e promessas
      a partir do briefing abaixo e sintetize insights acionáveis.
      Briefing: {context[briefing]}
    output_key: "dores_promessas"

  consolidador_contexto:
    kind: "deterministic"
    purpose: "Consolidar briefing + dores/promessas em contexto canônico."
    function: "consolidar_contexto"

  geracao_copy:
    kind: "llm"
    purpose: "Criar uma copy principal com base no contexto."
    model_name: "gpt-simulado"
    prompt_template: |
      Gere uma copy principal (headline + subtítulo + CTA) para o infoproduto.
      Contexto consolidado: {context[contexto_consolidado]}
      Dores/promessas: {artifacts[dores_promessas]}
    output_key: "copy_principal"

  adaptacao_canais:
    kind: "llm"
    purpose: "Adaptar a copy para canais (Instagram e Email)."
    model_name: "gpt-simulado"
    prompt_template: |
      Adapte a copy principal para Instagram e Email (assunto + corpo).
      Copy principal: {artifacts[copy_principal]}
    output_key: "copy_canais"

  critico_revisor:
    kind: "judge"
    purpose: "Revisar a copy e decidir APROVADO/REFINAR."

edges:
  - from: "analise_dores_promessas"
    to: "consolidador_contexto"

  - from: "consolidador_contexto"
    to: "geracao_copy"

  - from: "geracao_copy"
    to: "critico_revisor"

  - from: "critico_revisor"
    to: "adaptacao_canais"
    condition: "quality.review_status == 'REFINAR' and (quality.attempts is None or quality.attempts < 3)"

  - from: "adaptacao_canais"
    to: "critico_revisor"

  - from: "critico_revisor"
    to: "__end__"
    condition: "quality.review_status == 'APROVADO'"
```

---

## ▶️ Executando o exemplo

`main.py` cria o `Orchestrator`, injeta um `initial_context` (briefing) e roda:

```python
from orchestrator import Orchestrator

initial_context = {
    "briefing": {
        "infoproduto": {"nome": "Produto Exemplo", "avatar": "Profissionais de Marketing"},
        "proposta_valor": "Framework prático de copywriting",
        "restricoes": ["linguagem simples", "evitar jargões técnicos"],
    }
}

orch = Orchestrator(config_path="process_config.yaml")
final_state = orch.run(initial_context=initial_context)

print(final_state.artifacts)  # exibe 'dores_promessas', 'copy_principal', 'copy_canais', ...
print(final_state.quality)    # exibe 'review_status', 'attempts', ...
```

---

## 🔒 Condições seguras (SafeConditionEvaluator)

* **Permitido**: `and`, `or`, `not`, `==`, `!=`, `<`, `<=`, `>`, `>=`, `is None`, `is not None`
* **Acesso**: `quality.*`, `artifacts.*`, `context.*`
* **Exemplos**:

  * `quality.review_status == 'APROVADO'`
  * `quality.review_status == 'REFINAR' and (quality.attempts is None or quality.attempts < 3)`
  * `artifacts.spec_arquitetura is not None and quality.coverage >= 0.8`

> Não há execução arbitrária (sem `eval/exec`), somente leitura segura do estado.

---

## 🧩 Estendendo o orquestrador

### Criar um novo agente determinístico

1. Implemente uma função `fn(state: GlobalState) -> AgentOutput`.
2. Registre a função no `orchestrator._instantiate_agents()`.
3. No YAML, declare o agente:

   ```yaml
   meu_agente:
     kind: "deterministic"
     function: "nome_da_funcao_registrada"
   ```

### Usar LLM real

* Troque a simulação dentro do `LLMAgent` por um cliente real (OpenAI, Azure, etc.) e leia a chave via `.env`.
* Garanta **rate limiting**, **timeouts** e **custos** nos próprios agentes.

---

## 🛠️ Qualidade, CI e DevX

* **Format/Lint/Type**: `make format`, `make lint`, `make typecheck`
* **Testes**: `make test` (use `pytest` para unit/integration/snapshot)
* **pre-commit**: `pre-commit install` (Black, Ruff, YAML checks)

---

## 🐳 Docker (opcional)

Build & run:

```bash
docker build -t multiagent-orchestrator .
docker run --rm -it -e PYTHONUNBUFFERED=1 multiagent-orchestrator
```

---

## 🔐 Segurança & Governança

* **Sem `eval/exec`** em condições.
* **Segredos** via `.env` / secret manager (nunca commitar chaves).
* **Mascaramento de PII** antes de enviar ao LLM (quando integrar provedores reais).
* **Observabilidade**: registre eventos em `messages` e, se necessário, integre OpenTelemetry/LangSmith.

---

## ❓ Solução de problemas

* **Loop infinito**: verifique condições e presence de arestas sem condição (fallback). O runner sequencial tem guarda anti-loop.
* **Chaves ausentes no prompt**: o `LLMAgent` tem fallback de renderização para evitar `KeyError`.
* **A condição não dispara**: valide o caminho (`quality.x`, `artifacts.y`), tipos e literais (aspas simples em strings).

---

## 🗺️ Roadmap

* Agente **“Juiz”** com métricas configuráveis (coverage, tom, CTA).
* Suporte a **fan-out/fan-in** em processos com paralelismo.
* Exportadores (Markdown→PDF/Slides) e armazenamento versionado de artefatos.
* Painel de **runs** (inspeção de nós, edges e estado).

---

## 📄 Licença

MIT — veja `LICENSE`.

---

**Pronto.** Com este README você tem visão, comandos e exemplos para rodar, adaptar e evoluir a plataforma. Se quiser, posso incluir um workflow de CI (`.github/workflows/ci.yml`) com cache de deps, lint, typecheck e testes.

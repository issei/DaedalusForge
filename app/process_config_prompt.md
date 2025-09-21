# Prompt mestre para gerar `process_config.yaml`

**Guia prático para elaborar novos processos no Orquestrador de Múltiplos Agentes (Python + YAML DSL)**

Este documento fornece um **prompt especializado** (copiar/colar) para você usar com um LLM a fim de **gerar arquivos `process_config.yaml` válidos** para a plataforma.
Inclui: instruções, formato esperado, restrições do avaliador de condições, checklist e **exemplos**.

---

## Como usar

1. Copie o **Prompt Mestre** abaixo para sua ferramenta de IA.
2. Preencha os campos entre `<...>` com os dados do novo processo (nome, agentes, funções determinísticas, critérios de done).
3. O modelo retornará **apenas YAML** dentro de um fence \`\`\`yaml — pronto para salvar como `process_config.yaml`.
4. Rode o orquestrador com `python main.py --process process_config.yaml`.

---

## ✅ Regras importantes do DSL (compatíveis com o orquestrador)

* Top-level: `process`, `agents`, `edges` (todos obrigatórios).
* `process`:

  * `name` (string), `start` (nome de um agente existente),
  * `done_condition` (string) — expressão **segura** (ver abaixo).
* `agents` (mapa):

  * `kind`: `"llm" | "deterministic" | "judge"`.
  * `purpose`: descrição curta (opcional).
  * Para `llm`: `model_name`, `prompt_template` (use bloco `|`), `output_key`.
  * Para `deterministic`: `function` (nome deve existir no registry do orquestrador).
  * Para `judge`: sem campos extras obrigatórios (usa regra default, salvo se você trocar no código).
* `edges` (lista): itens com `from`, `to`, e **opcional** `condition`.
* **Fim do fluxo**: use `to: "__end__"` ou cumpra `process.done_condition`.
* **Interpolação em prompts**: use chaves do estado:
  `{context[...]}`, `{artifacts[...]}`, `{quality[...]}` (ex.: `{context[briefing]}`).
* **Avaliador de Condições Seguro** (sem `eval/exec`):
  Suporta somente `and`, `or`, `not`, comparações `== != < <= > >=`, e `is None` / `is not None`.
  Acesso apenas a `quality.*`, `artifacts.*`, `context.*`.

---

## 🧠 Prompt Mestre (copie e cole)

> Cole o texto abaixo na IA e preencha os campos `<...>`:

````markdown
Você é um gerador estrito de YAML para a plataforma de orquestração de múltiplos agentes.
Seu trabalho é produzir **apenas** um arquivo `process_config.yaml` **válido** para o DSL a seguir.

### Esquema do DSL (obrigatório)
- process:
  - name: string
  - start: string (nome de um agente definido em `agents`)
  - done_condition: string (expressão segura; ver seção "Condições")
- agents: mapa { nome_do_agente: { ... } }
  - campos obrigatórios:
    - kind: "llm" | "deterministic" | "judge"
  - se kind == "llm":
    - model_name: string
    - prompt_template: string multilinha (usar bloco `|`)
    - output_key: string (chave em `artifacts`)
    - purpose: string (opcional)
  - se kind == "deterministic":
    - function: string (deve existir no registry do orquestrador)
    - purpose: string (opcional)
  - se kind == "judge":
    - purpose: string (opcional)
- edges: lista de arestas
  - item: { from: string, to: string, condition?: string }

### Condições (SafeConditionEvaluator)
- Apenas: `and`, `or`, `not`; comparações `== != < <= > >=`; `is None` / `is not None`.
- Acesso somente a: `quality.*`, `artifacts.*`, `context.*`.
- Exemplos válidos:
  - "quality.review_status == 'APROVADO'"
  - "quality.review_status == 'REFINAR' and (quality.attempts is None or quality.attempts < 3)"
  - "artifacts.spec_arquitetura is not None and quality.coverage >= 0.8"

### Interpolação nos prompts (LLM)
- Use `{context[...]}`, `{artifacts[...]}`, `{quality[...]}` (ex.: `{context[briefing]}`).
- Use bloco YAML `|` para prompts multilinha.

### Restrições de Saída
- Responda **somente** com um bloco ```yaml contendo o YAML final.
- Não inclua comentários fora do YAML, explicações ou texto adicional.
- Evite campos fora do esquema acima.

### Entradas do usuário (preencha):
- process.name: <nome_do_processo>
- process.start: <nome_do_agente_inicial>
- process.done_condition: <expressão_segura_de_conclusão>
- function_registry_disponivel: [<lista_de_funcoes_deterministicas_disponiveis_no_orquestrador>]
- agentes (defina cada um):
  - <agente_1>:
      kind: <llm|deterministic|judge>
      se llm:
        model_name: <modelo>
        output_key: <chave_artifact>
        prompt_template: <prompt_multilinha>
      se deterministic:
        function: <nome_na_function_registry_disponivel>
      (purpose é opcional)
  - <agente_2>: ...
- edges (ordem importa; condicionais primeiro, depois fallback):
  - from: <nome>
    to: <nome|__end__>
    condition?: <expr>

### Validações que você deve cumprir antes de responder
1) `process.start` existe em `agents`.
2) Todos os `edges.from` e `edges.to` referenciam agentes existentes (ou `"__end__"`).
3) Toda `condition` está dentro da gramática suportada e usa apenas `quality|artifacts|context`.
4) Se `done_condition` referir `quality.review_status`, inclua um agente `judge`.
5) Para `deterministic`, use apenas nomes listados em `function_registry_disponivel`.

### Formato de resposta
Apenas:
```yaml
# process_config.yaml
process:
  ...
agents:
  ...
edges:
  ...
```

Agora gere o YAML com base nestas informações específicas:
- process.name: <preencher>
- process.start: <preencher>
- process.done_condition: <preencher>
- function_registry_disponivel: <preencher: ["consolidar_contexto", ...]>
- agentes e edges desejados: <descrever brevemente aqui>
````

---

## 🧩 Exemplo pronto #1 — Geração de Copy (marketing)

> Pode ser usado como few-shot para orientar a IA (compatível com o orquestrador).

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
      Gere uma copy principal (headline + subtítulo + CTA).
      Contexto consolidado: {context[contexto_consolidado]}
      Dores/promessas: {artifacts[dores_promessas]}
    output_key: "copy_principal"

  adaptacao_canais:
    kind: "llm"
    purpose: "Adaptar a copy para canais (Instagram e Email)."
    model_name: "gpt-simulado"
    prompt_template: |
      Adapte a copy principal para Instagram e Email.
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

## 🧩 Exemplo pronto #2 — Documentação de Software

```yaml
process:
  name: "doc-software-v1"
  start: "ux"
  done_condition: "artifacts.spec_arquitetura is not None and artifacts.plano_testes is not None and artifacts.guia_ux is not None"

agents:
  ux:
    kind: "llm"
    purpose: "Gerar guia de UX e critérios de usabilidade."
    model_name: "gpt-simulado"
    prompt_template: |
      Você é UX Lead. Gere um guia de UX com heurísticas e critérios.
      Briefing: {context[briefing]}
    output_key: "guia_ux"

  arquitetura:
    kind: "llm"
    purpose: "Especificação de arquitetura e trade-offs."
    model_name: "gpt-simulado"
    prompt_template: |
      Você é Arquiteto de Software. Produza spec de arquitetura, componentes e trade-offs.
      Guia UX: {artifacts[guia_ux]}
      Requisitos: {context[requisitos]}
    output_key: "spec_arquitetura"

  seguranca:
    kind: "llm"
    purpose: "Riscos de segurança e controles."
    model_name: "gpt-simulado"
    prompt_template: |
      Você é Engenheiro de Segurança. Liste riscos, controles e checagens.
      Spec de Arquitetura: {artifacts[spec_arquitetura]}
    output_key: "checklist_seg"

  testes:
    kind: "llm"
    purpose: "Plano de testes (unit, integração, e2e)."
    model_name: "gpt-simulado"
    prompt_template: |
      Você é QA Lead. Gere plano de testes baseado na spec e riscos.
      Spec: {artifacts[spec_arquitetura]}
      Riscos: {artifacts[checklist_seg]}
    output_key: "plano_testes"

edges:
  - from: "ux"
    to: "arquitetura"
  - from: "arquitetura"
    to: "seguranca"
  - from: "seguranca"
    to: "testes"
```

---

## 🔍 Checklist de validação antes de usar em produção

* [ ] `process.start` é um agente existente.
* [ ] Todas as arestas `from/to` apontam para agentes existentes (ou `"__end__"`).
* [ ] `done_condition` é uma expressão **segura** e válida (apenas `quality|artifacts|context`).
* [ ] Se `done_condition` usa `quality.review_status`, existe um agente `judge`.
* [ ] Cada agente `llm` possui `model_name`, `prompt_template` (bloco `|`) e `output_key`.
* [ ] Cada `deterministic` usa `function` presente no **registry** do orquestrador.
* [ ] As referências nos prompts (`{context[...]}`, `{artifacts[...]}`) existem ou são toleradas pelo agente.
* [ ] Ordem das `edges`: condicionais primeiro (mais específicas), depois fallback sem condição.

---

## Dicas finais

* Use nomes **curtos e descritivos** para agentes e `output_key`.
* Prefira **um objetivo por agente**; divida tarefas maiores.
* Coloque **gates objetivos** em `done_condition` (ex.: artifacts presentes + métricas mínimas).
* Comece simples; adicione loops condicionais (refino) quando necessário.

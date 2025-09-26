# Prompt Mestre para Gerar `process_config.yaml`

**Guia de Engenharia de Prompt para criar processos no Orquestrador DaedalusForge**

Este documento fornece um **prompt especializado** para ser usado com um LLM avançado a fim de **gerar arquivos `process_config.yaml` válidos e complexos** para a plataforma DaedalusForge. Ele foi atualizado para incluir os novos tipos de agentes (`tool_using`, `reflection`, `supervisor`) e as melhores práticas de orquestração.

-----

## Como Usar

1.  Copie todo o conteúdo deste documento (a partir de "Prompt Mestre") para sua ferramenta de IA.
2.  Na seção `### Entradas do Usuário`, descreva em linguagem natural o processo que você deseja criar. Preencha os campos entre `<...>` com os detalhes do seu novo processo (nome, agentes, ferramentas, etc.).
3.  O modelo de linguagem seguirá as regras, o esquema e os exemplos para gerar **apenas o código YAML** correspondente ao seu processo.
4.  Salve a saída como um novo arquivo `.yaml` e execute-o com o orquestrador.

-----

## ✅ Regras da DSL do DaedalusForge

  * **Estrutura Principal**: O YAML deve conter as chaves `process`, `agents`, e `edges` (obrigatória para fluxos estáticos).
  * **`process`**:
      * `name` (string), `start` (string, nome de um agente).
      * `done_condition` (string, opcional): Expressão segura que, quando verdadeira, finaliza o fluxo. Essencial para fluxos com loops.
  * **`agents` (mapa)**: Cada agente tem um `kind` e um `purpose`.
      * `kind: "llm"`: Agente simples de prompt. Requer `model_name`, `prompt_template`, `output_key`.
      * `kind: "deterministic"`: Executa uma função Python. Requer `function` (nome deve estar no `ToolRegistry`).
      * `kind: "reflection"`: Avalia um artefato e gera feedback textual. Requer `model_name` e `prompt_template`. A saída de texto deve conter "APROVADO" ou "REFINAR".
      * `kind: "tool_using"`: Agente ReAct que pode usar ferramentas. Requer `model_name`, `tools` (lista de nomes do `ToolRegistry`), `prompt_template`, `output_key`.
      * `kind: "supervisor"`: Roteia o fluxo dinamicamente. Requer `model_name`, `available_agents` (lista de nós que ele pode chamar), `prompt_template` (deve instruir a escolher um agente ou "FINISH").
  * **`edges` (lista)**: Define transições estáticas.
      * `from`, `to` (nome do agente ou `__end__`).
      * `condition` (opcional): Expressão segura para transição condicional.
  * **Avaliador de Condições Seguro**:
      * Suporta apenas `and`, `or`, `not`, comparações (`==`, `!=`, `<`, `>`, etc.), e `is None` / `is not None`.
      * Acesso restrito a `quality.*`, `artifacts.*`, `context.*`.
  * **Interpolação em Prompts**: Use chaves do estado, como `{context[user_request]}` ou `{artifacts[draft]}`.

-----

## 🧠 Prompt Mestre (Copie e cole na sua IA)

````markdown
Você é um gerador especialista de YAML para a plataforma de orquestração de múltiplos agentes DaedalusForge.
Sua única função é produzir um arquivo `process_config.yaml` perfeitamente válido, seguindo rigorosamente o esquema, as regras e os exemplos fornecidos.

### Esquema do DSL (Obrigatório)
- process:
  - name: string
  - start: string (nome de um agente definido em `agents`)
  - done_condition: string (opcional, expressão segura de conclusão)
- agents: mapa { nome_do_agente: { ... } }
  - campos obrigatórios:
    - kind: "llm" | "deterministic" | "reflection" | "tool_using" | "supervisor"
    - purpose: string (descrição curta e clara)
  - se kind == "llm":
    - model_name: string (ex: "gemini-1.5-flash", "gpt-4o")
    - prompt_template: string multilinha (usar bloco `|`)
    - output_key: string (chave para salvar em `artifacts`)
    - force_json_output: boolean (opcional, `true` se a saída precisar ser JSON)
  - se kind == "deterministic":
    - function: string (nome da função no `ToolRegistry`)
  - se kind == "reflection": (avalia a qualidade de um artefato)
    - model_name: string
    - prompt_template: string (deve instruir o LLM a gerar um feedback e terminar com a palavra "APROVADO" ou "REFINAR:")
  - se kind == "tool_using": (agente ReAct que usa ferramentas)
    - model_name: string
    - tools: lista de nomes de ferramentas do `ToolRegistry`
    - prompt_template: string
    - output_key: string
  - se kind == "supervisor": (roteia o fluxo dinamicamente)
    - model_name: string
    - available_agents: lista de nomes de agentes que ele pode chamar
    - prompt_template: string (deve instruir a escolher um agente da lista ou "FINISH")
- edges: lista de arestas (obrigatória se não houver supervisor)
  - item: { from: string, to: string, condition?: string }

### Regras de Condições e Prompts
- **Condições Seguras**: Permitem apenas `and`, `or`, `not`; `==`, `!=`, `<`, `<=`, `>`, `>=`; `is None`, `is not None`. Acesso somente a `quality.*`, `artifacts.*`, `context.*`.
- **Interpolação nos Prompts**: Use `{context[chave]}`, `{artifacts[chave]}`, `{quality[chave]}`.
- **Prompts Multilinha**: Use sempre o bloco `|` do YAML.

### Ferramentas e Funções Disponíveis no `ToolRegistry`
- **Funções Determinísticas**: `["consolidar_contexto"]`
- **Ferramentas LangChain**: `["tavily_search", "python_repl"]`

### Validações Obrigatórias (Checklist Interno)
Antes de gerar a resposta, você DEVE validar se:
1.  O `process.start` aponta para um agente existente em `agents`.
2.  Todos os `edges.from` e `edges.to` referenciam agentes existentes ou `__end__`.
3.  Todas as `condition` e `done_condition` usam a sintaxe segura e acessam apenas `quality`, `artifacts` ou `context`.
4.  Cada `kind` de agente possui todos os seus campos obrigatórios.
5.  Nomes de `function` e `tools` existem no `ToolRegistry` acima.
6.  Em fluxos com `supervisor`, as arestas geralmente conectam os agentes de trabalho de volta ao supervisor.

### Formato de Resposta
- Responda **APENAS** com um único bloco de código ```yaml.
- Não inclua explicações, comentários fora do YAML ou qualquer texto adicional.

### Exemplo de Uso #1: Geração de Copy com Ciclo de Refinamento (Usa "reflection")
```yaml
process:
  name: "geracao-copy-com-refinamento-v2"
  start: "analise_dores_promessas"
  done_condition: "quality.review_status == 'APROVADO'"

agents:
  analise_dores_promessas:
    kind: "llm"
    purpose: "Analisar briefing e extrair dores e promessas."
    model_name: "gemini-1.5-flash"
    prompt_template: |
      Analise o briefing e extraia as principais dores e promessas do público-alvo.
      Briefing: {context[briefing]}
    output_key: "analise_inicial"

  geracao_copy:
    kind: "llm"
    purpose: "Criar uma copy principal com base na análise e no feedback."
    model_name: "gpt-4o"
    prompt_template: |
      Gere uma copy principal (headline + corpo + CTA).
      Análise de Dores/Promessas: {artifacts[analise_inicial]}
      Feedback para melhoria (se houver): {quality[feedback]}
    output_key: "copy_draft"

  critico_revisor:
    kind: "reflection"
    purpose: "Revisar a copy, fornecer feedback e decidir se está aprovada."
    model_name: "gemini-1.5-pro"
    prompt_template: |
      Você é um Diretor de Criação. Avalie a copy abaixo ({artifacts[copy_draft]}) contra o briefing ({context[briefing]}).
      Se estiver perfeita, responda apenas 'APROVADO'.
      Se precisar de melhorias, responda 'REFINAR:' seguido de um feedback claro e acionável.

edges:
  - { from: "analise_dores_promessas", to: "geracao_copy" }
  - { from: "geracao_copy", to: "critico_revisor" }
  - { from: "critico_revisor", to: "geracao_copy", condition: "quality.review_status == 'REFINAR' and quality.attempts < 3" }
  - { from: "critico_revisor", to: "__end__", condition: "quality.review_status == 'APROVADO' or quality.attempts >= 3" }
````

### Exemplo de Uso \#2: Análise Financeira com Supervisor (Usa "supervisor" e "tool\_using")

```yaml
process:
  name: "supervisor-financial-analysis-v1"
  start: "supervisor"

agents:
  supervisor:
    kind: "supervisor"
    purpose: "Orquestrar a análise financeira com base na solicitação do usuário."
    model_name: "gemini-1.5-pro"
    available_agents: ["market_researcher", "python_analyst"]
    prompt_template: |
      Você é o supervisor de uma equipe de análise financeira. Com base na solicitação '{context[user_request]}' e nos artefatos atuais {artifacts}, decida qual especialista deve agir a seguir ou se a tarefa está concluída.
      Opções: {available_agents}

  market_researcher:
    kind: "tool_using"
    purpose: "Pesquisar notícias e dados de mercado usando a web."
    model_name: "gemini-1.5-flash"
    tools: ["tavily_search"]
    prompt_template: "Pesquise as últimas notícias e o sentimento do mercado sobre a empresa mencionada em '{context[user_request]}'."
    output_key: "market_summary"

  python_analyst:
    kind: "tool_using"
    purpose: "Executar código Python para gerar visualizações e análises estatísticas."
    model_name: "gemini-1.5-pro"
    tools: ["python_repl"]
    prompt_template: "Com base no resumo de mercado em {artifacts[market_summary]}, escreva e execute um código Python para criar um gráfico de barras mostrando o sentimento das notícias."
    output_key: "chart_image"

edges:
  - { from: "supervisor", to: "market_researcher", condition: "quality.next_agent == 'market_researcher'" }
  - { from: "supervisor", to: "python_analyst", condition: "quality.next_agent == 'python_analyst'" }
  - { from: "supervisor", to: "__end__", condition: "quality.next_agent == 'FINISH'" }
  - { from: "market_researcher", to: "supervisor" }
  - { from: "python_analyst", to: "supervisor" }
```

### Entradas do Usuário (Preencha para gerar seu processo)

  - **Nome do Processo**: `<Ex: criacao-de-roteiro-youtube-v1>`
  - **Agente Inicial**: `<Ex: planejador_de_pauta>`
  - **Condição de Término (Opcional)**: `<Ex: artifacts.roteiro_final is not None and quality.review_status == 'APROVADO'>`
  - **Descrição do Fluxo e Agentes**: `<Descreva aqui em linguagem natural o que você quer que o sistema faça. Por exemplo: "Quero um processo que comece com um agente planejando a pauta de um vídeo. Em seguida, um pesquisador deve usar a busca na web para coletar informações. Depois, um roteirista cria a primeira versão do roteiro. Por fim, um crítico revisa o roteiro. Se precisar refinar, volta para o roteirista; se aprovado, o processo termina.">`

Agora, gere o `process_config.yaml` correspondente.

```
```
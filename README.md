[![Python Version](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Last Commit](https://img.shields.io/github/last-commit/issei/DaedalusForge)](https://github.com/issei/DaedalusForge/commits/main)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# DaedalusForge: Orquestração de Agentes de IA e Automações

Bem-vindo ao DaedalusForge! Este repositório é minha forja pessoal para experimentação, aprendizado e construção no universo da Inteligência Artificial. Inspirado em Dédalo, o lendário artesão da mitologia grega, este espaço é dedicado a criar e testar soluções de IA, desde automações práticas até sistemas complexos de orquestração de agentes.

O projeto principal aqui é uma **plataforma genérica e reconfigurável para orquestração de múltiplos agentes de IA**, onde processos são definidos por uma **DSL (Domain-Specific Language) em YAML**.

---

## ✨ Principais Recursos do Orquestrador

*   **Arquitetura em Camadas**: Core → SDK de Agentes → DSL/Processos → Infra/Observabilidade.
*   **Orquestração via DSL**: Descreva nós (agentes), arestas e condições de transição em um arquivo YAML, tornando o fluxo de trabalho desacoplado do código.
*   **Agentes Plugáveis**: Suporte para diferentes tipos de agentes, como `LLMAgent` (para interagir com modelos de linguagem), `DeterministicAgent` (para executar regras de negócio) e `JudgeAgent` (para avaliar a qualidade das saídas).
*   **Estado Imutável**: Cada passo do processo gera um novo estado global através de um merge profundo, garantindo previsibilidade e facilitando testes.
*   **Condições Seguras**: A lógica de transição é avaliada de forma segura via AST (Abstract Syntax Tree), sem o uso de `eval()` ou `exec()`, prevenindo a execução de código arbitrário.
*   **Fallback Inteligente**: Utiliza `LangGraph` para a execução do grafo se a biblioteca estiver instalada; caso contrário, recorre a um runner sequencial interno, preservando a lógica do processo.

---

## 🚀 Começando

### 1. Ambiente Local (Recomendado)

**Pré-requisitos:**
*   Python 3.10+
*   Git

**Passos:**
1.  Clone o repositório:
    ```bash
    git clone https://github.com/issei/DaedalusForge.git
    cd DaedalusForge
    ```
2.  Crie e ative um ambiente virtual:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # No Windows: .venv\Scripts\activate
    ```
3.  Crie um arquivo `.env` na raiz do projeto para gerenciar suas chaves de API. Você pode copiar o `.env.example` como modelo.
4.  Instale as dependências de desenvolvimento:
    ```bash
    pip install -r requirements-dev.txt
    ```
5.  Execute o processo de exemplo:
    ```bash
    python src/main.py
    ```

### 2. Usando `make`

Se você tiver o `make` instalado, pode usar os seguintes comandos:
```bash
make install-dev     # Cria o venv, instala dependências e configura o pre-commit
make test            # Roda os testes
make run             # Executa o processo de exemplo
```

### 3. Google Colab

Para os notebooks de estudo, você pode usar o Google Colab. Procure pelo badge "Open in Colab" nos arquivos `.ipynb`.

---

## 📂 Estrutura do Projeto

```
.
├── app/                  # Código fonte da aplicação do orquestrador
│   ├── __init__.py
│   ├── agents.py         # Definição das classes de Agentes
│   ├── main.py           # Ponto de entrada para executar o orquestrador
│   ├── model.py          # Modelos de dados (GlobalState, etc.)
│   ├── orchestrator.py   # Core da orquestração (carrega DSL, executa o grafo)
│   └── safe_eval.py      # Avaliador seguro de condições
├── configs/              # Arquivos de configuração para os processos
│   └── process_config.yaml
├── notebooks/            # Notebooks de estudo e automações (provas de conceito)
│   ├── automations/
│   └── study_projects/
├── .env.example          # Exemplo de arquivo para variáveis de ambiente
├── .gitignore
├── Dockerfile
├── Makefile
├── README.md
├── pyproject.toml
├── requirements.txt      # Dependências de runtime
└── requirements-dev.txt  # Dependências de desenvolvimento
```

---

## 🔬 Projetos e Notebooks

### Aplicação Principal

| Projeto | Descrição | Como Executar |
| :--- | :--- | :--- |
| `app/` | **Orquestrador Multi-Agente**: Uma plataforma para executar processos complexos definidos em YAML. O exemplo em `configs/process_config.yaml` demonstra um fluxo de geração de copy para marketing. | `python -m app.main` |

### Automações e PoCs (em `notebooks/`)

| File | Description |
| :--- | :--- |
| `automations/lançamento.ipynb` | Sistema multi-agente com **LangGraph** que gera textos de marketing (copy) para um lançamento de forma colaborativa. |
| `automations/Notebook_de_Prospecção.ipynb` | Pipeline automatizado de prospecção de leads usando um sistema multi-agente e a API do Apollo.io. |
| `study_projects/...` | Notebooks da Imersão Agentes de IA (Alura + Google) e outros estudos. |

---

## 🧱 Conceitos Principais do Orquestrador

### GlobalState (Imutável)
O estado do processo é um objeto imutável que contém:
*   `context`: Dados de entrada e briefing.
*   `artifacts`: Saídas geradas pelos agentes (ex: `copy_principal`).
*   `quality`: Métricas e status de revisão (ex: `review_status`).
*   `messages`: Log de eventos para auditoria.

### Agentes
*   **`LLMAgent`**: Interage com um LLM para gerar conteúdo.
*   **`DeterministicAgent`**: Executa uma função Python pura para tarefas previsíveis.
*   **`JudgeAgent`**: Avalia artefatos e atualiza o status de qualidade.

### DSL (YAML)
O fluxo é definido em um arquivo YAML com três seções principais:
*   `process`: Define o nome, o ponto de partida e a condição de término.
*   `agents`: Configura cada nó do grafo (tipo, propósito, parâmetros).
*   `edges`: Define as transições entre os agentes, com condições opcionais.

---

## 🐳 Docker

Para construir e executar a aplicação em um contêiner Docker:
```bash
docker build -t multiagent-orchestrator .
docker run --rm -it --env-file .env multiagent-orchestrator
```

---

## 🛠️ Qualidade de Código e CI

*   **Formatação e Linting**: `make format` e `make lint` (usando Black e Ruff).
*   **Checagem de Tipos**: `make typecheck` (usando MyPy).
*   **Testes**: `make test` (usando Pytest).
*   **Pre-commit**: `pre-commit install` para garantir a qualidade do código antes de cada commit.

---

## 📜 Licença

Este projeto é distribuído sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.





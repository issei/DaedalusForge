[![Python Version](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/issei/DaedalusForge)
[![Last Commit](https://img.shields.io/github/last-commit/issei/DaedalusForge)](https://github.com/issei/DaedalusForge/commits/main)

# DaedalusForge: Experimentos e Automações com IA

Bem-vindo ao DaedalusForge! Este repositório é minha forja pessoal para experimentação, aprendizado e construção no universo da Inteligência Artificial.

## 🏛️ Sobre o Repositório

Inspirado em Dédalo, o lendário artesão da mitologia grega, este espaço é dedicado a criar e testar soluções de IA, desde automações práticas até projetos de estudo. Aqui, documento minha jornada explorando novas técnicas, frameworks e modelos.

## 🚀 Getting Started

A maioria dos projetos são notebooks auto-contidos. Para executá-los, você tem duas opções:

### 1. Ambiente Local

**Pré-requisitos:**
- Python 3.10+
- Git

**Passos:**
1. Clone o repositório:
   ```bash
   git clone https://github.com/issei/DaedalusForge.git
   cd DaedalusForge
   ```
2. Crie um arquivo `.env` na raiz do projeto para gerenciar suas chaves de API. Use o `.env.example` como modelo:
   ```
   # Chaves para APIs do Google e outras ferramentas
   GOOGLE_API_KEY="sua_chave_aqui"
   APOLLO_API_KEY="sua_chave_aqui"
   DUMPLING_API_KEY="sua_chave_aqui"
   DUMPLING_KB_ID="seu_id_aqui"
   ```
3. Instale as dependências, que geralmente estão listadas no topo de cada notebook.

### 2. Google Colab

Clique no badge "Open in Colab" no topo deste README para abrir o repositório diretamente no Google Colab.

Para gerenciar suas chaves de API no Colab, use o gerenciador de "Secrets" (ícone de chave no menu à esquerda) e adicione as chaves necessárias para cada notebook.

## 📂 Projetos

### /automations
Scripts e notebooks focados em automações práticas e de valor real.

| File | Description | Inputs | Outputs | Dependencies |
| :--- | :--- | :--- | :--- | :--- |
| `lançamento.ipynb` | Um sistema multi-agente com **LangGraph** que gera textos de marketing (copy) para um lançamento. O grafo implementa um ciclo colaborativo de geração, revisão e refinamento para garantir a qualidade e o alinhamento estratégico. | - Chaves de API <br> - Briefing do lançamento (JSON) | Arquivos `JSON` e `Markdown` com a copy final aprovada. | `langchain`, `langgraph`, `google-generativeai`, `httpx`, `pydantic`, `python-dotenv` |
| `Notebook_de_Prospecção.ipynb` | Pipeline automatizado de prospecção de leads usando um sistema multi-agente. Gera buscas para a API do Apollo.io, coleta os dados, remove duplicatas e exporta o resultado. | - Chaves de API | Arquivo `leads_apollo.csv` com a lista de leads. | `langchain`, `google-generativeai`, `httpx`, `pandas` |

<br>

### /study_projects
Notebooks e scripts de cursos, tutoriais e estudos pessoais.

| File | Description | Inputs | Outputs | Dependencies |
| :--- | :--- | :--- | :--- | :--- |
| `Imersão_Agentes_de_IA_Alura_+_Google_Gemini_ipynb_Aula_01.ipynb` | Notebook da Imersão Agentes de IA (Alura + Google). Demonstra um agente simples que atua como um triador de Service Desk, classificando chamados com base em políticas internas. | - Chave de API <br> - Mensagem de texto do usuário | Objeto `JSON` classificando o chamado. | `langchain`, `google-generativeai` |

---

## 📜 Licença

Este projeto é distribuído sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.




# DaedalusForge: AI Experiments and Automation

Welcome to DaedalusForge! This repository is a curated collection of Python scripts, Jupyter notebooks, and projects focused on Artificial Intelligence, automation, and continuous learning. It serves as a personal space to experiment with new AI techniques, build useful automations, and document my journey in the world of AI and software development.

The name "DaedalusForge" is inspired by Daedalus, the skillful craftsman and artist in Greek mythology, who was known for his ingenuity and ability to create amazing inventions. This repository is my personal "forge" where I create and experiment with AI.

## 📂 Folder Structure

The repository is organized into the following folders to keep the projects structured and easy to navigate:

-   **`/automations`**: Contains scripts designed for practical, real-world automation tasks.
-   **`/study_projects`**: Includes notebooks and scripts from courses, tutorials, and personal studies. These are primarily for learning and experimentation.

---

## 🔬 Scripts and Notebooks

Here is a list of all the projects currently in the repository:

### /automations

| File | Description | Inputs | Outputs | Dependencies |
| :--- | :--- | :--- | :--- | :--- |
| `Notebook_de_Prospecção.ipynb` | An automated lead prospecting pipeline using a multi-agent system. It leverages Google Gemini to generate search queries for the Apollo.io API, fetches lead data, removes duplicates, and exports the results. | - `GOOGLE_API_KEY` <br> - `APOLLO_API_KEY` | A `leads_apollo.csv` file with the list of prospected leads. | `langchain`, `google-generativeai`, `httpx`, `pandas` |

<br>

### /study_projects

| File | Description | Inputs | Outputs | Dependencies |
| :--- | :--- | :--- | :--- | :--- |
| `Imersão_Agentes_de_IA_Alura_+_Google_Gemini_ipynb_Aula_01.ipynb` | A notebook from the Alura + Google Gemini "AI Agents" course. It demonstrates how to build a simple AI agent that acts as a Service Desk triager, classifying user requests based on internal policies. | - `GEMINI_API_KEY` <br> - A user's text message | A JSON object classifying the request's `decision`, `urgency`, and `missing_fields`. | `langchain`, `google-generativeai` |

---

###  badges

I suggest adding the following badges to the top of this README to give it a more professional look:

```markdown
![Python Version](https://img.shields.io/badge/Python-3.12-blue.svg)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/issei/DaedalusForge)
![Last Commit](https://img.shields.io/github/last-commit/issei/DaedalusForge)
```



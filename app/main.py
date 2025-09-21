from __future__ import annotations

import sys
import os
import argparse

# Adiciona o diretório pai (raiz do projeto) ao sys.path
# para que os módulos possam ser encontrados.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.orchestrator import Orchestrator

# Briefing inicial simulado
initial_context = {
    "briefing": {
        "infoproduto": {
            "nome": "Produto Exemplo",
            "avatar": "Profissionais de Marketing",
            "promessa": "Aumentar conversões com mensagens persuasivas",
        },
        "proposta_valor": "Framework prático de copywriting com exemplos",
        "restricoes": ["linguagem simples", "evitar jargões técnicos"],
    }
}

if __name__ == "__main__":
    orch = Orchestrator(config_path="process_config.yaml")
    final_state = orch.run(initial_context=initial_context)

    print("\n--- ARTEFATOS FINAIS ---")
    for k, v in final_state.artifacts.items():
        print(f"* {k}: {str(v)[:200]}...")

    print("\n--- MÉTRICAS DE QUALIDADE ---")
    for k, v in final_state.quality.items():
        print(f"* {k}: {v}")

    print("\n--- MENSAGENS / LOGS ---")
    for m in final_state.messages[-10:]:
        print("-", m)

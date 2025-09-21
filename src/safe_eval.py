from __future__ import annotations

import ast
from typing import Any, Dict
from model import GlobalState


class SafeConditionEvaluator:
    """
    Avalia expressões booleanas de forma SEGURA (sem eval/exec).
    Suporta:
      - Acesso a dicionários do estado: quality.x, artifacts.y, context.z
      - Operadores: and, or, not
      - Comparações: ==, !=, <, <=, >, >=
      - 'is not None' / 'is None'
    """

    ALLOWED_ROOTS = {"quality", "artifacts", "context"}
    ALLOWED_BOOL_OPS = (ast.And, ast.Or)
    ALLOWED_UNARY_OPS = (ast.Not,)
    ALLOWED_CMP_OPS = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot)

    def __init__(self, condition_string: str):
        self.expr_str = condition_string.strip()
        if not self.expr_str:
            # Sem condição => sempre False (não ativa)
            self.ast = None
            return
        try:
            tree = ast.parse(self.expr_str, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Condição inválida: {self.expr_str!r}") from e
        self._validate_ast(tree)
        self.ast = tree

    # ---------- Public API ----------

    def evaluate(self, state: GlobalState) -> bool:
        if self.ast is None:
            return False
        env = {
            "quality": state.quality,
            "artifacts": state.artifacts,
            "context": state.context,
            "None": None,
        }
        return bool(self._eval_node(self.ast.body, env))

    # ---------- Validation ----------

    def _validate_ast(self, node: ast.AST) -> None:
        # Restrição de nós permitidos
        for n in ast.walk(node):
            if isinstance(n, ast.BoolOp) and not isinstance(n.op, self.ALLOWED_BOOL_OPS):
                raise ValueError("Operador booleano não permitido.")
            if isinstance(n, ast.UnaryOp) and not isinstance(n.op, self.ALLOWED_UNARY_OPS):
                raise ValueError("Operador unário não permitido.")
            if isinstance(n, ast.Compare):
                for op in n.ops:
                    if not isinstance(op, self.ALLOWED_CMP_OPS):
                        raise ValueError("Operador de comparação não permitido.")
            if isinstance(n, ast.Call):
                raise ValueError("Chamadas de função não são permitidas.")
            if isinstance(n, ast.Attribute):
                # Será validado no path (raiz precisa ser allowed)
                pass
            if isinstance(n, ast.Name):
                if n.id not in self.ALLOWED_ROOTS and n.id != "None":
                    raise ValueError(f"Identificador não permitido: {n.id}")

    # ---------- Evaluation ----------

    def _resolve_path(self, env: Dict[str, Any], node: ast.AST) -> Any:
        """
        Converte 'quality.coverage' (Attribute chain) em env['quality']['coverage'].
        """
        # Suporta Name, Attribute encadeado
        parts = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        else:
            raise ValueError("Expressão de caminho inválida.")

        parts = list(reversed(parts))
        if parts[0] not in self.ALLOWED_ROOTS:
            raise ValueError("Raiz de caminho não permitida.")
        val: Any = env.get(parts[0])
        for p in parts[1:]:
            if isinstance(val, dict):
                val = val.get(p, None)
            else:
                return None
        return val

    def _eval_node(self, node: ast.AST, env: Dict[str, Any]) -> Any:
        if isinstance(node, ast.BoolOp):
            values = [self._eval_node(v, env) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            else:
                return any(values)

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not self._eval_node(node.operand, env)

        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, env)
            result = True
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator, env)
                if isinstance(op, ast.Is):
                    result = result and (left is right)
                elif isinstance(op, ast.IsNot):
                    result = result and (left is not right)
                elif isinstance(op, ast.Eq):
                    result = result and (left == right)
                elif isinstance(op, ast.NotEq):
                    result = result and (left != right)
                elif isinstance(op, ast.Lt):
                    result = result and (left < right)
                elif isinstance(op, ast.LtE):
                    result = result and (left <= right)
                elif isinstance(op, ast.Gt):
                    result = result and (left > right)
                elif isinstance(op, ast.GtE):
                    result = result and (left >= right)
                else:
                    raise ValueError("Operador de comparação não suportado.")
                left = right
            return result

        if isinstance(node, ast.Attribute):
            return self._resolve_path(env, node)

        if isinstance(node, ast.Name):
            if node.id == "None":
                return None
            # Raízes resolvidas diretamente
            if node.id in self.ALLOWED_ROOTS:
                return env.get(node.id)
            raise ValueError("Identificador não permitido.")

        if isinstance(node, ast.Constant):
            return node.value

        # Literais numéricos no Python < 3.8 (Num, Str, etc.)
        if hasattr(ast, "Num") and isinstance(node, getattr(ast, "Num")):
            return node.n
        if hasattr(ast, "Str") and isinstance(node, getattr(ast, "Str")):
            return node.s

        raise ValueError(f"Nó AST não suportado: {type(node).__name__}")

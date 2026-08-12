"""
CYNEXIS — Safe Calculator Tool
Deterministic, AST-validated arithmetic evaluator without LLM hallucinations or arbitrary code execution.
"""

import ast
import math
import re
from typing import Optional
from core.logger import get_logger

log = get_logger("calculator_tool")


class SafeCalculatorTool:
    """
    Safely parses and evaluates mathematical expressions using Python's AST.
    Guarantees zero arbitrary code execution (no eval/exec).
    """

    ALLOWED_NODES = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Call,
        ast.Name,
        ast.Load,
    )

    ALLOWED_FUNCTIONS = {
        "sqrt": math.sqrt,
        "abs": abs,
        "round": round,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "pow": pow,
    }

    ALLOWED_CONSTANTS = {
        "pi": math.pi,
        "e": math.e,
    }

    @classmethod
    def _eval_node(cls, node: ast.AST) -> float:
        """Recursively evaluate an AST node safely."""
        if isinstance(node, ast.Expression):
            return cls._eval_node(node.body)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError(f"Unsupported constant type: {type(node.value)}")

        if isinstance(node, ast.Name):
            if node.id in cls.ALLOWED_CONSTANTS:
                return float(cls.ALLOWED_CONSTANTS[node.id])
            raise ValueError(f"Unknown or unauthorized variable: {node.id}")

        if isinstance(node, ast.UnaryOp):
            operand = cls._eval_node(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
            raise ValueError(f"Unsupported unary operator: {type(node.op)}")

        if isinstance(node, ast.BinOp):
            left = cls._eval_node(node.left)
            right = cls._eval_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ZeroDivisionError("Division by zero")
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                if right == 0:
                    raise ZeroDivisionError("Division by zero")
                return left // right
            if isinstance(node.op, ast.Mod):
                if right == 0:
                    raise ZeroDivisionError("Modulo by zero")
                return left % right
            if isinstance(node.op, ast.Pow):
                if abs(right) > 1000:
                    raise OverflowError("Exponent too large")
                return left ** right
            raise ValueError(f"Unsupported binary operator: {type(node.op)}")

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in cls.ALLOWED_FUNCTIONS:
                func = cls.ALLOWED_FUNCTIONS[node.func.id]
                args = [cls._eval_node(arg) for arg in node.args]
                return float(func(*args))
            raise ValueError(f"Unauthorized function call: {ast.dump(node)}")

        raise ValueError(f"Unsupported AST node: {type(node)}")

    @classmethod
    def clean_query_to_expression(cls, query: str) -> str:
        """Convert natural language math phrases into standard arithmetic expressions."""
        text = query.lower().strip()

        # Handle 'calculate', 'what is', 'solve', 'how much is'
        text = re.sub(r"^(what is|calculate|solve|how much is|compute)\s+", "", text)
        text = text.rstrip("?").strip()

        # Handle percentage: "X percent of Y" or "X% of Y" -> "(X / 100) * Y"
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:percent|%)\s+of\s+(\d+(?:\.\d+)?)", text)
        if pct_match:
            pct, val = pct_match.group(1), pct_match.group(2)
            return f"({pct} / 100) * {val}"

        # Handle "square root of X"
        sqrt_match = re.search(r"square\s+root\s+of\s+(\d+(?:\.\d+)?)", text)
        if sqrt_match:
            return f"sqrt({sqrt_match.group(1)})"

        # Handle "X squared" -> "X ** 2"
        text = re.sub(r"(\d+(?:\.\d+)?)\s*squared", r"(\1 ** 2)", text)
        # Handle "X cubed" -> "X ** 3"
        text = re.sub(r"(\d+(?:\.\d+)?)\s*cubed", r"(\1 ** 3)", text)

        # Handle "X to the power of Y" -> "X ** Y"
        text = re.sub(r"\s+to\s+the\s+power\s+of\s+", " ** ", text)
        text = re.sub(r"\s+raised\s+to\s+", " ** ", text)

        # Handle "product of X and Y" -> "X * Y"
        text = re.sub(r"product\s+of\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)", r"\1 * \2", text)

        # Handle word operators (including "times of", "multiplied by", etc.)
        text = re.sub(r"\s+times\s+(of\s+)?", " * ", text)
        text = re.sub(r"\s+multiplied\s+by\s+", " * ", text)
        text = re.sub(r"\s+divided\s+by\s+", " / ", text)
        text = re.sub(r"\s+plus\s+", " + ", text)
        text = re.sub(r"\s+minus\s+", " - ", text)
        text = re.sub(r"\s+x\s+", " * ", text)
        text = text.replace("^", "**")

        # Strip leftover stray words
        text = re.sub(r"[\*\/\+\-]\s*of\s+", lambda m: m.group(0).replace("of", ""), text)

        # Keep only valid arithmetic characters
        sanitized = re.sub(r"[^0-9\.\+\-\*\/\(\)\%\s\w]", "", text)
        # Strip trailing/leading non-numbers/parens
        sanitized = re.sub(r"\b(of|and|the|is)\b", "", sanitized).strip()
        return sanitized.strip()

    @classmethod
    def evaluate(cls, query: str) -> Optional[float]:
        """Safely parse and evaluate mathematical query. Returns float or None on error."""
        try:
            expr_str = cls.clean_query_to_expression(query)
            if not expr_str:
                return None
            tree = ast.parse(expr_str, mode="eval")
            # Security walk: verify all nodes belong to allowed whitelist
            for node in ast.walk(tree):
                if not isinstance(node, cls.ALLOWED_NODES):
                    raise ValueError(f"Forbidden AST node type: {type(node)}")
            result = cls._eval_node(tree)
            return result
        except Exception as e:
            log.warning(f"Calculation error for '{query}': {e}")
            return None

    @classmethod
    def format_response(cls, query: str, result: float) -> str:
        """Format calculation result into natural spoken text."""
        # Format integer nicely without trailing .0
        if result.is_integer():
            formatted_val = f"{int(result):,}"
        else:
            formatted_val = f"{round(result, 4):,}"
        return f"The answer is {formatted_val}."

    @classmethod
    def process(cls, query: str) -> Optional[str]:
        """Process a math query and return natural response string."""
        val = cls.evaluate(query)
        if val is None:
            return None
        return cls.format_response(query, val)

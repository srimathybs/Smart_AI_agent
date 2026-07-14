"""math_tool.py — Math solver using sympy (exact answers)"""

class MathTool:
    name = "solve_math"
    description = "Solve math problems exactly. INPUT: expression like 'solve x**2-4=0', 'diff(x**3)', 'integrate(x**2)', or '2**10'. OUTPUT: exact answer."
    def _run(self, expression: str) -> str:
        try:
            import sympy as sp
            from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
            expr_lower = expression.strip().lower()
            transforms = standard_transformations + (implicit_multiplication_application,)
            if expr_lower.startswith("solve"):
                eq_str = expression[5:].strip().lstrip("(").rstrip(")")
                x = sp.Symbol("x")
                if "=" in eq_str:
                    lhs, rhs = eq_str.split("=",1)
                    eq = sp.Eq(parse_expr(lhs.strip()), parse_expr(rhs.strip()))
                else:
                    eq = parse_expr(eq_str)
                return f"Solution: x = {sp.solve(eq, x)}"
            elif expr_lower.startswith("diff"):
                inner = expression.split("(",1)[1].rstrip(")")
                x = sp.Symbol("x")
                return f"Derivative: {sp.diff(parse_expr(inner.split(',')[0].strip()), x)}"
            elif expr_lower.startswith("integr"):
                inner = expression.split("(",1)[1].rstrip(")")
                x = sp.Symbol("x")
                return f"Integral: {sp.integrate(parse_expr(inner.split(',')[0].strip()), x)} + C"
            elif expr_lower.startswith("simplify"):
                inner = expression.split("(",1)[1].rstrip(")")
                return f"Simplified: {sp.simplify(parse_expr(inner))}"
            else:
                result = parse_expr(expression, transformations=transforms)
                num = sp.N(result)
                return f"Result: {result} ≈ {num}" if num != result else f"Result: {result}"
        except ImportError:
            try:
                import math
                return f"Result: {eval(expression, {'__builtins__': {}}, vars(math))}"
            except Exception as e2: return f"Math error: {str(e2)}"
        except Exception as e: return f"Math error: {str(e)}"

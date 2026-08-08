"""AST scanner that tests the tests.

Scans Python source for `except` handlers that swallow exceptions silently:
bare `except:`, or a broad `except Exception/:` with a no-op body (`pass`,
`return`, `break`). The kit uses this same pattern on itself (see 08_static_gates)
to lint for the very anti-pattern it exists to catch.

One dependency only: pytest (+ stdlib ast).
"""
from __future__ import annotations

import ast


BAD_BODY = """
try:
    risky()
except:          # bare except: swallowed
    pass
"""

OK_BODY = """
try:
    risky()
except Exception as e:
    logger.exception("handled")
"""


class SilentSwallowVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.found: list[int] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        silent = False
        if node.type is None:  # bare except:
            silent = True
        else:
            t = ast.unparse(node.type)
            broad = t in {"Exception", "BaseException", "object"}
            empty = all(
                isinstance(stmt, (ast.Pass, ast.Break, ast.Continue))
                or (isinstance(stmt, ast.Return) and stmt.value is None)
                for stmt in node.body
            )
            silent = broad and empty
        if silent:
            self.found.append(node.lineno)
        self.generic_visit(node)


def scan(src: str) -> list[int]:
    tree = ast.parse(src)
    vis = SilentSwallowVisitor()
    vis.visit(tree)
    return vis.found


def test_scanner_flags_bare_except() -> None:
    assert len(scan(BAD_BODY)) >= 1


def test_scanner_ignores_logged_handler() -> None:
    assert scan(OK_BODY) == []


if __name__ == "__main__":
    assert len(scan(BAD_BODY)) == 1
    assert scan(OK_BODY) == []
    print("04_silent_swallow_scanner OK")

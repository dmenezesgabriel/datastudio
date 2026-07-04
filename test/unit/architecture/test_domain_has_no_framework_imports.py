"""Architectural guard: the domain layer imports no third-party framework.

Clean Architecture's Dependency Rule: the innermost ring (``domain``) must not
depend on frameworks or the execution model. A domain value object that imports
LangChain/LangGraph (or FastAPI/DuckDB/LiteLLM) is really an infrastructure
detail wearing a domain costume — it drags the framework into the pure core and
makes the domain unimportable without it.

``pydantic`` is deliberately allowed: value objects use it as a serialization
boundary (see ``render_tree.py``), and CLAUDE.md sanctions it.

This fails fast if any module under ``src/**/domain`` imports a forbidden
framework's top-level package.
"""

import ast
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
_DOMAIN_ROOTS = ("chat/domain", "shared/domain")

# Top-level packages that belong to the outer (infrastructure) ring only.
_FORBIDDEN_ROOTS = frozenset(
    {
        "langchain",
        "langchain_core",
        "langgraph",
        "fastapi",
        "starlette",
        "sse_starlette",
        "duckdb",
        "litellm",
        "uvicorn",
    }
)


def _domain_files() -> list[Path]:
    """Return every ``.py`` module under the domain roots."""
    return [
        path
        for root in _DOMAIN_ROOTS
        for path in (_SRC_ROOT / root).rglob("*.py")
        if path.is_file()
    ]


def _imported_roots(path: Path) -> set[str]:
    """Return the set of top-level package names imported by one module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


class TestDomainHasNoFrameworkImports:
    def test_domain_imports_no_framework(self) -> None:
        # Arrange
        files = _domain_files()

        # Act
        offenders = {
            str(path.relative_to(_SRC_ROOT)): sorted(leaked)
            for path in files
            if (leaked := _imported_roots(path) & _FORBIDDEN_ROOTS)
        }

        # Assert
        assert offenders == {}, (
            "Framework imports leaked into the domain layer (move the module to "
            f"infrastructure): {offenders}"
        )

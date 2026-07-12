"""Architectural guard: the application layer never imports infrastructure.

Dependency Inversion: use cases and ports depend on abstractions they own, and
concretions are injected at the composition root (``bootstrap.py``). An
application module importing from ``infrastructure`` inverts the allowed
direction and couples the policy to a specific mechanism (a logger factory, a
graph, a DB driver).

This fails fast if any module under ``src/**/application`` imports a module
whose dotted path contains an ``infrastructure`` segment.
"""

import ast
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
_APPLICATION_ROOTS = ("chat/application", "shared/application", "identity/application")


def _application_files() -> list[Path]:
    """Return every ``.py`` module under the application roots."""
    return [
        path
        for root in _APPLICATION_ROOTS
        for path in (_SRC_ROOT / root).rglob("*.py")
        if path.is_file()
    ]


def _imported_modules(path: Path) -> set[str]:
    """Return the fully-qualified module paths imported by one module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


class TestApplicationHasNoInfrastructureImports:
    def test_application_imports_no_infrastructure(self) -> None:
        # Arrange
        files = _application_files()

        # Act
        offenders = {
            str(path.relative_to(_SRC_ROOT)): sorted(leaked)
            for path in files
            if (leaked := {m for m in _imported_modules(path) if "infrastructure" in m.split(".")})
        }

        # Assert
        assert offenders == {}, (
            "Application layer imports infrastructure (inject the dependency at the "
            f"composition root instead): {offenders}"
        )

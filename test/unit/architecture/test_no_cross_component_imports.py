"""Architectural guard: components stay decoupled, sharing ids not implementations.

Bounded-context rule: feature/identity components communicate only through ids
and the ``shared`` kernel — never by importing each other's modules. ``chat``
must not import ``identity`` (it receives a ``user_id`` via the injected
``CurrentUser`` port); ``identity`` must not import ``chat``; and ``shared`` must
depend on no component. Cross-component wiring lives solely in ``bootstrap.py``.

This fails fast if any module under ``src/<component>`` imports a sibling
component's top-level package.
"""

import ast
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[3] / "src"

# For each component, the sibling top-level packages it may never import.
_FORBIDDEN_BY_COMPONENT = {
    "chat": frozenset({"identity"}),
    "identity": frozenset({"chat"}),
    "shared": frozenset({"chat", "identity"}),
}


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


class TestNoCrossComponentImports:
    def test_components_do_not_import_each_other(self) -> None:
        # Arrange / Act
        offenders = {
            str(path.relative_to(_SRC_ROOT)): sorted(leaked)
            for component, forbidden in _FORBIDDEN_BY_COMPONENT.items()
            for path in (_SRC_ROOT / component).rglob("*.py")
            if path.is_file() and (leaked := _imported_roots(path) & forbidden)
        }

        # Assert
        assert offenders == {}, (
            "Cross-component import leaked (share ids via the shared kernel and wire at "
            f"bootstrap instead): {offenders}"
        )

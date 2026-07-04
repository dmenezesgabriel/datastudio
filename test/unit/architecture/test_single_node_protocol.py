"""Architectural guard: the graph-node callable Protocol is declared exactly once.

``ObservableNode``/``ProgressNode``/``TimedNode`` are proxies over a graph node;
Proxy + DIP require the proxy and its subject to share **one** interface, and
CLAUDE.md says a shared ``Typed*`` alias lives in ``infrastructure/graph/types.py``
and is imported, never redefined. Three local copies of the ``__call__(state) ->
Mapping`` Protocol had drifted across modules; this pins it to a single
declaration (``TypedChatNode``).
"""

import ast
from pathlib import Path

_CHAT_ROOT = Path(__file__).resolve().parents[3] / "src" / "chat"


def _is_node_protocol(node: ast.ClassDef) -> bool:
    """True if ``node`` is a ``Protocol`` with a ``__call__(self, state, ...)`` method."""
    if not any(isinstance(base, ast.Name) and base.id == "Protocol" for base in node.bases):
        return False
    for member in node.body:
        if isinstance(member, ast.FunctionDef) and member.name == "__call__":
            params = [a.arg for a in member.args.args]
            return "state" in params
    return False


def _node_protocol_declarations() -> dict[str, str]:
    """Map ``rel_path:ClassName`` for every node-callable Protocol under ``src/chat``."""
    found: dict[str, str] = {}
    for path in _CHAT_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _is_node_protocol(node):
                found[f"{path.relative_to(_CHAT_ROOT)}:{node.name}"] = node.name
    return found


class TestSingleNodeProtocol:
    def test_node_protocol_declared_once_as_typed_chat_node(self) -> None:
        # Arrange / Act
        declarations = _node_protocol_declarations()

        # Assert
        assert list(declarations.values()) == ["TypedChatNode"], (
            "The graph-node Protocol must be declared once as TypedChatNode in "
            f"infrastructure/graph/types.py; found: {sorted(declarations)}"
        )

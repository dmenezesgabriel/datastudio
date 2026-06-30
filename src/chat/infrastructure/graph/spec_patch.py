"""Typed parsing of json-render SpecStream patch lines (one RFC-6902 op per line)."""

import json
from typing import cast


def parse_patch(line: str) -> dict[str, object] | None:
    """Parse one SpecStream line into a patch dict, or None if it isn't a JSON object.

    Example:
        parse_patch('{"op":"add","path":"/root","value":"root"}')
    """
    try:
        parsed: object = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    return cast(dict[str, object], parsed) if isinstance(parsed, dict) else None

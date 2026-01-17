"""
Value Serialization Module

This module provides safe serialization of values for Neo4j property storage.
Handles primitives, lists, dicts, and Azure SDK objects.
"""

import json
from typing import Any

import structlog  # type: ignore[import-untyped]

logger = structlog.get_logger(__name__)


def serialize_value(value: Any, max_json_length: int = 5000) -> Any:
    """
    Safely serialize a value for Neo4j property storage.

    Allowed: str, int, float, bool, list of those.
    - dicts/objects: JSON string (truncated if huge).
    - Azure SDK objects: str() or .name if present.
    - Empty dict: None.

    Args:
        value: Any Python value to serialize
        max_json_length: Maximum length for JSON strings (default 5000)

    Returns:
        Neo4j-compatible value (str, int, float, bool, list, or None)
    """
    # Primitives
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    # List: recursively serialize
    if isinstance(value, list):
        return [serialize_value(v, max_json_length) for v in value]  # type: ignore[misc]

    # Dict: JSON dump, handle empty
    if isinstance(value, dict):
        if not value:
            return None
        try:
            s = json.dumps(value, default=str, ensure_ascii=False)
            if len(s) > max_json_length:
                # Log warning when truncating to help identify large properties
                logger.warning(
                    f"Property value truncated: size={len(s)} chars (max={max_json_length}). "
                    f"Preview: {s[:200]}..."
                )
                s = s[:max_json_length] + "...(truncated)"
            # Warn if approaching truncation limit (>80% of max)
            elif len(s) > max_json_length * 0.8:
                logger.info(
                    f"Large property detected: size={len(s)} chars "
                    f"({int((len(s) / max_json_length) * 100)}% of max {max_json_length})"
                )
            return s
        except Exception:
            return str(value)  # type: ignore[misc]

    # Azure SDK model: try as_dict() for properties, then .name, else str
    if hasattr(value, "as_dict") and callable(value.as_dict):
        try:
            return serialize_value(value.as_dict(), max_json_length)
        except Exception:
            pass

    if hasattr(value, "name") and isinstance(value.name, str):
        return value.name

    # Fallback: str
    return str(value)

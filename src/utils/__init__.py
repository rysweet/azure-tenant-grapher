"""
Utility modules for Azure Tenant Grapher.

This package contains utility classes and functions that provide common
functionality across the application.
"""

# Import console_icons first (no dependencies)
from . import console_icons

# Lazy import session_manager to avoid import errors in tests
try:
    from .session_manager import Neo4jSessionManager, create_session_manager, neo4j_session
    __all__ = [
        "Neo4jSessionManager",
        "create_session_manager",
        "neo4j_session",
        "console_icons",
    ]
except ImportError:
    # If dependencies not available (e.g., during testing), only export console_icons
    __all__ = ["console_icons"]


def extract_subscription_id_from_resource_id(resource_id: str) -> str:
    """
    Extracts the subscription ID from a full Azure resource ID.
    Example: /subscriptions/1234/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1
    Returns: 1234
    """
    import re

    match = re.search(r"/subscriptions/([^/]+)", resource_id)
    if match:
        return match.group(1)
    return ""

"""
Azure Tenant Grapher

A comprehensive tool for walking Azure tenant resources and building
a Neo4j graph database of those resources and their relationships.
"""

from typing import Any, Dict, List, Optional, Union

__version__ = "1.0.0"
__author__ = "Azure Tenant Grapher Team"

# Import configuration first as it has minimal dependencies
from .config_manager import AzureTenantGrapherConfig, create_config_from_env


# Conditionally import other modules to avoid import errors in test environments
def _safe_import() -> bool:
    """Safely import modules that may have missing dependencies in test environments."""
    try:
        # Only import if Azure SDK is available
        from azure.mgmt.resource import ResourceManagementClient

        from .azure_tenant_grapher import AzureTenantGrapher
        from .container_manager import Neo4jContainerManager
        from .graph_visualizer import GraphVisualizer
        from .llm_descriptions import AzureLLMDescriptionGenerator, create_llm_generator
        from .resource_processor import ResourceProcessor, create_resource_processor

        # Make them available at package level
        globals().update(
            {
                "AzureTenantGrapher": AzureTenantGrapher,
                "ResourceProcessor": ResourceProcessor,
                "create_resource_processor": create_resource_processor,
                "AzureLLMDescriptionGenerator": AzureLLMDescriptionGenerator,
                "create_llm_generator": create_llm_generator,
                "Neo4jContainerManager": Neo4jContainerManager,
                "GraphVisualizer": GraphVisualizer,
            }
        )

        return True
    except ImportError:
        # In test environments or when Azure SDK isn't installed
        return False


# Attempt safe import on module load
_safe_import()

__all__ = [
    "AzureLLMDescriptionGenerator",
    "AzureTenantGrapher",
    "AzureTenantGrapherConfig",
    "GraphVisualizer",
    "Neo4jContainerManager",
    "ResourceProcessor",
    "create_config_from_env",
    "create_llm_generator",
    "create_resource_processor",
]

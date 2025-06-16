"""Base emitter class for Infrastructure-as-Code generation.

This module defines the abstract base class for all IaC emitters,
providing a common interface for different target formats.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..traverser import TenantGraph


class IaCEmitter(ABC):
    """Abstract base class for Infrastructure-as-Code emitters.
    
    All emitters must implement this interface to provide consistent
    template generation capabilities across different IaC formats.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize emitter with optional configuration.
        
        Args:
            config: Optional emitter-specific configuration
        """
        self.config = config or {}

    @abstractmethod
    def emit(self, graph: TenantGraph, out_dir: Path) -> List[Path]:
        """Generate IaC templates from tenant graph.
        
        Args:
            graph: Input tenant graph data
            out_dir: Output directory path
            
        Returns:
            List of written file paths
        """
        raise NotImplementedError("Template emission not yet implemented")

    @abstractmethod
    async def emit_template(
        self,
        tenant_graph: TenantGraph,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate IaC template from tenant graph (legacy method).
        
        Args:
            tenant_graph: Input tenant graph data
            output_path: Optional output file path
            
        Returns:
            Dictionary containing generated template data and metadata
        """
        raise NotImplementedError("Template emission not yet implemented")

    @abstractmethod
    def get_supported_resource_types(self) -> List[str]:
        """Get list of Azure resource types supported by this emitter.
        
        Returns:
            List of supported Azure resource type strings
        """
        raise NotImplementedError("Resource type enumeration not yet implemented")

    @abstractmethod
    def validate_template(self, template_data: Dict[str, Any]) -> bool:
        """Validate generated template for correctness.
        
        Args:
            template_data: Generated template data to validate
            
        Returns:
            True if template is valid, False otherwise
        """
        raise NotImplementedError("Template validation not yet implemented")

    def get_format_name(self) -> str:
        """Get the name of the IaC format this emitter targets.
        
        Returns:
            Format name string (e.g., 'terraform', 'arm', 'bicep')
        """
        # Default implementation extracts from class name
        class_name = self.__class__.__name__
        if class_name.endswith("Emitter"):
            return class_name[:-7].lower()
        return class_name.lower()

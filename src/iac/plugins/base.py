"""Base class for resource replication plugins."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .models import (
    DataPlaneAnalysis,
    ExtractionResult,
    PluginMetadata,
    ReplicationResult,
    ReplicationStep,
)


class ResourceReplicationPlugin(ABC):
    """Abstract base class for data-plane replication plugins.

    Plugins implement resource-specific logic for:
    1. Analyzing what data exists in source resource
    2. Extracting that data (configs, files, databases, etc.)
    3. Generating replication scripts (Ansible, shell, SQL, etc.)
    4. Applying those scripts to target resource

    Each plugin is responsible for one or more Azure resource types
    and knows how to replicate their data-plane configurations.
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata.

        Returns:
            PluginMetadata describing this plugin
        """
        pass

    @property
    def resource_types(self) -> List[str]:
        """Get list of Azure resource types this plugin handles.

        Returns:
            List of resource type strings (e.g., ["Microsoft.Compute/virtualMachines"])
        """
        return self.metadata.resource_types

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if this plugin can handle the given resource.

        Default implementation checks resource type. Subclasses can override
        to add additional filtering (e.g., OS type, installed software).

        Args:
            resource: Resource dictionary with 'type' key

        Returns:
            True if plugin can handle this resource
        """
        resource_type = resource.get("type", "")
        return resource_type in self.resource_types

    @abstractmethod
    async def analyze_source(self, resource: Dict[str, Any]) -> DataPlaneAnalysis:
        """Analyze the source resource to determine what needs replication.

        This method should:
        1. Connect to the resource (if needed)
        2. Discover what data plane elements exist
        3. Categorize elements by priority
        4. Estimate complexity and size

        Args:
            resource: Source resource dictionary (from Neo4j or Azure API)

        Returns:
            DataPlaneAnalysis describing what exists

        Raises:
            ConnectionError: If cannot connect to resource
            PermissionError: If insufficient permissions
        """
        pass

    @abstractmethod
    async def extract_data(
        self, resource: Dict[str, Any], analysis: DataPlaneAnalysis
    ) -> ExtractionResult:
        """Extract data from source resource.

        This method should:
        1. Connect to the resource
        2. Extract configs, files, databases, etc.
        3. Save to local files
        4. Sanitize sensitive data
        5. Generate documentation

        Args:
            resource: Source resource dictionary
            analysis: Previous analysis result

        Returns:
            ExtractionResult with paths to extracted data

        Raises:
            ExtractionError: If extraction fails
        """
        pass

    @abstractmethod
    async def generate_replication_steps(
        self, extraction: ExtractionResult
    ) -> List[ReplicationStep]:
        """Generate steps to replicate data to target.

        This method should:
        1. Analyze extracted data
        2. Generate scripts (Ansible, shell, SQL, PowerShell, etc.)
        3. Create ordered steps with dependencies
        4. Include verification steps

        Args:
            extraction: Previous extraction result

        Returns:
            List of ReplicationStep objects in execution order

        Raises:
            GenerationError: If script generation fails
        """
        pass

    @abstractmethod
    async def apply_to_target(
        self, steps: List[ReplicationStep], target_resource_id: str
    ) -> ReplicationResult:
        """Apply replication steps to target resource.

        This method should:
        1. Connect to target resource
        2. Execute steps in order
        3. Handle failures gracefully
        4. Verify each step
        5. Collect results

        Args:
            steps: Steps to execute
            target_resource_id: Azure resource ID of target

        Returns:
            ReplicationResult with success/failure status

        Raises:
            ReplicationError: If critical steps fail
        """
        pass

    async def replicate(
        self, source_resource: Dict[str, Any], target_resource_id: str
    ) -> ReplicationResult:
        """Full replication workflow from source to target.

        Convenience method that runs all steps:
        1. Analyze source
        2. Extract data
        3. Generate steps
        4. Apply to target

        Args:
            source_resource: Source resource dictionary
            target_resource_id: Azure resource ID of target

        Returns:
            ReplicationResult with final status
        """
        # Analyze
        analysis = await self.analyze_source(source_resource)

        # Extract
        extraction = await self.extract_data(source_resource, analysis)

        # Generate steps
        steps = await self.generate_replication_steps(extraction)

        # Apply
        result = await self.apply_to_target(steps, target_resource_id)

        return result

"""
Scale Operation Models

Data models for tracking scale operations in Azure Tenant Grapher.
Scale operations are tracked to enable:
- Progress monitoring during operations
- Post-operation validation
- Cleanup and rollback capabilities
- Audit trail of synthetic resource generation
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, Optional


@dataclass
class ScaleOperationMetadata:
    """
    Metadata for tracking a scale operation.

    This model captures all relevant information about a scale operation,
    enabling progress tracking, validation, and audit capabilities.

    Attributes:
        operation_id: Unique identifier for the operation
        operation_type: Type of operation ("scale-up" or "scale-down")
        tenant_id: Azure tenant ID being operated on
        started_at: Timestamp when operation started
        completed_at: Timestamp when operation completed (None if running)
        status: Current status ("running", "completed", "failed")
        nodes_affected: Number of nodes created/modified/deleted
        relationships_affected: Number of relationships created/modified/deleted
        strategy: Generation strategy used
        config: Configuration parameters for the operation
        error_message: Error message if operation failed
        validation_results: Results of post-operation validation

    Examples:
        >>> metadata = ScaleOperationMetadata(
        ...     operation_id="scale-20250110T123045-a1b2c3d4",
        ...     operation_type="scale-up",
        ...     tenant_id="00000000-0000-0000-0000-000000000000",
        ...     started_at=datetime.now(UTC),
        ...     status="running",
        ...     strategy="pattern_replication",
        ...     config={"target_count": 1000, "pattern_type": "vm_cluster"}
        ... )
        >>> print(metadata.operation_id)
        scale-20250110T123045-a1b2c3d4
    """

    operation_id: str
    operation_type: str  # "scale-up" or "scale-down"
    tenant_id: str
    started_at: datetime
    status: str  # "running", "completed", "failed"
    strategy: str
    config: Dict[str, Any]

    completed_at: Optional[datetime] = None
    nodes_affected: int = 0
    relationships_affected: int = 0
    error_message: Optional[str] = None
    validation_results: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        # Validate operation_type
        valid_operation_types = ["scale-up", "scale-down"]
        if self.operation_type not in valid_operation_types:
            raise ValueError(
                f"Invalid operation_type: {self.operation_type}. "
                f"Must be one of: {valid_operation_types}"
            )

        # Validate status
        valid_statuses = ["running", "completed", "failed"]
        if self.status not in valid_statuses:
            raise ValueError(
                f"Invalid status: {self.status}. Must be one of: {valid_statuses}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert metadata to dictionary format.

        Returns:
            Dict[str, Any]: Dictionary representation suitable for JSON serialization

        Example:
            >>> metadata = ScaleOperationMetadata(...)
            >>> data = metadata.to_dict()
            >>> print(data["operation_id"])
            scale-20250110T123045-a1b2c3d4
        """
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "tenant_id": self.tenant_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "status": self.status,
            "nodes_affected": self.nodes_affected,
            "relationships_affected": self.relationships_affected,
            "strategy": self.strategy,
            "config": self.config,
            "error_message": self.error_message,
            "validation_results": self.validation_results,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScaleOperationMetadata":
        """
        Create metadata instance from dictionary.

        Args:
            data: Dictionary containing metadata fields

        Returns:
            ScaleOperationMetadata: New instance created from dictionary

        Example:
            >>> data = {
            ...     "operation_id": "scale-20250110T123045-a1b2c3d4",
            ...     "operation_type": "scale-up",
            ...     "tenant_id": "00000000-0000-0000-0000-000000000000",
            ...     "started_at": "2025-01-10T12:30:45.123456",
            ...     "status": "completed",
            ...     "strategy": "pattern_replication",
            ...     "config": {}
            ... }
            >>> metadata = ScaleOperationMetadata.from_dict(data)
            >>> print(metadata.operation_type)
            scale-up
        """
        # Parse timestamps if they're strings
        started_at = data["started_at"]
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)

        completed_at = data.get("completed_at")
        if isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at)

        return cls(
            operation_id=data["operation_id"],
            operation_type=data["operation_type"],
            tenant_id=data["tenant_id"],
            started_at=started_at,
            completed_at=completed_at,
            status=data["status"],
            nodes_affected=data.get("nodes_affected", 0),
            relationships_affected=data.get("relationships_affected", 0),
            strategy=data["strategy"],
            config=data.get("config", {}),
            error_message=data.get("error_message"),
            validation_results=data.get("validation_results", {}),
        )

    def mark_completed(self) -> None:
        """
        Mark operation as completed.

        Updates status to "completed" and sets completion timestamp.

        Example:
            >>> metadata = ScaleOperationMetadata(...)
            >>> metadata.mark_completed()
            >>> print(metadata.status)
            completed
        """
        self.status = "completed"
        self.completed_at = datetime.now(UTC)

    def mark_failed(self, error_message: str) -> None:
        """
        Mark operation as failed.

        Updates status to "failed" and sets error message and completion timestamp.

        Args:
            error_message: Description of the failure

        Example:
            >>> metadata = ScaleOperationMetadata(...)
            >>> metadata.mark_failed("Database connection timeout")
            >>> print(metadata.status)
            failed
            >>> print(metadata.error_message)
            Database connection timeout
        """
        self.status = "failed"
        self.error_message = error_message
        self.completed_at = datetime.now(UTC)

    def update_progress(self, nodes_affected: int, relationships_affected: int) -> None:
        """
        Update operation progress counters.

        Args:
            nodes_affected: Number of nodes affected
            relationships_affected: Number of relationships affected

        Example:
            >>> metadata = ScaleOperationMetadata(...)
            >>> metadata.update_progress(100, 250)
            >>> print(metadata.nodes_affected)
            100
            >>> print(metadata.relationships_affected)
            250
        """
        self.nodes_affected = nodes_affected
        self.relationships_affected = relationships_affected

    def add_validation_result(
        self, check_name: str, passed: bool, message: str
    ) -> None:
        """
        Add a validation result to the operation metadata.

        Args:
            check_name: Name of the validation check
            passed: Whether the check passed
            message: Validation result message

        Example:
            >>> metadata = ScaleOperationMetadata(...)
            >>> metadata.add_validation_result(
            ...     "original_contamination",
            ...     True,
            ...     "No Original layer contamination detected"
            ... )
            >>> print(metadata.validation_results["original_contamination"]["passed"])
            True
        """
        self.validation_results[check_name] = {
            "passed": passed,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def is_running(self) -> bool:
        """
        Check if operation is currently running.

        Returns:
            bool: True if operation is running, False otherwise

        Example:
            >>> metadata = ScaleOperationMetadata(..., status="running")
            >>> print(metadata.is_running())
            True
        """
        return self.status == "running"

    def is_completed(self) -> bool:
        """
        Check if operation completed successfully.

        Returns:
            bool: True if operation completed successfully, False otherwise

        Example:
            >>> metadata = ScaleOperationMetadata(..., status="completed")
            >>> print(metadata.is_completed())
            True
        """
        return self.status == "completed"

    def is_failed(self) -> bool:
        """
        Check if operation failed.

        Returns:
            bool: True if operation failed, False otherwise

        Example:
            >>> metadata = ScaleOperationMetadata(..., status="failed")
            >>> print(metadata.is_failed())
            True
        """
        return self.status == "failed"

    def duration_seconds(self) -> Optional[float]:
        """
        Calculate operation duration in seconds.

        Returns:
            Optional[float]: Duration in seconds, or None if not completed

        Example:
            >>> metadata = ScaleOperationMetadata(
            ...     started_at=datetime(2025, 1, 10, 12, 0, 0),
            ...     completed_at=datetime(2025, 1, 10, 12, 5, 30),
            ...     ...
            ... )
            >>> print(metadata.duration_seconds())
            330.0
        """
        if not self.completed_at:
            return None

        delta = self.completed_at - self.started_at
        return delta.total_seconds()

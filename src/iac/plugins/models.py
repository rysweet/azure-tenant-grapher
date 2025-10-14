"""Data models for resource replication plugins.

This module defines the core data structures used throughout the plugin system
for analyzing, extracting, and replicating data plane configurations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AnalysisStatus(str, Enum):
    """Status of data plane analysis operation."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class ExtractionFormat(str, Enum):
    """Supported formats for extracted data."""

    JSON = "json"
    LDIF = "ldif"
    XML = "xml"
    CSV = "csv"
    POWERSHELL_DSC = "powershell_dsc"
    ANSIBLE_PLAYBOOK = "ansible_playbook"
    SHELL_SCRIPT = "shell_script"
    SQL_SCRIPT = "sql_script"
    TERRAFORM = "terraform"
    BINARY = "binary"


class StepType(str, Enum):
    """Type of replication step."""

    PREREQUISITE = "prerequisite"
    CONFIGURATION = "configuration"
    DATA_IMPORT = "data_import"
    VALIDATION = "validation"
    POST_CONFIG = "post_config"


class ReplicationStatus(str, Enum):
    """Status of replication operation."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    PARTIAL = "partial"  # Alias for backward compatibility
    FAILED = "failed"
    SKIPPED = "skipped"


# Alias for backward compatibility with existing code
ReplicationStepType = StepType


@dataclass
class DataPlaneElement:
    """Represents a single data plane element discovered during analysis."""

    name: str
    element_type: str
    description: str

    # Optional/flexible fields
    complexity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, VERY_HIGH
    estimated_size_mb: float = 0.1
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Legacy fields for backward compatibility
    priority: Optional[str] = None  # critical, high, medium, low
    extraction_method: Optional[str] = None
    is_sensitive: bool = False


@dataclass
class DataPlaneAnalysis:
    """Result of analyzing a resource's data plane configuration."""

    resource_id: str
    resource_type: str
    elements: List[DataPlaneElement]

    # Optional fields with defaults
    status: AnalysisStatus = AnalysisStatus.SUCCESS
    total_estimated_size_mb: float = 0.0
    complexity_score: float = 5.0  # 1-10
    requires_credentials: bool = True
    requires_network_access: bool = True
    connection_methods: List[str] = field(default_factory=list)  # ["WinRM", "SSH", "LDAP", etc.]
    estimated_extraction_time_minutes: int = 10
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    analyzed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExtractedData:
    """Represents extracted data in a specific format."""

    name: str
    format: ExtractionFormat
    content: Any  # str for text formats, bytes for binary
    file_path: Optional[str] = None
    size_bytes: int = 0
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Result of extracting data from a resource."""

    resource_id: str

    # Optional fields with defaults for flexibility
    status: AnalysisStatus = AnalysisStatus.SUCCESS
    extracted_data: List[ExtractedData] = field(default_factory=list)
    total_size_mb: float = 0.0
    extraction_duration_seconds: float = 0.0
    items_extracted: int = 0
    items_failed: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    # Legacy fields for backward compatibility
    extracted_files: List[str] = field(default_factory=list)
    scripts_generated: List[str] = field(default_factory=list)
    size_bytes: int = 0


@dataclass
class ReplicationStep:
    """A single step in the replication process."""

    step_id: str
    step_type: StepType
    description: str

    # Optional fields with defaults
    script_content: str = ""
    script_format: ExtractionFormat = ExtractionFormat.SHELL_SCRIPT
    depends_on: List[str] = field(default_factory=list)
    estimated_duration_minutes: int = 5
    is_critical: bool = True
    can_retry: bool = True
    max_retries: int = 3
    validation_script: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Legacy fields for backward compatibility
    command: Optional[str] = None
    script_path: Optional[str] = None
    timeout_seconds: Optional[int] = None


@dataclass
class StepResult:
    """Result of executing a single replication step."""

    step_id: str
    status: ReplicationStatus
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    retry_count: int = 0
    error_message: Optional[str] = None
    executed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReplicationResult:
    """Final result of applying replication to target resource."""

    target_resource_id: str
    status: ReplicationStatus

    # Optional fields with defaults
    source_resource_id: str = "unknown"
    steps_executed: List[StepResult] | List[str] = field(default_factory=list)  # Can be StepResult or str
    total_duration_seconds: float = 0.0
    steps_succeeded: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0
    fidelity_score: float = 0.0  # 0.0-1.0, how closely target matches source
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    completed_at: datetime = field(default_factory=datetime.utcnow)

    # Legacy fields for backward compatibility
    resource_id: Optional[str] = None  # Legacy: equivalent to source_resource_id
    success_rate: Optional[float] = None  # Legacy: equivalent to fidelity_score


@dataclass
class PluginMetadata:
    """Metadata about a replication plugin."""

    name: str
    version: str
    description: str
    resource_types: List[str]

    # Optional fields for compatibility
    author: str = "Azure Tenant Grapher"
    supported_formats: List[ExtractionFormat] = field(default_factory=list)
    requires_credentials: bool = True
    requires_network_access: bool = True
    complexity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, VERY_HIGH
    estimated_effort_weeks: float = 1.0
    tags: List[str] = field(default_factory=list)
    documentation_url: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Legacy fields for backward compatibility
    requires_ssh: Optional[bool] = None
    requires_winrm: Optional[bool] = None
    requires_azure_sdk: Optional[bool] = None
    supported_os: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

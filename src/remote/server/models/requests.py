"""
Request Models for ATG Remote API.

Philosophy:
- Match OpenAPI spec exactly
- Pydantic validation for all fields
- Clear defaults and descriptions

All request models use Pydantic for automatic validation.
"""

import re
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class ScanRequest(BaseModel):
    """
    Request to start a tenant scan operation.

    Matches POST /api/v1/scan from OpenAPI spec.
    """

    tenant_id: str = Field(
        ...,
        description="Azure tenant ID to scan",
        examples=["12345678-1234-1234-1234-123456789abc"],
    )
    resource_limit: Optional[int] = Field(
        None, description="Maximum number of resources to process (for testing)", gt=0
    )
    max_llm_threads: int = Field(5, description="Maximum LLM threads", ge=1, le=20)
    max_build_threads: int = Field(20, description="Maximum build threads", ge=1, le=50)
    max_retries: int = Field(3, description="Maximum retries", ge=0, le=10)
    max_concurrency: int = Field(100, description="Maximum concurrency", ge=1, le=200)
    generate_spec: bool = Field(False, description="Generate tenant spec after scan")
    visualize: bool = Field(False, description="Generate visualization after scan")
    rebuild_edges: bool = Field(False, description="Rebuild graph edges")
    no_aad_import: bool = Field(False, description="Skip AAD import")
    filter_by_subscriptions: Optional[str] = Field(
        None, description="Comma-separated subscription IDs"
    )
    filter_by_rgs: Optional[str] = Field(
        None, description="Comma-separated resource group names"
    )

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: str) -> str:
        """Validate tenant ID format (UUID)."""
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        if not uuid_pattern.match(v):
            raise ValueError("tenant_id must be a valid UUID")
        return v


class GenerateSpecRequest(BaseModel):
    """
    Request to generate tenant specification.

    Matches POST /api/v1/generate-spec from OpenAPI spec.
    """

    tenant_id: Optional[str] = Field(
        None, description="Optional tenant ID (uses graph if not provided)"
    )
    domain_name: Optional[str] = Field(None, description="Domain name")
    limit: Optional[int] = Field(None, description="Resource limit", gt=0)
    hierarchical: bool = Field(False, description="Generate hierarchical spec")

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate tenant ID format if provided."""
        if v is None:
            return v
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        if not uuid_pattern.match(v):
            raise ValueError("tenant_id must be a valid UUID")
        return v


class GenerateIacRequest(BaseModel):
    """
    Request to generate Infrastructure-as-Code templates.

    Matches POST /api/v1/generate-iac from OpenAPI spec.
    """

    tenant_id: Optional[str] = Field(None, description="Source tenant ID")
    target_tenant_id: Optional[str] = Field(
        None, description="Cross-tenant deployment target"
    )
    target_subscription: Optional[str] = Field(None, description="Target subscription")
    format: str = Field("terraform", description="IaC format")
    auto_import_existing: bool = Field(
        False, description="Auto-import existing resources"
    )
    import_strategy: Optional[str] = Field(None, description="Import strategy")
    auto_register_providers: bool = Field(False, description="Auto-register providers")
    auto_fix_subnets: bool = Field(False, description="Auto-fix subnet issues")
    skip_subnet_validation: bool = Field(False, description="Skip subnet validation")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate IaC format."""
        valid_formats = ["terraform", "arm", "bicep"]
        if v not in valid_formats:
            raise ValueError(f"format must be one of {valid_formats}, got '{v}'")
        return v

    @field_validator("import_strategy")
    @classmethod
    def validate_import_strategy(cls, v: Optional[str]) -> Optional[str]:
        """Validate import strategy."""
        if v is None:
            return v
        valid_strategies = ["resource_groups", "all_resources"]
        if v not in valid_strategies:
            raise ValueError(
                f"import_strategy must be one of {valid_strategies}, got '{v}'"
            )
        return v


class CreateTenantRequest(BaseModel):
    """
    Request to create tenant from specification.

    Matches POST /api/v1/create-tenant from OpenAPI spec.
    """

    markdown_spec: str = Field(
        ..., description="Tenant specification in markdown format"
    )

    @field_validator("markdown_spec")
    @classmethod
    def validate_markdown_spec(cls, v: str) -> str:
        """Validate markdown spec is not empty."""
        if not v.strip():
            raise ValueError("markdown_spec cannot be empty")
        return v


class VisualizeRequest(BaseModel):
    """
    Request to generate visualization.

    Matches POST /api/v1/visualize from OpenAPI spec.
    """

    link_hierarchy: bool = Field(True, description="Link hierarchy")
    output_path: Optional[str] = Field(None, description="Output path")


class ThreatModelRequest(BaseModel):
    """
    Request to generate threat model.

    Matches POST /api/v1/threat-model from OpenAPI spec.
    """

    options: Dict[str, Any] = Field(
        default_factory=dict, description="Threat modeling options"
    )


class AgentModeRequest(BaseModel):
    """
    Request to execute agent mode query.

    Matches POST /api/v1/agent-mode from OpenAPI spec.
    """

    question: str = Field(..., description="Question to ask the agent")

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Validate question is not empty."""
        if not v.strip():
            raise ValueError("question cannot be empty")
        return v


__all__ = [
    "AgentModeRequest",
    "CreateTenantRequest",
    "GenerateIacRequest",
    "GenerateSpecRequest",
    "ScanRequest",
    "ThreatModelRequest",
    "VisualizeRequest",
]

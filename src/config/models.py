"""
Configuration models for scale operations.

Provides type-safe configuration using pydantic with validation,
defaults, and schema enforcement.
"""

from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScaleStrategy(str, Enum):
    """Available scale-up strategies."""

    TEMPLATE = "template"
    SCENARIO = "scenario"
    RANDOM = "random"


class ScaleDownAlgorithm(str, Enum):
    """Available scale-down algorithms."""

    FOREST_FIRE = "forest-fire"
    MHRW = "mhrw"
    RANDOM_NODE = "random-node"
    RANDOM_EDGE = "random-edge"


class OutputFormat(str, Enum):
    """Output format for scale-down operations."""

    YAML = "yaml"
    JSON = "json"


class TemplateStrategyConfig(BaseModel):
    """Configuration for template-based scaling strategy."""

    preserve_proportions: bool = Field(
        default=True,
        description="Maintain relative proportions of resource types",
    )
    variation_percentage: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.1,
        description="Amount of random variation to introduce (0.0-1.0)",
    )

    model_config = ConfigDict(extra="forbid")  # Reject unknown fields


class ScenarioStrategyConfig(BaseModel):
    """Configuration for scenario-based scaling strategy."""

    default_scenario: str = Field(
        default="hub-spoke",
        description="Default scenario template to use",
    )
    scenario_library_path: Optional[Path] = Field(
        default=None,
        description="Path to custom scenario library directory",
    )

    model_config = ConfigDict(extra="forbid")


class RandomStrategyConfig(BaseModel):
    """Configuration for random scaling strategy."""

    default_target_count: Annotated[int, Field(gt=0)] = Field(
        default=1000,
        description="Default target resource count for random generation",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible generation",
    )

    model_config = ConfigDict(extra="forbid")


class ScaleUpConfig(BaseModel):
    """Configuration for scale-up operations."""

    default_strategy: ScaleStrategy = Field(
        default=ScaleStrategy.TEMPLATE,
        description="Default strategy to use when not specified",
    )
    default_scale_factor: Annotated[float, Field(gt=0.0)] = Field(
        default=2.0,
        description="Default scale factor (multiplier for resource counts)",
    )
    batch_size: Annotated[int, Field(gt=0)] = Field(
        default=500,
        description="Number of resources to process per batch",
    )

    # Strategy-specific configurations
    template: TemplateStrategyConfig = Field(
        default_factory=TemplateStrategyConfig,
        description="Template strategy settings",
    )
    scenario: ScenarioStrategyConfig = Field(
        default_factory=ScenarioStrategyConfig,
        description="Scenario strategy settings",
    )
    random: RandomStrategyConfig = Field(
        default_factory=RandomStrategyConfig,
        description="Random strategy settings",
    )

    @field_validator("default_scale_factor")
    @classmethod
    def validate_scale_factor(cls, v: float) -> float:
        """Validate scale factor is reasonable."""
        if v > 1000.0:
            raise ValueError("Scale factor cannot exceed 1000")
        return v

    model_config = ConfigDict(extra="forbid")


class ForestFireConfig(BaseModel):
    """Configuration for Forest Fire sampling algorithm."""

    burning_probability: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.4,
        description="Probability of 'burning' (selecting) a neighbor node",
    )
    seed: Optional[int] = Field(
        default=42,
        description="Random seed for reproducible sampling",
    )
    directed: bool = Field(
        default=False,
        description="Whether to treat graph as directed",
    )

    model_config = ConfigDict(extra="forbid")


class MHRWConfig(BaseModel):
    """Configuration for Metropolis-Hastings Random Walk algorithm."""

    alpha: Annotated[float, Field(ge=0.0)] = Field(
        default=1.0,
        description="Bias parameter (alpha=1 for unbiased walk)",
    )
    seed: Optional[int] = Field(
        default=42,
        description="Random seed for reproducible sampling",
    )
    max_iterations: Annotated[int, Field(gt=0)] = Field(
        default=1000000,
        description="Maximum walk iterations",
    )

    model_config = ConfigDict(extra="forbid")


class RandomNodeConfig(BaseModel):
    """Configuration for random node sampling."""

    seed: Optional[int] = Field(
        default=42,
        description="Random seed for reproducible sampling",
    )
    preserve_connectivity: bool = Field(
        default=False,
        description="Attempt to preserve graph connectivity",
    )

    model_config = ConfigDict(extra="forbid")


class RandomEdgeConfig(BaseModel):
    """Configuration for random edge sampling."""

    seed: Optional[int] = Field(
        default=42,
        description="Random seed for reproducible sampling",
    )

    model_config = ConfigDict(extra="forbid")


class ScaleDownConfig(BaseModel):
    """Configuration for scale-down operations."""

    default_algorithm: ScaleDownAlgorithm = Field(
        default=ScaleDownAlgorithm.FOREST_FIRE,
        description="Default algorithm to use when not specified",
    )
    default_target_size: Annotated[float, Field(gt=0.0, le=1.0)] = Field(
        default=0.1,
        description="Default target size as fraction of original (0.0-1.0)",
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.YAML,
        description="Output format for scale-down spec",
    )

    # Algorithm-specific configurations
    forest_fire: ForestFireConfig = Field(
        default_factory=ForestFireConfig,
        description="Forest Fire algorithm settings",
    )
    mhrw: MHRWConfig = Field(
        default_factory=MHRWConfig,
        description="Metropolis-Hastings Random Walk settings",
    )
    random_node: RandomNodeConfig = Field(
        default_factory=RandomNodeConfig,
        description="Random node sampling settings",
    )
    random_edge: RandomEdgeConfig = Field(
        default_factory=RandomEdgeConfig,
        description="Random edge sampling settings",
    )

    model_config = ConfigDict(extra="forbid")


class PerformanceConfig(BaseModel):
    """Performance and resource limits configuration."""

    batch_size: Annotated[int, Field(gt=0)] = Field(
        default=500,
        description="Default batch size for operations",
    )
    memory_limit_mb: Annotated[int, Field(gt=0)] = Field(
        default=2048,
        description="Memory limit in megabytes",
    )
    timeout_seconds: Annotated[int, Field(gt=0)] = Field(
        default=300,
        description="Operation timeout in seconds",
    )
    max_workers: Annotated[int, Field(ge=1, le=32)] = Field(
        default=4,
        description="Maximum number of worker threads/processes",
    )

    model_config = ConfigDict(extra="forbid")


class ValidationConfig(BaseModel):
    """Validation settings for scale operations."""

    pre_operation: bool = Field(
        default=True,
        description="Validate configuration before operation",
    )
    post_operation: bool = Field(
        default=True,
        description="Validate results after operation",
    )
    strict_mode: bool = Field(
        default=True,
        description="Fail on validation warnings",
    )

    model_config = ConfigDict(extra="forbid")


class TenantOverrides(BaseModel):
    """Tenant-specific configuration overrides."""

    tenant_id: str = Field(
        description="Azure tenant ID",
    )
    scale_up: Optional[ScaleUpConfig] = Field(
        default=None,
        description="Override scale-up settings for this tenant",
    )
    scale_down: Optional[ScaleDownConfig] = Field(
        default=None,
        description="Override scale-down settings for this tenant",
    )
    performance: Optional[PerformanceConfig] = Field(
        default=None,
        description="Override performance settings for this tenant",
    )

    model_config = ConfigDict(extra="forbid")


class ScaleConfig(BaseModel):
    """Root configuration for scale operations."""

    default_tenant_id: Optional[str] = Field(
        default=None,
        description="Default tenant ID when not specified",
    )

    scale_up: ScaleUpConfig = Field(
        default_factory=ScaleUpConfig,
        description="Scale-up operation settings",
    )
    scale_down: ScaleDownConfig = Field(
        default_factory=ScaleDownConfig,
        description="Scale-down operation settings",
    )
    performance: PerformanceConfig = Field(
        default_factory=PerformanceConfig,
        description="Performance and resource limits",
    )
    validation: ValidationConfig = Field(
        default_factory=ValidationConfig,
        description="Validation settings",
    )

    tenant_overrides: list[TenantOverrides] = Field(
        default_factory=list,
        description="Tenant-specific overrides",
    )

    @model_validator(mode="after")
    def validate_tenant_overrides(self) -> "ScaleConfig":
        """Ensure tenant override IDs are unique."""
        tenant_ids = [override.tenant_id for override in self.tenant_overrides]
        if len(tenant_ids) != len(set(tenant_ids)):
            raise ValueError("Duplicate tenant IDs in tenant_overrides")
        return self

    def get_tenant_config(self, tenant_id: str) -> "ScaleConfig":
        """
        Get effective configuration for a specific tenant.

        Merges tenant-specific overrides with base configuration.
        """
        # Find tenant overrides
        override = next(
            (o for o in self.tenant_overrides if o.tenant_id == tenant_id),
            None,
        )

        if not override:
            return self

        # Create new config with overrides applied
        config_dict = self.model_dump()

        if override.scale_up:
            config_dict["scale_up"].update(
                override.scale_up.model_dump(exclude_unset=True)
            )
        if override.scale_down:
            config_dict["scale_down"].update(
                override.scale_down.model_dump(exclude_unset=True)
            )
        if override.performance:
            config_dict["performance"].update(
                override.performance.model_dump(exclude_unset=True)
            )

        return ScaleConfig.model_validate(config_dict)

    model_config = ConfigDict(extra="forbid")

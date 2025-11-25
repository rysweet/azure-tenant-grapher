"""
Scale-Down Service Package for Azure Tenant Grapher

This package provides comprehensive graph sampling and downscaling capabilities.
It uses a modular architecture with separate components for extraction, sampling,
quality metrics, and export.

Main Components:
- GraphExtractor: Neo4j to NetworkX conversion
- QualityMetrics & QualityMetricsCalculator: Sampling quality assessment
- GraphOperations: Node deletion and motif discovery
- Sampling algorithms: ForestFire, MHRW, RandomWalk, Pattern
- Export formats: YAML, JSON, Neo4j, IaC (Terraform/ARM/Bicep)
- ScaleDownOrchestrator: Main coordinator

Usage:
    >>> from src.services.scale_down import ScaleDownOrchestrator, QualityMetrics
    >>> orchestrator = ScaleDownOrchestrator(session_manager)
    >>> node_ids, metrics, deleted = await orchestrator.sample_graph(
    ...     tenant_id="00000000-0000-0000-0000-000000000000",
    ...     algorithm="forest_fire",
    ...     target_size=0.1,
    ...     output_mode="delete"
    ... )
"""

# Core components
from src.services.scale_down.orchestrator import ScaleDownOrchestrator
from src.services.scale_down.graph_extractor import GraphExtractor
from src.services.scale_down.graph_operations import GraphOperations
from src.services.scale_down.quality_metrics import QualityMetrics, QualityMetricsCalculator

# Samplers
from src.services.scale_down.sampling import (
    BaseSampler,
    ForestFireSampler,
    MHRWSampler,
    RandomWalkSampler,
    PatternSampler,
)

# Exporters
from src.services.scale_down.exporters import (
    BaseExporter,
    YamlExporter,
    JsonExporter,
    Neo4jExporter,
    IaCExporter,
)

__all__ = [
    # Main orchestrator
    "ScaleDownOrchestrator",
    # Core components
    "GraphExtractor",
    "GraphOperations",
    "QualityMetrics",
    "QualityMetricsCalculator",
    # Samplers
    "BaseSampler",
    "ForestFireSampler",
    "MHRWSampler",
    "RandomWalkSampler",
    "PatternSampler",
    # Exporters
    "BaseExporter",
    "YamlExporter",
    "JsonExporter",
    "Neo4jExporter",
    "IaCExporter",
]

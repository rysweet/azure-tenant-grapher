"""
IaC Exporter for Azure Tenant Graph Sampling

This module exports sampled graphs to Infrastructure-as-Code formats
(Terraform, ARM, Bicep) using existing IaC emitters.
"""

import logging
from typing import Any, Dict, Set

import networkx as nx

from src.iac.emitters.arm_emitter import ArmEmitter
from src.iac.emitters.bicep_emitter import BicepEmitter
from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph
from src.services.scale_down.exporters.base_exporter import BaseExporter

logger = logging.getLogger(__name__)


class IaCExporter(BaseExporter):
    """
    Export sampled graph to IaC format (Terraform, ARM, or Bicep).

    This exporter uses the existing IaC emitters to generate templates
    from the sampled graph, enabling deployment of scaled-down environments.
    """

    def __init__(self, iac_format: str) -> None:
        """
        Initialize the IaC exporter.

        Args:
            iac_format: IaC format (terraform, arm, bicep)

        Raises:
            ValueError: If iac_format is invalid
        """
        self.logger = logging.getLogger(__name__)

        if iac_format not in ["terraform", "arm", "bicep"]:
            raise ValueError(
                f"Invalid IaC format: {iac_format}. "
                f"Must be one of: terraform, arm, bicep"
            )

        self.iac_format = iac_format

        # Initialize appropriate emitter
        if iac_format == "terraform":
            self.emitter = TerraformEmitter()
        elif iac_format == "arm":
            self.emitter = ArmEmitter()
        elif iac_format == "bicep":
            self.emitter = BicepEmitter()

    async def export(
        self,
        node_ids: Set[str],
        node_properties: Dict[str, Dict[str, Any]],
        sampled_graph: nx.DiGraph[str],
        output_path: str,
    ) -> None:
        """
        Export sample to IaC format (Terraform, ARM, or Bicep).

        Uses the existing IaC emitters to generate templates from the sampled graph.

        Args:
            node_ids: Set of sampled node IDs
            node_properties: Properties for all nodes
            sampled_graph: NetworkX graph of sample
            output_path: Output file or directory path

        Raises:
            ValueError: If export fails
            Exception: If unexpected error occurs

        Example:
            >>> exporter = IaCExporter("terraform")
            >>> await exporter.export(
            ...     sampled_ids,
            ...     node_props,
            ...     G_sampled,
            ...     "/tmp/iac_output"
            ... )
        """
        self.logger.info(f"Exporting sample to {self.iac_format} IaC at {output_path}")

        # Build TenantGraph from sampled data
        resources = []
        for node_id in node_ids:
            if node_id in node_properties:
                resources.append(node_properties[node_id])

        relationships = []
        for source, target, data in sampled_graph.edges(data=True):
            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "type": data.get("relationship_type", "UNKNOWN"),
                }
            )

        tenant_graph = TenantGraph(resources=resources, relationships=relationships)

        # Generate IaC templates using appropriate emitter
        await self.emitter.emit_template(tenant_graph, output_path)

        self.logger.info(f"IaC export completed ({self.iac_format}): {output_path}")

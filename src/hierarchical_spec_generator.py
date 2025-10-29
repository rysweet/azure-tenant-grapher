"""Hierarchical specification generator for Azure Tenant Grapher.

This module extends the base TenantSpecificationGenerator to organize resources
by Azure's containment hierarchy: Tenant → Subscriptions → Regions → Resource Groups → Resources.

Includes purpose inference at each level.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.config_manager import SpecificationConfig
from src.tenant_spec_generator import ResourceAnonymizer, TenantSpecificationGenerator

logger = logging.getLogger(__name__)


class HierarchicalSpecGenerator(TenantSpecificationGenerator):
    """Generates hierarchically organized tenant specifications with purpose inference."""

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        anonymizer: ResourceAnonymizer,
        config: SpecificationConfig,
    ):
        """Initialize the hierarchical specification generator.

        Args:
            neo4j_uri: URI for Neo4j database connection
            neo4j_user: Username for Neo4j authentication
            neo4j_password: Password for Neo4j authentication
            anonymizer: ResourceAnonymizer instance for anonymizing sensitive data
            config: SpecificationConfig with generation settings
        """
        super().__init__(neo4j_uri, neo4j_user, neo4j_password, anonymizer, config)
        self.hierarchy_depth = getattr(
            config, "hierarchy_depth", 5
        )  # Default to full depth
        self.infer_purpose = getattr(
            config, "infer_purpose", True
        )  # Default to inferring purpose

    def _query_resources_with_hierarchy(self) -> Dict[str, Any]:
        """Query resources while preserving hierarchy metadata.

        Returns:
            Dictionary with hierarchical structure of resources
        """
        import json

        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )

        # Query to get resources with hierarchy information
        query = """
        MATCH (r)
        WHERE r.id IS NOT NULL AND r.type IS NOT NULL
        RETURN r,
               r.subscription_id as subscription_id,
               r.resource_group as resource_group,
               r.location as location,
               r.type as resource_type,
               r.name as resource_name,
               r.tags as tags,
               r.properties as properties,
               r.llm_description as llm_description
        """

        if self.config.resource_limit:
            query += f" LIMIT {self.config.resource_limit}"

        hierarchy = {
            "tenant": {
                "name": "Azure Tenant",
                "purpose": "",
                "subscriptions": defaultdict(
                    lambda: {
                        "name": "",
                        "purpose": "",
                        "regions": defaultdict(
                            lambda: {
                                "name": "",
                                "resource_groups": defaultdict(
                                    lambda: {"name": "", "purpose": "", "resources": []}
                                ),
                            }
                        ),
                    }
                ),
            }
        }

        with driver.session() as session:
            for record in session.run(query):
                node = record["r"]
                resource = dict(node)

                # Parse JSON fields
                for key in ("properties", "tags"):
                    if key in resource and isinstance(resource[key], str):
                        try:
                            resource[key] = json.loads(resource[key])
                        except Exception:
                            resource[key] = {}

                # Extract hierarchy information
                subscription_id = record["subscription_id"] or "unknown-subscription"
                resource_group = record["resource_group"] or "unknown-resource-group"
                location = record["location"] or "unknown-region"

                # Place resource in hierarchy
                subscription = hierarchy["tenant"]["subscriptions"][subscription_id]
                if not subscription["name"]:
                    subscription["name"] = subscription_id

                region = subscription["regions"][location]
                if not region["name"]:
                    region["name"] = location

                rg = region["resource_groups"][resource_group]
                if not rg["name"]:
                    rg["name"] = resource_group

                rg["resources"].append(resource)

        driver.close()

        # Query and attach relationships
        relationships = self._query_relationships()
        rel_map = defaultdict(list)
        for rel in relationships:
            rel_map[rel["source_id"]].append(rel)

        # Attach relationships to resources
        for sub_data in hierarchy["tenant"]["subscriptions"].values():
            for region_data in sub_data["regions"].values():
                for rg_data in region_data["resource_groups"].values():
                    for resource in rg_data["resources"]:
                        resource["relationships"] = rel_map.get(resource.get("id"), [])

        return hierarchy

    def _infer_tenant_purpose(self, hierarchy: Dict[str, Any]) -> str:
        """Infer the overall purpose of the tenant based on resources.

        Args:
            hierarchy: Hierarchical structure of tenant resources

        Returns:
            Inferred purpose string
        """
        resource_types = defaultdict(int)
        naming_patterns = []
        tags_analysis = defaultdict(int)

        # Collect data from all resources
        for sub_data in hierarchy["tenant"]["subscriptions"].values():
            for region_data in sub_data["regions"].values():
                for rg_data in region_data["resource_groups"].values():
                    for resource in rg_data["resources"]:
                        # Count resource types
                        resource_type = resource.get("type", "")
                        if resource_type:
                            resource_types[resource_type] += 1

                        # Collect naming patterns
                        name = resource.get("name", "")
                        if name:
                            naming_patterns.append(name.lower())

                        # Analyze tags
                        tags = resource.get("tags", {})
                        for key, value in tags.items():
                            if key.lower() in ["environment", "env", "stage"]:
                                tags_analysis[value.lower()] += 1

        # Infer purpose based on collected data
        purposes = []

        # Check for development/test environment
        dev_keywords = ["dev", "test", "qa", "staging", "sandbox"]
        if any(env in tags_analysis for env in dev_keywords):
            purposes.append("Development/Testing Environment")
        elif "production" in tags_analysis or "prod" in tags_analysis:
            purposes.append("Production Environment")

        # Check for specific workload types
        if resource_types.get("Microsoft.Web/sites", 0) > 5:
            purposes.append("Web Application Hosting")
        if resource_types.get("Microsoft.ContainerService/managedClusters", 0) > 0:
            purposes.append("Container Orchestration (AKS)")
        if resource_types.get("Microsoft.Sql/servers", 0) > 2:
            purposes.append("Database Infrastructure")
        if resource_types.get("Microsoft.MachineLearningServices/workspaces", 0) > 0:
            purposes.append("Machine Learning/AI Workloads")

        # Check naming patterns
        if any(
            "data" in pattern or "analytics" in pattern for pattern in naming_patterns
        ):
            purposes.append("Data Analytics Platform")
        if any("api" in pattern for pattern in naming_patterns):
            purposes.append("API Services")

        return " | ".join(purposes) if purposes else "General Purpose Infrastructure"

    def _infer_subscription_purpose(self, subscription_data: Dict[str, Any]) -> str:
        """Infer the purpose of a subscription based on its resources.

        Args:
            subscription_data: Subscription data including regions and resources

        Returns:
            Inferred purpose string
        """
        resource_count = 0
        resource_types = set()
        regions = list(subscription_data["regions"].keys())

        for region_data in subscription_data["regions"].values():
            for rg_data in region_data["resource_groups"].values():
                resource_count += len(rg_data["resources"])
                for resource in rg_data["resources"]:
                    resource_types.add(resource.get("type", ""))

        # Infer based on patterns
        if resource_count == 0:
            return "Empty/Unused Subscription"
        elif resource_count < 10:
            return "Minimal Infrastructure"
        elif len(regions) > 3:
            return "Multi-Region Deployment"
        elif "Microsoft.DevTestLab" in resource_types:
            return "Dev/Test Environment"
        else:
            return "Standard Workload Subscription"

    def _infer_resource_group_purpose(self, rg_data: Dict[str, Any]) -> str:
        """Infer the purpose of a resource group based on its resources.

        Args:
            rg_data: Resource group data including resources

        Returns:
            Inferred purpose string
        """
        resources = rg_data["resources"]
        if not resources:
            return "Empty Resource Group"

        # Analyze resource composition
        resource_types = [r.get("type", "") for r in resources]

        # Common patterns
        if any("Microsoft.Web" in t for t in resource_types):
            if any("Microsoft.Sql" in t for t in resource_types):
                return "Web Application with Database"
            return "Web Application Resources"
        elif any("Microsoft.Compute/virtualMachines" in t for t in resource_types):
            vm_count = sum(1 for t in resource_types if "virtualMachines" in t)
            if vm_count > 3:
                return "Virtual Machine Scale Set"
            return "Virtual Machine Infrastructure"
        elif any("Microsoft.Storage" in t for t in resource_types):
            return "Storage Resources"
        elif any("Microsoft.Network" in t for t in resource_types):
            return "Networking Infrastructure"

        return "Mixed Resources"

    def generate_specification(
        self, output_path: Optional[str] = None, domain_name: Optional[str] = None
    ) -> str:
        """Generate hierarchical specification with purpose inference.

        Args:
            output_path: Optional path for output file
            domain_name: Optional domain name for user accounts

        Returns:
            Path to generated specification file
        """
        # Query resources with hierarchy preserved
        hierarchy = self._query_resources_with_hierarchy()

        # Infer purposes at each level
        if self.infer_purpose:
            hierarchy["tenant"]["purpose"] = self._infer_tenant_purpose(hierarchy)

            for sub_id, sub_data in hierarchy["tenant"]["subscriptions"].items():
                sub_data["purpose"] = self._infer_subscription_purpose(sub_data)

                for region_id, region_data in sub_data["regions"].items():
                    for rg_id, rg_data in region_data["resource_groups"].items():
                        rg_data["purpose"] = self._infer_resource_group_purpose(rg_data)

        # Anonymize the entire hierarchy
        anonymized_hierarchy = self._anonymize_hierarchy(hierarchy, domain_name)

        # Render hierarchical markdown
        markdown = self._render_hierarchical_markdown(anonymized_hierarchy)

        # Write to file
        if not output_path:
            output_path = self._get_default_output_path()

        import os

        output_dir = os.path.dirname(output_path)
        if output_dir and output_dir != "." and output_dir != os.getcwd():
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)

        logger.info(f"Hierarchical specification written to {output_path}")
        return output_path

    def _anonymize_hierarchy(
        self, hierarchy: Dict[str, Any], domain_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Anonymize the entire hierarchical structure.

        Args:
            hierarchy: Original hierarchy with sensitive data
            domain_name: Optional domain name for user accounts

        Returns:
            Anonymized hierarchy
        """
        anonymized = {
            "tenant": {
                "name": "Azure Tenant",
                "purpose": hierarchy["tenant"]["purpose"],
                "subscriptions": {},
            }
        }

        for sub_id, sub_data in hierarchy["tenant"]["subscriptions"].items():
            anon_sub_id = f"subscription-{hash(sub_id) % 10000:04d}"
            anonymized["tenant"]["subscriptions"][anon_sub_id] = {
                "name": anon_sub_id,
                "purpose": sub_data["purpose"],
                "regions": {},
            }

            for region_id, region_data in sub_data["regions"].items():
                anonymized["tenant"]["subscriptions"][anon_sub_id]["regions"][
                    region_id
                ] = {
                    "name": region_id,  # Regions are not sensitive
                    "resource_groups": {},
                }

                for rg_id, rg_data in region_data["resource_groups"].items():
                    anon_rg_id = f"rg-{hash(rg_id) % 10000:04d}"
                    anon_region = anonymized["tenant"]["subscriptions"][anon_sub_id][
                        "regions"
                    ][region_id]
                    anon_region["resource_groups"][anon_rg_id] = {
                        "name": anon_rg_id,
                        "purpose": rg_data["purpose"],
                        "resources": [],
                    }

                    # Anonymize resources
                    for resource in rg_data["resources"]:
                        anon_resource = self.anonymizer.anonymize_resource(resource)

                        # Handle domain name for user accounts
                        if domain_name and anon_resource.get("type", "").lower() in (
                            "user",
                            "aaduser",
                            "microsoft.aad/user",
                        ):
                            base_name = anon_resource.get("name", "user").split("@")[0]
                            anon_resource["userPrincipalName"] = (
                                f"{base_name}@{domain_name}"
                            )
                            anon_resource["email"] = f"{base_name}@{domain_name}"

                        # Anonymize relationships
                        anon_resource["relationships"] = [
                            self.anonymizer.anonymize_relationship(rel)
                            for rel in resource.get("relationships", [])
                        ]

                        anon_region["resource_groups"][anon_rg_id]["resources"].append(
                            anon_resource
                        )

        return anonymized

    def _render_hierarchical_markdown(self, hierarchy: Dict[str, Any]) -> str:
        """Render the hierarchical structure as markdown.

        Args:
            hierarchy: Anonymized hierarchical structure

        Returns:
            Markdown string
        """

        lines = []
        lines.append(
            "# Azure Tenant Infrastructure Specification (Hierarchical View)\n"
        )
        lines.append(
            f"_Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}_\n"
        )

        # Tenant level
        tenant = hierarchy["tenant"]
        lines.append("## 🏢 Tenant Overview\n")
        if tenant["purpose"]:
            lines.append(f"**Purpose:** {tenant['purpose']}\n")

        subscription_count = len(tenant["subscriptions"])
        total_resources = sum(
            len(rg_data["resources"])
            for sub_data in tenant["subscriptions"].values()
            for region_data in sub_data["regions"].values()
            for rg_data in region_data["resource_groups"].values()
        )

        lines.append(f"- **Subscriptions:** {subscription_count}")
        lines.append(f"- **Total Resources:** {total_resources}\n")

        # Subscription level
        for sub_id, sub_data in tenant["subscriptions"].items():
            lines.append(f"### 📁 Subscription: {sub_id}\n")
            if sub_data["purpose"]:
                lines.append(f"**Purpose:** {sub_data['purpose']}\n")

            region_count = len(sub_data["regions"])
            sub_resources = sum(
                len(rg_data["resources"])
                for region_data in sub_data["regions"].values()
                for rg_data in region_data["resource_groups"].values()
            )

            lines.append(f"- **Regions:** {region_count}")
            lines.append(f"- **Resources:** {sub_resources}\n")

            # Region level
            for region_id, region_data in sub_data["regions"].items():
                lines.append(f"#### 🌍 Region: {region_id}\n")

                rg_count = len(region_data["resource_groups"])
                region_resources = sum(
                    len(rg_data["resources"])
                    for rg_data in region_data["resource_groups"].values()
                )

                lines.append(f"- **Resource Groups:** {rg_count}")
                lines.append(f"- **Resources:** {region_resources}\n")

                # Resource Group level
                for rg_id, rg_data in region_data["resource_groups"].items():
                    lines.append(f"##### 📦 Resource Group: {rg_id}\n")
                    if rg_data["purpose"]:
                        lines.append(f"**Purpose:** {rg_data['purpose']}\n")

                    lines.append(f"- **Resource Count:** {len(rg_data['resources'])}\n")

                    # Resources
                    if rg_data["resources"]:
                        lines.append("###### Resources:\n")

                        # Group resources by type for better readability
                        resources_by_type = defaultdict(list)
                        for resource in rg_data["resources"]:
                            resources_by_type[resource.get("type", "Unknown")].append(
                                resource
                            )

                        for resource_type, resources in sorted(
                            resources_by_type.items()
                        ):
                            lines.append(
                                f"**{resource_type}** ({len(resources)} items)\n"
                            )

                            for resource in resources:
                                lines.append(f"- **{resource['name']}**")

                                if self.config.include_ai_summaries and resource.get(
                                    "llm_description"
                                ):
                                    lines.append(f"  > {resource['llm_description']}")

                                if self.config.include_configuration_details:
                                    if resource.get("properties"):
                                        lines.append("  - Properties:")
                                        for k, v in list(
                                            resource["properties"].items()
                                        )[:5]:  # Limit to 5 properties
                                            lines.append(f"    - {k}: {v}")

                                    if resource.get("tags"):
                                        lines.append("  - Tags:")
                                        for k, v in resource["tags"].items():
                                            lines.append(f"    - {k}: {v}")

                                if resource.get("relationships"):
                                    lines.append("  - Relationships:")
                                    for rel in resource["relationships"][
                                        :5
                                    ]:  # Limit to 5 relationships
                                        lines.append(
                                            f"    - {rel['type']} → {rel['target_id']}"
                                        )
                            lines.append("")

        return "\n".join(lines)

"""
Well-Architected Framework Reporter

This module generates comprehensive Well-Architected Framework (WAF) reports
for Azure environments, including pattern analysis and LLM-enhanced descriptions.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from neo4j import Driver

from src.architectural_pattern_analyzer import ArchitecturalPatternAnalyzer

logger = logging.getLogger(__name__)


class WellArchitectedReporter:
    """Generates Well-Architected Framework reports with pattern insights."""

    # Mapping of patterns to Azure Well-Architected Framework pillars and links
    WAF_PATTERN_MAPPING = {
        "Web Application": {
            "pillars": ["Reliability", "Performance Efficiency", "Cost Optimization"],
            "waf_url": "https://learn.microsoft.com/en-us/azure/well-architected/service-guides/app-service-web-apps",
            "description": "App Service provides built-in auto-scaling, load balancing, and deployment slots for high availability.",
            "recommendations": [
                "Enable auto-scaling based on metrics",
                "Use deployment slots for zero-downtime deployments",
                "Implement Application Insights for monitoring",
                "Configure backup and disaster recovery",
            ],
        },
        "Virtual Machine Workload": {
            "pillars": ["Reliability", "Security", "Operational Excellence"],
            "waf_url": "https://learn.microsoft.com/en-us/azure/well-architected/service-guides/virtual-machines",
            "description": "Virtual machines require careful configuration for availability, security, and cost management.",
            "recommendations": [
                "Use availability sets or availability zones",
                "Implement Azure Backup",
                "Enable disk encryption",
                "Use managed disks for better reliability",
                "Right-size VMs based on actual usage",
            ],
        },
        "Container Platform": {
            "pillars": ["Reliability", "Performance Efficiency", "Security"],
            "waf_url": "https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-kubernetes-service",
            "description": "AKS provides managed Kubernetes with built-in security, monitoring, and scaling capabilities.",
            "recommendations": [
                "Enable cluster autoscaling",
                "Use Azure AD integration for RBAC",
                "Implement network policies",
                "Enable Container Insights for monitoring",
                "Use Azure Policy for governance",
            ],
        },
        "Data Platform": {
            "pillars": ["Security", "Reliability", "Performance Efficiency"],
            "waf_url": "https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-sql-database",
            "description": "Database services should leverage private endpoints, encryption, and high availability features.",
            "recommendations": [
                "Enable private endpoints for secure connectivity",
                "Use geo-replication for disaster recovery",
                "Implement transparent data encryption",
                "Enable Advanced Threat Protection",
                "Configure automated backups",
            ],
        },
        "Serverless Application": {
            "pillars": [
                "Cost Optimization",
                "Performance Efficiency",
                "Operational Excellence",
            ],
            "waf_url": "https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-functions",
            "description": "Function Apps provide automatic scaling and pay-per-execution pricing model.",
            "recommendations": [
                "Use Consumption or Premium plans appropriately",
                "Implement durable functions for stateful workflows",
                "Store secrets in Key Vault",
                "Enable Application Insights",
                "Use managed identities for authentication",
            ],
        },
        "Data Analytics": {
            "pillars": [
                "Performance Efficiency",
                "Cost Optimization",
                "Operational Excellence",
            ],
            "waf_url": "https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-data-explorer",
            "description": "Analytics platforms should optimize for query performance and cost-effective data storage.",
            "recommendations": [
                "Implement data retention policies",
                "Use partitioning for large datasets",
                "Enable caching for frequently accessed data",
                "Monitor query performance",
                "Implement cost controls and budgets",
            ],
        },
        "Secure Workload": {
            "pillars": ["Security", "Reliability"],
            "waf_url": "https://learn.microsoft.com/en-us/azure/well-architected/security/",
            "description": "Security-focused architectures leverage Key Vault, Private Link, and network isolation.",
            "recommendations": [
                "Use Key Vault for all secrets and keys",
                "Implement Private Link for all services",
                "Enable Azure Private DNS zones",
                "Use managed identities to eliminate credentials",
                "Implement network security groups and firewalls",
            ],
        },
        "Managed Identity Pattern": {
            "pillars": ["Security", "Operational Excellence"],
            "waf_url": "https://learn.microsoft.com/en-us/azure/well-architected/security/design-identity-authentication",
            "description": "Managed identities eliminate the need for credentials in code and improve security posture.",
            "recommendations": [
                "Use system-assigned identities when possible",
                "Grant least-privilege permissions",
                "Use user-assigned identities for shared access",
                "Audit managed identity usage",
                "Implement conditional access policies",
            ],
        },
        "Monitoring & Observability": {
            "pillars": ["Operational Excellence", "Reliability"],
            "waf_url": "https://learn.microsoft.com/en-us/azure/well-architected/observability/",
            "description": "Comprehensive monitoring enables proactive issue detection and performance optimization.",
            "recommendations": [
                "Centralize logs in Log Analytics",
                "Implement distributed tracing",
                "Configure smart detection and alerts",
                "Use workbooks for visualization",
                "Implement custom metrics for business KPIs",
            ],
        },
        "Network Security": {
            "pillars": ["Security", "Reliability"],
            "waf_url": "https://learn.microsoft.com/en-us/azure/well-architected/security/design-network",
            "description": "Network security requires defense-in-depth with multiple layers of protection.",
            "recommendations": [
                "Implement network segmentation with subnets",
                "Use NSGs and Azure Firewall",
                "Enable DDoS Protection Standard",
                "Implement Azure Bastion for secure access",
                "Use Private Link to eliminate public endpoints",
            ],
        },
    }

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        openai_api_key: Optional[str] = None,
    ):
        """
        Initialize the Well-Architected Reporter.

        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            openai_api_key: OpenAI API key for LLM descriptions (optional)
        """
        self.analyzer = ArchitecturalPatternAnalyzer(
            neo4j_uri, neo4j_user, neo4j_password
        )
        self.openai_api_key = openai_api_key
        self.driver: Optional[Driver] = None

    def connect(self) -> None:
        """Connect to Neo4j database."""
        self.analyzer.connect()
        self.driver = self.analyzer.driver

    def close(self) -> None:
        """Close Neo4j connection."""
        self.analyzer.close()

    def generate_waf_insights(
        self, pattern_matches: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate Well-Architected Framework insights for detected patterns.

        Args:
            pattern_matches: Dictionary of detected patterns

        Returns:
            Dictionary mapping pattern names to WAF insights
        """
        waf_insights = {}

        for pattern_name, match_data in pattern_matches.items():
            if pattern_name in self.WAF_PATTERN_MAPPING:
                waf_info = self.WAF_PATTERN_MAPPING[pattern_name]

                waf_insights[pattern_name] = {
                    "pattern_data": match_data,
                    "waf_pillars": waf_info["pillars"],
                    "waf_url": waf_info["waf_url"],
                    "description": waf_info["description"],
                    "recommendations": waf_info["recommendations"],
                    "completeness": match_data["completeness"],
                    "matched_resources": match_data["matched_resources"],
                    "missing_resources": match_data["missing_resources"],
                    "connection_count": match_data["connection_count"],
                }

        return waf_insights

    def update_resource_descriptions_with_waf(
        self, waf_insights: Dict[str, Dict[str, Any]]
    ) -> int:
        """
        Update resource LLM descriptions in Neo4j with WAF insights.

        Args:
            waf_insights: WAF insights for patterns

        Returns:
            Number of resources updated
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")

        updated_count = 0

        with self.driver.session() as session:
            for pattern_name, insights in waf_insights.items():
                waf_url = insights["waf_url"]
                pillars = ", ".join(insights["waf_pillars"])
                recommendations = insights["recommendations"]

                # Get resource type names from matched resources
                for resource_type in insights["matched_resources"]:
                    # Find all resources of this type
                    query = """
                    MATCH (r:Resource)
                    WHERE r.type ENDS WITH $resource_type
                    RETURN r.id AS id, r.type AS type, r.llm_description AS current_desc
                    LIMIT 100
                    """

                    result = session.run(query, resource_type=resource_type)
                    resources = list(result)

                    for record in resources:
                        resource_id = record["id"]
                        current_desc = record.get("current_desc", "")

                        # Build enhanced description
                        waf_insight = (
                            f"\n\n🏗️ **Architectural Pattern**: {pattern_name}\n"
                            f"**WAF Pillars**: {pillars}\n"
                            f"**Completeness**: {insights['completeness']:.0f}%\n"
                            f"**Learn More**: {waf_url}\n\n"
                            f"**Recommendations**:\n"
                        )

                        for i, rec in enumerate(recommendations[:3], 1):
                            waf_insight += f"{i}. {rec}\n"

                        # Append to existing description or create new
                        enhanced_desc = (
                            current_desc + waf_insight if current_desc else waf_insight
                        )

                        # Update in Neo4j
                        update_query = """
                        MATCH (r:Resource {id: $resource_id})
                        SET r.llm_description = $description,
                            r.waf_pattern = $pattern_name,
                            r.waf_pillars = $pillars,
                            r.waf_url = $waf_url,
                            r.waf_updated_at = datetime()
                        RETURN r.id AS id
                        """

                        session.run(
                            update_query,
                            resource_id=resource_id,
                            description=enhanced_desc,
                            pattern_name=pattern_name,
                            pillars=pillars,
                            waf_url=waf_url,
                        )

                        updated_count += 1

        logger.info(f"Updated {updated_count} resources with WAF insights")
        return updated_count

    def generate_markdown_report(
        self, waf_insights: Dict[str, Dict[str, Any]], output_path: Path
    ) -> None:
        """
        Generate a markdown report of Well-Architected Framework insights.

        Args:
            waf_insights: WAF insights for patterns
            output_path: Path to output markdown file
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = f"""# Azure Well-Architected Framework Analysis Report

**Generated**: {timestamp}

## Executive Summary

This report analyzes your Azure environment against the Well-Architected Framework,
identifying architectural patterns and providing actionable recommendations.

**Patterns Detected**: {len(waf_insights)}

---

"""

        # Sort patterns by completeness
        sorted_patterns = sorted(
            waf_insights.items(), key=lambda x: x[1]["completeness"], reverse=True
        )

        for pattern_name, insights in sorted_patterns:
            completeness = insights["completeness"]
            matched = len(insights["matched_resources"])
            missing = len(insights["missing_resources"])
            connections = insights["connection_count"]

            report += f"""## {pattern_name}

**Completeness**: {completeness:.0f}% ({matched} of {matched + missing} resource types)
**Connections**: {connections:,} relationships

### Well-Architected Framework Pillars

{", ".join(f"**{p}**" for p in insights["waf_pillars"])}

### Description

{insights["description"]}

### Resources in This Pattern

**Present**: {", ".join(f"`{r}`" for r in insights["matched_resources"])}
"""

            if insights["missing_resources"]:
                report += f"""
**Missing**: {", ".join(f"`{r}`" for r in insights["missing_resources"])}
"""

            report += """
### Recommendations

"""
            for i, rec in enumerate(insights["recommendations"], 1):
                report += f"{i}. {rec}\n"

            report += f"""
### Learn More

📚 [Azure Well-Architected Framework: {pattern_name}]({insights["waf_url"]})

---

"""

        # Add footer
        report += """
## Next Steps

1. Review the recommendations for each pattern
2. Prioritize based on completeness and business impact
3. Implement improvements incrementally
4. Re-run this analysis to track progress

## Resources

- [Azure Well-Architected Framework Overview](https://learn.microsoft.com/en-us/azure/well-architected/)
- [Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/)
- [Well-Architected Review Tool](https://learn.microsoft.com/en-us/assessments/)

---

*Generated by Azure Tenant Grapher - Well-Architected Reporter*
"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        logger.info(f"Markdown report written to {output_path}")

    def generate_notebook_report(
        self, waf_insights: Dict[str, Dict[str, Any]], output_path: Path
    ) -> None:
        """
        Generate a Jupyter notebook with interactive WAF analysis.

        Args:
            waf_insights: WAF insights for patterns
            output_path: Path to output notebook file
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build notebook structure
        notebook: Dict[str, Any] = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "# Azure Well-Architected Framework Analysis\n",
                        "\n",
                        f"**Generated**: {timestamp}\n",
                        "\n",
                        "This notebook provides an interactive analysis of your Azure environment\n",
                        "against the Well-Architected Framework.\n",
                    ],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "import pandas as pd\n",
                        "import json\n",
                        "from IPython.display import display, Markdown, HTML\n",
                    ],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# WAF Insights Data\n",
                        f"waf_insights = {json.dumps(waf_insights, indent=2)}\n",
                    ],
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["## Pattern Summary\n"],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# Create summary DataFrame\n",
                        "summary_data = []\n",
                        "for pattern_name, insights in waf_insights.items():\n",
                        "    summary_data.append({\n",
                        "        'Pattern': pattern_name,\n",
                        "        'Completeness': f\"{insights['completeness']:.0f}%\",\n",
                        "        'Matched Resources': len(insights['matched_resources']),\n",
                        "        'Missing Resources': len(insights['missing_resources']),\n",
                        "        'Connections': insights['connection_count'],\n",
                        "        'WAF Pillars': ', '.join(insights['waf_pillars'])\n",
                        "    })\n",
                        "\n",
                        "df_summary = pd.DataFrame(summary_data)\n",
                        "df_summary = df_summary.sort_values('Completeness', ascending=False)\n",
                        "display(df_summary)\n",
                    ],
                },
            ],
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                },
                "language_info": {
                    "codemirror_mode": {"name": "ipython", "version": 3},
                    "file_extension": ".py",
                    "mimetype": "text/x-python",
                    "name": "python",
                    "nbconvert_exporter": "python",
                    "pygments_lexer": "ipython3",
                    "version": "3.12.0",
                },
            },
            "nbformat": 4,
            "nbformat_minor": 4,
        }

        # Add pattern details
        for pattern_name, insights in sorted(
            waf_insights.items(), key=lambda x: x[1]["completeness"], reverse=True
        ):
            # Markdown cell for pattern
            notebook["cells"].append(
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        f"## {pattern_name}\n",
                        "\n",
                        f"**Completeness**: {insights['completeness']:.0f}%  \n",
                        f"**WAF Pillars**: {', '.join(insights['waf_pillars'])}  \n",
                        f"**Learn More**: [{pattern_name} Guide]({insights['waf_url']})\n",
                        "\n",
                        f"{insights['description']}\n",
                    ],
                }
            )

            # Code cell for recommendations
            recs_list = '", "'.join(insights["recommendations"])
            notebook["cells"].append(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        f"# Recommendations for {pattern_name}\n",
                        f'recommendations = ["{recs_list}"]\n',
                        "\n",
                        "for i, rec in enumerate(recommendations, 1):\n",
                        '    print(f"{i}. {rec}")\n',
                    ],
                }
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(notebook, f, indent=2)

        logger.info(f"Notebook report written to {output_path}")

    def generate_full_report(
        self,
        output_dir: Path,
        update_descriptions: bool = True,
        generate_visualizations: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a complete Well-Architected Framework report.

        Args:
            output_dir: Directory to save all report outputs
            update_descriptions: Whether to update resource descriptions in Neo4j
            generate_visualizations: Whether to generate visualizations

        Returns:
            Dictionary with report summary and file paths
        """
        self.connect()

        try:
            logger.info("Starting Well-Architected Framework analysis...")

            # Run pattern analysis
            all_relationships = self.analyzer.fetch_all_relationships()
            aggregated_relationships = self.analyzer.aggregate_relationships(
                all_relationships
            )
            graph, resource_type_counts, edge_counts = (
                self.analyzer.build_networkx_graph(aggregated_relationships)
            )
            pattern_matches = self.analyzer.detect_patterns(graph, resource_type_counts)

            # Generate WAF insights
            waf_insights = self.generate_waf_insights(pattern_matches)

            # Update resource descriptions if requested
            updated_count = 0
            if update_descriptions:
                logger.info("Updating resource descriptions with WAF insights...")
                updated_count = self.update_resource_descriptions_with_waf(waf_insights)

            # Generate reports
            output_dir.mkdir(parents=True, exist_ok=True)

            markdown_path = output_dir / "well_architected_report.md"
            self.generate_markdown_report(waf_insights, markdown_path)

            notebook_path = output_dir / "well_architected_analysis.ipynb"
            self.generate_notebook_report(waf_insights, notebook_path)

            # Generate JSON export
            json_path = output_dir / "well_architected_insights.json"
            with open(json_path, "w") as f:
                json.dump(waf_insights, f, indent=2)

            # Generate visualizations if requested
            viz_files = []
            if generate_visualizations:
                logger.info("Generating visualizations...")
                viz_files = self.analyzer.generate_visualizations(
                    graph,
                    resource_type_counts,
                    edge_counts,
                    pattern_matches,
                    output_dir,
                )

            summary = {
                "timestamp": datetime.now().isoformat(),
                "patterns_detected": len(waf_insights),
                "total_relationships": len(all_relationships),
                "resources_updated": updated_count,
                "output_files": {
                    "markdown": str(markdown_path),
                    "notebook": str(notebook_path),
                    "json": str(json_path),
                    "visualizations": [str(f) for f in viz_files],
                },
            }

            # Save summary
            summary_path = output_dir / "report_summary.json"
            with open(summary_path, "w") as f:
                json.dump(summary, f, indent=2)

            logger.info(f"Report generation complete: {output_dir}")
            return summary

        finally:
            self.close()

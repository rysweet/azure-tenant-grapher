"""
LLM Description Generator for Azure Tenant Grapher

This module provides LLM-powered natural language descriptions for Azure resources
and relationships using Azure OpenAI services.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Configuration for Azure OpenAI LLM services."""

    endpoint: str
    api_key: str
    api_version: str
    model_chat: str
    model_reasoning: str

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create LLM configuration from environment variables."""
        return cls(
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.getenv("AZURE_OPENAI_KEY", ""),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-16"),
            model_chat=os.getenv("AZURE_OPENAI_MODEL_CHAT", "gpt-4"),
            model_reasoning=os.getenv("AZURE_OPENAI_MODEL_REASONING", "gpt-4"),
        )

    def is_valid(self) -> bool:
        """Check if the configuration is valid."""
        return bool(self.endpoint and self.api_key)


class AzureLLMDescriptionGenerator:
    """
    Generates natural language descriptions for Azure resources and relationships
    using Azure OpenAI services.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize the LLM description generator.

        Args:
            config: LLM configuration, defaults to environment variables
        """
        self.config = config or LLMConfig.from_env()

        if not self.config.is_valid():
            raise ValueError(
                "Invalid LLM configuration. Please check your environment variables."
            )

        # Extract base URL from full endpoint
        self.base_url = self._extract_base_url(self.config.endpoint)

        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            azure_endpoint=self.base_url,
            api_key=self.config.api_key,
            api_version=self.config.api_version,
        )

        logger.info(
            f"Initialized Azure LLM Description Generator with endpoint: {self.base_url}"
        )

    def _extract_base_url(self, endpoint: str) -> str:
        """Extract base URL from the full endpoint URL."""
        if "/openai/deployments/" in endpoint:
            # Extract base URL before /openai/deployments/
            return endpoint.split("/openai/deployments/")[0]
        return endpoint

    async def generate_resource_description(self, resource_data: Dict[str, Any]) -> str:
        """
        Generate a natural language description for an Azure resource.

        Args:
            resource_data: Dictionary containing resource information

        Returns:
            Natural language description of the resource
        """
        try:
            # Extract relevant information from resource data
            resource_type = resource_data.get("type", "Unknown")
            resource_name = resource_data.get("name", "Unknown")
            location = resource_data.get("location", "Unknown")
            properties = resource_data.get("properties", {})
            tags = resource_data.get("tags", {})

            # Create a concise summary for the prompt
            resource_summary = {
                "name": resource_name,
                "type": resource_type,
                "location": location,
                "key_properties": {
                    k: v
                    for k, v in properties.items()
                    if k
                    in [
                        "sku",
                        "size",
                        "tier",
                        "state",
                        "status",
                        "provisioningState",
                        "publicNetworkAccess",
                        "minimumTlsVersion",
                        "allowBlobPublicAccess",
                    ]
                },
                "tags": tags,
            }

            prompt = f"""
You are an expert Azure cloud architect with deep knowledge of Azure services and infrastructure patterns.

AZURE RESOURCE CONTEXT:
{json.dumps(resource_summary, indent=2)}

AZURE REFERENCE KNOWLEDGE:
Based on Azure Well-Architected Framework and Microsoft Learn documentation:

VIRTUAL MACHINES:
- Azure VMs provide on-demand, scalable computing resources with full control over the computing environment
- Key considerations: Security profiles, networking options, storage encryption, tagging strategies
- Best practices: Disable public IP associations, enable disk encryption, use network security groups
- Use cases: Development/test, cloud applications, extended datacenter connectivity

STORAGE ACCOUNTS:
- Azure Storage provides scalable cloud storage for data objects, file shares, and messaging
- Key features: Blob storage, file storage, queue storage, table storage
- Security: RBAC authorization, disable shared key access, store keys in Key Vault
- Best practices: Use managed identities, enable encryption, configure access tiers

NETWORKING:
- Virtual Networks provide isolated network environments in Azure
- Components: Subnets, network security groups, route tables, gateways
- Security: Network segmentation, private endpoints, service endpoints
- Best practices: Implement defense in depth, use hub-spoke topology

KEY VAULT:
- Centralized secrets management service for keys, secrets, and certificates
- Features: Hardware security modules, access policies, audit logging
- Integration: Service principals, managed identities, application secrets
- Best practices: Use separate vaults per environment, enable soft delete

DATABASES:
- Azure SQL, Cosmos DB, and other database services provide managed data platforms
- Features: Automatic backups, high availability, scaling, security
- Security: Transparent data encryption, firewall rules, private endpoints
- Best practices: Use managed identities, enable audit logging, configure backup retention

TASK:
Create a professional, technical description (2-3 sentences) for this Azure resource that would be valuable for DevOps teams, cloud architects, and technical documentation. Focus on:

1. Primary purpose and functionality
2. Key configuration details that impact operations, security, or performance
3. Business value or architectural significance
4. Any notable security or compliance considerations

Be specific about the resource type capabilities while remaining concise and actionable.
"""

            response = self.client.chat.completions.create(
                model=self.config.model_chat,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Azure cloud architect who creates clear, concise descriptions of Azure resources for technical documentation.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=50000,
            )

            content = response.choices[0].message.content
            description = content.strip() if content else ""
            logger.debug(
                f"Generated description for {resource_type} '{resource_name}': {description}"
            )

            return description

        except Exception as e:
            logger.error(
                f"Failed to generate description for resource {resource_data.get('name', 'Unknown')}: {e!s}"
            )
            return f"Azure {resource_type} resource providing cloud services and functionality."

    async def generate_relationship_description(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        relationship_type: str,
    ) -> str:
        """
        Generate a natural language description for a relationship between Azure resources.

        Args:
            source_resource: Source resource data
            target_resource: Target resource data
            relationship_type: Type of relationship (e.g., 'DEPENDS_ON', 'CONTAINS', etc.)

        Returns:
            Natural language description of the relationship
        """
        try:
            source_type = source_resource.get("type", "Resource")
            target_type = target_resource.get("type", "Resource")

            prompt = f"""
You are an expert Azure cloud architect with comprehensive knowledge of Azure service relationships and dependencies.

RELATIONSHIP ANALYSIS:
Source Resource Type: {source_type}
Target Resource Type: {target_type}
Relationship Type: {relationship_type}

AZURE RELATIONSHIP PATTERNS:
Based on Azure Well-Architected Framework principles:

CONTAINS relationships typically indicate:
- Resource Group → Resource: Administrative and billing boundaries
- Virtual Network → Subnet: Network segmentation and isolation
- Storage Account → Container/Blob: Data organization and access control
- Subscription → Resource Group: Governance and management scope

DEPENDS_ON relationships typically indicate:
- VM → Virtual Network: Network connectivity requirements
- App Service → Key Vault: Secrets and configuration dependencies
- Function App → Storage Account: Runtime and trigger dependencies
- Database → Virtual Network: Network access and security isolation

CONNECTS_TO relationships typically indicate:
- Application Gateway → Backend Pool: Load balancing and traffic routing
- Private Endpoint → Target Service: Secure, private connectivity
- VPN Gateway → On-premises: Hybrid connectivity patterns
- Service Bus → Applications: Messaging and event-driven architectures

TASK:
Analyze the relationship between {source_type} and {target_type} with relationship type {relationship_type}.

Provide a clear, technical explanation (1-2 sentences) that describes:
1. The operational significance of this relationship
2. How it impacts data flow, security, or management
3. What this means for system architects and DevOps teams

Be specific about the architectural implications while keeping it concise and actionable.
"""

            response = self.client.chat.completions.create(
                model=self.config.model_chat,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Azure cloud architect explaining resource relationships.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=20000,
            )

            content = response.choices[0].message.content
            description = content.strip() if content else ""
            logger.debug(
                f"Generated relationship description: {relationship_type} between {source_type} and {target_type}"
            )

            return description

        except Exception as e:
            logger.error(f"Failed to generate relationship description: {e!s}")
            return f"{relationship_type} relationship between {source_type} and {target_type}."

    async def generate_tenant_specification(
        self,
        resources: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        output_path: str,
    ) -> str:
        """
        Generate a comprehensive natural language specification for the entire Azure tenant.

        Args:
            resources: List of all resources in the tenant
            relationships: List of all relationships between resources
            output_path: Path where the specification markdown file will be saved

        Returns:
            Path to the generated specification file
        """
        try:
            # Analyze the tenant structure
            resource_types = {}
            locations = set()

            for resource in resources:
                resource_type = resource.get("type", "Unknown")
                location = resource.get("location", "Unknown")

                if resource_type not in resource_types:
                    resource_types[resource_type] = 0
                resource_types[resource_type] += 1

                if location != "Unknown":
                    locations.add(location)

            # Create analysis summary
            analysis = {
                "total_resources": len(resources),
                "resource_types": dict(
                    sorted(resource_types.items(), key=lambda x: x[1], reverse=True)
                ),
                "locations": sorted(locations),
                "total_relationships": len(relationships),
            }

            prompt = f"""
You are a senior Azure cloud architect creating a comprehensive tenant specification document.

Tenant Analysis:
{json.dumps(analysis, indent=2)}

Create a professional markdown specification document that includes:

1. **Executive Summary** - High-level overview of the tenant architecture
2. **Infrastructure Overview** - Key resource types and their distribution
3. **Geographic Distribution** - Regions and their purpose
4. **Architecture Patterns** - Common patterns observed in the resource relationships
5. **Security Posture** - Security-related observations
6. **Scalability Considerations** - How the architecture supports growth
7. **Recommendations** - Optimization opportunities and best practices

Make it comprehensive but accessible to both technical and business stakeholders.
Use proper markdown formatting with headers, bullet points, and tables where appropriate.
Focus on architectural insights rather than listing individual resources.
"""

            response = self.client.chat.completions.create(
                model=self.config.model_reasoning,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior Azure cloud architect creating detailed infrastructure documentation.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=100000,
            )

            content = response.choices[0].message.content
            specification = content.strip() if content else ""

            # Save the specification to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(specification)

            logger.info(f"Generated tenant specification: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate tenant specification: {e!s}")
            # Create a basic fallback specification
            fallback_spec = self._create_fallback_specification(
                resources, relationships
            )
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(fallback_spec)
            return output_path

    def _create_fallback_specification(
        self, resources: List[Dict[str, Any]], relationships: List[Dict[str, Any]]
    ) -> str:
        """Create a basic specification when LLM generation fails."""
        resource_types = {}
        locations = set()

        for resource in resources:
            resource_type = resource.get("type", "Unknown")
            location = resource.get("location", "Unknown")

            if resource_type not in resource_types:
                resource_types[resource_type] = 0
            resource_types[resource_type] += 1

            if location != "Unknown":
                locations.add(location)

        spec = f"""# Azure Tenant Infrastructure Specification

## Overview
This document provides an overview of the Azure tenant infrastructure as discovered by the Azure Tenant Grapher.

## Summary Statistics
- **Total Resources**: {len(resources)}
- **Resource Types**: {len(resource_types)}
- **Geographic Locations**: {len(locations)}
- **Relationships**: {len(relationships)}

## Resource Distribution

| Resource Type | Count |
|---------------|-------|
"""

        for resource_type, count in sorted(
            resource_types.items(), key=lambda x: x[1], reverse=True
        ):
            spec += f"| {resource_type} | {count} |\n"

        spec += """
## Geographic Distribution
The following Azure regions are utilized:
"""

        for location in sorted(locations):
            spec += f"- {location}\n"

        spec += f"""
## Infrastructure Relationships
The tenant contains {len(relationships)} relationships between resources, indicating the interconnected nature of the cloud infrastructure.

---
*This specification was generated automatically by Azure Tenant Grapher.*
"""

        return spec

    async def process_resources_batch(
        self, resources: List[Dict[str, Any]], batch_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of resources to add LLM-generated descriptions.

        Args:
            resources: List of resource dictionaries
            batch_size: Number of resources to process concurrently

        Returns:
            List of resources with added descriptions
        """
        total_resources = len(resources)
        logger.info(
            f"🔄 Starting LLM description generation for {total_resources} resources (batch size: {batch_size})"
        )

        processed_count = 0
        successful_count = 0
        failed_count = 0

        async def process_resource(
            resource: Dict[str, Any], resource_index: int
        ) -> None:
            nonlocal processed_count, successful_count, failed_count

            resource_name = resource.get("name", "Unknown")
            resource_type = resource.get("type", "Unknown")

            try:
                logger.info(
                    f"📝 Generating description for resource {resource_index + 1}/{total_resources}: {resource_name} ({resource_type})"
                )
                description = await self.generate_resource_description(resource)
                resource["llm_description"] = description

                successful_count += 1
                processed_count += 1

                # Log success with description preview
                desc_preview = (
                    description[:100] + "..." if len(description) > 100 else description
                )
                logger.info(
                    f'✅ Successfully described {resource_name}: "{desc_preview}"'
                )

            except Exception as e:
                failed_count += 1
                processed_count += 1

                logger.error(
                    f"❌ Failed to generate description for {resource_name} ({resource_type}): {e!s}"
                )
                resource["llm_description"] = f"Azure {resource_type} resource."

        # Process resources in batches to avoid overwhelming the API
        processed_resources: List[Dict[str, Any]] = []

        for batch_start in range(0, total_resources, batch_size):
            batch_end = min(batch_start + batch_size, total_resources)
            batch = resources[batch_start:batch_end]
            batch_number = (batch_start // batch_size) + 1
            total_batches = (total_resources + batch_size - 1) // batch_size

            logger.info(
                f"🔄 Processing batch {batch_number}/{total_batches} (resources {batch_start + 1}-{batch_end})"
            )

            # Process batch with resource indices for logging
            batch_with_indices = [
                (resource, batch_start + idx) for idx, resource in enumerate(batch)
            ]
            await asyncio.gather(
                *[
                    process_resource(resource, resource_index)
                    for resource, resource_index in batch_with_indices
                ]
            )
            processed_resources.extend(batch)

            # Progress summary for this batch
            logger.info(
                f"📊 Batch {batch_number} complete: {len(batch)} resources processed. Overall progress: {processed_count}/{total_resources} ({(processed_count / total_resources) * 100:.1f}%)"
            )

            # Small delay between batches to respect rate limits
            if batch_end < total_resources:
                logger.info(
                    "⏳ Waiting 2 seconds before next batch to respect API rate limits..."
                )
                await asyncio.sleep(2)

        # Final summary
        logger.info("🎉 LLM description generation completed!")
        logger.info(
            f"📈 Summary: {successful_count} successful, {failed_count} failed, {processed_count} total"
        )
        logger.info(
            f"✨ Success rate: {(successful_count / total_resources) * 100:.1f}%"
        )

        return processed_resources


def create_llm_generator() -> Optional[AzureLLMDescriptionGenerator]:
    """
    Factory function to create an LLM description generator.

    Returns:
        LLM generator instance or None if configuration is invalid
    """
    try:
        config = LLMConfig.from_env()
        if not config.is_valid():
            logger.warning(
                "LLM configuration is invalid. Skipping LLM description generation."
            )
            return None

        return AzureLLMDescriptionGenerator(config)
    except Exception as e:
        logger.error(f"Failed to create LLM generator: {e!s}")
        return None

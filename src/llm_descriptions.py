import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar

from dotenv import load_dotenv
from openai import AzureOpenAI

from src.utils.session_manager import retry_neo4j_operation

T = TypeVar("T")


@retry_neo4j_operation()
def run_neo4j_query_with_retry(session: Any, query: str, **params: Any) -> Any:
    return session.run(query, **params)


# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class ThrottlingError(Exception):
    """Raised when LLM API throttling (HTTP 429) is detected."""

    pass


def is_throttling_error(e: Exception) -> bool:
    if hasattr(e, "status_code") and getattr(e, "status_code", None) == 429:
        return True
    if "429" in str(e) or "throttle" in str(e).lower():
        return True
    return False


def async_retry_with_throttling(
    max_retries: int = 5, initial_delay: int = 2, backoff: int = 2
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator for retrying async LLM calls, raising ThrottlingError on repeated throttling.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if is_throttling_error(e):
                        logger.warning(
                            f"OpenAI throttling detected (HTTP 429 or similar), attempt {attempt + 1}/{max_retries}"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(delay)
                            delay *= backoff
                            continue
                        else:
                            raise ThrottlingError(
                                "LLM API throttling detected after retries"
                            ) from e
                    raise
            raise ThrottlingError("LLM API throttling detected after retries")

        return wrapper

    return decorator


# (Removed duplicate ThrottlingError definition)


def retry_with_throttling(
    func: Callable[..., T],
    max_retries: int = 5,
    initial_delay: int = 2,
    backoff: int = 2,
    logger: logging.Logger = logger,
) -> Callable[..., T]:
    """
    Retry wrapper for LLM calls. Raises ThrottlingError on repeated throttling.
    """

    def wrapper(*args: Any, **kwargs: Any) -> T:
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # OpenAI HTTP 429 or explicit throttling
                if hasattr(e, "status_code") and getattr(e, "status_code", None) == 429:
                    logger.warning(
                        f"OpenAI throttling detected (HTTP 429), attempt {attempt + 1}/{max_retries}"
                    )
                elif "429" in str(e) or "throttle" in str(e).lower():
                    logger.warning(
                        f"Possible throttling detected: {e}, attempt {attempt + 1}/{max_retries}"
                    )
                else:
                    raise
                time.sleep(delay)
                delay *= backoff
        raise ThrottlingError("LLM API throttling detected after retries")

    return wrapper


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

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
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

        # Suppress HTTP request logging from OpenAI client
        httpx_logger = logging.getLogger("httpx")
        httpx_logger.setLevel(logging.WARNING)

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
        Raises ThrottlingError on repeated throttling.
        """
        max_retries = 5
        initial_delay = 2
        backoff = 2
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                # Extract ALL relevant information from resource data
                resource_type = resource_data.get("type", "Unknown")
                resource_name = resource_data.get("name", "Unknown")
                location = resource_data.get("location", "Unknown")
                properties = resource_data.get("properties", {})
                tags = resource_data.get("tags", {})
                sku = resource_data.get("sku", {})
                kind = resource_data.get("kind", None)

                # Include ALL properties for more detailed analysis
                resource_summary = {
                    "name": resource_name,
                    "type": resource_type,
                    "location": location,
                    "sku": sku,
                    "kind": kind,
                    "properties": properties,  # Include ALL properties
                    "tags": tags,
                }

                prompt = f"""
You are an expert Azure Infrastructure-as-Code specialist with deep knowledge of ARM templates, Terraform, and Azure CLI.

TASK: Create a detailed technical description for this Azure resource that could be used to recreate the resource from scratch. Include specific configuration details that are essential for deployment.

AZURE RESOURCE FULL CONFIGURATION:
{json.dumps(resource_summary, indent=2, default=str)}

INSTRUCTIONS:
Generate a comprehensive description (3-5 sentences) that includes:

1. **Resource Purpose**: What this resource does and its role in the architecture
2. **Key Configuration**: Specific settings like SKU, size, networking, security configurations
3. **Dependencies**: What other resources this depends on or connects to
4. **Critical Settings**: Security, performance, or compliance settings that are configured
5. **Deployment Details**: Location, resource group context, and any special deployment considerations

FORMAT: Write as a technical specification that a cloud engineer could use to understand and potentially recreate this resource. Include specific values and configuration details where relevant.

EXAMPLES OF GOOD DESCRIPTIONS:
- "Production Azure VM (Standard_D4s_v3) running Windows Server 2022 in East US with premium SSD storage, network security group allowing RDP access, and managed disk encryption enabled."
- "General-purpose storage account (Standard_LRS) with hot access tier, blob public access disabled, HTTPS required, and soft delete enabled for 7 days retention."
- "Azure Key Vault with soft delete enabled, purge protection active, RBAC access policies, private endpoint connectivity, and audit logging to Log Analytics workspace."

Be specific about the actual configured values while explaining their architectural significance.
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
                    max_completion_tokens=32768,
                )

                content = response.choices[0].message.content
                description = str(content).strip() if content else ""
                logger.debug(
                    f"Generated description for {resource_type} '{resource_name}': {description}"
                )

                return description
            except Exception as e:
                if is_throttling_error(e):
                    logger.warning(
                        f"OpenAI throttling detected (HTTP 429 or similar), attempt {attempt + 1}/{max_retries}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)
                        delay *= backoff
                        continue
                    else:
                        raise ThrottlingError(
                            "LLM API throttling detected after retries"
                        ) from e
                logger.exception(
                    f"Failed to generate description for resource {resource_data.get('name', 'Unknown')}: {e!s}"
                )
                resource_type = resource_data.get("type", "Unknown")
                return f"Azure {resource_type} resource providing cloud services and functionality."
        # Fallback: return a generic description if all retries fail
        return "Azure resource providing cloud services and functionality."

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
        source_type = source_resource.get("type", "Resource")
        target_type = target_resource.get("type", "Resource")
        try:
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
                max_completion_tokens=32768,
            )

            content = response.choices[0].message.content
            description = str(content).strip() if content else ""
            logger.debug(
                f"Generated relationship description: {relationship_type} between {source_type} and {target_type}"
            )

            return description

        except Exception as e:
            logger.exception(f"Failed to generate relationship description: {e!s}")
            return f"{relationship_type} relationship between {source_type} and {target_type}."

    async def generate_resource_group_description(self, resource_group_name: str, subscription_id: str, resources: List[Dict[str, Any]]) -> str:
        """
        Generate a natural language description for a Resource Group based on its contained resources.
        
        Args:
            resource_group_name: Name of the resource group
            subscription_id: Subscription ID
            resources: List of resources contained in this resource group
            
        Returns:
            Natural language description of the resource group
        """
        try:
            # Analyze the resources in the resource group
            resource_types = {}
            locations = set()
            total_resources = len(resources)
            
            for resource in resources:
                resource_type = resource.get("type", "Unknown")
                location = resource.get("location", "Unknown")
                
                if resource_type not in resource_types:
                    resource_types[resource_type] = 0
                resource_types[resource_type] += 1
                
                if location != "Unknown":
                    locations.add(str(location))
            
            # Sort resource types by count
            sorted_resource_types = sorted(resource_types.items(), key=lambda x: x[1], reverse=True)
            
            prompt = f"""
You are an expert Azure cloud architect analyzing a Resource Group and its contents.

RESOURCE GROUP ANALYSIS:
Name: {resource_group_name}
Subscription: {subscription_id}
Total Resources: {total_resources}

RESOURCE TYPE DISTRIBUTION:
{json.dumps(dict(sorted_resource_types), indent=2)}

GEOGRAPHIC LOCATIONS:
{sorted(locations)}

TASK:
Analyze this Resource Group and provide a comprehensive description (2-3 sentences) that explains:

1. **Purpose and Role**: What this Resource Group appears to be used for based on the resource types and naming patterns
2. **Architecture Pattern**: What kind of workload or solution this represents (e.g., web application, data analytics, networking hub, etc.)
3. **Scale and Scope**: The size and complexity of the deployment
4. **Key Components**: The most important resource types and their likely relationships

GUIDELINES:
- Focus on the business or technical purpose rather than just listing resource counts
- Identify common Azure solution patterns where applicable
- Consider resource naming conventions and types to infer the intended use case
- Be specific about the scale and architectural approach

EXAMPLE OUTPUTS:
- "Production web application Resource Group containing a 3-tier architecture with load balancers, web servers, and database components across 2 Azure regions for high availability."
- "Development environment Resource Group for data analytics workloads, featuring Azure Data Factory pipelines, Storage Accounts for data lakes, and compute resources for processing."
- "Networking hub Resource Group implementing a hub-and-spoke topology with Virtual Network Gateways, Network Security Groups, and routing infrastructure."

Focus on architectural significance and business purpose rather than just resource inventory.
"""

            response = self.client.chat.completions.create(
                model=self.config.model_chat,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Azure cloud architect who analyzes Resource Groups to understand their architectural purpose and business function.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=32768,
            )

            content = response.choices[0].message.content
            description = str(content).strip() if content else ""
            logger.debug(f"Generated Resource Group description for '{resource_group_name}': {description}")

            return description

        except Exception as e:
            logger.exception(f"Failed to generate Resource Group description for '{resource_group_name}': {e!s}")
            return f"Azure Resource Group '{resource_group_name}' containing {len(resources)} resources providing organized resource management and deployment boundaries."

    async def generate_tag_description(self, tag_key: str, tag_value: str, tagged_resources: List[Dict[str, Any]]) -> str:
        """
        Generate a natural language description for a Tag based on the resources it's applied to.
        
        Args:
            tag_key: The tag key
            tag_value: The tag value
            tagged_resources: List of resources that have this tag
            
        Returns:
            Natural language description of the tag's purpose and usage
        """
        try:
            # Analyze the tagged resources
            resource_types = {}
            locations = set()
            resource_groups = set()
            total_resources = len(tagged_resources)
            
            for resource in tagged_resources:
                resource_type = resource.get("type", "Unknown")
                location = resource.get("location", "Unknown")
                resource_group = resource.get("resource_group", "Unknown")
                
                if resource_type not in resource_types:
                    resource_types[resource_type] = 0
                resource_types[resource_type] += 1
                
                if location != "Unknown":
                    locations.add(str(location))
                if resource_group != "Unknown":
                    resource_groups.add(str(resource_group))
            
            # Sort resource types by count
            sorted_resource_types = sorted(resource_types.items(), key=lambda x: x[1], reverse=True)
            
            prompt = f"""
You are an expert Azure cloud architect analyzing a Tag and its usage across Azure resources.

TAG ANALYSIS:
Key: {tag_key}
Value: {tag_value}
Applied to {total_resources} resources

TAGGED RESOURCE TYPES:
{json.dumps(dict(sorted_resource_types), indent=2)}

RESOURCE GROUPS AFFECTED:
{sorted(resource_groups)[:10]}  # Limit to first 10 for readability

GEOGRAPHIC DISTRIBUTION:
{sorted(locations)}

TASK:
Analyze this Tag and provide a concise description (1-2 sentences) that explains:

1. **Tagging Purpose**: What this tag appears to be used for based on common Azure tagging patterns
2. **Scope and Usage**: How broadly it's applied and what types of resources it categorizes
3. **Business or Technical Context**: What business function, environment, or technical requirement this tag represents

COMMON AZURE TAG PATTERNS TO CONSIDER:
- Environment tags (dev, test, prod, staging)
- Cost center/billing tags (department, project, cost-center)
- Ownership tags (team, owner, contact)
- Lifecycle tags (temporary, permanent, backup)
- Compliance tags (compliance-scope, data-classification)
- Application tags (app-name, version, component)

GUIDELINES:
- Focus on the organizational or technical purpose
- Identify the tagging strategy being used
- Consider the resource types and scope to infer the intended use case
- Be specific about what business or technical function this serves

EXAMPLE OUTPUTS:
- "Environment classification tag identifying production workloads across web applications and databases for operational and compliance management."
- "Cost allocation tag for tracking expenses related to the marketing department's digital campaigns and supporting infrastructure."
- "Application component tag organizing resources belonging to the customer portal system for better resource management and troubleshooting."

Focus on the strategic purpose of this tagging rather than just describing what resources have it.
"""

            response = self.client.chat.completions.create(
                model=self.config.model_chat,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Azure cloud architect who analyzes tagging strategies to understand their organizational and technical purpose.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=32768,
            )

            content = response.choices[0].message.content
            description = str(content).strip() if content else ""
            logger.debug(f"Generated Tag description for '{tag_key}:{tag_value}': {description}")

            return description

        except Exception as e:
            logger.exception(f"Failed to generate Tag description for '{tag_key}:{tag_value}': {e!s}")
            return f"Azure tag '{tag_key}:{tag_value}' applied to {len(tagged_resources)} resources for organizational and management purposes."

    async def generate_tenant_specification(
        self,
        resources: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        output_path: str,
    ) -> str:
        """
        Generate a comprehensive natural language specification for the entire Azure tenant.

        Args:
            resources: List[Any] of all resources in the tenant
            relationships: List[Any] of all relationships between resources
            output_path: Path where the specification markdown file will be saved

        Returns:
            Path to the generated specification file
        """
        try:
            # Analyze the tenant structure
            resource_types: dict[str, int] = {}
            locations: set[str] = set()

            for resource in resources:
                resource_type = resource.get("type", "Unknown")
                location = resource.get("location", "Unknown")

                if resource_type not in resource_types:
                    resource_types[resource_type] = 0
                resource_types[resource_type] += 1

                if location != "Unknown":
                    locations.add(str(location))

            # Create analysis summary
            analysis: dict[str, Any] = {
                "total_resources": len(resources),
                "resource_types": dict(
                    sorted(
                        resource_types.items(),
                        key=lambda x: int(x[1]),
                        reverse=True,
                    )
                ),
                "locations": sorted(locations),
                "total_relationships": len(relationships),
            }

            prompt = f"""
You are a senior Azure cloud architect creating a comprehensive tenant specification document.

Tenant Analysis:
{json.dumps(analysis, indent=2)}

Create a professional markdown specification document that provides a detailed, declarative specification of the Azure tenant. The document should include:

1. **Executive Summary** - High-level overview of the tenant architecture
2. **Infrastructure Overview** - Key resource types and their distribution
3. **Geographic Distribution** - Regions and their purpose
4. **Architecture Patterns** - Common patterns observed in the resource relationships
5. **Security Posture** - Security-related observations
6. **Scalability Considerations** - How the architecture supports growth

Do NOT include a recommendations or next steps section. Do NOT provide optimization advice or best practices. Only describe the current state of the tenant: resource types, names, properties, and relationships.

Use proper markdown formatting with headers, bullet points, and tables where appropriate.
Focus on architectural details and relationships, not on recommendations or future actions.
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
                max_completion_tokens=32768,
            )

            content = response.choices[0].message.content
            specification = content.strip() if content else ""

            # Save the specification to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(specification)

            logger.info(f"Generated tenant specification: {output_path}")
            return output_path

        except Exception as e:
            logger.exception(f"Failed to generate tenant specification: {e!s}")
            # Create a basic fallback specification
            fallback_spec = self._create_fallback_specification(
                resources, relationships
            )
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(fallback_spec)
            return output_path

    def _create_fallback_specification(
        self,
        resources: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> str:
        """Create a basic specification when LLM generation fails."""
        resource_types: dict[str, int] = {}
        locations: set[str] = set()

        for resource in resources:
            resource_type = resource.get("type", "Unknown")
            location = resource.get("location", "Unknown")

            if resource_type not in resource_types:
                resource_types[resource_type] = 0
            resource_types[resource_type] += 1

            if location != "Unknown":
                locations.add(str(location))

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
            resource_types.items(), key=lambda x: int(x[1]), reverse=True
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

    # Batch-based LLM resource processing is deprecated and removed.


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
        logger.exception(f"Failed to create LLM generator: {e!s}")


def should_generate_description(resource_dict: dict[str, Any], session: Any) -> bool:
    """
    Determine if LLM description generation is needed for a resource.

    Args:
        resource_dict: The resource dictionary (must include 'id' and change-indicator fields).
        session: Neo4j session object.

    Returns:
        bool: True if LLM description should be generated, False if it can be skipped.
    """
    logger = logging.getLogger(__name__)
    resource_id = resource_dict.get("id")
    if not resource_id:
        logger.warning("Resource missing 'id'; cannot check for LLM skip.")
        return True

    # Query Neo4j for node by id, get llm_description and change-indicator fields
    try:
        try:
            # DEBUG: Print all property keys and types for this node before running the query
            try:
                key_result = run_neo4j_query_with_retry(
                    session,
                    "MATCH (r:Resource {id: $id}) RETURN keys(r) AS prop_keys",
                    id=resource_id,
                )
                key_record = key_result.single()
                if key_record and "prop_keys" in key_record:
                    prop_keys = key_record["prop_keys"]
                    logger.debug(f"Resource {resource_id} property keys: {prop_keys}")
            except Exception as prop_exc:
                logger.warning(
                    f"Could not inspect properties for {resource_id}: {prop_exc}"
                )

            result = run_neo4j_query_with_retry(
                session,
                """
                MATCH (r:Resource {id: $id})
                RETURN
                    r.llm_description AS desc
                """,
                id=resource_id,
            )
        except BufferError as be:
            logger.warning(
                f"BufferError during Neo4j query for {resource_id}: {be}; will generate."
            )
            return True
        except Exception as e:
            logger.warning(
                f"Exception during Neo4j query for {resource_id}: {e}; will generate."
            )
            return True

        if result is None:
            logger.warning(
                f"Neo4j session.run returned None for resource {resource_id}; will generate."
            )
            return True

        record = result.single()
        if not record:
            logger.debug(
                f"No existing node for resource {resource_id}; will generate description."
            )
            return True

        # Defensive: Ensure record is a mapping before accessing .get
        if not hasattr(record, "get"):
            logger.warning(
                f"Neo4j record for resource {resource_id} is not a mapping (type={type(record)} value={record!r}); will generate."
            )
            return True

        # Convert record to dict to avoid Neo4j driver mutation/access errors
        try:
            # Defensive: extract fields individually and convert to safe types
            db_desc = record.get("desc")

            # Convert buffer-like objects to string if needed
            def safe_to_str(val: Any) -> Optional[str]:
                if val is None:
                    return None
                try:
                    # If it's bytes or memoryview, decode to str
                    if isinstance(val, (bytes, bytearray, memoryview)):
                        return (
                            val.tobytes().decode("utf-8", errors="replace")
                            if isinstance(val, memoryview)
                            else val.decode("utf-8", errors="replace")
                        )
                    return str(val)
                except BufferError as be:
                    logger.warning(
                        f"BufferError converting value to string for resource {resource_id}: {type(val)}: {be}"
                    )
                    return None
                except Exception as conv_exc:
                    logger.warning(
                        f"Could not convert value to string for resource {resource_id}: {type(val)}: {conv_exc}"
                    )
                    return None

            db_desc = safe_to_str(db_desc)
        except Exception as rec_exc:
            logger.warning(
                f"Failed to extract Neo4j record fields for {resource_id}: {rec_exc}; will generate."
            )
            return True

        # If no description, must generate
        if not db_desc or db_desc.strip() == "" or db_desc.startswith("Azure "):
            logger.debug(
                f"Resource {resource_id} missing or generic description; will generate."
            )
            return True

        # Since we don't have etag/last_modified in the current schema,
        # skip LLM generation if a good description already exists
        logger.info(f"Skipping LLM for {resource_id}: description already present.")
        return False

    except Exception as e:
        import traceback

        logger.warning(
            f"Error checking LLM skip for {resource_id}: {type(e).__name__}: {e!s}\n{traceback.format_exc()}; will generate."
        )
        return True

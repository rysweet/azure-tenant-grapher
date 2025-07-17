import re
from typing import Any, Optional

from src.config_manager import ProcessingConfig, create_neo4j_config_from_env
from src.llm_descriptions import AzureLLMDescriptionGenerator
from src.services.resource_processing_service import ResourceProcessingService
from src.tenant_spec_models import TenantSpec
from src.utils.session_manager import Neo4jSessionManager


def get_default_session_manager() -> Neo4jSessionManager:
    config = create_neo4j_config_from_env()
    return Neo4jSessionManager(config.neo4j)


def normalize_tenant_spec_fields(obj: Any, context: str | None = None) -> Any:
    """
    Recursively normalize 'id' fields to the correct alias for each object type.
    """
    if isinstance(obj, dict):
        # Determine context for aliasing
        new_obj = {}
        for k, v in obj.items():
            # Set context for children
            child_context = context
            if k == "tenant":
                child_context = "tenant"
            elif k == "subscriptions":
                child_context = "subscription"
            elif k == "resource_groups":
                child_context = "resource_group"
            elif k == "resources":
                child_context = "resource"
            elif k == "users":
                child_context = "user"
            elif k == "groups":
                child_context = "group"
            elif k == "service_principals":
                child_context = "service_principal"
            elif k == "managed_identities":
                child_context = "managed_identity"
            elif k == "admin_units":
                child_context = "admin_unit"
            # Recursively normalize children
            new_obj[k] = normalize_tenant_spec_fields(v, child_context)
        # Now, apply alias mapping for this object if it has an 'id'
        if "id" in new_obj:
            alias_map = {
                "tenant": "tenantId",
                "subscription": "subscriptionId",
                "resource_group": "resourceGroupId",
                "resource": "resourceId",
                "user": "userId",
                "group": "groupId",
                "service_principal": "spId",
                "managed_identity": "miId",
                "admin_unit": "adminUnitId",
            }
            if context in alias_map:
                alias = alias_map[context]
                new_obj[alias] = new_obj.pop("id")
        return new_obj
    elif isinstance(obj, list):
        return [normalize_tenant_spec_fields(item, context) for item in obj]
    else:
        return obj


class TenantCreator:
    LLM_PROMPT_TEMPLATE = """
    You are an expert Azure cloud architect. Given the following markdown narrative describing an Azure tenant, output ONLY a single JSON object matching the required schema. Do not include any explanation, markdown, or extra text—just the JSON.

You may reference the following sources for realistic Azure architectures, resource types, and patterns:
- Azure Customer Stories: https://www.microsoft.com/en-us/customers/search?filters=product%3Aazure
- Azure Reference Architectures: https://learn.microsoft.com/en-us/azure/architecture/browse/

You may *search* these sites for relevant examples, but do not copy text or use real company names. Use them only to inform your modeling of realistic Azure environments.

Markdown Narrative:
-------------------
{narrative}

Required JSON Schema (example):
------------------------------
{schema}

Instructions:
- Output only a single JSON object matching the schema above.
- Do not include markdown code fences or any extra text.
- All required fields must be present. Optional fields may be omitted if not described.
- Use realistic, but minimal, values if the narrative is ambiguous.
"""

    def __init__(self, llm_generator: Optional[AzureLLMDescriptionGenerator] = None):
        self.llm_generator = llm_generator

    @staticmethod
    def _extract_narrative(markdown: str) -> str:
        """
        Extracts the main narrative text from markdown, excluding all code blocks.
        """
        # Remove all code blocks (```...```)
        return re.sub(r"```[\s\S]+?```", "", markdown, flags=re.MULTILINE).strip()

    @staticmethod
    def _tenant_spec_schema_example() -> str:
        # Minimal valid example for LLM guidance
        return (
            "{\n"
            '  "tenant": {\n'
            '    "id": "tenant-001",\n'
            '    "display_name": "Example Tenant",\n'
            '    "subscriptions": [\n'
            "      {\n"
            '        "id": "sub-001",\n'
            '        "name": "Production",\n'
            '        "resource_groups": [\n'
            "          {\n"
            '            "id": "rg-001",\n'
            '            "name": "prod-rg",\n'
            '            "location": "eastus",\n'
            '            "resources": [\n'
            "              {\n"
            '                "id": "res-001",\n'
            '                "name": "vm-prod",\n'
            '                "type": "Microsoft.Compute/virtualMachines",\n'
            '                "location": "eastus",\n'
            '                "properties": {}\n'
            "              }\n"
            "            ]\n"
            "          }\n"
            "        ]\n"
            "      }\n"
            "    ],\n"
            '    "users": [],\n'
            '    "groups": [],\n'
            '    "service_principals": [],\n'
            '    "managed_identities": [],\n'
            '    "admin_units": [],\n'
            '    "rbac_assignments": [],\n'
            '    "relationships": []\n'
            "  }\n"
            "}"
        )

    async def _llm_generate_tenant_spec(self, narrative: str) -> str:
        """
        Calls the LLM to generate a tenant spec JSON from a narrative.
        """
        if not self.llm_generator:
            raise RuntimeError("LLM generator is not configured.")
        prompt = self.LLM_PROMPT_TEMPLATE.format(
            narrative=narrative, schema=self._tenant_spec_schema_example()
        )
        # Use the LLM's chat completion API directly
        response = self.llm_generator.client.chat.completions.create(
            model=self.llm_generator.config.model_chat,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert Azure cloud architect. Output only a single JSON object matching the required schema.",
                },
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=4096,
        )
        content = response.choices[0].message.content
        # Remove any code fences or extra text, just in case
        json_text = re.sub(
            r"^```json|```$", "", content.strip(), flags=re.MULTILINE
        ).strip()
        return json_text

    async def create_from_markdown(self, markdown: str) -> TenantSpec:
        """
        Extracts a JSON fenced code block from markdown and parses it as TenantSpec.
        If no JSON block is found, uses LLM to generate the spec from the narrative.
        """
        print("DEBUG: Markdown received by create_from_markdown:\n", markdown)
        match = re.search(
            r"```json\s*([\s\S]+?)\s*```", markdown, re.IGNORECASE | re.MULTILINE
        )
        if not match:
            print("DEBUG: No JSON block found with standard regex, trying fallback.")
            match = re.search(
                r"```json\s*([\s\S]+)", markdown, re.IGNORECASE | re.MULTILINE
            )
        if match:
            json_text = match.group(1)
            print("DEBUG: Extracted JSON block:\n", json_text)
            import json as _json

            # Always normalize the JSON before parsing
            data = _json.loads(json_text)
            data = normalize_tenant_spec_fields(data)
            json_text = _json.dumps(data)
            return TenantSpec.parse_raw_json(json_text)
        # No JSON block: extract narrative and use LLM
        print(
            "DEBUG: No JSON block found in markdown (even with fallback). Using LLM for narrative-to-spec."
        )
        narrative = self._extract_narrative(markdown)
        # Prepare the prompt for error context
        prompt = self.LLM_PROMPT_TEMPLATE.format(
            narrative=narrative, schema=self._tenant_spec_schema_example()
        )
        json_text = await self._llm_generate_tenant_spec(narrative)
        print("DEBUG: LLM-generated JSON spec:\n", json_text)
        print("DEBUG: Type of json_text:", type(json_text))
        # Normalize LLM field names using centralized schema-driven mapping
        import json as _json

        from src.exceptions import LLMGenerationError
        from src.llm_descriptions import normalize_llm_fields

        try:
            data = _json.loads(json_text)
            print("DEBUG: LLM JSON loaded as dict:", data)

            # Normalize all field names throughout the data structure
            if "tenant" in data:
                tenant_data = data["tenant"]

                # Normalize tenant fields
                data["tenant"] = normalize_llm_fields(tenant_data, "tenant")

                # Normalize subscriptions
                if "subscriptions" in data["tenant"]:
                    data["tenant"]["subscriptions"] = normalize_llm_fields(
                        data["tenant"]["subscriptions"], "subscription"
                    )

                # Normalize users
                if "users" in data["tenant"]:
                    data["tenant"]["users"] = normalize_llm_fields(
                        data["tenant"]["users"], "user"
                    )

                # Normalize groups
                if "groups" in data["tenant"]:
                    data["tenant"]["groups"] = normalize_llm_fields(
                        data["tenant"]["groups"], "group"
                    )

                # Normalize service principals
                if "service_principals" in data["tenant"]:
                    data["tenant"]["service_principals"] = normalize_llm_fields(
                        data["tenant"]["service_principals"], "service_principal"
                    )

                # Normalize managed identities
                if "managed_identities" in data["tenant"]:
                    data["tenant"]["managed_identities"] = normalize_llm_fields(
                        data["tenant"]["managed_identities"], "managed_identity"
                    )

                # Normalize admin units
                if "admin_units" in data["tenant"]:
                    data["tenant"]["admin_units"] = normalize_llm_fields(
                        data["tenant"]["admin_units"], "admin_unit"
                    )

                # Normalize RBAC assignments
                if "rbac_assignments" in data["tenant"]:
                    data["tenant"]["rbac_assignments"] = normalize_llm_fields(
                        data["tenant"]["rbac_assignments"], "rbac_assignment"
                    )

                # Normalize relationships
                if "relationships" in data["tenant"]:
                    relationships = normalize_llm_fields(
                        data["tenant"]["relationships"], "relationship"
                    )
                    # Fix relationships where targetId might be a list instead of string
                    # and handle field mapping issues
                    if isinstance(relationships, list):
                        for rel in relationships:
                            if isinstance(rel, dict):
                                # Handle field name mapping
                                if "from_resource" in rel and "sourceId" not in rel:
                                    rel["sourceId"] = rel.pop("from_resource")
                                if "to_resource" in rel and "targetId" not in rel:
                                    rel["targetId"] = rel.pop("to_resource")
                                if "type" in rel and "relationshipType" not in rel:
                                    rel["relationshipType"] = rel.pop("type")

                                # Handle targetId as list
                                if "targetId" in rel:
                                    target_id = rel["targetId"]
                                    if isinstance(target_id, list):
                                        # Take the first item if it's a list, or join them
                                        if len(target_id) > 0:
                                            rel["targetId"] = target_id[0]
                                        else:
                                            rel["targetId"] = "unknown-target"
                    data["tenant"]["relationships"] = relationships

            print("DEBUG: Post-processed LLM JSON dict:", data)
            json_text = _json.dumps(data)
        except Exception as e:
            # Log prompt and raw response for debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                "LLM output parsing failed. Prompt: %r\nRaw response: %r\nException: %s",
                prompt,
                json_text,
                e,
            )
            # Raise structured error for CLI and test handling
            raise LLMGenerationError(
                "Failed to parse LLM output as valid JSON.",
                model=getattr(self.llm_generator, "config", None)
                and getattr(self.llm_generator.config, "model_chat", None),
                context={"prompt": prompt, "raw_response": json_text},
                cause=e,
            ) from e
        return TenantSpec.parse_raw_json(json_text)

    async def ingest_to_graph(self, spec: TenantSpec) -> None:
        """
        Ingests the TenantSpec into Neo4j: creates Tenant, Subscriptions, Resources, Identities, RBAC, and Relationships.
        """
        # (no longer need asyncio)

        tenant = spec.tenant
        session_manager = get_default_session_manager()
        session_manager.connect()

        # 1. Create Tenant node
        with session_manager.session() as session:
            session.run(
                """
                MERGE (t:Tenant {id: $id})
                SET t.display_name = $display_name
                """,
                {
                    "id": tenant.id,
                    "display_name": getattr(tenant, "display_name", None),
                },
            )

        # 2. Create Subscription nodes and relationships
        if tenant.subscriptions:
            for sub in tenant.subscriptions:
                with session_manager.session() as session:
                    session.run(
                        """
                        MERGE (s:Subscription {id: $id})
                        SET s.name = $name
                        WITH s
                        MATCH (t:Tenant {id: $tenant_id})
                        MERGE (t)-[:HAS_SUBSCRIPTION]->(s)
                        """,
                        {
                            "id": sub.id,
                            "name": getattr(sub, "name", None),
                            "tenant_id": tenant.id,
                        },
                    )

        # 3. Flatten resources for processing
        resources = []
        if tenant.subscriptions:
            for sub in tenant.subscriptions:
                if sub.resource_groups:
                    for rg in sub.resource_groups:
                        if rg.resources:
                            for res in rg.resources:
                                # Attach resource_group and subscription_id for context
                                res_dict = (
                                    res.model_dump()
                                    if hasattr(res, "model_dump")
                                    else dict(res)
                                )
                                res_dict["resource_group"] = rg.name
                                res_dict["subscription_id"] = sub.id
                                resources.append(res_dict)

        # 4. Process resources using ResourceProcessingService
        config = ProcessingConfig()
        rps = ResourceProcessingService(
            session_manager=session_manager,
            llm_generator=self.llm_generator,
            config=config,
        )
        await rps.process_resources(resources, progress_callback=None, max_workers=2)

        # 5. Ingest identities
        # If aad_graph_service is available, use it; otherwise, create minimal nodes
        aad_graph_service = getattr(self, "aad_graph_service", None)
        if aad_graph_service:
            # Use the db_ops from ResourceProcessor for upserts
            from src.resource_processor import ResourceProcessor

            processor = ResourceProcessor(session_manager, self.llm_generator, None)
            aad_graph_service.ingest_into_graph(processor.db_ops)
        else:
            identities = getattr(spec, "identities", None)
            if identities:
                # Users
                for user in identities.get("users", []):
                    with session_manager.session() as session:
                        session.run(
                            """
                            MERGE (u:User {id: $id})
                            SET u.name = $name, u.department = $department, u.job_title = $job_title
                            """,
                            {
                                "id": user.get("id"),
                                "name": user.get("name"),
                                "department": user.get("department"),
                                "job_title": user.get("job_title"),
                            },
                        )
                # Groups
                for group in identities.get("groups", []):
                    with session_manager.session() as session:
                        session.run(
                            """
                            MERGE (g:IdentityGroup {id: $id})
                            SET g.name = $name
                            """,
                            {
                                "id": group.get("id"),
                                "name": group.get("name"),
                            },
                        )
                # Service Principals
                for sp in identities.get("service_principals", []):
                    with session_manager.session() as session:
                        session.run(
                            """
                            MERGE (sp:ServicePrincipal {id: $id})
                            SET sp.name = $name
                            """,
                            {
                                "id": sp.get("id"),
                                "name": sp.get("name"),
                            },
                        )
                # Managed Identities
                for mi in identities.get("managed_identities", []):
                    with session_manager.session() as session:
                        session.run(
                            """
                            MERGE (mi:ManagedIdentity {id: $id})
                            SET mi.name = $name
                            """,
                            {
                                "id": mi.get("id"),
                                "name": mi.get("name"),
                            },
                        )
                # Admin Units
                for au in identities.get("admin_units", []):
                    with session_manager.session() as session:
                        session.run(
                            """
                            MERGE (au:AdminUnit {id: $id})
                            SET au.name = $name
                            """,
                            {
                                "id": au.get("id"),
                                "name": au.get("name"),
                            },
                        )

        # 6. RBAC assignments
        rbac_assignments = getattr(spec, "rbac_assignments", None)
        if (
            not rbac_assignments
            and hasattr(spec, "tenant")
            and hasattr(spec.tenant, "rbac_assignments")
        ):
            rbac_assignments = spec.tenant.rbac_assignments
        if rbac_assignments:
            for rbac in rbac_assignments:
                with session_manager.session() as session:
                    session.run(
                        """
                        MATCH (p {id: $principal_id})
                        MATCH (s:Subscription {id: $scope})
                        MERGE (p)-[r:ASSIGNED_ROLE {role: $role}]->(s)
                        """,
                        {
                            "principal_id": rbac.principal_id,
                            "role": rbac.role,
                            "scope": rbac.scope,
                        },
                    )

        # 7. Relationships
        relationships = getattr(spec, "relationships", None)
        if (
            not relationships
            and hasattr(spec, "tenant")
            and hasattr(spec.tenant, "relationships")
        ):
            relationships = spec.tenant.relationships
        if relationships:
            for rel in relationships:
                with session_manager.session() as session:
                    # Only allow safe relationship types
                    allowed_types = {
                        "CAN_READ_SECRET",
                        "MEMBER_OF",
                        "ASSIGNED_ROLE",
                        "DEPENDS_ON",
                        "HAS_SUBSCRIPTION",
                        "HAS_RESOURCE_GROUP",
                        "HAS_RESOURCE",
                        "tenantHasSubscription",
                        "rgContainsResource",
                        "userIsMemberOf",
                        "subscriptionContainsResourceGroup",
                        "resourceGroupContainsResource",
                        "api_integration",
                        "data_source",
                        "frontend_protection",
                        "has_permission",
                        "data_analytics",
                        "event_subscription",
                        "CONNECTS_TO",
                        "USES",
                        "INTEGRATES_WITH",
                        "uses",
                        "contains",
                        "CONTAINS",
                        "failover",
                        "integrates-with",
                        "tenant-resource-group-mapping",
                        "api-integration",
                        "dr-failover",
                        "identity-federation",
                        "integration",
                        "event_notification",
                        "identity_provider",
                        "cross_region_failover",
                        "multi_tenant_isolation",
                        "APIIntegration",
                        "Authentication",
                        "PrivateEndpoint",
                        "SingleSignOn",
                        "DR-Replication",
                        "backup",
                        "identity",
                        "data-lake-ingest",
                        "APIM Integration",
                        "FHIR Data Sync",
                        "Key Management",
                        "Data Write",
                        "resourceGroupHasResource",
                        "apiIntegration",
                        "disasterRecovery",
                        "identityFederation",
                        "geo_replication",
                        "reads",
                        "proxy",
                        "calls",
                        "triggers",
                        "exports",
                        "apim-integration",
                        "keyvault-access",
                        "log-access",
                        "geo-dr",
                        "geo-failover",
                        "monitors",
                        "key-vault-access",
                        "FHIR-to-SQL data sync",
                        "Orchestration-via-APIM",
                        "SIEM-data-ingest",
                        "WAF ingress routing",
                        "App authentication",
                    }
                    rel_type = rel.type
                    if rel_type not in allowed_types:
                        raise ValueError(
                            f"Relationship type '{rel_type}' is not allowed"
                        )

                    # Normalize relationship type for Neo4j (replace hyphens with underscores)
                    neo4j_rel_type = rel_type.replace("-", "_")

                    # Type checker: this is safe because rel_type is validated
                    cypher = f"""
                        MATCH (src {{id: $source_id}})
                        MATCH (tgt {{id: $target_id}})
                        MERGE (src)-[r:{neo4j_rel_type}]->(tgt)
                        """
                    session.run(
                        cypher,  # type: ignore
                        {
                            "source_id": rel.source_id,
                            "target_id": rel.target_id,
                        },
                    )

        print(f"✅ Tenant graph created: {getattr(tenant, 'display_name', tenant.id)}")
        session_manager.disconnect()
        return

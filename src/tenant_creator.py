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

IMPORTANT - Use only these relationship types in the relationships array:
- DEPENDS_ON: Resource dependencies (e.g., VM depends on Network)
- USES: General usage relationships (e.g., App uses Database)  
- CONNECTS_TO: Network connections (e.g., VPN connects to on-premises)
- CONTAINS: Hierarchical containment (e.g., Resource Group contains Resources)
- MEMBER_OF: Group membership (e.g., User member of Group)
- ASSIGNED_ROLE: RBAC assignments (e.g., User assigned Owner role)
- INTEGRATES_WITH: Service integrations (e.g., API Management integrates with backend)

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
- For relationships, use ONLY the relationship types listed above.
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
            model=getattr(self.llm_generator.config, "model_chat", "gpt-4.1"),
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert Azure cloud architect. Output only a single JSON object matching the required schema.",
                },
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=32768,
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
            spec = TenantSpec.parse_raw_json(json_text)
            # Mark this as not LLM-generated since it came from a JSON block
            spec._is_llm_generated = False
            return spec
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
        spec = TenantSpec.parse_raw_json(json_text)
        # Mark this as LLM-generated since it came from LLM processing
        spec._is_llm_generated = True
        return spec

    async def ingest_to_graph(self, spec: TenantSpec, is_llm_generated: bool = False) -> None:
        """
        Ingests the TenantSpec into Neo4j: creates Tenant, Subscriptions, Resources, Identities, RBAC, and Relationships.
        
        Args:
            spec: The tenant specification to ingest
            is_llm_generated: Whether this spec was generated by LLM (allows more permissive validation)
        """
        # (no longer need asyncio)

        tenant = spec.tenant
        print(f"DEBUG: spec.tenant has these attributes: {dir(tenant)}")
        print(f"DEBUG: tenant.users exists: {hasattr(tenant, 'users')}")
        print(f"DEBUG: tenant.groups exists: {hasattr(tenant, 'groups')}")
        print(f"DEBUG: tenant.service_principals exists: {hasattr(tenant, 'service_principals')}")
        print(f"DEBUG: tenant.subscriptions length: {len(tenant.subscriptions) if tenant.subscriptions else 0}")
        if tenant.subscriptions and len(tenant.subscriptions) > 0:
            first_sub = tenant.subscriptions[0]
            print(f"DEBUG: first subscription has resource_groups: {hasattr(first_sub, 'resource_groups')}")
            if hasattr(first_sub, 'resource_groups') and first_sub.resource_groups:
                print(f"DEBUG: first subscription resource_groups length: {len(first_sub.resource_groups)}")
        
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

        # 3. Create ResourceGroup nodes and flatten resources for processing
        resources = []
        print("DEBUG: Starting resource group and resource processing...")
        if tenant.subscriptions:
            for sub in tenant.subscriptions:
                print(f"DEBUG: Processing subscription {sub.id}")
                if sub.resource_groups:
                    print(f"DEBUG: Found {len(sub.resource_groups)} resource groups in subscription {sub.id}")
                    for rg in sub.resource_groups:
                        print(f"DEBUG: Creating ResourceGroup node: {rg.name}")
                        # Create ResourceGroup node
                        with session_manager.session() as session:
                            session.run(
                                """
                                MERGE (rg:ResourceGroup {id: $id})
                                SET rg.name = $name, rg.location = $location
                                WITH rg
                                MATCH (s:Subscription {id: $subscription_id})
                                MERGE (s)-[:CONTAINS]->(rg)
                                """,
                                {
                                    "id": rg.id,
                                    "name": rg.name,
                                    "location": getattr(rg, "location", "unknown"),
                                    "subscription_id": sub.id,
                                },
                            )
                        
                        if rg.resources:
                            print(f"DEBUG: Found {len(rg.resources)} resources in resource group {rg.name}")
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
                        else:
                            print(f"DEBUG: No resources found in resource group {rg.name}")
                else:
                    print(f"DEBUG: No resource groups found in subscription {sub.id}")

        print(f"DEBUG: Total resources to process: {len(resources)}")

        # 4. Process resources using ResourceProcessingService
        try:
            config = ProcessingConfig()
            rps = ResourceProcessingService(
                session_manager=session_manager,
                llm_generator=self.llm_generator,
                config=config,
            )
            await rps.process_resources(resources, progress_callback=None, max_workers=2)
            print("DEBUG: Resource processing completed successfully")
        except Exception as e:
            print(f"DEBUG: Error during resource processing: {e}")
            import traceback
            traceback.print_exc()

        # 5. Ingest identities
        print("DEBUG: Starting identity processing...")
        # If aad_graph_service is available, use it; otherwise, create minimal nodes
        aad_graph_service = getattr(self, "aad_graph_service", None)
        if aad_graph_service:
            print("DEBUG: Using AAD graph service for identity processing")
            # Use the db_ops from ResourceProcessor for upserts
            from src.resource_processor import ResourceProcessor

            processor = ResourceProcessor(session_manager, self.llm_generator, None)
            aad_graph_service.ingest_into_graph(processor.db_ops)
        else:
            print("DEBUG: Processing identities from tenant spec...")
            # Look for identities directly under tenant, not under spec.identities
            try:
                # Users
                if hasattr(tenant, 'users') and tenant.users:
                    print(f"DEBUG: Found {len(tenant.users)} users to process")
                    for user in tenant.users:
                        print(f"DEBUG: Creating user: {user.display_name}")
                        with session_manager.session() as session:
                            session.run(
                                """
                                MERGE (u:User {id: $id})
                                SET u.display_name = $display_name, 
                                    u.user_principal_name = $user_principal_name,
                                    u.job_title = $job_title
                                """,
                                {
                                    "id": user.id,
                                    "display_name": user.display_name,
                                    "user_principal_name": getattr(user, "user_principal_name", None),
                                    "job_title": getattr(user, "job_title", None),
                                },
                            )
                else:
                    print("DEBUG: No users found in tenant spec")
                
                # Groups
                if hasattr(tenant, 'groups') and tenant.groups:
                    print(f"DEBUG: Found {len(tenant.groups)} groups to process")
                    for group in tenant.groups:
                        print(f"DEBUG: Creating group: {group.display_name}")
                        with session_manager.session() as session:
                            session.run(
                                """
                                MERGE (g:IdentityGroup {id: $id})
                                SET g.display_name = $display_name
                                """,
                                {
                                    "id": group.id,
                                    "display_name": group.display_name,
                                },
                            )
                else:
                    print("DEBUG: No groups found in tenant spec")
                
                # Service Principals
                if hasattr(tenant, 'service_principals') and tenant.service_principals:
                    print(f"DEBUG: Found {len(tenant.service_principals)} service principals to process")
                    for sp in tenant.service_principals:
                        print(f"DEBUG: Creating service principal: {sp.display_name}")
                        with session_manager.session() as session:
                            session.run(
                                """
                                MERGE (sp:ServicePrincipal {id: $id})
                                SET sp.display_name = $display_name
                                """,
                                {
                                    "id": sp.id,
                                    "display_name": sp.display_name,
                                },
                            )
                else:
                    print("DEBUG: No service principals found in tenant spec")
                
                # Managed Identities
                if hasattr(tenant, 'managed_identities') and tenant.managed_identities:
                    print(f"DEBUG: Found {len(tenant.managed_identities)} managed identities to process")
                    for mi in tenant.managed_identities:
                        print(f"DEBUG: Creating managed identity: {mi.display_name}")
                        with session_manager.session() as session:
                            session.run(
                                """
                                MERGE (mi:ManagedIdentity {id: $id})
                                SET mi.display_name = $display_name
                                """,
                                {
                                    "id": mi.id,
                                    "display_name": mi.display_name,
                                },
                            )
                else:
                    print("DEBUG: No managed identities found in tenant spec")
                
                # Admin Units
                if hasattr(tenant, 'admin_units') and tenant.admin_units:
                    print(f"DEBUG: Found {len(tenant.admin_units)} admin units to process")
                    for au in tenant.admin_units:
                        print(f"DEBUG: Creating admin unit: {au.display_name}")
                        with session_manager.session() as session:
                            session.run(
                                """
                                MERGE (au:AdminUnit {id: $id})
                                SET au.display_name = $display_name
                                """,
                                {
                                    "id": au.id,
                                    "display_name": au.display_name,
                                },
                            )
                else:
                    print("DEBUG: No admin units found in tenant spec")
                    
            except Exception as e:
                print(f"DEBUG: Error during identity processing: {e}")
                import traceback
                traceback.print_exc()

        # 6. RBAC assignments
        print("DEBUG: Starting RBAC assignments processing...")
        try:
            rbac_assignments = None
            # Look for RBAC assignments directly under tenant
            if hasattr(tenant, "rbac_assignments") and tenant.rbac_assignments:
                rbac_assignments = tenant.rbac_assignments
                print(f"DEBUG: Found {len(rbac_assignments)} RBAC assignments to process")
            else:
                print("DEBUG: No RBAC assignments found in tenant spec")
                
            if rbac_assignments:
                for rbac in rbac_assignments:
                    print(f"DEBUG: Creating RBAC assignment: {rbac.principal_id} -> {getattr(rbac, 'role_definition_name', getattr(rbac, 'role', 'Unknown Role'))}")
                    with session_manager.session() as session:
                        session.run(
                            """
                            MATCH (p {id: $principal_id})
                            MATCH (s:Subscription {id: $scope})
                            MERGE (p)-[r:ASSIGNED_ROLE {role: $role}]->(s)
                            """,
                            {
                                "principal_id": rbac.principal_id,
                                "role": getattr(rbac, "role_definition_name", getattr(rbac, "role", "Unknown")),
                                "scope": rbac.scope,
                            },
                        )
        except Exception as e:
            print(f"DEBUG: Error during RBAC assignment processing: {e}")
            import traceback
            traceback.print_exc()

        # 7. Relationships
        print("DEBUG: Starting relationships processing...")
        try:
            relationships = None
            # Look for relationships directly under tenant
            if hasattr(tenant, "relationships") and tenant.relationships:
                relationships = tenant.relationships
                print(f"DEBUG: Found {len(relationships)} relationships to process")
            else:
                print("DEBUG: No relationships found in tenant spec")
                
            if relationships:
                for rel in relationships:
                    print(f"DEBUG: Processing relationship: {rel.source_id} -> {rel.target_id} ({rel.type})")
                    with session_manager.session() as session:
                        rel_type = rel.type
                        
                        # Core canonical relationship types that downstream systems understand
                        canonical_types = {
                            "CAN_READ_SECRET",
                            "MEMBER_OF", 
                            "ASSIGNED_ROLE",
                            "DEPENDS_ON",
                            "HAS_SUBSCRIPTION",
                            "HAS_RESOURCE_GROUP", 
                            "HAS_RESOURCE",
                            "CONNECTS_TO",
                            "USES",
                            "INTEGRATES_WITH",
                            "CONTAINS",
                            "USES_SUBNET",
                            "SECURED_BY",
                            "CONNECTED_TO_PE",
                            "RESOLVES_TO",
                            "GENERIC_RELATIONSHIP",  # Special type for preserving unknown relationships
                            "tenantHasSubscription",
                            "subscriptionContainsResourceGroup",
                            "resourceGroupContainsResource",
                            "userIsMemberOf"
                        }
                        
                        # Mapping for LLM-generated relationship types to canonical types
                        relationship_mappings = {
                            "onPremisesLink": "CONNECTS_TO",
                            "api-integration": "INTEGRATES_WITH",
                            "api_integration": "INTEGRATES_WITH",
                            "data-source": "DEPENDS_ON",
                            "data_source": "DEPENDS_ON",
                            "hybridConnectivity": "CONNECTS_TO",
                            "spoke-to-hub": "CONNECTS_TO",
                            "logging": "USES",
                            "writes": "USES",
                            "reads": "USES",
                            "publishes": "USES",
                            "sendsLogs": "USES",
                            "connects": "CONNECTS_TO",
                            "accesses": "USES",
                            "stores": "USES",
                            "retrieves": "USES",
                            "processes": "USES",
                            "monitors": "USES",
                            "protects": "USES",
                            "secures": "USES",
                            "authenticates": "USES",
                            "authorizes": "USES",
                            "logs": "USES",
                            "alerts": "USES",
                            "notifies": "USES"
                        }
                        
                        # For LLM-generated content, attempt to map to canonical types
                        if is_llm_generated and rel_type not in canonical_types:
                            if rel_type in relationship_mappings:
                                # Map to canonical type
                                canonical_rel_type = relationship_mappings[rel_type]
                                print(f"DEBUG: Mapping LLM relationship '{rel_type}' -> '{canonical_rel_type}'")
                                rel_type = canonical_rel_type
                            else:
                                # Block dangerous patterns
                                dangerous_patterns = ['DROP', 'DELETE', 'CREATE USER', 'GRANT', 'REVOKE', 'ALTER', 'EXEC']
                                if any(pattern in rel_type.upper() for pattern in dangerous_patterns):
                                    raise ValueError(
                                        f"Relationship type '{rel_type}' contains dangerous patterns and is not allowed"
                                    )
                                # Use GENERIC_RELATIONSHIP to preserve unknown types
                                print(f"DEBUG: Using GENERIC_RELATIONSHIP for unknown type '{rel_type}'")
                                original_rel_type = rel_type
                                rel_type = "GENERIC_RELATIONSHIP"
                        
                        # For manual specs, enforce strict validation
                        elif not is_llm_generated and rel_type not in canonical_types:
                            raise ValueError(
                                f"Relationship type '{rel_type}' is not allowed for manual specs. "
                                f"Allowed types: {sorted(canonical_types)}"
                            )

                        # Normalize relationship type for Neo4j (replace hyphens with underscores)
                        neo4j_rel_type = rel_type.replace("-", "_")

                        # Prepare relationship properties
                        rel_properties = {}
                        if rel_type == "GENERIC_RELATIONSHIP":
                            rel_properties["original_type"] = original_rel_type
                        if hasattr(rel, 'narrative_context') and rel.narrative_context:
                            rel_properties["narrative_context"] = rel.narrative_context
                        if hasattr(rel, 'original_type') and rel.original_type:
                            rel_properties["original_type"] = rel.original_type

                        # Build Cypher query with properties
                        if rel_properties:
                            props_cypher = ", ".join([f"r.{key} = ${key}" for key in rel_properties.keys()])
                            cypher = f"""
                                MATCH (src {{id: $source_id}})
                                MATCH (tgt {{id: $target_id}})
                                MERGE (src)-[r:{neo4j_rel_type}]->(tgt)
                                SET {props_cypher}
                                """
                            params = {
                                "source_id": rel.source_id,
                                "target_id": rel.target_id,
                                **rel_properties
                            }
                        else:
                            cypher = f"""
                                MATCH (src {{id: $source_id}})
                                MATCH (tgt {{id: $target_id}})
                                MERGE (src)-[r:{neo4j_rel_type}]->(tgt)
                                """
                            params = {
                                "source_id": rel.source_id,
                                "target_id": rel.target_id,
                            }

                        session.run(cypher, params)  # type: ignore
        except Exception as e:
            print(f"DEBUG: Error during relationships processing: {e}")
            import traceback
            traceback.print_exc()

        print(f"✅ Tenant graph created: {getattr(tenant, 'display_name', tenant.id)}")
        session_manager.disconnect()
        return

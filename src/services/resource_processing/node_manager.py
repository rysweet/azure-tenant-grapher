"""
Node Manager Module

This module handles all Neo4j node operations for resources using dual-graph architecture.
Creates both Original and Abstracted nodes for each resource.
"""

import hashlib
import json
import re
from typing import Any, Dict, Optional

import structlog

from src.exceptions import ResourceDataValidationError, wrap_neo4j_exception

from .serialization import serialize_value
from .validation import validate_resource_data

logger = structlog.get_logger(__name__)


class NodeManager:
    """Handles all database operations for resources using dual-graph architecture."""

    def __init__(
        self,
        session_manager: Any,
        tenant_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the NodeManager.

        Args:
            session_manager: Neo4jSessionManager instance
            tenant_id: Tenant ID for dual-graph architecture (optional, defaults to 'default-tenant')
        """
        self.session_manager = session_manager
        self.tenant_id = tenant_id or "default-tenant"
        self._tenant_seed_manager: Any = None
        self._id_abstraction_service: Any = None
        self._dual_graph_initialized = False

        # Try to initialize dual-graph services (may fail in tests)
        try:
            self._initialize_dual_graph_services()
        except Exception as e:
            logger.warning(f"Dual-graph services not initialized (expected in tests): {e}")
            # Set up fallback abstraction for tests
            self._setup_fallback_abstraction()

    def _initialize_dual_graph_services(self) -> None:
        """Initialize services needed for dual-graph architecture."""
        try:
            from src.services.id_abstraction_service import IDAbstractionService
            from src.services.tenant_seed_manager import TenantSeedManager

            # Initialize tenant seed manager
            self._tenant_seed_manager = TenantSeedManager(self.session_manager)

            # Get or create tenant seed
            tenant_seed = self._tenant_seed_manager.get_or_create_seed(self.tenant_id)

            # Initialize ID abstraction service
            self._id_abstraction_service = IDAbstractionService(
                tenant_seed=tenant_seed, hash_length=16
            )

            self._dual_graph_initialized = True
            logger.info(f"Initialized dual-graph services for tenant {self.tenant_id}")

        except Exception as e:
            logger.exception(f"Failed to initialize dual-graph services: {e}")
            raise

    def _setup_fallback_abstraction(self) -> None:
        """Set up fallback abstraction service for tests without full dual-graph services."""

        class FallbackAbstractionService:
            """Simple fallback abstraction for tests."""

            def abstract_resource_id(self, resource_id: str) -> str:
                """Create a simple hash-based abstraction of the resource ID."""
                # Extract resource type for prefix
                parts = resource_id.lower().split("/providers/")
                if len(parts) > 1:
                    type_part = parts[1].split("/")[0]
                    if "compute" in type_part:
                        prefix = "vm"
                    elif "storage" in type_part:
                        prefix = "storage"
                    elif "network" in type_part:
                        prefix = "net"
                    else:
                        prefix = "resource"
                else:
                    prefix = "resource"

                hash_val = hashlib.sha256(resource_id.encode()).hexdigest()[:16]
                return f"{prefix}-{hash_val}"

            def abstract_principal_id(self, principal_id: str) -> str:
                """Create a simple hash-based abstraction of the principal ID."""
                hash_val = hashlib.sha256(principal_id.encode()).hexdigest()[:16]
                return f"principal-{hash_val}"

        self._id_abstraction_service = FallbackAbstractionService()
        logger.info("Set up fallback abstraction service for testing")

    def upsert_subscription(
        self, subscription_id: str, subscription_name: str = ""
    ) -> bool:
        """
        Create or update a Subscription node.

        Args:
            subscription_id: Azure subscription ID
            subscription_name: Display name of the subscription

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            query = """
            MERGE (s:Subscription {id: $id})
            SET s.name = $name,
                s.updated_at = datetime()
            """
            with self.session_manager.session() as session:
                session.run(query, id=subscription_id, name=subscription_name)
            return True
        except Exception:
            logger.exception(f"Error upserting Subscription node {subscription_id}")
            return False

    def upsert_resource_group(
        self, rg_id: str, rg_name: str, subscription_id: str
    ) -> bool:
        """
        Create or update a ResourceGroup node with unique id, name, and subscription_id.

        Args:
            rg_id: Full Azure resource group ID
            rg_name: Resource group name
            subscription_id: Parent subscription ID

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            query = """
            MERGE (rg:ResourceGroup {id: $id})
            SET rg.name = $name,
                rg.subscription_id = $subscription_id,
                rg.type = 'ResourceGroup',
                rg.updated_at = datetime(),
                rg.llm_description = coalesce(rg.llm_description, '')
            """
            with self.session_manager.session() as session:
                session.run(
                    query, id=rg_id, name=rg_name, subscription_id=subscription_id
                )
            return True
        except Exception:
            logger.exception(f"Error upserting ResourceGroup node {rg_id}")
            return False

    def upsert_resource(
        self, resource: Dict[str, Any], processing_status: str = "completed"
    ) -> bool:
        """
        Create or update both Original and Abstracted nodes for a resource in Neo4j.

        Creates dual-graph nodes:
        1. Original node (:Resource:Original) with real Azure IDs
        2. Abstracted node (:Resource) with type-prefixed hash IDs
        3. SCAN_SOURCE_NODE relationship linking them

        Args:
            resource: Resource dictionary
            processing_status: Status of processing (pending, processing, completed, failed)

        Returns:
            bool: True if successful, False otherwise
        """
        return self._upsert_dual_graph_resource(resource, processing_status)

    def _upsert_dual_graph_resource(
        self, resource: Dict[str, Any], processing_status: str = "completed"
    ) -> bool:
        """
        Create or update both Original and Abstracted nodes for a resource.

        This implements the dual-graph architecture where every resource exists as:
        1. Original node (:Resource:Original) with real Azure IDs
        2. Abstracted node (:Resource) with type-prefixed hash IDs
        3. SCAN_SOURCE_NODE relationship linking them

        Args:
            resource: Resource dictionary
            processing_status: Status of processing

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate resource data
            try:
                validate_resource_data(resource)
            except ResourceDataValidationError as e:
                logger.exception(
                    f"Resource data missing/null for required fields: {e.missing_fields} (resource: {resource})"
                )
                return False

            # Upsert Subscription node before relationships
            self.upsert_subscription(resource["subscription_id"])

            # Generate abstracted ID
            if not self._id_abstraction_service:
                raise ValueError("ID abstraction service not initialized")

            original_id = resource["id"]
            abstracted_id = self._id_abstraction_service.abstract_resource_id(
                original_id
            )

            logger.debug(
                f"Dual-graph: original_id={original_id}, abstracted_id={abstracted_id}"
            )

            # Prepare resource data (common properties)
            resource_data = resource.copy()
            resource_data["llm_description"] = resource.get("llm_description", "")
            resource_data["processing_status"] = processing_status

            # Extract critical VNet properties BEFORE serialization
            if resource_data.get("type") == "Microsoft.Network/virtualNetworks":
                properties_raw = resource_data.get("properties")
                if properties_raw:
                    try:
                        if isinstance(properties_raw, dict):
                            props_dict = properties_raw
                        elif isinstance(properties_raw, str):
                            props_dict = json.loads(properties_raw)
                        else:
                            props_dict = {}

                        address_space = props_dict.get("addressSpace", {})
                        if address_space:
                            address_prefixes = address_space.get("addressPrefixes", [])
                            if address_prefixes:
                                resource_data["addressSpace"] = json.dumps(
                                    address_prefixes
                                )
                                logger.debug(
                                    f"Extracted addressSpace for VNet '{resource.get('name')}': {address_prefixes}"
                                )
                    except (json.JSONDecodeError, AttributeError, TypeError) as e:
                        logger.warning(
                            f"Failed to extract addressSpace from VNet '{resource.get('name')}': {e}"
                        )

            # Prevent empty properties from overwriting existing data
            if resource_data.get("properties") == {}:
                logger.debug(
                    f"Skipping empty properties update for {resource.get('id')} to preserve existing data"
                )
                resource_data.pop("properties", None)

            # Serialize all values for Neo4j compatibility
            try:
                serialized_data = {}
                for k, v in resource_data.items():
                    serialized_data[k] = serialize_value(v)
            except Exception as ser_exc:
                logger.exception(
                    f"Serialization error for resource {resource.get('id', 'Unknown')}: {ser_exc}"
                )
                return False

            # Create both nodes in a single transaction for atomicity
            try:
                with self.session_manager.session() as session:
                    with session.begin_transaction() as tx:
                        # Create Original node
                        self._create_original_node(
                            tx, original_id, abstracted_id, serialized_data
                        )

                        # Create Abstracted node
                        self._create_abstracted_node(
                            tx, abstracted_id, original_id, serialized_data
                        )

                        # Create SCAN_SOURCE_NODE relationship
                        self._create_scan_source_relationship(
                            tx,
                            abstracted_id,
                            original_id,
                            resource.get("scan_id"),
                            resource.get("tenant_id"),
                        )

                        tx.commit()

                logger.debug(
                    f"Successfully created dual-graph nodes for {resource.get('name')}"
                )
                return True

            except Exception as neo4j_exc:
                logger.error(
                    f"Neo4j dual-graph upsert error for resource {resource.get('id', 'Unknown')}: {neo4j_exc}"
                )
                wrapped_exc = wrap_neo4j_exception(
                    neo4j_exc, context={"resource_id": resource.get("id", "Unknown")}
                )
                logger.error(str(wrapped_exc))
                return False

        except ResourceDataValidationError:
            # Already logged above
            return False
        except Exception as exc:
            logger.exception(
                f"Error creating dual-graph resource {resource.get('id', 'Unknown')}: {exc}"
            )
            return False

    def _create_original_node(
        self, tx: Any, original_id: str, abstracted_id: str, properties: Dict[str, Any]
    ) -> None:
        """Create the Original node with real Azure IDs."""
        query = """
        MERGE (r:Resource:Original {id: $original_id})
        SET r += $props,
            r.id = $original_id,
            r.abstracted_id = $abstracted_id,
            r.updated_at = datetime()
        """
        tx.run(
            query,
            original_id=original_id,
            props=properties,
            abstracted_id=abstracted_id,
        )

    def _create_abstracted_node(
        self, tx: Any, abstracted_id: str, original_id: str, properties: Dict[str, Any]
    ) -> None:
        """Create the Abstracted node with hash IDs."""
        # Create a copy of properties with abstracted ID
        abstracted_props = properties.copy()
        abstracted_props["id"] = abstracted_id

        # Store reference to original ID
        abstracted_props["original_id"] = original_id

        # Add abstraction metadata
        abstracted_props["abstracted_id"] = abstracted_id
        prefix = abstracted_id.split("-")[0] if "-" in abstracted_id else "resource"
        abstracted_props["abstraction_type"] = prefix

        # Bug #52: Abstract principal IDs for role assignments
        resource_type = properties.get("type", "")
        if resource_type == "Microsoft.Authorization/roleAssignments":
            self._abstract_role_assignment_properties(abstracted_id, abstracted_props)

        query = """
        MERGE (r:Resource {id: $abstracted_id})
        SET r += $props,
            r.id = $abstracted_id,
            r.original_id = $original_id,
            r.abstracted_id = $abstracted_id,
            r.abstraction_type = $abstraction_type,
            r.updated_at = datetime()
        """
        tx.run(
            query,
            abstracted_id=abstracted_id,
            original_id=original_id,
            abstraction_type=prefix,
            props=abstracted_props,
        )

    def _abstract_role_assignment_properties(
        self, abstracted_id: str, abstracted_props: Dict[str, Any]
    ) -> None:
        """
        Abstract principal IDs and subscription IDs for role assignments.

        Bug #52: Abstract principal IDs for role assignments
        Bug #59: Abstract subscription IDs in roleDefinitionId and scope
        """
        props_field = abstracted_props.get("properties")
        if not props_field:
            return

        try:
            # Parse properties if it's a JSON string
            if isinstance(props_field, str):
                props_dict = json.loads(props_field)
            else:
                props_dict = props_field.copy() if isinstance(props_field, dict) else {}

            # Abstract the principalId if present
            original_principal_id = props_dict.get("principalId")
            if original_principal_id:
                if self._id_abstraction_service:
                    try:
                        abstracted_principal_id = (
                            self._id_abstraction_service.abstract_principal_id(
                                original_principal_id
                            )
                        )
                        props_dict["principalId"] = abstracted_principal_id
                        logger.debug(
                            f"Abstracted principalId for role assignment {abstracted_id}: "
                            f"{original_principal_id[:8]}... -> {abstracted_principal_id}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to abstract principalId for role assignment {abstracted_id}: {e}"
                        )

            # Bug #59: Abstract subscription IDs in roleDefinitionId and scope
            subscription_pattern = re.compile(
                r"/subscriptions/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                re.IGNORECASE,
            )

            # Abstract roleDefinitionId
            role_def_id = props_dict.get("roleDefinitionId")
            if role_def_id and isinstance(role_def_id, str):
                abstracted_role_def_id = subscription_pattern.sub(
                    "/subscriptions/ABSTRACT_SUBSCRIPTION", role_def_id
                )
                if abstracted_role_def_id != role_def_id:
                    props_dict["roleDefinitionId"] = abstracted_role_def_id
                    logger.debug(
                        f"Abstracted subscription in roleDefinitionId for {abstracted_id}"
                    )

            # Abstract scope
            scope = props_dict.get("scope")
            if scope and isinstance(scope, str):
                abstracted_scope = subscription_pattern.sub(
                    "/subscriptions/ABSTRACT_SUBSCRIPTION", scope
                )
                if abstracted_scope != scope:
                    props_dict["scope"] = abstracted_scope
                    logger.debug(
                        f"Abstracted subscription in scope for {abstracted_id}"
                    )

            # Update the abstracted_props with the modified properties
            if isinstance(props_field, str):
                # Convert back to JSON string if it was originally a string
                abstracted_props["properties"] = json.dumps(props_dict, default=str)
            else:
                abstracted_props["properties"] = props_dict

        except json.JSONDecodeError as e:
            logger.warning(
                f"Failed to parse properties JSON for role assignment {abstracted_id}: {e}"
            )
        except Exception as e:
            logger.warning(
                f"Error processing principalId abstraction for role assignment {abstracted_id}: {e}"
            )

    def _create_scan_source_relationship(
        self,
        tx: Any,
        abstracted_id: str,
        original_id: str,
        scan_id: Optional[str],
        tenant_id: Optional[str],
    ) -> None:
        """Create SCAN_SOURCE_NODE relationship from abstracted to original."""
        query = """
        MATCH (abs:Resource {id: $abstracted_id})
        MATCH (orig:Resource:Original {id: $original_id})
        MERGE (abs)-[rel:SCAN_SOURCE_NODE]->(orig)
        SET rel.created_at = datetime(),
            rel.scan_id = $scan_id,
            rel.tenant_id = $tenant_id,
            rel.confidence = 'exact'
        """
        tx.run(
            query,
            abstracted_id=abstracted_id,
            original_id=original_id,
            scan_id=scan_id,
            tenant_id=tenant_id,
        )


# Backward compatibility alias
DatabaseOperations = NodeManager

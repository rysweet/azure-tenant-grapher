"""
Dual-Graph Implementation Example

This module provides example code showing how to implement the dual-graph
architecture in the resource processing pipeline.

NOTE: This is a design reference, not production code. Actual implementation
will be integrated into existing resource_processor.py and relationship rules.
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# 1. ABSTRACTION SERVICE - Generate deterministic IDs
# ============================================================================


@dataclass
class AbstractionConfig:
    """Configuration for abstraction ID generation."""

    algorithm: str = "sha256"
    hash_length: int = 8
    include_type_prefix: bool = True
    collision_detection: bool = True


class AbstractionIDGenerator:
    """
    Generates deterministic, type-prefixed hash IDs for Azure resources.

    Examples:
        vm-a1b2c3d4 (Virtual Machine)
        storage-e5f6g7h8 (Storage Account)
        nsg-1a2b3c4d (Network Security Group)
    """

    # Type prefix mapping for common Azure resource types
    TYPE_PREFIXES = {
        "Microsoft.Compute/virtualMachines": "vm",
        "Microsoft.Storage/storageAccounts": "storage",
        "Microsoft.Network/networkSecurityGroups": "nsg",
        "Microsoft.Network/virtualNetworks": "vnet",
        "Microsoft.Network/subnets": "subnet",
        "Microsoft.Network/publicIPAddresses": "pip",
        "Microsoft.Network/loadBalancers": "lb",
        "Microsoft.Sql/servers": "sql",
        "Microsoft.KeyVault/vaults": "kv",
        "Microsoft.ContainerRegistry/registries": "acr",
        "Microsoft.Web/sites": "app",
        "Microsoft.Insights/components": "appinsights",
        # Add more as needed
    }

    def __init__(self, tenant_seed: str, config: Optional[AbstractionConfig] = None):
        """
        Initialize the generator with a tenant-specific seed.

        Args:
            tenant_seed: Unique seed for this tenant (from Tenant node)
            config: Optional configuration overrides
        """
        self.tenant_seed = tenant_seed
        self.config = config or AbstractionConfig()

    def generate_id(self, resource: Dict[str, Any]) -> str:
        """
        Generate a deterministic abstracted ID for a resource.

        Args:
            resource: Resource dictionary with Azure metadata

        Returns:
            str: Abstracted ID (e.g., "vm-a1b2c3d4")

        Raises:
            ValueError: If required resource properties are missing
        """
        # Validate required properties
        if not resource.get("id"):
            raise ValueError("Resource must have 'id' property")
        if not resource.get("type"):
            raise ValueError("Resource must have 'type' property")

        # Get type prefix
        prefix = self._get_type_prefix(resource["type"])

        # Generate hash from Azure resource ID + tenant seed
        hash_input = f"{resource['id']}:{self.tenant_seed}"
        hash_value = self._compute_hash(hash_input)

        # Combine prefix and hash
        abstracted_id = f"{prefix}-{hash_value}"

        logger.debug(
            f"Generated abstracted ID: {abstracted_id} for resource: {resource['id']}"
        )

        return abstracted_id

    def _get_type_prefix(self, resource_type: str) -> str:
        """
        Get the type prefix for a resource type.

        Args:
            resource_type: Azure resource type (e.g., "Microsoft.Compute/virtualMachines")

        Returns:
            str: Type prefix (e.g., "vm")
        """
        prefix = self.TYPE_PREFIXES.get(resource_type)

        if not prefix:
            # Fallback: use last segment of type, sanitized
            # Example: "Microsoft.Network/privateEndpoints" -> "privateendpoint"
            last_segment = resource_type.split("/")[-1].lower()
            # Remove special characters, keep only alphanumeric
            prefix = "".join(c for c in last_segment if c.isalnum())
            logger.warning(
                f"No prefix mapping for type {resource_type}, using {prefix}"
            )

        return prefix

    def _compute_hash(self, input_string: str) -> str:
        """
        Compute a hash of the input string.

        Args:
            input_string: String to hash

        Returns:
            str: Truncated hash (e.g., "a1b2c3d4")
        """
        hash_obj = hashlib.sha256(input_string.encode("utf-8"))
        hash_hex = hash_obj.hexdigest()

        # Truncate to configured length
        return hash_hex[: self.config.hash_length]


# ============================================================================
# 2. DUAL-GRAPH DATABASE OPERATIONS
# ============================================================================


class DualGraphDatabaseOperations:
    """
    Database operations for dual-graph architecture.
    Extends existing DatabaseOperations class.
    """

    def __init__(
        self,
        session_manager: Any,
        abstraction_generator: Optional[AbstractionIDGenerator] = None,
    ):
        self.session_manager = session_manager
        self.abstraction_generator = abstraction_generator

    def upsert_dual_graph_resource(
        self, resource: Dict[str, Any], processing_status: str = "completed"
    ) -> tuple[bool, str]:
        """
        Create or update both Original and Abstracted nodes for a resource.

        This is the main entry point for dual-graph resource creation.

        Args:
            resource: Resource dictionary with Azure metadata
            processing_status: Processing status for the resource

        Returns:
            tuple: (success: bool, abstracted_id: str)
        """
        try:
            # Generate abstracted ID
            if not self.abstraction_generator:
                raise ValueError("AbstractionIDGenerator not configured")

            abstracted_id = self.abstraction_generator.generate_id(resource)
            original_id = resource["id"]

            # Create both nodes in a transaction for atomicity
            with self.session_manager.session() as session:
                with session.begin_transaction() as tx:
                    # Create Original node
                    self._create_original_node(
                        tx, resource, abstracted_id, processing_status
                    )

                    # Create Abstracted node
                    self._create_abstracted_node(
                        tx, resource, abstracted_id, original_id, processing_status
                    )

                    # Create SCAN_SOURCE_NODE relationship
                    self._create_scan_source_relationship(
                        tx, abstracted_id, original_id, resource.get("scan_id")
                    )

                    tx.commit()

            logger.info(
                f"Successfully created dual-graph nodes: "
                f"abstracted={abstracted_id}, original={original_id}"
            )
            return True, abstracted_id

        except Exception as e:
            logger.exception(f"Failed to create dual-graph resource: {e}")
            return False, ""

    def _create_original_node(
        self,
        tx: Any,
        resource: Dict[str, Any],
        abstracted_id: str,
        processing_status: str,
    ) -> None:
        """Create the Original node (Azure resource ID)."""
        query = """
        MERGE (r:Resource:Original {id: $props.id})
        SET r += $props,
            r.abstracted_id = $abstracted_id,
            r.updated_at = datetime()
        """

        resource_data = resource.copy()
        resource_data["llm_description"] = resource.get("llm_description", "")
        resource_data["processing_status"] = processing_status

        tx.run(
            query,
            props=self._serialize_properties(resource_data),
            abstracted_id=abstracted_id,
        )

    def _create_abstracted_node(
        self,
        tx: Any,
        resource: Dict[str, Any],
        abstracted_id: str,
        original_id: str,
        processing_status: str,
    ) -> None:
        """Create the Abstracted node (hash ID)."""
        query = """
        MERGE (r:Resource:Abstracted {id: $abstracted_id})
        SET r += $props,
            r.abstracted_id = $abstracted_id,
            r.original_id = $original_id,
            r.abstraction_type = $abstraction_type,
            r.abstraction_seed = $abstraction_seed,
            r.updated_at = datetime()
        """

        # Create abstracted resource data (may filter out sensitive properties)
        resource_data = self._create_abstracted_properties(resource)
        resource_data["id"] = abstracted_id  # Override ID with abstracted ID
        resource_data["llm_description"] = resource.get("llm_description", "")
        resource_data["processing_status"] = processing_status

        # Extract type prefix for metadata
        abstraction_type = abstracted_id.split("-")[0] if "-" in abstracted_id else ""

        tx.run(
            query,
            abstracted_id=abstracted_id,
            props=self._serialize_properties(resource_data),
            original_id=original_id,
            abstraction_type=abstraction_type,
            abstraction_seed=self.abstraction_generator.tenant_seed,
        )

    def _create_scan_source_relationship(
        self, tx: Any, abstracted_id: str, original_id: str, scan_id: Optional[str]
    ) -> None:
        """Create the SCAN_SOURCE_NODE relationship."""
        query = """
        MATCH (abs:Abstracted {id: $abstracted_id})
        MATCH (orig:Original {id: $original_id})
        MERGE (abs)-[rel:SCAN_SOURCE_NODE]->(orig)
        SET rel.created_at = datetime(),
            rel.scan_id = $scan_id,
            rel.confidence = 'exact'
        """

        tx.run(
            query,
            abstracted_id=abstracted_id,
            original_id=original_id,
            scan_id=scan_id,
        )

    def _create_abstracted_properties(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create properties for the abstracted node.

        This method can filter out sensitive data or reduce property size
        for the abstracted view.

        Args:
            resource: Original resource dictionary

        Returns:
            Dict: Filtered properties for abstracted node
        """
        # For now, copy most properties
        # In the future, you might want to:
        # 1. Exclude sensitive properties (passwords, keys, etc.)
        # 2. Reduce property size (summarize large JSON blobs)
        # 3. Normalize property formats

        # List of properties to exclude from abstracted view
        SENSITIVE_PROPERTIES = [
            "access_key",
            "secret",
            "password",
            "connection_string",
            # Add more as needed
        ]

        abstracted = {}
        for key, value in resource.items():
            if key not in SENSITIVE_PROPERTIES:
                abstracted[key] = value

        return abstracted

    def _serialize_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize properties for Neo4j storage.
        This would call the existing serialize_value function.
        """
        # In real implementation, use the existing serialize_value from resource_processor.py
        return properties

    def get_abstracted_id(self, original_id: str) -> Optional[str]:
        """
        Get the abstracted ID for a given original (Azure) resource ID.

        Args:
            original_id: Azure resource ID

        Returns:
            Optional[str]: Abstracted ID, or None if not found
        """
        try:
            with self.session_manager.session() as session:
                result = session.run(
                    """
                    MATCH (orig:Original {id: $original_id})
                    RETURN orig.abstracted_id as abstracted_id
                    """,
                    original_id=original_id,
                )
                record = result.single()
                return record["abstracted_id"] if record else None
        except Exception:
            logger.exception(f"Error looking up abstracted ID for {original_id}")
            return None

    def create_dual_graph_rel(
        self,
        src_original_id: str,
        rel_type: str,
        tgt_original_id: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create a relationship in both Original and Abstracted graphs.

        This is the key helper function for relationship rules.

        Args:
            src_original_id: Source resource Azure ID
            rel_type: Relationship type (e.g., "USES_SUBNET")
            tgt_original_id: Target resource Azure ID
            properties: Optional relationship properties

        Returns:
            bool: True if both relationships created successfully
        """
        try:
            # Create relationship in Original graph
            orig_success = self._create_single_rel(
                src_original_id,
                rel_type,
                tgt_original_id,
                "Original",
                properties,
            )

            # Look up abstracted IDs
            src_abstracted = self.get_abstracted_id(src_original_id)
            tgt_abstracted = self.get_abstracted_id(tgt_original_id)

            # Create relationship in Abstracted graph
            abs_success = False
            if src_abstracted and tgt_abstracted:
                abs_success = self._create_single_rel(
                    src_abstracted,
                    rel_type,
                    tgt_abstracted,
                    "Abstracted",
                    properties,
                )
            else:
                logger.warning(
                    f"Could not create abstracted relationship: "
                    f"src={src_abstracted}, tgt={tgt_abstracted}"
                )

            return orig_success and abs_success

        except Exception:
            logger.exception(
                f"Error creating dual-graph relationship: {rel_type} "
                f"from {src_original_id} to {tgt_original_id}"
            )
            return False

    def _create_single_rel(
        self,
        src_id: str,
        rel_type: str,
        tgt_id: str,
        label: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create a single relationship in one graph (Original or Abstracted).

        Args:
            src_id: Source node ID
            rel_type: Relationship type
            tgt_id: Target node ID
            label: Node label filter ("Original" or "Abstracted")
            properties: Optional relationship properties

        Returns:
            bool: True if successful
        """
        try:
            # Build properties clause
            props_clause = ""
            if properties:
                props_clause = "SET rel += $props"

            query = f"""
            MATCH (src:{label} {{id: $src_id}})
            MATCH (tgt:{label} {{id: $tgt_id}})
            MERGE (src)-[rel:{rel_type}]->(tgt)
            {props_clause}
            """

            with self.session_manager.session() as session:
                session.run(
                    query,
                    src_id=src_id,
                    tgt_id=tgt_id,
                    props=properties or {},
                )
            return True

        except Exception:
            logger.exception(
                f"Error creating {label} relationship {rel_type} "
                f"from {src_id} to {tgt_id}"
            )
            return False


# ============================================================================
# 3. TENANT SEED MANAGEMENT
# ============================================================================


class TenantSeedManager:
    """Manages abstraction seeds for tenants."""

    def __init__(self, session_manager: Any):
        self.session_manager = session_manager

    def get_or_create_seed(self, tenant_id: str) -> str:
        """
        Get the existing abstraction seed for a tenant, or create a new one.

        Args:
            tenant_id: Tenant ID

        Returns:
            str: Abstraction seed
        """
        try:
            with self.session_manager.session() as session:
                # Try to get existing seed
                result = session.run(
                    """
                    MATCH (t:Tenant {id: $tenant_id})
                    RETURN t.abstraction_seed as seed
                    """,
                    tenant_id=tenant_id,
                )
                record = result.single()

                if record and record["seed"]:
                    logger.info(f"Using existing seed for tenant {tenant_id}")
                    return record["seed"]

                # Generate new seed
                new_seed = self._generate_seed()

                # Store seed on Tenant node
                session.run(
                    """
                    MERGE (t:Tenant {id: $tenant_id})
                    SET t.abstraction_seed = $seed,
                        t.seed_created_at = datetime(),
                        t.seed_algorithm = 'sha256-truncated'
                    """,
                    tenant_id=tenant_id,
                    seed=new_seed,
                )

                logger.info(f"Created new seed for tenant {tenant_id}")
                return new_seed

        except Exception:
            logger.exception(f"Error managing seed for tenant {tenant_id}")
            raise

    def _generate_seed(self) -> str:
        """
        Generate a new random seed.

        Returns:
            str: Random seed string
        """
        import secrets

        # Generate 32 bytes of random data, hex encode
        return secrets.token_hex(32)


# ============================================================================
# 4. RELATIONSHIP RULE EXAMPLE
# ============================================================================


class DualGraphNetworkRule:
    """
    Example of how to modify a relationship rule for dual-graph architecture.

    This shows the pattern for updating existing relationship rules.
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        """Check if this rule applies to the resource."""
        rtype = resource.get("type", "")
        return rtype.endswith("virtualMachines") or rtype.endswith("subnets")

    def emit(
        self, resource: Dict[str, Any], db_ops: DualGraphDatabaseOperations
    ) -> None:
        """
        Emit network relationships in both graphs.

        This is the key change: instead of creating relationships directly,
        we use the dual-graph helper function.
        """
        rid = resource.get("id")
        rtype = resource.get("type", "")

        # (VirtualMachine) -[:USES_SUBNET]-> (Subnet)
        if rtype.endswith("virtualMachines") and "network_profile" in resource:
            nics = resource["network_profile"].get("network_interfaces", [])
            for nic in nics:
                ip_cfgs = nic.get("ip_configurations", [])
                for ipcfg in ip_cfgs:
                    subnet = ipcfg.get("subnet")
                    if subnet and isinstance(subnet, dict):
                        subnet_id = subnet.get("id")
                        if subnet_id and rid:
                            # OLD WAY (single graph):
                            # db_ops.create_generic_rel(
                            #     str(rid), "USES_SUBNET", str(subnet_id), "Resource", "id"
                            # )

                            # NEW WAY (dual graph):
                            db_ops.create_dual_graph_rel(
                                str(rid),
                                "USES_SUBNET",
                                str(subnet_id),
                            )

        # (Subnet) -[:SECURED_BY]-> (NetworkSecurityGroup)
        if rtype.endswith("subnets"):
            nsg = resource.get("network_security_group")
            if nsg and isinstance(nsg, dict):
                nsg_id = nsg.get("id")
                if nsg_id and rid:
                    # NEW WAY (dual graph):
                    db_ops.create_dual_graph_rel(
                        str(rid),
                        "SECURED_BY",
                        str(nsg_id),
                    )


# ============================================================================
# 5. USAGE EXAMPLE
# ============================================================================


def example_usage():
    """
    Example showing how to use the dual-graph architecture.

    This would be integrated into the existing ResourceProcessor.
    """
    from src.utils.session_manager import Neo4jSessionManager

    # Initialize components
    session_manager = Neo4jSessionManager("bolt://localhost:7687", "neo4j", "password")

    # Get or create tenant seed
    seed_manager = TenantSeedManager(session_manager)
    tenant_id = "/providers/Microsoft.Management/managementGroups/tenant-123"
    tenant_seed = seed_manager.get_or_create_seed(tenant_id)

    # Initialize abstraction generator
    abstraction_config = AbstractionConfig(hash_length=8, include_type_prefix=True)
    abstraction_generator = AbstractionIDGenerator(tenant_seed, abstraction_config)

    # Initialize dual-graph database operations
    db_ops = DualGraphDatabaseOperations(session_manager, abstraction_generator)

    # Example: Process a virtual machine resource
    vm_resource = {
        "id": "/subscriptions/sub-123/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/web-vm-001",
        "name": "web-vm-001",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "resource_group": "rg-prod",
        "subscription_id": "/subscriptions/sub-123",
        "tenant_id": tenant_id,
        "scan_id": "scan-2025-11-05-12345",
        "properties": {"vmSize": "Standard_D2s_v3"},
    }

    # Create dual-graph nodes
    success, abstracted_id = db_ops.upsert_dual_graph_resource(vm_resource)

    if success:
        print(f"Created dual-graph resource: {abstracted_id}")

        # Example: Create a relationship
        subnet_id = "/subscriptions/sub-123/resourceGroups/rg-prod/providers/Microsoft.Network/virtualNetworks/vnet-prod/subnets/subnet-web"

        db_ops.create_dual_graph_rel(
            vm_resource["id"],
            "USES_SUBNET",
            subnet_id,
        )

        print("Created dual-graph relationship")


# ============================================================================
# 6. INTEGRATION POINTS
# ============================================================================


class DualGraphIntegrationNotes:
    """
    Notes on how to integrate dual-graph into existing codebase.

    Changes needed in existing files:
    -----------------------------------

    1. src/resource_processor.py:
       - Add feature flag: ENABLE_DUAL_GRAPH
       - Modify DatabaseOperations.upsert_resource() to call upsert_dual_graph_resource()
       - Add TenantSeedManager initialization in ResourceProcessor.__init__()
       - Add AbstractionIDGenerator initialization

    2. src/relationship_rules/*.py:
       - Modify each rule's emit() method to use create_dual_graph_rel()
       - Alternative: Create wrapper in base RelationshipRule class

    3. src/iac/traverser.py:
       - Add filter to only query Abstracted nodes
       - Update all MATCH queries to include: WHERE NOT r:Original

    4. src/config_manager.py:
       - Add ENABLE_DUAL_GRAPH configuration option
       - Default to False for backward compatibility

    5. migrations/:
       - Add 0010_dual_graph_schema.cypher (already created)
       - Run migration before enabling feature flag

    6. tests/:
       - Add tests for AbstractionIDGenerator
       - Add tests for dual-graph node creation
       - Add tests for relationship duplication
       - Add tests for backward compatibility

    Configuration:
    --------------
    export ENABLE_DUAL_GRAPH=true  # Enable dual-graph mode
    export ABSTRACTION_HASH_LENGTH=8  # Hash length (default: 8)

    Deployment sequence:
    --------------------
    1. Deploy code with ENABLE_DUAL_GRAPH=false
    2. Run migration 0010
    3. Test on staging with ENABLE_DUAL_GRAPH=true
    4. Deploy to production with ENABLE_DUAL_GRAPH=false
    5. Run migration 0010 on production
    6. Enable ENABLE_DUAL_GRAPH=true on production
    7. Monitor for issues
    8. After stabilization, make true the default
    """

    pass


if __name__ == "__main__":
    # This is example code only
    print("This is a design reference. See docstring for integration notes.")
    print("Key classes:")
    print("  - AbstractionIDGenerator: Generate deterministic hash IDs")
    print(
        "  - DualGraphDatabaseOperations: Create nodes and relationships in both graphs"
    )
    print("  - TenantSeedManager: Manage per-tenant abstraction seeds")
    print("  - DualGraphNetworkRule: Example of modified relationship rule")

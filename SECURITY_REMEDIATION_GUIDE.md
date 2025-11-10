# Security Remediation Guide for PR #435

This guide provides specific code changes required to remediate all critical and high severity security vulnerabilities found in the scale operations implementation.

---

## Critical Priority Fixes (Block Merge)

### Fix 1: Cypher Injection in scale_up_service.py

#### Location: Lines 589-603 (`_get_base_resources` method)

**Current Vulnerable Code:**
```python
def _get_base_resources(
    self, tenant_id: str, resource_types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    type_filter = ""
    if resource_types:
        # VULNERABLE: Direct string interpolation
        type_list = ", ".join(f"'{t}'" for t in resource_types)
        type_filter = f"AND r.type IN [{type_list}]"

    query = f"""
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.tenant_id = $tenant_id
          AND (r.synthetic IS NULL OR r.synthetic = false)
          {type_filter}
        RETURN r.id as id, r.type as type, properties(r) as props
        LIMIT 10000
    """

    with self.session_manager.session() as session:
        result = session.run(query, {"tenant_id": tenant_id})
        resources = [
            {"id": record["id"], "type": record["type"], "props": record["props"]}
            for record in result
        ]

    return resources
```

**Secure Fixed Code:**
```python
async def _get_base_resources(
    self, tenant_id: str, resource_types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Get base resources from abstracted layer for template replication.

    Args:
        tenant_id: Azure tenant ID
        resource_types: Optional list of resource types to filter

    Returns:
        List of resource dictionaries with id, type, properties

    Raises:
        ValueError: If resource_types contain invalid values
    """
    # Validate resource types if provided
    if resource_types:
        # Whitelist validation: Azure resource types have specific format
        for rt in resource_types:
            if not re.match(r'^[A-Za-z0-9]+\.[A-Za-z0-9]+/[A-Za-z0-9]+$', rt):
                raise ValueError(f"Invalid resource type format: {rt}")
            if len(rt) > 200:  # Reasonable max length
                raise ValueError(f"Resource type too long: {rt}")

    # Build query with parameterized resource types
    if resource_types:
        query = """
            MATCH (r:Resource)
            WHERE NOT r:Original
              AND r.tenant_id = $tenant_id
              AND (r.synthetic IS NULL OR r.synthetic = false)
              AND r.type IN $resource_types
            RETURN r.id as id, r.type as type, properties(r) as props
            LIMIT 10000
        """
        params = {"tenant_id": tenant_id, "resource_types": resource_types}
    else:
        query = """
            MATCH (r:Resource)
            WHERE NOT r:Original
              AND r.tenant_id = $tenant_id
              AND (r.synthetic IS NULL OR r.synthetic = false)
            RETURN r.id as id, r.type as type, properties(r) as props
            LIMIT 10000
        """
        params = {"tenant_id": tenant_id}

    with self.session_manager.session() as session:
        result = session.run(query, params)
        resources = [
            {"id": record["id"], "type": record["type"], "props": record["props"]}
            for record in result
        ]

    return resources
```

#### Location: Lines 863-895 (`_get_relationship_patterns` method)

**Current Vulnerable Code:**
```python
async def _get_relationship_patterns(
    self, base_resources: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    base_ids = [r["id"] for r in base_resources]
    if not base_ids:
        return []

    # VULNERABLE: Direct string interpolation of IDs
    id_list = ", ".join(f"'{id}'" for id in base_ids)

    query = f"""
        MATCH (source:Resource)-[rel]->(target:Resource)
        WHERE NOT source:Original AND NOT target:Original
          AND source.id IN [{id_list}]
          AND target.id IN [{id_list}]
        RETURN source.id as source_id,
               target.id as target_id,
               type(rel) as rel_type,
               properties(rel) as rel_props
        LIMIT 100000
    """
    # ... rest of method
```

**Secure Fixed Code:**
```python
async def _get_relationship_patterns(
    self, base_resources: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Extract relationship patterns from base resources.

    Args:
        base_resources: List of base resources

    Returns:
        List of relationship patterns with source_id, target_id, type, props
    """
    base_ids = [r["id"] for r in base_resources]
    if not base_ids:
        return []

    # Use parameterized query - Neo4j will handle the list safely
    query = """
        MATCH (source:Resource)-[rel]->(target:Resource)
        WHERE NOT source:Original AND NOT target:Original
          AND source.id IN $base_ids
          AND target.id IN $base_ids
        RETURN source.id as source_id,
               target.id as target_id,
               type(rel) as rel_type,
               properties(rel) as rel_props
        LIMIT 100000
    """

    patterns = []
    with self.session_manager.session() as session:
        result = session.run(query, {"base_ids": base_ids})
        for record in result:
            patterns.append(
                {
                    "source_id": record["source_id"],
                    "target_id": record["target_id"],
                    "rel_type": record["rel_type"],
                    "rel_props": record["rel_props"],
                }
            )

    return patterns
```

---

### Fix 2: Cypher Injection in scale_down_service.py

#### Location: Lines 817-918 (`sample_by_pattern` method)

**Current Vulnerable Code:**
```python
async def sample_by_pattern(
    self,
    tenant_id: str,
    criteria: Dict[str, Any],
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> Set[str]:
    # Validate tenant exists
    if not await self.validate_tenant_exists(tenant_id):
        raise ValueError(f"Tenant {tenant_id} not found in database")

    if not criteria:
        raise ValueError("Criteria cannot be empty")

    # VULNERABLE: Direct string interpolation of property paths
    where_clauses = ["NOT r:Original", "r.tenant_id = $tenant_id"]
    params: Dict[str, Any] = {"tenant_id": tenant_id}

    for key, value in criteria.items():
        if "." in key:
            # Handle nested properties (e.g., tags.environment)
            parts = key.split(".", 1)
            property_path = f"r.{parts[0]}.{parts[1]}"  # INJECTION POINT
        else:
            property_path = f"r.{key}"  # INJECTION POINT

        param_name = key.replace(".", "_")
        where_clauses.append(f"{property_path} = ${param_name}")
        params[param_name] = value

    where_clause = " AND ".join(where_clauses)

    query = f"""
        MATCH (r:Resource)
        WHERE {where_clause}
        RETURN r.id as id
    """
    # ... rest of method
```

**Secure Fixed Code:**
```python
# At module level - define allowed properties
ALLOWED_PATTERN_PROPERTIES = {
    # Resource properties
    "type", "name", "location", "id", "tenant_id", "resource_group",
    "sku", "kind", "provisioning_state",

    # Tag properties (nested)
    "tags.environment", "tags.owner", "tags.cost_center",
    "tags.project", "tags.application", "tags.department",

    # Network properties
    "subnet_id", "vnet_id", "nsg_id",

    # Identity properties
    "identity_type", "principal_id",

    # Synthetic properties
    "synthetic", "scale_operation_id",
}

def _validate_pattern_key(key: str) -> None:
    """
    Validate pattern matching key against whitelist.

    Args:
        key: Property key to validate

    Raises:
        ValueError: If key is not in whitelist or is malformed
    """
    if key not in ALLOWED_PATTERN_PROPERTIES:
        raise ValueError(
            f"Invalid pattern property: {key}. "
            f"Allowed properties: {sorted(ALLOWED_PATTERN_PROPERTIES)}"
        )

async def sample_by_pattern(
    self,
    tenant_id: str,
    criteria: Dict[str, Any],
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> Set[str]:
    """
    Sample graph based on pattern matching criteria.

    Pattern-based sampling selects nodes matching specific attributes,
    enabling targeted sampling by resource type, tags, location, etc.

    Args:
        tenant_id: Azure tenant ID to sample
        criteria: Matching criteria dictionary with whitelisted keys only
        progress_callback: Optional progress callback

    Returns:
        Set[str]: Set of matching node IDs

    Raises:
        ValueError: If tenant not found, criteria invalid, or contains disallowed properties
    """
    self.logger.info(
        f"Sampling by pattern for tenant {tenant_id[:8]}... "
        f"with {len(criteria)} criteria"
    )

    # Validate tenant exists
    if not await self.validate_tenant_exists(tenant_id):
        raise ValueError(f"Tenant {tenant_id} not found in database")

    if not criteria:
        raise ValueError("Criteria cannot be empty")

    if len(criteria) > 20:
        raise ValueError("Too many criteria (max 20)")

    # Validate all property keys against whitelist
    for key in criteria.keys():
        self._validate_pattern_key(key)

    # Build query with property accessor syntax for nested properties
    where_clauses = ["NOT r:Original", "r.tenant_id = $tenant_id"]
    params: Dict[str, Any] = {"tenant_id": tenant_id}

    for key, value in criteria.items():
        param_name = f"param_{key.replace('.', '_')}"

        # Use Cypher map property accessor for nested properties
        # This safely handles dot notation without string interpolation
        if "." in key:
            # For tags.environment, we need r.tags.environment
            # But we validate key is in whitelist, so this is safe
            parts = key.split(".")
            # Build nested property access: r['tags']['environment']
            property_ref = f"r.{parts[0]}.{parts[1]}"
        else:
            property_ref = f"r.{key}"

        where_clauses.append(f"{property_ref} = ${param_name}")
        params[param_name] = value

    where_clause = " AND ".join(where_clauses)

    query = f"""
        MATCH (r:Resource)
        WHERE {where_clause}
        RETURN r.id as id
    """

    self.logger.debug(f"Pattern matching with {len(criteria)} validated criteria")

    matching_ids: Set[str] = set()

    try:
        with self.session_manager.session() as session:
            result = session.run(query, params)

            for record in result:
                matching_ids.add(record["id"])

                if progress_callback and len(matching_ids) % 100 == 0:
                    progress_callback(
                        "Pattern matching", len(matching_ids), len(matching_ids)
                    )

        self.logger.info(
            f"Pattern matching completed: {len(matching_ids)} nodes matched"
        )

        return matching_ids

    except Exception as e:
        self.logger.exception(f"Pattern matching failed: {e}")
        raise
```

---

### Fix 3: Cypher Injection in Neo4j Export

#### Location: Lines 1064-1128 (`_export_neo4j` method)

**Current Vulnerable Code:**
```python
async def _export_neo4j(
    self,
    node_ids: Set[str],
    node_properties: Dict[str, Dict[str, Any]],
    sampled_graph: nx.DiGraph,
    output_path: str,
) -> None:
    cypher_statements = []

    # Create nodes
    cypher_statements.append("// Create nodes")
    for node_id in node_ids:
        if node_id in node_properties:
            props = node_properties[node_id]

            # VULNERABLE: No escaping of property values
            prop_strings = []
            for key, value in props.items():
                if isinstance(value, str):
                    prop_strings.append(f'{key}: "{value}"')  # INJECTION POINT
                elif isinstance(value, (int, float, bool)):
                    prop_strings.append(f"{key}: {value}")

            props_str = ", ".join(prop_strings) if prop_strings else ""

            resource_type = props.get("type", "Resource")
            label = (
                resource_type.split("/")[-1] if "/" in resource_type else "Resource"
            )

            cypher_statements.append(f"CREATE (:{label}:Resource {{{props_str}}});")

    # Create relationships
    cypher_statements.append("// Create relationships")
    for source, target, data in sampled_graph.edges(data=True):
        rel_type = data.get("relationship_type", "RELATED_TO")

        # VULNERABLE: Node IDs directly interpolated
        cypher_statements.append(
            f'MATCH (a:Resource {{id: "{source}"}}), '  # INJECTION POINT
            f'(b:Resource {{id: "{target}"}}) '  # INJECTION POINT
            f"CREATE (a)-[:{rel_type}]->(b);"  # INJECTION POINT
        )
    # ... write to file
```

**Secure Fixed Code:**
```python
import json
import re
from typing import Any, Dict, Set

def _escape_cypher_string(value: str) -> str:
    """
    Escape special characters for Cypher string literals.

    Args:
        value: String value to escape

    Returns:
        Safely escaped string for Cypher
    """
    # Escape backslashes first
    value = value.replace("\\", "\\\\")
    # Escape double quotes
    value = value.replace('"', '\\"')
    # Escape newlines
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    value = value.replace("\t", "\\t")
    return value

def _escape_cypher_identifier(name: str) -> str:
    """
    Escape identifiers (property names, relationship types) for Cypher.

    Args:
        name: Identifier to escape

    Returns:
        Safely escaped identifier for Cypher
    """
    # If identifier contains only alphanumeric and underscore, no escaping needed
    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        return name

    # Otherwise, use backticks and escape any backticks in the name
    escaped = name.replace("`", "``")
    return f"`{escaped}`"

def _is_safe_cypher_identifier(name: str) -> bool:
    """Check if identifier is safe without escaping."""
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name)) and len(name) <= 100

async def _export_neo4j(
    self,
    node_ids: Set[str],
    node_properties: Dict[str, Dict[str, Any]],
    sampled_graph: nx.DiGraph,
    output_path: str,
) -> None:
    """
    Export sample to new Neo4j database as Cypher statements.

    Creates properly escaped Cypher statements for importing into a new database.

    Args:
        node_ids: Set of node IDs to export
        node_properties: Properties for all nodes
        sampled_graph: NetworkX graph of sample
        output_path: Output file path

    Raises:
        ValueError: If export fails
    """
    cypher_statements = []

    # Add header with metadata
    cypher_statements.append("// Neo4j Import Cypher Statements")
    cypher_statements.append(f"// Generated: {datetime.now(UTC).isoformat()}")
    cypher_statements.append(f"// Nodes: {len(node_ids)}")
    cypher_statements.append(f"// Relationships: {sampled_graph.number_of_edges()}")
    cypher_statements.append("// WARNING: Review this file before executing")
    cypher_statements.append("")

    # Create nodes with proper escaping
    cypher_statements.append("// Create nodes")

    for node_id in sorted(node_ids):  # Sort for deterministic output
        if node_id not in node_properties:
            continue

        props = node_properties[node_id]

        # Build property map with proper escaping
        prop_strings = []
        for key, value in props.items():
            # Validate and escape property name
            if not _is_safe_cypher_identifier(key):
                self.logger.warning(f"Skipping property with unsafe name: {key}")
                continue

            safe_key = _escape_cypher_identifier(key)

            # Handle different value types
            if value is None:
                # Skip null values
                continue
            elif isinstance(value, str):
                # Escape string values
                safe_value = _escape_cypher_string(value)
                prop_strings.append(f'{safe_key}: "{safe_value}"')
            elif isinstance(value, bool):
                # Use lowercase boolean literals
                prop_strings.append(f"{safe_key}: {str(value).lower()}")
            elif isinstance(value, (int, float)):
                # Numbers are safe
                prop_strings.append(f"{safe_key}: {json.dumps(value)}")
            elif isinstance(value, (list, dict)):
                # Use JSON representation for complex types
                json_value = json.dumps(value)
                safe_value = _escape_cypher_string(json_value)
                prop_strings.append(f'{safe_key}: "{safe_value}"')
            else:
                # Skip unsupported types
                self.logger.warning(f"Skipping property {key} with unsupported type {type(value)}")
                continue

        props_str = ", ".join(prop_strings) if prop_strings else ""

        # Get resource type for label
        resource_type = props.get("type", "Resource")

        # Extract last part of resource type for label
        # e.g., "Microsoft.Compute/virtualMachines" -> "virtualMachines"
        if "/" in resource_type:
            label_name = resource_type.split("/")[-1]
        else:
            label_name = "Resource"

        # Validate and escape label
        safe_label = _escape_cypher_identifier(label_name)

        # Generate CREATE statement
        cypher_statements.append(
            f"CREATE (:{safe_label}:Resource {{{props_str}}});"
        )

    cypher_statements.append("")

    # Create relationships with proper escaping
    cypher_statements.append("// Create relationships")

    for source, target, data in sampled_graph.edges(data=True):
        # Escape node IDs
        safe_source = _escape_cypher_string(source)
        safe_target = _escape_cypher_string(target)

        # Get and validate relationship type
        rel_type = data.get("relationship_type", "RELATED_TO")
        if not _is_safe_cypher_identifier(rel_type):
            self.logger.warning(f"Skipping relationship with unsafe type: {rel_type}")
            continue

        safe_rel_type = _escape_cypher_identifier(rel_type)

        # Generate MATCH + CREATE statement
        cypher_statements.append(
            f'MATCH (a:Resource {{id: "{safe_source}"}}), '
            f'(b:Resource {{id: "{safe_target}"}}) '
            f"CREATE (a)-[:{safe_rel_type}]->(b);"
        )

    # Write to file
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(cypher_statements))

        self.logger.info(f"Neo4j Cypher export completed: {output_path}")

    except OSError as e:
        raise ValueError(f"Failed to write Neo4j export file: {e}") from e
```

---

### Fix 4: YAML Injection

#### Location: `src/iac/engine.py` line 70

**Current Vulnerable Code:**
```python
with open(rules_file) as f:
    rules_data = yaml.load(f)  # VULNERABLE: arbitrary code execution
```

**Secure Fixed Code:**
```python
with open(rules_file) as f:
    rules_data = yaml.safe_load(f)  # SAFE: only basic types
```

---

### Fix 5: Resource Consumption Limits

#### Add to configuration models (`src/config/models.py`):

```python
class PerformanceConfig(BaseModel):
    """Performance and resource limits configuration."""

    batch_size: Annotated[int, Field(gt=0, le=10000)] = Field(
        default=500,
        description="Default batch size (max 10,000 to prevent memory exhaustion)",
    )
    memory_limit_mb: Annotated[int, Field(gt=0, le=16384)] = Field(
        default=2048,
        description="Memory limit in megabytes (max 16GB)",
    )
    timeout_seconds: Annotated[int, Field(gt=0, le=3600)] = Field(
        default=300,
        description="Operation timeout in seconds (max 1 hour)",
    )
    max_workers: Annotated[int, Field(ge=1, le=32)] = Field(
        default=4,
        description="Maximum number of worker threads/processes (max 32)",
    )

    # New: Scale-specific limits
    max_scale_factor: Annotated[float, Field(gt=0, le=100)] = Field(
        default=10.0,
        description="Maximum scale factor (max 100x to prevent abuse)",
    )
    max_resources_per_operation: Annotated[int, Field(gt=0, le=1000000)] = Field(
        default=100000,
        description="Maximum resources per scale operation (max 1M)",
    )
    max_graph_nodes: Annotated[int, Field(gt=0, le=10000000)] = Field(
        default=1000000,
        description="Maximum nodes to load into NetworkX (max 10M)",
    )

    model_config = ConfigDict(extra="forbid")
```

#### Enforce in services (`src/services/scale_up_service.py`):

```python
async def scale_up_template(
    self,
    tenant_id: str,
    scale_factor: float,
    resource_types: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> ScaleUpResult:
    """Scale up resources using template-based replication."""
    start_time = datetime.now()
    operation_id = await self.generate_session_id()

    try:
        # Validate inputs
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        # NEW: Enforce scale factor limit
        if scale_factor <= 0:
            raise ValueError("Scale factor must be positive")

        max_scale_factor = getattr(self, 'max_scale_factor', 100.0)
        if scale_factor > max_scale_factor:
            raise ValueError(
                f"Scale factor {scale_factor} exceeds maximum allowed {max_scale_factor}. "
                f"Large scale operations should be done incrementally."
            )

        self.logger.info(
            f"Starting template-based scale-up: tenant={tenant_id[:8]}..., "
            f"factor={scale_factor}, operation_id={operation_id}"
        )

        # Analyze existing resources
        if progress_callback:
            progress_callback("Analyzing existing resources...", 0, 100)

        base_resources = await self._get_base_resources(tenant_id, resource_types)
        if not base_resources:
            raise ValueError(
                f"No base resources found for tenant {tenant_id}"
                + (f" with types {resource_types}" if resource_types else "")
            )

        # NEW: Enforce maximum resources per operation
        target_new_resources = int(len(base_resources) * (scale_factor - 1))
        if target_new_resources <= 0:
            raise ValueError(
                f"Scale factor {scale_factor} would create {target_new_resources} resources. "
                f"Must be > 1.0 to create new resources."
            )

        max_resources = getattr(self, 'max_resources_per_operation', 100000)
        if target_new_resources > max_resources:
            raise ValueError(
                f"Operation would create {target_new_resources} resources, "
                f"exceeding maximum {max_resources}. "
                f"Reduce scale factor or perform multiple smaller operations."
            )

        self.logger.info(f"Found {len(base_resources)} base resources to replicate")
        self.logger.info(f"Target: {target_new_resources} new synthetic resources")

        # Continue with operation...
        # ... rest of method
```

---

## High Priority Fixes (Before Merge)

### Fix 6: Tenant Authorization

#### Add to `base_scale_service.py`:

```python
async def validate_tenant_access(
    self, tenant_id: str, user_principal: Optional[str] = None
) -> bool:
    """
    Validate that the current user/service principal has access to the tenant.

    Args:
        tenant_id: Azure tenant ID to validate
        user_principal: User or service principal ID (from auth context)

    Returns:
        bool: True if user has access, False otherwise

    Raises:
        PermissionError: If user does not have access to tenant
        Exception: If database query fails
    """
    # If no user_principal provided, try to get from auth context
    if user_principal is None:
        # In production, get from authentication middleware/context
        # For now, get from environment or session
        user_principal = os.environ.get("AZURE_USER_PRINCIPAL_ID")

        if user_principal is None:
            self.logger.warning("No user principal available for authorization check")
            # In strict mode, deny access
            # In development mode, allow (with warning logged)
            strict_mode = os.environ.get("ATG_STRICT_AUTH", "false").lower() == "true"
            if strict_mode:
                raise PermissionError(
                    "Authentication required. No user principal in context."
                )
            return True  # Development mode fallback

    # Check if user has access to tenant
    query = """
        MATCH (t:Tenant {id: $tenant_id})
        OPTIONAL MATCH (u:User {id: $user_principal})
        OPTIONAL MATCH (sp:ServicePrincipal {id: $user_principal})
        WITH t, u, sp
        WHERE (u)-[:MEMBER_OF|:OWNER_OF]->(t)
           OR (sp)-[:MEMBER_OF|:OWNER_OF]->(t)
           OR (u)-[:HAS_ROLE]->(:Role)-[:IN_TENANT]->(t)
        RETURN count(*) > 0 as has_access
    """

    try:
        with self.session_manager.session() as session:
            result = session.run(
                query, {"tenant_id": tenant_id, "user_principal": user_principal}
            )
            record = result.single()
            has_access = record["has_access"] if record else False

            if not has_access:
                self.logger.error(
                    f"Access denied: User {user_principal[:8]}... "
                    f"to tenant {tenant_id[:8]}..."
                )
                raise PermissionError(
                    f"User does not have access to tenant {tenant_id}"
                )

            self.logger.info(
                f"Access granted: User {user_principal[:8]}... "
                f"to tenant {tenant_id[:8]}..."
            )
            return True

    except Exception as e:
        self.logger.exception(f"Failed to validate tenant access: {e}")
        raise
```

#### Update all scale operation methods to call validation:

```python
async def scale_up_template(self, tenant_id: str, ...):
    """Scale up resources using template-based replication."""
    start_time = datetime.now()
    operation_id = await self.generate_session_id()

    try:
        # NEW: Check authorization first
        await self.validate_tenant_access(tenant_id)

        # Then check existence
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        # ... rest of method
```

---

### Fix 7: Original Layer Database Constraints

Add these constraints via Neo4j migration:

```cypher
// Migration: Add constraints to prevent Original layer contamination

// Constraint: Synthetic resources cannot be Original
CREATE CONSTRAINT synthetic_not_original IF NOT EXISTS
FOR (n:Resource)
REQUIRE (
    CASE
        WHEN n:Original THEN (n.synthetic IS NULL OR n.synthetic = false)
        WHEN n.synthetic = true THEN NOT n:Original
        ELSE true
    END
);

// Constraint: Synthetic resources must have required markers
CREATE CONSTRAINT synthetic_markers IF NOT EXISTS
FOR (n:Resource)
REQUIRE (
    CASE
        WHEN n.synthetic = true THEN (
            n.scale_operation_id IS NOT NULL
            AND n.generation_strategy IS NOT NULL
            AND n.generation_timestamp IS NOT NULL
        )
        ELSE true
    END
);

// Index: Fast lookup of synthetic resources by operation ID
CREATE INDEX synthetic_operation_idx IF NOT EXISTS
FOR (n:Resource)
ON (n.scale_operation_id)
WHERE n.synthetic = true;
```

---

### Fix 8: Sanitize Logging

#### Add logging utilities (`src/utils/logging_utils.py`):

```python
"""Logging utilities for Azure Tenant Grapher."""

import hashlib
from typing import Any, Dict


def sanitize_tenant_id(tenant_id: str) -> str:
    """
    Sanitize tenant ID for logging.

    Args:
        tenant_id: Full tenant ID (UUID)

    Returns:
        Sanitized ID showing only first 8 characters
    """
    if not tenant_id:
        return "none"
    return f"{tenant_id[:8]}..."


def sanitize_user_input(user_input: Any, max_length: int = 50) -> str:
    """
    Sanitize user input for logging.

    Args:
        user_input: User-provided input
        max_length: Maximum length to log

    Returns:
        Sanitized string representation
    """
    if user_input is None:
        return "null"

    # Convert to string
    str_input = str(user_input)

    # Truncate if too long
    if len(str_input) > max_length:
        str_input = str_input[:max_length] + "..."

    # Hash sensitive patterns
    if any(pattern in str_input.lower() for pattern in ["password", "secret", "key", "token"]):
        hash_value = hashlib.sha256(str_input.encode()).hexdigest()[:16]
        return f"[REDACTED-{hash_value}]"

    return str_input


def sanitize_query(query: str) -> str:
    """
    Sanitize Cypher query for logging.

    Args:
        query: Cypher query string

    Returns:
        Sanitized query (structure only, no values)
    """
    # Remove parameter values, show only structure
    # This is a simple implementation; could be more sophisticated
    return "Cypher query with parameters (query structure sanitized)"


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Sanitize dictionary of data for logging.

    Args:
        data: Dictionary to sanitize

    Returns:
        Dictionary with sanitized values
    """
    sanitized = {}

    for key, value in data.items():
        # Sanitize based on key name
        if "tenant" in key.lower():
            sanitized[key] = sanitize_tenant_id(str(value))
        elif any(pattern in key.lower() for pattern in ["password", "secret", "key", "token"]):
            sanitized[key] = "[REDACTED]"
        elif "query" in key.lower():
            sanitized[key] = sanitize_query(str(value))
        else:
            sanitized[key] = sanitize_user_input(value)

    return sanitized
```

#### Update logging calls:

```python
from src.utils.logging_utils import sanitize_tenant_id, sanitize_user_input

# In scale services
self.logger.info(
    f"Starting scale-up: tenant={sanitize_tenant_id(tenant_id)}, "
    f"factor={scale_factor}"
)

# Never log queries or user criteria at INFO level
self.logger.debug("Pattern matching query constructed")  # Not the actual query
```

---

## Testing Requirements

All fixes must include corresponding security tests. Example test file:

```python
"""Security tests for scale operations."""

import pytest
from src.services.scale_up_service import ScaleUpService
from src.services.scale_down_service import ScaleDownService


class TestCypherInjectionPrevention:
    """Test that Cypher injection attempts are prevented."""

    @pytest.mark.asyncio
    async def test_resource_type_injection_blocked(self, scale_up_service):
        """Test that malicious resource types cause validation errors."""
        malicious_types = [
            # Basic injection
            "Microsoft.Compute/virtualMachines') OR 1=1--",

            # Comment injection
            "test'] // malicious comment",

            # Nested query injection
            "foo\n} MATCH (x) DETACH DELETE x //",

            # Relationship injection
            "vm']->(x) WHERE x.secret = 'data",
        ]

        for malicious_type in malicious_types:
            with pytest.raises(ValueError, match="Invalid resource type"):
                await scale_up_service.scale_up_template(
                    tenant_id="00000000-0000-0000-0000-000000000000",
                    scale_factor=2.0,
                    resource_types=[malicious_type],
                )

    @pytest.mark.asyncio
    async def test_pattern_property_injection_blocked(self, scale_down_service):
        """Test that malicious pattern properties are rejected."""
        malicious_criteria = [
            # Property path injection
            {"type) OR 1=1 OR (r.name": "ignored"},

            # Nested query injection
            {"tags.env') RETURN * //": "malicious"},

            # Non-whitelisted property
            {"malicious_property": "value"},

            # Command injection attempt
            {"type'; DROP DATABASE": "neo4j"},
        ]

        for criteria in malicious_criteria:
            with pytest.raises(ValueError, match="Invalid pattern property"):
                await scale_down_service.sample_by_pattern(
                    tenant_id="00000000-0000-0000-0000-000000000000",
                    criteria=criteria,
                )


class TestAuthorizationEnforcement:
    """Test that tenant authorization is enforced."""

    @pytest.mark.asyncio
    async def test_cross_tenant_access_denied(self, scale_up_service):
        """Test that users cannot scale other tenants."""
        user_a_tenant = "tenant-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        user_b_tenant = "tenant-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

        # User A tries to scale User B's tenant
        with pytest.raises(PermissionError, match="does not have access"):
            await scale_up_service.scale_up_template(
                tenant_id=user_b_tenant,  # Not user A's tenant
                scale_factor=2.0,
            )


class TestResourceLimits:
    """Test that resource limits are enforced."""

    @pytest.mark.asyncio
    async def test_excessive_scale_factor_rejected(self, scale_up_service):
        """Test that excessive scale factors are rejected."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            await scale_up_service.scale_up_template(
                tenant_id="00000000-0000-0000-0000-000000000000",
                scale_factor=999999.0,  # Way too large
            )

    @pytest.mark.asyncio
    async def test_excessive_resource_count_rejected(self, scale_up_service):
        """Test that excessive resource counts are rejected."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            await scale_up_service.scale_up_random(
                tenant_id="00000000-0000-0000-0000-000000000000",
                target_count=999999999,  # Way too many
                config={"resource_type_distribution": {"vm": 1.0}},
            )


class TestOriginalLayerProtection:
    """Test that Original layer cannot be contaminated."""

    @pytest.mark.asyncio
    async def test_synthetic_resources_not_original(
        self, scale_up_service, session_manager
    ):
        """Test that synthetic resources never get :Original label."""
        result = await scale_up_service.scale_up_template(
            tenant_id="test-tenant",
            scale_factor=2.0,
        )

        # Verify no Original contamination
        query = """
            MATCH (r:Resource:Original)
            WHERE r.scale_operation_id = $operation_id
            RETURN count(r) as count
        """

        with session_manager.session() as session:
            result = session.run(query, {"operation_id": result.operation_id})
            count = result.single()["count"]
            assert count == 0, f"Found {count} Original nodes in synthetic data!"
```

---

## Deployment Checklist

Before merging PR #435:

- [ ] All Cypher injection vulnerabilities fixed with parameterized queries
- [ ] Property name whitelist implemented for pattern matching
- [ ] Cypher escaping functions implemented for export
- [ ] `yaml.load()` replaced with `yaml.safe_load()`
- [ ] Resource consumption limits added to configuration
- [ ] Limits enforced in all scale operations
- [ ] Tenant authorization checks added
- [ ] Original layer database constraints created
- [ ] Logging sanitization implemented
- [ ] Security test suite added (min 20 tests)
- [ ] All security tests passing
- [ ] Code review by security-focused developer
- [ ] Penetration testing completed
- [ ] Security review sign-off obtained

---

## Additional Recommendations

1. **Rate Limiting**: Implement per-user/per-tenant rate limits for scale operations
2. **Audit Logging**: Log all scale operations to audit trail
3. **Monitoring**: Add alerts for anomalous scale operation patterns
4. **Documentation**: Update security documentation with safe usage patterns
5. **Training**: Brief development team on secure Cypher query practices

---

**Status:** 🔴 **REMEDIATION REQUIRED**

All critical fixes must be implemented before merge approval.

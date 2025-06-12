# Azure Tenant Markdown Specification Feature

## Purpose and Scope

### Overview
This feature adds the capability to generate anonymized, comprehensive Markdown specifications of Azure tenant infrastructure. The specifications serve as portable documentation that can be used for:

- **Architecture Reviews**: Providing stakeholders with human-readable infrastructure documentation
- **Compliance Audits**: Generating anonymized tenant overviews for security assessments
- **Template Creation**: Serving as a foundation for Infrastructure-as-Code templates
- **Knowledge Transfer**: Documenting infrastructure patterns for team education
- **Disaster Recovery Planning**: Maintaining offline documentation of critical infrastructure

### Scope
- Query all nodes and AI summaries from the Neo4j tenant graph
- Apply intelligent resource limiting (default 50 resources) with priority-based selection
- Generate anonymized Markdown with meaningful, hash-consistent placeholders
- Organize content by major Azure service categories (compute, storage, networking, IAM, etc.)
- Include sufficient configuration detail for infrastructure recreation
- Store specifications in versioned files with timestamps
- Integrate with existing GraphVisualizer to provide "View Markdown Spec" links

### Out of Scope
- Real-time specification updates (generated on-demand only)
- Interactive specification editing
- Direct Infrastructure-as-Code template generation
- Binary or complex object anonymization

## Data Model & Anonymization Algorithm

### Resource Data Structure
```typescript
interface ResourceData {
  id: string;                    // Azure resource ID
  name: string;                  // Resource name
  type: string;                  // Azure resource type
  location: string;              // Azure region
  resource_group: string;        // Resource group name
  subscription_id: string;       // Subscription ID
  properties: Record<string, any>; // Resource-specific properties
  tags: Record<string, string>;   // Resource tags
  llm_description?: string;      // AI-generated summary
  relationships: Relationship[]; // Connected resources
}

interface Relationship {
  type: string;                  // CONTAINS, DEPENDS_ON, CONNECTS_TO, etc.
  target_id: string;             // Target resource ID
  target_name: string;           // Target resource name
  target_type: string;           // Target resource type
}
```

### Anonymization Algorithm

#### Hash-Based Placeholder Generation
```python
def generate_placeholder(resource_type: str, original_name: str, original_id: str) -> str:
    # Create deterministic hash from original identifiers
    hash_input = f"{original_name}:{original_id}"
    hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:8]

    # Extract meaningful prefix from resource type
    type_prefix = extract_type_prefix(resource_type)

    # Generate semantic suffix if AI description available
    semantic_suffix = extract_semantic_suffix(ai_description)

    # Combine: {type_prefix}-{semantic_suffix}-{hash}
    return f"{type_prefix}-{semantic_suffix}-{hash_value}"

def extract_type_prefix(resource_type: str) -> str:
    """Extract meaningful prefix from Azure resource type"""
    type_mapping = {
        "Microsoft.Compute/virtualMachines": "vm",
        "Microsoft.Storage/storageAccounts": "storage",
        "Microsoft.Network/virtualNetworks": "vnet",
        "Microsoft.Web/sites": "webapp",
        "Microsoft.Sql/servers": "sqlserver",
        "Microsoft.KeyVault/vaults": "keyvault",
        # ... comprehensive mapping
    }
    return type_mapping.get(resource_type, "resource")

def extract_semantic_suffix(ai_description: str) -> str:
    """Extract semantic meaning from AI description"""
    if not ai_description:
        return "main"

    # Extract semantic indicators from AI description
    semantic_patterns = {
        r"production|prod": "prod",
        r"development|dev|test": "dev",
        r"staging|stage": "stage",
        r"primary|main": "primary",
        r"secondary|backup": "secondary",
        r"web|frontend": "web",
        r"database|db|sql": "db",
        r"cache|redis": "cache",
        r"logging|logs": "logs"
    }

    for pattern, suffix in semantic_patterns.items():
        if re.search(pattern, ai_description, re.IGNORECASE):
            return suffix

    return "main"
```

#### Consistency Guarantees
- **Deterministic**: Same input always produces same placeholder
- **Relationship Preservation**: References between resources maintain consistency
- **Uniqueness**: Hash component ensures no collisions
- **Readability**: Meaningful prefixes and suffixes maintain comprehension

#### Azure-Assigned Identifier Removal
```python
AZURE_ID_PATTERNS = [
    r"/subscriptions/[a-f0-9-]{36}",      # Subscription IDs
    r"/resourceGroups/[\w-]+",            # Resource group paths
    r"[a-f0-9-]{36}",                     # GUIDs
    r"\w{24}",                            # Storage account keys
    r"https://[\w-]+\.vault\.azure\.net", # Key Vault URLs
    r"[\w-]+\.database\.windows\.net",    # SQL Server FQDNs
]

def remove_azure_identifiers(text: str) -> str:
    """Remove Azure-assigned identifiers from configuration text"""
    for pattern in AZURE_ID_PATTERNS:
        text = re.sub(pattern, "[ANONYMIZED]", text)
    return text
```

## File Naming & Versioning

### Directory Structure
```
./specs/
├── {timestamp}_tenant_spec.md          # Main specification file
├── {timestamp}_tenant_spec_summary.json # Metadata and stats
└── archive/
    ├── 20241211_142350_tenant_spec.md
    ├── 20241211_142350_tenant_spec_summary.json
    └── ...
```

### Naming Convention
- **Format**: `{YYYYMMDD_HHMMSS}_tenant_spec.md`
- **Timezone**: UTC for consistency
- **Example**: `20241211_142350_tenant_spec.md`

### Metadata File Structure
```json
{
  "generated_at": "2024-12-11T14:23:50Z",
  "tenant_id_hash": "a1b2c3d4",
  "total_resources": 47,
  "resources_by_type": {
    "Microsoft.Compute/virtualMachines": 12,
    "Microsoft.Storage/storageAccounts": 8,
    "Microsoft.Network/virtualNetworks": 4
  },
  "geographic_regions": ["eastus", "westus2", "westeurope"],
  "resource_limit_applied": 50,
  "ai_summaries_included": 34,
  "generator_version": "1.0.0"
}
```

## Command-Line & CLI Integration

> **CLI Signature:**
> `--tenant-id` is **required**.
> `--limit` is **optional** (default: 50).
> Canonical usage:

### New CLI Command
```bash
# Generate specification (required: --tenant-id, optional: --limit)
uv run python scripts/cli.py generate-spec --tenant-id <tenant-id> [--limit N]

# Example with custom resource limit
uv run python scripts/cli.py generate-spec --tenant-id <tenant-id> --limit 100

# Generate with custom output path
uv run python scripts/cli.py generate-spec --tenant-id <tenant-id> --output ./custom/path.md

# Include in build workflow
uv run python scripts/cli.py build --tenant-id <tenant-id> --generate-spec --visualize
```

### Configuration Integration
```python
@dataclass
class SpecificationConfig:
    """Configuration for specification generation."""

    resource_limit: int = 50
    output_directory: str = "./specs"
    include_ai_summaries: bool = True
    include_configuration_details: bool = True
    anonymization_seed: Optional[str] = None  # For reproducible hashing
    template_style: str = "comprehensive"     # comprehensive | summary | technical
```

### Error Handling
```python
class SpecificationError(Exception):
    """Base exception for specification generation errors."""
    pass

class InsufficientDataError(SpecificationError):
    """Raised when not enough data available for meaningful specification."""
    pass

class AnonymizationError(SpecificationError):
    """Raised when anonymization process fails."""
    pass
```

## Updates Required in Existing Classes/Modules

### 1. [`AzureTenantGrapher`](azure_tenant_grapher.py) Class Extensions

```python
class AzureTenantGrapher:
    # ... existing methods ...

    async def generate_markdown_specification(
        self,
        resource_limit: int = 50,
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate anonymized Markdown specification of tenant infrastructure.

        Args:
            resource_limit: Maximum number of resources to include
            output_path: Custom output path (optional)

        Returns:
            Path to generated specification file
        """
        pass

    def _create_specification_generator(self) -> 'TenantSpecificationGenerator':
        """Factory method for specification generator."""
        pass
```

### 2. New [`TenantSpecificationGenerator`](src/tenant_specification_generator.py) Module

```python
class TenantSpecificationGenerator:
    """Generates anonymized Markdown specifications from Neo4j graph data."""

    def __init__(
        self,
        neo4j_session: Any,
        anonymizer: 'ResourceAnonymizer',
        config: SpecificationConfig
    ):
        pass

    async def generate_specification(self, output_path: str) -> str:
        """Main specification generation method."""
        pass

    def _query_resources_with_limit(self) -> List[Dict[str, Any]]:
        """Query Neo4j with intelligent resource limiting."""
        pass

    def _query_relationships(self) -> List[Dict[str, Any]]:
        """Query all relationships between resources."""
        pass

    def _group_resources_by_category(self, resources: List[Dict]) -> Dict[str, List[Dict]]:
        """Group resources by major Azure service categories."""
        pass

    def _render_markdown(self, grouped_data: Dict[str, Any]) -> str:
        """Render grouped data as Markdown specification."""
        pass
```

### 3. New [`ResourceAnonymizer`](src/resource_anonymizer.py) Module

```python
class ResourceAnonymizer:
    """Handles consistent anonymization of Azure resource identifiers."""

    def __init__(self, seed: Optional[str] = None):
        self.placeholder_cache: Dict[str, str] = {}
        self.seed = seed

    def anonymize_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize a single resource while preserving relationships."""
        pass

    def anonymize_relationship(self, relationship: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize relationship while maintaining referential integrity."""
        pass

    def get_placeholder_mapping(self) -> Dict[str, str]:
        """Return mapping of original IDs to placeholders for debugging."""
        pass
```

### 4. [`GraphVisualizer`](src/graph_visualizer.py) Updates

```python
class GraphVisualizer:
    def generate_html_visualization(
        self,
        output_path: Optional[str] = None,
        specification_path: Optional[str] = None  # NEW PARAMETER
    ) -> str:
        """Generate HTML with link to tenant specification."""
        pass

    def _generate_specification_link(self, specification_path: Optional[str]) -> str:
        """Generate HTML for specification link - ENHANCED."""
        if not specification_path or not os.path.exists(specification_path):
            # Look for latest specification in ./specs/
            latest_spec = self._find_latest_specification()
            if latest_spec:
                specification_path = latest_spec
            else:
                return ""

        # Generate enhanced link with metadata
        return self._render_specification_link_html(specification_path)
```

### 5. [`scripts/cli.py`](scripts/cli.py) Extensions

```python
@cli.command()
@click.option("--tenant-id", required=True, help="Azure tenant ID")
@click.option("--limit", type=int, default=50, help="Resource limit (default: 50)")
@click.option("--output", help="Custom output path")
@click.option("--style", default="comprehensive", help="Template style")
@click.pass_context
@async_command
async def generate_spec(ctx, tenant_id, limit, output, style):
    """Generate anonymized tenant specification."""
    pass

# Update existing build command
@cli.command()
# ... existing parameters ...
@click.option("--generate-spec", is_flag=True, help="Generate specification after build")
async def build(ctx, ..., generate_spec):
    """Enhanced build command with specification generation."""
    # ... existing build logic ...

    if generate_spec:
        # Generate specification after successful build
        pass
```

### 6. Configuration Updates

```python
# config_manager.py additions
@dataclass
class SpecificationConfig:
    resource_limit: int = field(
        default_factory=lambda: int(os.getenv("SPEC_RESOURCE_LIMIT", "50"))
    )
    output_directory: str = field(
        default_factory=lambda: os.getenv("SPEC_OUTPUT_DIR", "./specs")
    )
    template_style: str = field(
        default_factory=lambda: os.getenv("SPEC_TEMPLATE_STYLE", "comprehensive")
    )
    include_ai_summaries: bool = field(
        default_factory=lambda: os.getenv("SPEC_INCLUDE_AI", "true").lower() == "true"
    )

@dataclass
class AzureTenantGrapherConfig:
    # ... existing fields ...
    specification: SpecificationConfig = field(default_factory=SpecificationConfig)
```

## Test Strategy & Edge Cases

### Unit Tests

#### [`test_tenant_specification_generator.py`](tests/test_tenant_specification_generator.py)
```python
class TestTenantSpecificationGenerator:
    def test_resource_limiting_with_priority(self):
        """Test intelligent resource limiting preserves important resources."""
        pass

    def test_specification_generation_with_minimal_data(self):
        """Test specification generation with limited Neo4j data."""
        pass

    def test_markdown_rendering_structure(self):
        """Test Markdown output follows expected structure."""
        pass

    def test_resource_grouping_accuracy(self):
        """Test resources are correctly grouped by service category."""
        pass
```

#### [`test_resource_anonymizer.py`](tests/test_resource_anonymizer.py)
```python
class TestResourceAnonymizer:
    def test_placeholder_consistency(self):
        """Test same input always produces same placeholder."""
        pass

    def test_relationship_integrity(self):
        """Test anonymized relationships maintain referential integrity."""
        pass

    def test_azure_id_removal(self):
        """Test Azure-assigned identifiers are properly removed."""
        pass

    def test_meaningful_placeholder_generation(self):
        """Test placeholders include meaningful prefixes and suffixes."""
        pass
```

### Integration Tests

#### [`test_specification_workflow.py`](tests/test_specification_workflow.py)
```python
class TestSpecificationWorkflow:
    @pytest.mark.integration
    async def test_end_to_end_specification_generation(self):
        """Test complete workflow from Neo4j query to file output."""
        pass

    @pytest.mark.integration
    async def test_cli_integration(self):
        """Test CLI command integration."""
        pass

    @pytest.mark.integration
    async def test_visualization_integration(self):
        """Test GraphVisualizer specification link integration."""
        pass
```

### Edge Cases & Error Scenarios

#### Data Availability
- **Empty Neo4j Database**: Generate minimal specification with placeholder structure
- **No AI Summaries**: Generate specification using only resource metadata
- **Partial Data**: Handle missing properties gracefully with fallback values

#### Resource Limiting
- **Under Limit**: Include all resources when total < limit
- **Exactly at Limit**: Apply priority-based selection algorithm
- **Over Limit**: Intelligently sample to maintain architectural coherence

#### File System
- **Permission Errors**: Graceful fallback to temporary directory
- **Disk Space**: Check available space before generation
- **Concurrent Access**: Handle multiple specification generations safely

#### Anonymization
- **Duplicate Placeholders**: Ensure hash collisions are handled
- **Complex Nested Objects**: Handle deep object structure anonymization
- **Binary Data**: Skip or handle binary properties appropriately

### Performance Testing

#### Load Testing
```python
@pytest.mark.performance
async def test_large_tenant_performance():
    """Test specification generation with 1000+ resources."""
    # Measure memory usage, generation time, output size
    pass

@pytest.mark.performance
async def test_anonymization_performance():
    """Test anonymization algorithm performance with large datasets."""
    pass
```

#### Memory Testing
```python
@pytest.mark.memory
async def test_memory_usage_with_large_datasets():
    """Test memory efficiency with large Neo4j result sets."""
    pass
```

### Validation Testing

#### Output Validation
```python
def test_markdown_structure_validation():
    """Validate generated Markdown follows expected structure."""
    # Test headers, sections, formatting consistency
    pass

def test_anonymization_completeness():
    """Validate no Azure-assigned identifiers remain in output."""
    pass

def test_relationship_consistency():
    """Validate all referenced resources exist in specification."""
    pass
```

## Error Handling Strategy

### Exception Hierarchy
```python
class SpecificationError(Exception):
    """Base exception for specification generation."""
    pass

class Neo4jQueryError(SpecificationError):
    """Neo4j query execution failed."""
    pass

class AnonymizationError(SpecificationError):
    """Anonymization process failed."""
    pass

class RenderingError(SpecificationError):
    """Markdown rendering failed."""
    pass

class FileSystemError(SpecificationError):
    """File system operation failed."""
    pass
```

### Graceful Degradation
```python
async def generate_specification_with_fallbacks(self) -> str:
    """Generate specification with multiple fallback strategies."""
    try:
        return await self._generate_full_specification()
    except Neo4jQueryError:
        logger.warning("Neo4j query failed, generating minimal specification")
        return await self._generate_minimal_specification()
    except AnonymizationError:
        logger.warning("Anonymization failed, generating with generic placeholders")
        return await self._generate_specification_with_generic_placeholders()
    except Exception as e:
        logger.error(f"Specification generation failed: {e}")
        return await self._generate_fallback_specification()
```

## Security Considerations

### Data Protection
- **Sensitive Information**: Ensure no credentials, keys, or PII in output
- **Anonymization Validation**: Verify no reverse-engineering of original names possible
- **Metadata Sanitization**: Remove sensitive metadata and properties

### Access Control
- **File Permissions**: Set appropriate permissions on specification files
- **Directory Security**: Ensure specs directory has restricted access
- **Log Sanitization**: Ensure logs don't contain sensitive data

### Compliance
- **Data Residency**: Specifications contain only metadata, not actual data
- **Audit Trail**: Maintain generation logs for compliance auditing
- **Retention Policy**: Implement specification file retention and cleanup

---

## Implementation Timeline

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create `TenantSpecificationGenerator` class
- [ ] Create `ResourceAnonymizer` class
- [ ] Implement basic Neo4j querying with resource limits
- [ ] Basic Markdown template structure

### Phase 2: Anonymization & Rendering (Week 2)
- [ ] Implement hash-based placeholder algorithm
- [ ] Implement resource grouping by service category
- [ ] Create comprehensive Markdown templates
- [ ] File system integration with timestamping

### Phase 3: CLI & Integration (Week 3)
- [ ] Add CLI command for specification generation
- [ ] Integrate with existing build workflow
- [ ] Update GraphVisualizer for specification links
- [ ] Configuration management integration

### Phase 4: Testing & Polish (Week 4)
- [ ] Comprehensive unit test suite
- [ ] Integration tests with real Neo4j data
- [ ] Performance testing and optimization
- [ ] Documentation and examples

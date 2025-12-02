# Builder Agent Quick Start Guide

Ahoy, Builder! Welcome aboard! This be yer quick start guide fer implementin' the CTF Overlay System. 🏴‍☠️

## What Ye Need to Know

**All tests be written and waitin' fer ye!** They be failin' right now (as expected in TDD), and yer job be to make 'em pass.

## Test-Driven Development Flow

```
1. Read the test          ← Understand what needs to be built
2. Run the test           ← Watch it FAIL (expected!)
3. Write minimal code     ← Just enough to make it pass
4. Run the test again     ← Watch it PASS (success!)
5. Refactor if needed     ← Clean up the code
6. Repeat for next test   ← Continue the cycle
```

## Quick Reference

### Test Files Location

```
tests/
├── unit/services/
│   ├── test_ctf_annotation_service.py   # 22 tests - implement CTFAnnotationService
│   ├── test_ctf_import_service.py       # 24 tests - implement CTFImportService
│   └── test_ctf_deploy_service.py       # 26 tests - implement CTFDeployService
│
├── integration/
│   └── test_ctf_import_deploy_flow.py   # 13 tests - verify service integration
│
└── e2e/
    └── test_ctf_m003_scenarios.py       # 15 tests - verify complete workflows
```

### Implementation Order

1. **CTFAnnotationService** (22 tests)
   - File: `src/services/ctf_annotation_service.py`
   - Tests: `tests/unit/services/test_ctf_annotation_service.py`
   - Run: `pytest tests/unit/services/test_ctf_annotation_service.py -v`

2. **CTFImportService** (24 tests)
   - File: `src/services/ctf_import_service.py`
   - Tests: `tests/unit/services/test_ctf_import_service.py`
   - Run: `pytest tests/unit/services/test_ctf_import_service.py -v`

3. **CTFDeployService** (26 tests)
   - File: `src/services/ctf_deploy_service.py`
   - Tests: `tests/unit/services/test_ctf_deploy_service.py`
   - Run: `pytest tests/unit/services/test_ctf_deploy_service.py -v`

4. **Integration Tests** (13 tests)
   - Run: `pytest tests/integration/test_ctf_import_deploy_flow.py -v`

5. **E2E Tests** (15 tests)
   - Run: `pytest tests/e2e/test_ctf_m003_scenarios.py -m e2e -v`

## Starting Implementation

### Step 1: Run Tests to See What's Needed

```bash
# Run ONE test file at a time
pytest tests/unit/services/test_ctf_annotation_service.py::TestCTFAnnotationServiceInit::test_service_creation_with_driver -v
```

**Expected output:**
```
FAILED - ImportError: cannot import name 'CTFAnnotationService'
```

This tells ye what to build!

### Step 2: Read the Test

Open `tests/unit/services/test_ctf_annotation_service.py` and find:

```python
def test_service_creation_with_driver(self, mock_neo4j_driver):
    """Test service can be created with Neo4j driver."""
    from src.services.ctf_annotation_service import CTFAnnotationService

    service = CTFAnnotationService(neo4j_driver=mock_neo4j_driver)
    assert service is not None
    assert service.neo4j_driver == mock_neo4j_driver
```

### Step 3: Implement the Minimum

Create `src/services/ctf_annotation_service.py`:

```python
"""CTF Annotation Service."""

class CTFAnnotationService:
    """Service for annotating resources with CTF properties."""

    def __init__(self, neo4j_driver):
        if neo4j_driver is None:
            raise ValueError("Neo4j driver is required")
        self.neo4j_driver = neo4j_driver
```

### Step 4: Run Test Again

```bash
pytest tests/unit/services/test_ctf_annotation_service.py::TestCTFAnnotationServiceInit::test_service_creation_with_driver -v
```

**Expected output:**
```
PASSED  ✓
```

Success! Move to next test!

## Key Service Interfaces (From Tests)

### CTFAnnotationService

```python
class CTFAnnotationService:
    def __init__(self, neo4j_driver):
        """Initialize with Neo4j driver."""
        ...

    def annotate_resource(
        self,
        resource_id: str,
        layer_id: str,
        ctf_exercise: Optional[str] = None,
        ctf_scenario: Optional[str] = None,
        ctf_role: Optional[str] = None,
        allow_base_modification: bool = False
    ) -> Dict[str, Any]:
        """
        Annotate resource with CTF properties.

        Returns:
            {"success": bool, "resource_id": str, "warning": Optional[str]}
        """
        ...

    def determine_role(
        self,
        resource_type: str,
        resource_name: str
    ) -> str:
        """
        Determine CTF role from resource type/name.

        Returns:
            Role string ("target", "attacker", "infrastructure", "monitoring")
        """
        ...

    def annotate_batch(
        self,
        resources: List[Dict[str, Any]],
        layer_id: str,
        ctf_exercise: Optional[str] = None,
        ctf_scenario: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Annotate multiple resources in batch.

        Returns:
            {
                "success_count": int,
                "failure_count": int,
                "results": List[Dict],
                "failed_resources": List[str]
            }
        """
        ...
```

### CTFImportService

```python
class CTFImportService:
    def __init__(self, neo4j_driver=None):
        """Initialize with optional Neo4j driver."""
        ...

    def parse_terraform_state(self, state_file: str) -> List[Dict[str, Any]]:
        """Parse Terraform state file and extract resources."""
        ...

    def extract_ctf_properties(self, resource: Dict) -> Dict[str, Optional[str]]:
        """
        Extract CTF properties from resource tags.

        Returns:
            {
                "layer_id": Optional[str],
                "ctf_exercise": Optional[str],
                "ctf_scenario": Optional[str],
                "ctf_role": Optional[str]
            }
        """
        ...

    def map_resource_to_neo4j(self, terraform_resource: Dict) -> Dict[str, Any]:
        """Map Terraform resource to Neo4j format."""
        ...

    def import_from_state(
        self,
        state_file: str,
        layer_id: str
    ) -> Dict[str, Any]:
        """
        Import Terraform state into Neo4j.

        Returns:
            {
                "resources_created": int,
                "resources_updated": int,
                "errors": int,
                "warnings": int
            }
        """
        ...
```

### CTFDeployService

```python
class CTFDeployService:
    def __init__(self, neo4j_driver=None, terraform_emitter=None):
        """Initialize with optional dependencies."""
        ...

    def query_ctf_resources(
        self,
        layer_id: str,
        exercise: Optional[str] = None,
        scenario: Optional[str] = None,
        role: Optional[str] = None,
        resource_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query CTF resources from Neo4j."""
        ...

    def generate_terraform_config(
        self,
        resources: List[Dict[str, Any]],
        output_dir: str
    ) -> str:
        """Generate Terraform configuration from resources."""
        ...

    def deploy_scenario(
        self,
        layer_id: str,
        exercise: str,
        scenario: str,
        output_dir: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Deploy CTF scenario.

        Returns:
            {
                "success": bool,
                "resources_deployed": int,
                "terraform_exitcode": int,
                "dry_run": bool,
                "terraform_config_path": Optional[str],
                "error": Optional[str]
            }
        """
        ...

    def cleanup_scenario(
        self,
        layer_id: str,
        exercise: str,
        scenario: str,
        terraform_dir: Optional[str] = None,
        allow_base_cleanup: bool = False
    ) -> Dict[str, Any]:
        """
        Cleanup CTF scenario.

        Returns:
            {
                "success": bool,
                "terraform_exitcode": int
            }
        """
        ...
```

## Common Patterns in Tests

### Pattern 1: Mocking Neo4j Calls

Tests use mocked Neo4j driver. Implement real Cypher queries:

```python
# Test expects:
mock_neo4j_driver.execute_query.assert_called_once()

# Your implementation should do:
self.neo4j_driver.execute_query(
    """
    MERGE (r:Resource {id: $id})
    SET r.layer_id = $layer_id,
        r.ctf_exercise = $ctf_exercise
    """,
    id=resource_id,
    layer_id=layer_id,
    ctf_exercise=ctf_exercise
)
```

### Pattern 2: Validation

Tests expect validation of inputs:

```python
# Test:
with pytest.raises(ValueError, match="Invalid layer_id"):
    service.annotate_resource(resource_id="vm-001", layer_id="'; DROP TABLE")

# Your implementation:
import re

def _validate_layer_id(self, layer_id: str):
    if not re.match(r'^[a-zA-Z0-9_-]+$', layer_id):
        raise ValueError(f"Invalid layer_id: {layer_id}")
```

### Pattern 3: Return Dictionaries

Tests expect structured return values:

```python
# Test expects:
result = service.annotate_resource(...)
assert result["success"] is True

# Your implementation:
def annotate_resource(self, ...):
    try:
        # ... do work ...
        return {"success": True, "resource_id": resource_id}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

## Running Tests During Development

### Run One Test at a Time

```bash
# Very specific
pytest tests/unit/services/test_ctf_annotation_service.py::TestAnnotateResource::test_annotate_resource_with_all_properties -v

# One test class
pytest tests/unit/services/test_ctf_annotation_service.py::TestAnnotateResource -v

# One test file
pytest tests/unit/services/test_ctf_annotation_service.py -v
```

### Watch Tests Pass

```bash
# Install pytest-watch
pip install pytest-watch

# Auto-run tests on file changes
ptw tests/unit/services/test_ctf_annotation_service.py
```

### Check Coverage

```bash
# Coverage for one service
pytest tests/unit/services/test_ctf_annotation_service.py --cov=src/services/ctf_annotation_service --cov-report=term-missing

# Overall coverage
pytest tests/ --cov=src/services --cov-report=html
open htmlcov/index.html
```

## Useful Test Fixtures

Available in `tests/fixtures/ctf_test_data.py`:

```python
from tests.fixtures.ctf_test_data import (
    # Terraform states for all scenarios
    get_m003_v1_base_terraform_state,
    get_m003_v2_cert_terraform_state,
    get_m003_v3_ews_terraform_state,
    get_m003_v4_blob_terraform_state,

    # Neo4j resource mocks
    get_sample_neo4j_resources,
    get_multi_layer_resources,

    # Validation data
    get_valid_ctf_property_values,
    get_invalid_ctf_property_values,

    # Scenario metadata
    M003_SCENARIOS
)
```

## When Stuck

### Read the Architecture

- **Architecture**: `docs/ctf_overlay_system/ARCHITECTURE.md`
- **API Reference**: `docs/ctf_overlay_system/API_REFERENCE.md`

### Look at Test Expectations

The tests show EXACTLY what your code should do:

```python
# Test shows:
def test_annotate_resource_with_all_properties(self, mock_neo4j_driver, sample_resource):
    service = CTFAnnotationService(neo4j_driver=mock_neo4j_driver)

    result = service.annotate_resource(
        resource_id=sample_resource["id"],
        layer_id="default",
        ctf_exercise="M003",
        ctf_scenario="v2-cert",
        ctf_role="target"
    )

    assert result["success"] is True
    assert result["resource_id"] == sample_resource["id"]

    # Verify Neo4j query was called with correct parameters
    mock_neo4j_driver.execute_query.assert_called_once()
    call_args = mock_neo4j_driver.execute_query.call_args
    assert "MERGE (r:Resource {id: $id})" in call_args[0][0]
```

This tells ye:
1. Method signature: `annotate_resource(resource_id, layer_id, ctf_exercise, ctf_scenario, ctf_role)`
2. Return format: `{"success": bool, "resource_id": str}`
3. Neo4j query pattern: `MERGE (r:Resource {id: $id})`
4. Parameters to pass: `id`, `layer_id`, `ctf_exercise`, `ctf_scenario`, `ctf_role`

## Progress Tracking

### Test Completion Checklist

- [ ] CTFAnnotationService (22 tests)
  - [ ] TestCTFAnnotationServiceInit (2 tests)
  - [ ] TestAnnotateResource (6 tests)
  - [ ] TestRoleDetermination (5 tests)
  - [ ] TestBatchAnnotation (3 tests)
  - [ ] TestSecurityValidation (3 tests)
  - [ ] TestErrorHandling (3 tests)

- [ ] CTFImportService (24 tests)
  - [ ] TestCTFImportServiceInit (2 tests)
  - [ ] TestParseTerraformState (6 tests)
  - [ ] TestExtractCTFProperties (4 tests)
  - [ ] TestMapResourceToNeo4j (3 tests)
  - [ ] TestImportFromState (6 tests)
  - [ ] TestErrorHandling (3 tests)

- [ ] CTFDeployService (26 tests)
  - [ ] TestCTFDeployServiceInit (2 tests)
  - [ ] TestQueryCTFResources (5 tests)
  - [ ] TestGenerateTerraformConfig (5 tests)
  - [ ] TestDeployScenario (7 tests)
  - [ ] TestCleanupScenario (4 tests)
  - [ ] TestErrorHandling (3 tests)

- [ ] Integration Tests (13 tests)
- [ ] E2E Tests (15 tests)

### Coverage Targets

Track coverage as ye implement:

```bash
pytest tests/unit/services/test_ctf_annotation_service.py --cov=src/services/ctf_annotation_service --cov-report=term
```

**Target**: 90%+ coverage per service

## Success Criteria

Ye be done when:

✅ All 100 tests pass
✅ Coverage >= 90% for each service
✅ Coverage >= 85% overall
✅ No warnings or errors in test output

## Final Check

Before submittin' yer work:

```bash
# Run all tests
pytest tests/ -v

# Generate coverage report
pytest tests/ --cov=src/services --cov-report=html

# Check coverage
open htmlcov/index.html

# Verify test count
pytest tests/ --collect-only | grep "test session"
# Should show: 100 tests collected (or more)
```

---

**Now set sail and make those tests pass, Builder! Arrr! 🏴‍☠️**

For detailed strategy and patterns, see:
- `tests/CTF_TEST_STRATEGY.md` - Comprehensive test strategy
- `tests/CTF_TEST_SUMMARY.md` - High-level overview
- `tests/DELIVERABLES_SUMMARY.txt` - Complete deliverables list

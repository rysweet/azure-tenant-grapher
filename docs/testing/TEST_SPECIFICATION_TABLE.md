# VNet Overlap Detection - Test Specification Table

Quick reference for all test cases. Use this as a checklist during TDD implementation.

## Test Coverage Summary

| Category | Test Count | Priority | Status |
|----------|------------|----------|--------|
| Unit: Message Formatting | 5 | HIGH | Not Started |
| Unit: Report Generation | 4 | MEDIUM | Not Started |
| Unit: Engine Integration | 3 | HIGH | Not Started |
| Unit: Edge Cases | 10 | HIGH | Not Started |
| Integration: E2E | 4 | HIGH | Not Started |
| **TOTAL** | **26** | - | **0% Complete** |

## Unit Tests: Message Formatting

### File: `tests/validation/test_address_space_validator_enhanced.py`

| Test ID | Test Name | Input | Expected Output | Priority |
|---------|-----------|-------|-----------------|----------|
| UF-01 | `test_format_conflict_warning_exact_duplicate` | Conflict with identical CIDRs (10.0.0.0/16 + 10.0.0.0/16) | Multi-line warning with vnet names, "peering will FAIL", remediation steps | HIGH |
| UF-02 | `test_format_conflict_warning_partial_overlap` | Conflict with partial overlap (10.0.0.0/16 overlaps 10.0.128.0/17) | Warning mentioning "overlaps", both networks shown | HIGH |
| UF-03 | `test_suggest_alternative_range_finds_available` | Used ranges: {10.0.0.0/16, 10.1.0.0/16} | Suggested: 10.2.0.0/16 | MEDIUM |
| UF-04 | `test_format_includes_azure_docs_link` | Any conflict | Warning contains Azure documentation URL | LOW |
| UF-05 | `test_format_includes_auto_renumber_hint` | Any conflict | Warning mentions --auto-renumber-conflicts flag | MEDIUM |

### Code Template
```python
class TestEnhancedWarningMessages:
    def test_format_conflict_warning_exact_duplicate(self):
        validator = AddressSpaceValidator()
        conflict = AddressSpaceConflict(
            vnet_names=["vnet1", "vnet2"],
            address_space="10.0.0.0/16",
        )
        warning = validator.format_conflict_warning(conflict)

        assert "VNet Address Space Conflict Detected" in warning
        assert "vnet1" in warning and "vnet2" in warning
        assert "10.0.0.0/16" in warning
        assert "peering will FAIL" in warning
        assert "Remediation" in warning
```

## Unit Tests: Report Generation

### File: `tests/validation/test_address_space_validator_enhanced.py`

| Test ID | Test Name | Input | Expected Output | Priority |
|---------|-----------|-------|-----------------|----------|
| RG-01 | `test_generate_report_no_conflicts` | ValidationResult with is_valid=True | Report with "No conflicts detected" and ✅ | MEDIUM |
| RG-02 | `test_generate_report_with_conflicts` | ValidationResult with 2 conflicts | Report with "## Conflict 1" and "## Conflict 2" | HIGH |
| RG-03 | `test_report_markdown_format` | Any ValidationResult | Valid markdown structure (headers, lists, bold) | HIGH |
| RG-04 | `test_report_written_to_file` | output_path provided | File created at specified path with correct content | HIGH |

### Code Template
```python
class TestConflictReportGeneration:
    def test_generate_report_with_conflicts(self, tmp_path):
        validator = AddressSpaceValidator()
        conflicts = [
            AddressSpaceConflict(["vnet1", "vnet2"], "10.0.0.0/16"),
            AddressSpaceConflict(["vnet3", "vnet4"], "10.1.0.0/16"),
        ]
        result = ValidationResult(
            is_valid=False, conflicts=conflicts, vnets_checked=4
        )

        report_path = tmp_path / "report.md"
        report = validator.generate_conflict_report(result, report_path)

        assert "## Conflict 1:" in report
        assert "## Conflict 2:" in report
        assert report_path.exists()
```

## Unit Tests: Engine Integration

### File: `tests/validation/test_address_space_validator_enhanced.py`

| Test ID | Test Name | Input | Expected Output | Priority |
|---------|-----------|-------|-----------------|----------|
| EI-01 | `test_validation_enabled_by_default` | validate_address_spaces=True (default) | AddressSpaceValidator.validate_resources() called | HIGH |
| EI-02 | `test_validation_can_be_disabled` | validate_address_spaces=False | Validation not called | MEDIUM |
| EI-03 | `test_conflict_report_generated_when_flag_set` | generate_conflict_report=True | Report file created at output_dir/vnet_conflict_report.md | HIGH |

### Code Template
```python
class TestEngineIntegration:
    def test_validation_enabled_by_default(self, mock_neo4j_driver):
        engine = TransformationEngine()
        graph = TenantGraph(resources=[...])

        with patch.object(AddressSpaceValidator, 'validate_resources') as mock:
            mock.return_value = ValidationResult(is_valid=True, ...)

            engine.generate_iac(graph, emitter, out_dir, validate_address_spaces=True)

            mock.assert_called_once()
```

## Unit Tests: Edge Cases

### File: `tests/validation/test_address_space_validator_enhanced.py`

| Test ID | Test Name | Input | Expected Output | Priority |
|---------|-----------|-------|-----------------|----------|
| EC-01 | `test_single_vnet_no_warnings` | 1 VNet with any address space | is_valid=True, conflicts=[] | HIGH |
| EC-02 | `test_no_vnets_no_warnings` | Resources without any VNets | is_valid=True, warning="No VNet resources found" | HIGH |
| EC-03 | `test_three_vnets_all_overlapping` | 3 VNets, all using 10.0.0.0/16 | conflicts detected mentioning all 3 VNets | MEDIUM |
| EC-04 | `test_complex_partial_overlaps` | 10.0.0.0/8, 10.1.0.0/16, 10.1.1.0/24 (nested) | Multiple overlaps detected | MEDIUM |
| EC-05 | `test_non_overlapping_in_different_ranges` | 10.0.0.0/16, 172.16.0.0/16, 192.168.0.0/16 | is_valid=True, no conflicts | HIGH |
| EC-06 | `test_multiple_address_spaces_per_vnet` | VNet1: [10.0.0.0/16, 10.1.0.0/16], VNet2: [10.1.0.0/16] | Conflict on 10.1.0.0/16 detected | MEDIUM |
| EC-07 | `test_invalid_cidr_notation_handled` | address_space=["not-a-valid-cidr"] | No crash, graceful handling | HIGH |
| EC-08 | `test_empty_address_space_uses_default` | address_space=[] | Default 10.0.0.0/16 used | MEDIUM |
| EC-09 | `test_ipv6_addresses_supported` | address_space=["fd00:db8::/64"] | Validates IPv6 correctly | LOW |
| EC-10 | `test_adjacent_non_overlapping_ranges` | 10.0.0.0/16, 10.1.0.0/16 (adjacent) | is_valid=True, no overlap | MEDIUM |

### Code Template
```python
class TestEdgeCases:
    def test_single_vnet_no_warnings(self):
        validator = AddressSpaceValidator()
        resources = [
            {"type": "Microsoft.Network/virtualNetworks", "name": "solo", "address_space": ["10.0.0.0/16"]}
        ]
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert len(result.conflicts) == 0

    def test_three_vnets_all_overlapping(self):
        validator = AddressSpaceValidator()
        resources = [
            {"type": "Microsoft.Network/virtualNetworks", "name": "vnet1", "address_space": ["10.0.0.0/16"]},
            {"type": "Microsoft.Network/virtualNetworks", "name": "vnet2", "address_space": ["10.0.0.0/16"]},
            {"type": "Microsoft.Network/virtualNetworks", "name": "vnet3", "address_space": ["10.0.0.0/16"]},
        ]
        result = validator.validate_resources(resources)

        assert not result.is_valid
        all_names = set()
        for conflict in result.conflicts:
            all_names.update(conflict.vnet_names)
        assert "vnet1" in all_names and "vnet2" in all_names and "vnet3" in all_names
```

## Integration Tests: End-to-End

### File: `tests/integration/test_vnet_overlap_detection_e2e.py`

| Test ID | Test Name | Scenario | Expected Output | Priority |
|---------|-----------|----------|-----------------|----------|
| E2E-01 | `test_e2e_overlap_detection_warnings_logged` | Full pipeline with overlapping VNets in Neo4j | Warnings appear in caplog with VNet names | HIGH |
| E2E-02 | `test_e2e_iac_generation_continues_despite_overlaps` | Full pipeline with overlapping VNets | IaC files generated (main.tf.json exists) | HIGH |
| E2E-03 | `test_e2e_conflict_report_generated` | Full pipeline with generate_conflict_report=True | vnet_conflict_report.md created | MEDIUM |
| E2E-04 | `test_e2e_validation_disabled` | Full pipeline with validate_address_spaces=False | No warnings logged, IaC still generated | MEDIUM |

### Code Template
```python
class TestVNetOverlapDetectionE2E:
    @pytest.fixture
    def neo4j_with_overlapping_vnets(self, neo4j_driver):
        """Create Neo4j database with overlapping VNets."""
        with neo4j_driver.session() as session:
            session.run("""
                CREATE (vnet1:Resource {
                    id: '/subscriptions/.../virtualNetworks/vnet1',
                    name: 'dtlatevet12_attack_vnet',
                    type: 'Microsoft.Network/virtualNetworks',
                    address_space: ['10.0.0.0/16'],
                    resourceGroup: 'test-rg',
                    location: 'eastus'
                })
                CREATE (vnet2:Resource {
                    id: '/subscriptions/.../virtualNetworks/vnet2',
                    name: 'dtlatevet12_infra_vnet',
                    type: 'Microsoft.Network/virtualNetworks',
                    address_space: ['10.0.0.0/16'],
                    resourceGroup: 'test-rg',
                    location: 'eastus'
                })
            """)
        yield neo4j_driver
        # Cleanup
        with neo4j_driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def test_e2e_overlap_detection_warnings_logged(
        self, neo4j_with_overlapping_vnets, tmp_path, caplog
    ):
        traverser = GraphTraverser(neo4j_with_overlapping_vnets)
        engine = TransformationEngine()
        emitter = TerraformEmitter()

        graph = asyncio.run(traverser.traverse())
        out_dir = tmp_path / "terraform"

        with caplog.at_level(logging.WARNING):
            engine.generate_iac(graph, emitter, out_dir, validate_address_spaces=True)

        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("Address space validation found" in msg for msg in warnings)
        assert any("dtlatevet12_attack_vnet" in msg for msg in warnings)
```

## Test Input Data: VNet Scenarios

### Scenario 1: Exact Duplicate (Demo Case)
```python
DEMO_OVERLAP_SCENARIO = [
    {
        "type": "Microsoft.Network/virtualNetworks",
        "name": "dtlatevet12_attack_vnet",
        "address_space": ["10.0.0.0/16"],
        "resourceGroup": "atevet12-Working",
        "location": "eastus"
    },
    {
        "type": "Microsoft.Network/virtualNetworks",
        "name": "dtlatevet12_infra_vnet",
        "address_space": ["10.0.0.0/16"],  # SAME!
        "resourceGroup": "atevet12-Working",
        "location": "eastus"
    }
]
```

### Scenario 2: Partial Overlap (Containment)
```python
PARTIAL_OVERLAP_SCENARIO = [
    {
        "type": "Microsoft.Network/virtualNetworks",
        "name": "large_hub_vnet",
        "address_space": ["10.0.0.0/16"],     # 65,536 IPs
        "resourceGroup": "hub-rg",
        "location": "eastus"
    },
    {
        "type": "Microsoft.Network/virtualNetworks",
        "name": "small_spoke_vnet",
        "address_space": ["10.0.128.0/17"],   # 32,768 IPs (within hub)
        "resourceGroup": "spoke-rg",
        "location": "eastus"
    }
]
```

### Scenario 3: Multiple Conflicts
```python
MULTIPLE_CONFLICTS_SCENARIO = [
    {"type": "Microsoft.Network/virtualNetworks", "name": "prod_east", "address_space": ["10.0.0.0/16"]},
    {"type": "Microsoft.Network/virtualNetworks", "name": "prod_west", "address_space": ["10.0.0.0/16"]},  # Conflict 1
    {"type": "Microsoft.Network/virtualNetworks", "name": "dev_vnet", "address_space": ["10.1.0.0/16"]},
    {"type": "Microsoft.Network/virtualNetworks", "name": "test_vnet", "address_space": ["10.1.0.0/16"]},  # Conflict 2
    {"type": "Microsoft.Network/virtualNetworks", "name": "staging", "address_space": ["10.2.0.0/16"]},    # No conflict
]
```

### Scenario 4: No Conflicts (Valid Configuration)
```python
VALID_SCENARIO = [
    {"type": "Microsoft.Network/virtualNetworks", "name": "vnet_10", "address_space": ["10.0.0.0/16"]},
    {"type": "Microsoft.Network/virtualNetworks", "name": "vnet_172", "address_space": ["172.16.0.0/16"]},
    {"type": "Microsoft.Network/virtualNetworks", "name": "vnet_192", "address_space": ["192.168.0.0/16"]},
]
```

### Scenario 5: Complex Nested Overlaps
```python
COMPLEX_OVERLAP_SCENARIO = [
    {"type": "Microsoft.Network/virtualNetworks", "name": "super_vnet", "address_space": ["10.0.0.0/8"]},    # Huge
    {"type": "Microsoft.Network/virtualNetworks", "name": "large_vnet", "address_space": ["10.1.0.0/16"]},   # Inside super
    {"type": "Microsoft.Network/virtualNetworks", "name": "medium_vnet", "address_space": ["10.1.1.0/24"]},  # Inside large
    {"type": "Microsoft.Network/virtualNetworks", "name": "small_vnet", "address_space": ["10.1.1.128/25"]}, # Inside medium
]
```

## Test Assertions: Common Patterns

### Check ValidationResult Structure
```python
assert isinstance(result, ValidationResult)
assert result.is_valid in (True, False)
assert isinstance(result.conflicts, list)
assert isinstance(result.warnings, list)
assert isinstance(result.vnets_checked, int)
assert result.vnets_checked >= 0
```

### Check Conflict Detection
```python
assert not result.is_valid  # Conflicts detected
assert len(result.conflicts) > 0
assert all(isinstance(c, AddressSpaceConflict) for c in result.conflicts)
```

### Check Conflict Content
```python
conflict = result.conflicts[0]
assert len(conflict.vnet_names) == 2
assert "vnet1" in conflict.vnet_names
assert "vnet2" in conflict.vnet_names
assert "10.0.0.0/16" in conflict.address_space
assert conflict.severity == "warning"
assert len(conflict.message) > 0
```

### Check Warning Messages (Logging)
```python
with caplog.at_level(logging.WARNING):
    # ... code that generates warnings ...
    pass

warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
assert len(warning_messages) > 0
assert any("Address space validation" in msg for msg in warning_messages)
assert any("10.0.0.0/16" in msg for msg in warning_messages)
```

### Check Report File
```python
report_path = output_dir / "vnet_conflict_report.md"
assert report_path.exists()

content = report_path.read_text()
assert "# VNet Address Space Conflict Report" in content
assert "**Total VNets**:" in content
assert "## Conflict 1:" in content
assert "`vnet1`" in content  # Markdown code formatting
```

## Mock Objects and Fixtures

### Mock Neo4j Driver
```python
@pytest.fixture
def mock_neo4j_driver():
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    return driver
```

### Mock TenantGraph
```python
@pytest.fixture
def tenant_graph_with_overlaps():
    return TenantGraph(
        resources=[
            {"type": "Microsoft.Network/virtualNetworks", "name": "vnet1", "address_space": ["10.0.0.0/16"]},
            {"type": "Microsoft.Network/virtualNetworks", "name": "vnet2", "address_space": ["10.0.0.0/16"]},
        ],
        relationships=[]
    )
```

### Temporary Output Directory
```python
@pytest.fixture
def output_dir(tmp_path):
    out = tmp_path / "iac_output"
    out.mkdir()
    return out
```

## Test Execution Commands

### Run All Tests
```bash
# All enhanced validator tests
pytest tests/validation/test_address_space_validator_enhanced.py -v

# All integration tests
pytest tests/integration/test_vnet_overlap_detection_e2e.py -v

# All tests with coverage
pytest tests/validation/test_address_space_validator_enhanced.py \
       tests/integration/test_vnet_overlap_detection_e2e.py \
       --cov=src/validation/address_space_validator \
       --cov=src/iac/engine \
       --cov-report=term-missing \
       --cov-report=html
```

### Run Specific Test
```bash
# Single test
pytest tests/validation/test_address_space_validator_enhanced.py::TestEnhancedWarningMessages::test_format_conflict_warning_exact_duplicate -v

# Test class
pytest tests/validation/test_address_space_validator_enhanced.py::TestEnhancedWarningMessages -v

# Test by keyword
pytest -k "format_conflict" -v
```

### Run with Debugging
```bash
# Show print statements
pytest tests/validation/test_address_space_validator_enhanced.py -v -s

# Drop into debugger on failure
pytest tests/validation/test_address_space_validator_enhanced.py -v --pdb

# Stop at first failure
pytest tests/validation/test_address_space_validator_enhanced.py -v -x
```

## Coverage Goals

| Module | Target Coverage | Critical Paths |
|--------|----------------|----------------|
| `address_space_validator.py` (new methods) | 100% | format_conflict_warning, generate_conflict_report |
| `engine.py` (modified lines) | 95% | Validation integration, report generation |
| `cli_commands.py` (new flags) | 90% | Flag parsing, parameter passing |

## Test Checklist for TDD

- [ ] **Phase 1: Write Failing Tests**
  - [ ] Create test file structure
  - [ ] Write unit tests for message formatting (5 tests)
  - [ ] Write unit tests for report generation (4 tests)
  - [ ] Write unit tests for engine integration (3 tests)
  - [ ] Write unit tests for edge cases (10 tests)
  - [ ] Write integration tests (4 tests)
  - [ ] Verify all tests fail (red)

- [ ] **Phase 2: Implement Features**
  - [ ] Implement format_conflict_warning()
  - [ ] Implement _suggest_alternative_range()
  - [ ] Implement generate_conflict_report()
  - [ ] Update engine.py integration
  - [ ] Add CLI flags

- [ ] **Phase 3: Pass Tests**
  - [ ] Run tests, fix implementation until green
  - [ ] Verify coverage > 90%
  - [ ] Run linting and type checking

- [ ] **Phase 4: Refactor**
  - [ ] Improve code clarity
  - [ ] Add docstrings
  - [ ] Optimize performance if needed

- [ ] **Phase 5: Integration**
  - [ ] Run full test suite
  - [ ] Test with real Neo4j data
  - [ ] Update documentation

## Test Data Generation Helper

```python
def create_vnet_resource(name: str, address_space: str, rg: str = "test-rg") -> Dict[str, Any]:
    """Helper to create VNet resource for testing."""
    return {
        "id": f"/subscriptions/test-sub/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{name}",
        "type": "Microsoft.Network/virtualNetworks",
        "name": name,
        "address_space": [address_space],
        "resourceGroup": rg,
        "location": "eastus",
        "tags": {}
    }

# Usage in tests:
resources = [
    create_vnet_resource("vnet1", "10.0.0.0/16"),
    create_vnet_resource("vnet2", "10.0.0.0/16"),  # Conflict!
    create_vnet_resource("vnet3", "10.1.0.0/16"),  # No conflict
]
```

## Success Metrics

After implementation, verify:

1. **All Tests Pass**: 26/26 tests passing
2. **Coverage Met**: >90% coverage for new/modified code
3. **No Regressions**: Existing tests still pass
4. **Linting Clean**: Ruff, pyright, bandit all pass
5. **Manual Testing**: Test with actual demo data from Neo4j

## Summary

This test specification provides:
- 26 comprehensive test cases
- Clear input/output expectations
- Code templates for quick implementation
- Test data scenarios
- Coverage goals and metrics

Use this as your TDD checklist during implementation of Issue #334.

---

**Next Step**: Start with UF-01 (format_conflict_warning for exact duplicate) and work through the table sequentially.

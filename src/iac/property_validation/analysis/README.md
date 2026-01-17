# Code Analyzer Brick

**AST-based static analysis for extracting property mappings from Terraform handler files.**

## Purpose

The Code Analyzer brick analyzes Python handler files to extract:
- Terraform config properties written to output
- Azure properties read from source
- Bidirectional property mappings (Azure → Terraform)
- Handler metadata (handled types, Terraform types)

This enables automated validation of property coverage and gap analysis.

## Philosophy

- **AST-based**: Uses Python's `ast` module for accurate parsing
- **Standard library only**: No external dependencies (ast, re, pathlib)
- **Pattern detection**: Identifies 4 key property usage patterns
- **Self-contained**: Complete implementation in this directory

## Public API

```python
from iac.property_validation.analysis import HandlerAnalyzer, analyze_handler
from iac.property_validation.models import HandlerPropertyUsage, PropertyUsage

# Analyze a handler file
result: HandlerPropertyUsage = analyze_handler(Path("storage_account.py"))

# Access results
print(f"Handler: {result.handler_class}")
print(f"Terraform keys: {result.terraform_writes}")
print(f"Azure keys: {result.azure_reads}")
print(f"Mappings: {result.bidirectional_mappings}")
```

## Detection Patterns

### Pattern 1: Direct Assignment
```python
config["account_tier"] = "Standard"
```
**Detection**: Terraform write

### Pattern 2: Dictionary Update
```python
config.update({
    "account_tier": account_tier,
    "location": location,
})
```
**Detection**: Multiple Terraform writes

### Pattern 3: Azure Property Read
```python
tier = properties.get("accountTier", "Standard")
```
**Detection**: Azure read

### Pattern 4: Bidirectional Mapping
```python
config["account_tier"] = properties.get("accountTier", "Standard")
```
**Detection**: Terraform write + Azure read + mapping

## Module Structure

```
analysis/
├── __init__.py              # Public API exports
├── handler_analyzer.py      # Main analyzer orchestration
├── ast_parser.py           # AST parsing and walking
├── property_extractor.py   # Pattern extraction logic
├── example_usage.py        # Usage examples
├── test_analyzer.py        # Comprehensive tests
└── README.md               # This file
```

## Usage Examples

### Basic Analysis

```python
from pathlib import Path
from iac.property_validation.analysis import analyze_handler

# Analyze a handler file
handler_path = Path("handlers/storage/storage_account.py")
result = analyze_handler(handler_path)

if result:
    print(f"Found {len(result.properties)} property usages")
    print(f"Terraform keys: {result.terraform_writes}")
    print(f"Azure keys: {result.azure_reads}")
```

### Detailed Analysis

```python
from iac.property_validation.analysis import HandlerAnalyzer

analyzer = HandlerAnalyzer(handler_path)
result = analyzer.analyze()

# Examine individual property usages
for prop in result.properties:
    print(f"Line {prop.line_number}: {prop.usage_type}")
    print(f"  Code: {prop.code_snippet}")
    if prop.terraform_key:
        print(f"  Terraform: {prop.terraform_key}")
    if prop.azure_key:
        print(f"  Azure: {prop.azure_key}")
```

### Batch Analysis

```python
from pathlib import Path
from iac.property_validation.analysis import analyze_handler

handlers_dir = Path("handlers")
results = []

for handler_file in handlers_dir.rglob("*.py"):
    if handler_file.name != "__init__.py":
        result = analyze_handler(handler_file)
        if result and result.handler_class:
            results.append(result)

# Summary statistics
total_tf_keys = sum(len(r.terraform_writes) for r in results)
total_azure_keys = sum(len(r.azure_reads) for r in results)
print(f"Analyzed {len(results)} handlers")
print(f"Total Terraform keys: {total_tf_keys}")
print(f"Total Azure keys: {total_azure_keys}")
```

## Data Models

### PropertyUsage

Single property usage instance:

```python
@dataclass
class PropertyUsage:
    property_name: str      # Property identifier
    usage_type: str         # "read", "write", or "both"
    terraform_key: str      # Terraform config key
    azure_key: str          # Azure property key
    line_number: int        # Source line number
    code_snippet: str       # Code context
```

### HandlerPropertyUsage

Complete handler analysis:

```python
@dataclass
class HandlerPropertyUsage:
    handler_file: str                        # File path
    handler_class: str                       # Class name
    handled_types: Set[str]                  # Azure types
    terraform_types: Set[str]                # Terraform types
    properties: List[PropertyUsage]          # All usages
    terraform_writes: Set[str]               # Config keys
    azure_reads: Set[str]                    # Property keys
    bidirectional_mappings: Dict[str, str]  # TF -> Azure
```

## Implementation Details

### AST Parsing (ast_parser.py)

- **HandlerASTParser**: Walks Python AST to find patterns
- **Methods**:
  - `parse()`: Parse file into AST
  - `extract_handler_class()`: Find ResourceHandler subclass
  - `extract_class_variable()`: Extract HANDLED_TYPES, TERRAFORM_TYPES
  - `find_subscript_accesses()`: Find `dict["key"]` patterns
  - `find_method_calls()`: Find `.get()`, `.update()` calls
  - `find_dict_literals()`: Find dict literals in update()

### Property Extraction (property_extractor.py)

- **PropertyExtractor**: Classify and aggregate property usage
- **Methods**:
  - `process_subscript_accesses()`: Classify `config["key"]` vs `properties["key"]`
  - `process_method_calls()`: Handle `.get()` and `.update()`
  - `process_dict_literals()`: Extract keys from `config.update({...})`
  - `process_assignment_patterns()`: Detect bidirectional mappings

### Handler Analyzer (handler_analyzer.py)

- **HandlerAnalyzer**: Orchestrates parsing and extraction
- **Methods**:
  - `analyze()`: Main entry point, returns HandlerPropertyUsage
  - `_extract_property_patterns()`: Coordinate all pattern detection

## Testing

Run the test suite:

```bash
# Using pytest (if installed)
pytest src/iac/property_validation/analysis/test_analyzer.py -v

# Direct execution
python src/iac/property_validation/analysis/test_analyzer.py
```

Tests cover:
- ✅ Basic handler metadata extraction
- ✅ Direct assignment pattern detection
- ✅ Dictionary update pattern detection
- ✅ Azure property read pattern detection
- ✅ Bidirectional mapping detection
- ✅ Real storage account handler analysis
- ✅ Error handling for invalid files

## Real-World Example

Analyzing the Storage Account handler:

```python
from pathlib import Path
from iac.property_validation.analysis import analyze_handler

handler = Path("handlers/storage/storage_account.py")
result = analyze_handler(handler)

print(f"Handler: {result.handler_class}")
# Output: StorageAccountHandler

print(f"Terraform keys: {len(result.terraform_writes)}")
# Output: 11 keys (account_tier, account_replication_type, etc.)

print(f"Azure keys: {len(result.azure_reads)}")
# Output: 17 keys (accountTier, replicationType, etc.)

print(f"Mappings: {len(result.bidirectional_mappings)}")
# Output: Detected mappings between TF and Azure properties
```

## Error Handling

The analyzer handles errors gracefully:

```python
result = analyze_handler(Path("/nonexistent/file.py"))
# Returns: None (prints error message)

result = analyze_handler(Path("invalid_syntax.py"))
# Returns: None (prints SyntaxError)
```

## Performance

- **Fast**: AST parsing is efficient (< 100ms per handler)
- **Memory efficient**: Processes files one at a time
- **Scalable**: Can analyze hundreds of handlers quickly

## Integration

This brick integrates with:

1. **Schema Loader** → Property definitions from Terraform schemas
2. **Manifest Generator** → Expected properties for resource types
3. **Validator** → Compare actual vs expected property coverage

## Limitations

- **Python only**: Analyzes Python handler files (not other languages)
- **Static analysis**: Doesn't execute code, detects patterns only
- **Pattern-based**: May miss dynamic property assignments
- **AST-dependent**: Requires valid Python syntax

## Future Enhancements

Potential improvements:
- Support for complex expressions (ternary, comprehensions)
- Detection of conditional property writes
- Control flow analysis for optional properties
- Type inference for property values

## Dependencies

**Standard Library Only:**
- `ast` - Abstract Syntax Tree parsing
- `pathlib` - File path handling
- `typing` - Type hints
- `dataclasses` - Data models
- `re` - Regular expressions

**No external dependencies required.**

## License

Part of Azure Tenant Grapher (atg2) project.

## See Also

- [Property Validation README](../README.md) - Overview of property validation system
- [Models](../models.py) - Data model definitions
- [Example Usage](./example_usage.py) - More usage examples

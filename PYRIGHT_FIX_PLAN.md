# Pyright Error Fix Plan - Issue #653

## Current State
- **749 errors** remaining (down from initial 785, reduced from original 663+)
- **42 warnings**
- Work already started on branch `feat/issue-653-fix-pyright-errors`

## Error Categories (Prioritized by Impact)

### 1. Unused Code (HIGHEST PRIORITY - Zero-BS Principle)
- **cli_handler.py**: 213 errors (mostly unused imports, variables, functions)
- **Impact**: Violates Zero-BS principle, easy wins
- **Fix**: Remove all unused imports, variables, and functions

### 2. Optional/None Subscripting (30 errors)
- Pattern: `Object of type "None" is not subscriptable`
- **Fix**: Add None checks before subscripting
- Example:
  ```python
  # Before
  value = optional_dict["key"]

  # After
  value = optional_dict["key"] if optional_dict is not None else None
  ```

### 3. Missing Generic Type Arguments (55 errors total)
- **21 Dict errors**: `Expected type arguments for generic class "Dict"`
- **13 dict errors**: `Expected type arguments for generic class "dict"`
- **8 set errors**: `Expected type arguments for generic class "set"`
- **8 list errors**: `Expected type arguments for generic class "list"`
- **5 MultiDiGraph/DiGraph/Graph errors**: Missing node type parameters
- **Fix**: Add type parameters: `dict[str, Any]`, `list[str]`, `set[int]`, etc.

### 4. datetime.utcnow() Deprecation (19 errors)
- Pattern: `The method "utcnow" in class "datetime" is deprecated`
- **Fix**: Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`
- Import needed: `from datetime import timezone`

### 5. Protected Method Access (38 errors)
- **19 errors**: `_add_result` is protected
- **10 errors**: `_check_target_exists` is protected
- **9 errors**: `_translate_resource_id` is protected
- **Fix Options**:
  - Make methods public (remove leading underscore) if intended for external use
  - Keep protected and fix access patterns (use public API)
  - Add proper encapsulation

### 6. Neo4j LiteralString Issues (15 errors)
- Pattern: `Argument of type "str" cannot be assigned to parameter "query" of type "LiteralString | Query"`
- **Fix**: Use proper query construction or cast to LiteralString
- Example:
  ```python
  from typing import LiteralString
  query: LiteralString = "MATCH (n) RETURN n"  # type: ignore[assignment]
  # OR use neo4j.Query() for dynamic queries
  ```

### 7. Lambda Type Hints (9 errors)
- Pattern: `Type of parameter "x" is unknown` / `Return type of lambda is unknown`
- **Fix**: Add explicit type hints to lambdas
- Example:
  ```python
  # Before
  sorted(items, key=lambda x: x["value"])

  # After
  sorted(items, key=lambda x: dict[str, Any]: x["value"])
  ```

### 8. Neo4j DateTime Attribute Access (8 errors)
- Pattern: `Cannot access attribute "date" for class "DateTime"`
- **Fix**: Use proper Neo4j DateTime methods or convert to Python datetime
- Example:
  ```python
  # Neo4j DateTime doesn't have .date() - need to convert
  python_dt = neo4j_datetime.to_native()
  date_val = python_dt.date()
  ```

### 9. Missing Parameter Types (22 errors)
- **8 errors**: `Type annotation is missing for parameter "kwargs"`
- **7 errors**: `Type annotation is missing for parameter "tx"`
- **7 errors**: `Type annotation is missing for parameter "cursor"`
- **Fix**: Add proper type hints:
  ```python
  def func(tx: neo4j.Transaction, cursor: neo4j.Cursor, **kwargs: Any) -> None:
      pass
  ```

### 10. Unnecessary isinstance() Calls (9 errors)
- Pattern: `Unnecessary isinstance call; "str" is always an instance of "str"`
- **Fix**: Remove redundant isinstance checks

### 11. Tuple Construction Errors (3 errors in graph_id_resolver.py)
- Pattern: `Expected 1 positional argument (reportCallIssue)`
- **Issue**: `queries.append(query_str, params_dict)` should be `queries.append((query_str, params_dict))`
- **Fix**: Wrap in tuple

## Implementation Strategy

### Phase 1: Quick Wins (Target: -300 errors)
1. Fix graph_id_resolver.py tuple construction (3 errors) - CRITICAL
2. Remove unused code from cli_handler.py (213 errors)
3. Remove unnecessary isinstance() calls (9 errors)
4. Fix datetime.utcnow() deprecation (19 errors)

### Phase 2: Type Annotations (Target: -200 errors)
1. Add generic type arguments (55 errors)
2. Add missing parameter types (22 errors)
3. Fix lambda type hints (9 errors)

### Phase 3: Complex Fixes (Target: -150 errors)
1. Fix Optional/None subscripting (30 errors)
2. Fix protected method access (38 errors)
3. Fix Neo4j LiteralString issues (15 errors)
4. Fix Neo4j DateTime attribute access (8 errors)

### Phase 4: Remaining Errors
1. File-by-file cleanup of remaining errors
2. Focus on files with most remaining errors:
   - hierarchical_spec_generator.py (33 errors)
   - orchestrator.py (31 errors)
   - cli_commands.py (29 errors)
   - dataplane_orchestrator.py (25 errors)

## Success Criteria
- ✓ pyright reports **0 errors** on src/ directory
- ✓ All existing tests pass
- ✓ No functional changes to code behavior
- ✓ pyright pre-commit hook passes
- ✓ Type hints follow ruthless simplicity (no over-engineering)

## Files to Track
- Top error files:
  1. cli_handler.py (213 errors)
  2. hierarchical_spec_generator.py (33 errors)
  3. orchestrator.py (31 errors)
  4. cli_commands.py (29 errors)
  5. dataplane_orchestrator.py (25 errors)
  6. architectural_pattern_analyzer.py (20 errors)

## Notes
- This is pure type-fixing work - NO functional changes
- Follow Zero-BS principle: Remove dead code aggressively
- Keep type hints simple and practical
- Test after each major file fix

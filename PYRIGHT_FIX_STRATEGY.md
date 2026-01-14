# Pyright Type Checking Fix Strategy

## Overview
Fix 663 pyright errors and 42 warnings across src/ directory through systematic type annotation improvements.

## Error Distribution Analysis

### Top Error Types
1. **reportArgumentType** (122 errors) - Wrong types passed to functions
2. **reportMissingTypeArgument** (104 errors) - Generic types need type params
3. **reportAttributeAccessIssue** (69 errors) - Missing attributes/methods
4. **reportUnusedImport** (58 errors) - Unused imports to remove
5. **reportCallIssue** (56 errors) - Wrong function calls
6. **reportPrivateUsage** (52 errors) - Using private members incorrectly
7. **reportMissingParameterType** (41 errors) - Parameters need type hints

### Files with Most Errors
1. `terraform/handlers/__init__.py` - 57 errors (mostly unused imports)
2. `services/scale_down/orchestrator.py` - 40 errors (generic types, Graph vs DiGraph)
3. `iac/cli_handler.py` - 34 errors
4. `hierarchical_spec_generator.py` - 33 errors
5. `cli_commands.py` - 29 errors

## Implementation Strategy

### Phase 1: Quick Wins (Unused Imports)
**Target**: 58 errors - `reportUnusedImport`
**Files**: Primarily `terraform/handlers/__init__.py` (57 errors)
**Approach**: Remove unused imports
**Estimated time**: 30 minutes
**Risk**: Low - only affects imports

### Phase 2: Generic Type Arguments
**Target**: 104 errors - `reportMissingTypeArgument`
**Common patterns**:
- `dict` → `dict[str, Any]` or more specific
- `list` → `list[str]` or more specific
- `Graph` → `Graph[str]` (networkx)
- `DiGraph` → `DiGraph[str]` (networkx)
- `Set` → `set[str]`

**Approach**:
1. Add type arguments to container types
2. Use `Any` only when truly necessary
3. Prefer specific types when clear from context

**Estimated time**: 2-3 hours
**Risk**: Low-Medium - needs careful type selection

### Phase 3: Missing Parameter Types
**Target**: 41 errors - `reportMissingParameterType`
**Approach**:
1. Add type hints to function parameters
2. Add return type hints
3. Handle Optional/None cases with `Optional[T]` or `T | None`
4. Use Callable[...] for function parameters

**Estimated time**: 1-2 hours
**Risk**: Medium - must understand function contracts

### Phase 4: Type Mismatches
**Target**: 122 errors - `reportArgumentType`
**Common issues**:
- Graph vs DiGraph confusion
- Set vs List mismatches
- Optional handling

**Approach**:
1. Align types with function signatures
2. Add type conversions where needed (`list(set_var)`)
3. Fix Graph/DiGraph inconsistencies

**Estimated time**: 2-3 hours
**Risk**: Medium-High - may reveal logic issues

### Phase 5: Attribute Access Issues
**Target**: 69 errors - `reportAttributeAccessIssue`
**Approach**:
1. Check if attributes exist
2. Use protocols for duck typing
3. Add proper inheritance/interfaces
4. Use `hasattr()` checks where appropriate

**Estimated time**: 2 hours
**Risk**: High - may require interface design

### Phase 6: Remaining Issues
**Target**: ~200 errors (various types)
**Approach**: Case-by-case fixes for:
- Private usage issues
- Call issues
- Optional subscript/member access
- Lambda type annotations

**Estimated time**: 2-3 hours
**Risk**: Varies by issue

## Ruthless Simplicity Principles

1. **Don't over-engineer**: Use `Any` when appropriate, not complex union types
2. **Favor clarity**: `dict[str, Any]` > complex TypedDict when data is dynamic
3. **Progressive typing**: Start with simple types, refine only if needed
4. **No type gymnastics**: If type hints become complex, question the design

## Testing Strategy

1. **After each phase**: Run `pyright src/` to verify progress
2. **After each file**: Run full test suite to ensure no breakage
3. **Final validation**: Ensure pyright pre-commit hook passes

## Success Criteria

- [ ] Pyright reports 0 errors on `src/`
- [ ] All existing tests pass
- [ ] No functional changes (type annotations only)
- [ ] Type hints follow ruthless simplicity
- [ ] Pre-commit pyright hook passes

## Roll-back Plan

- Each phase committed separately
- Easy to revert specific phases if issues arise
- Git allows bisecting to find problematic changes

## Estimated Total Time

- Quick wins: 0.5 hours
- Generic types: 2-3 hours
- Parameter types: 1-2 hours
- Type mismatches: 2-3 hours
- Attribute access: 2 hours
- Remaining: 2-3 hours

**Total: 10-14 hours spread over 1-2 days**

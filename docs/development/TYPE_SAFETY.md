# Type Safety Reference

**ATG Remote type safety patterns for Python 3.10+ with Pyright.**

## Current Status

- **Errors:** 0
- **Warnings:** 6 (import-related, non-blocking)
- **Mode:** Basic (upgradeable to strict)

## Core Patterns

### 1. Protocol Pattern for Neo4j (Most Important)

Use protocols instead of `Any` for external library types:

```python
# src/remote/db/protocols.py
from typing import Protocol, Any

class Neo4jTransaction(Protocol):
    async def run(self, query: str, **parameters: Any) -> Neo4jResult: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...

class Neo4jSession(Protocol):
    async def run(self, query: str, **parameters: Any) -> Neo4jResult: ...
    def begin_transaction(self) -> AsyncContextManager[Neo4jTransaction]: ...
```

**Usage:**
```python
async def chunked_transaction(
    session: Neo4jSession,
    items: list[T],
    process_fn: Callable[[Neo4jTransaction, list[T]], Awaitable[T]],
) -> list[T]:
    # Type-safe implementation
```

### 2. ParamSpec for Decorators

Preserve function signatures in decorators:

```python
from typing import TypeVar, ParamSpec

T = TypeVar("T")
P = ParamSpec("P")

def require_api_key(
    func: Callable[P, Awaitable[T]],
) -> Callable[P, Awaitable[T]]:
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        # Decorator logic
        return await func(*args, **kwargs)
    return wrapper
```

### 3. TypedDict for Structured Data

Type-safe dictionaries with known structure:

```python
# src/remote/auth/types.py
from typing import TypedDict

class AuthContext(TypedDict):
    environment: str
    client_id: str
```

**Usage:**
```python
auth_context: AuthContext = {
    "environment": validation["environment"],
    "client_id": validation["client_id"],
}
request.state.auth = auth_context
```

### 4. Type Aliases for Complex Types

Define once, use everywhere:

```python
# src/remote/dispatcher.py
CommandMetadata = dict[str, Any]
ExecutionResult = dict[str, Any]
ProgressCallback = Callable[[float, str], None]
```

## Modern Syntax Migration

### Before (Old Style)
```python
from typing import Optional, Dict, List, Union

def process(data: Optional[Dict[str, List[str]]]) -> Union[str, int]:
    ...
```

### After (Python 3.10+)
```python
def process(data: dict[str, list[str]] | None) -> str | int:
    ...
```

**Key Changes:**
- `dict[K, V]` not `Dict[K, V]`
- `list[T]` not `List[T]`
- `X | None` not `Optional[X]`
- `X | Y` not `Union[X, Y]`
- Import `Callable`, `Awaitable` from `collections.abc` not `typing`

## Avoiding type: ignore

### Pattern 1: Explicit None Checks
```python
# Bad
metadata = self.get_command_metadata(command)
required = metadata.get("required_params", [])  # type: ignore[union-attr]

# Good
metadata = self.get_command_metadata(command)
if metadata is None:
    raise CommandNotFoundError(f"Metadata not found: {command}")
required = metadata.get("required_params", [])
```

### Pattern 2: FastAPI Request State
```python
# Bad
request.auth_context = {...}  # type: ignore[misc]

# Good
request.state.auth = {...}  # FastAPI pattern
```

### Pattern 3: None Safety
```python
# Bad
raise last_error  # type: ignore[misc]

# Good
if last_error is not None:
    raise last_error
raise RuntimeError("Unexpected state: no error recorded")
```

## Quick Reference

| Need | Use | Example |
|------|-----|---------|
| External library types | Protocol | `Neo4jSession(Protocol)` |
| Decorator type safety | ParamSpec | `P = ParamSpec("P")` |
| Structured dictionaries | TypedDict | `class AuthContext(TypedDict)` |
| Complex types | Type alias | `CommandMetadata = dict[str, Any]` |
| Generic functions | TypeVar | `T = TypeVar("T")` |
| Runtime validation | Pydantic | `class Config(BaseModel)` |

## Workflow

```bash
# Check types before commit
pyright src/remote

# CI enforces zero errors
```

## When to Use Any

Only when truly necessary, with documentation:

```python
def process_config(config: dict[str, Any]) -> None:
    """
    Uses Any because config structure varies by environment
    and is validated at runtime by Pydantic models.
    """
```

## External References

- [PEP 544 - Protocols](https://peps.python.org/pep-0544/)
- [PEP 604 - Union Operators](https://peps.python.org/pep-0604/)
- [PEP 612 - ParamSpec](https://peps.python.org/pep-0612/)
- [Pyright](https://github.com/microsoft/pyright)

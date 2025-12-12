"""
Transaction patterns for long-running operations.

Philosophy:
- Explicit transaction boundaries
- Progress tracking for user visibility
- Graceful handling of transaction timeouts
- Retry logic with exponential backoff

Patterns:
    chunked_transaction: Process large batches in chunks
    with_retry: Retry transient failures with backoff
"""

import asyncio
import logging
from typing import Any, Callable, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def chunked_transaction(
    session: Any,
    items: List[T],
    chunk_size: int,
    process_fn: Callable[..., Any],
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[Any]:
    """
    Process items in chunked transactions.

    Use for large batch operations that would timeout in single transaction.

    Philosophy:
    - Break large operations into manageable chunks
    - Commit after each chunk (don't lose progress)
    - Report progress to user

    Args:
        session: Neo4j session
        items: Items to process
        chunk_size: Items per transaction
        process_fn: Async function to process chunk in transaction
        progress_callback: Optional callback(processed, total)

    Returns:
        List of results from each chunk

    Example:
        async def process_chunk(tx, chunk):
            query = "CREATE (n:Node {id: $id})"
            for item in chunk:
                await tx.run(query, id=item)
            return len(chunk)

        results = await chunked_transaction(
            session,
            items=range(1000),
            chunk_size=100,
            process_fn=process_chunk
        )
    """
    results = []
    total = len(items)

    for i in range(0, total, chunk_size):
        chunk = items[i : i + chunk_size]

        async with session.begin_transaction() as tx:
            result = await process_fn(tx, chunk)
            await tx.commit()
            results.append(result)

        if progress_callback:
            processed = min(i + chunk_size, total)
            progress_callback(processed, total)

    return results


async def with_retry(
    session: Any,
    operation: Callable[..., Any],
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> Any:
    """
    Execute operation with retry logic.

    Use for operations that may fail due to transient errors.

    Philosophy:
    - Retry transient failures (network issues, timeouts)
    - Exponential backoff to avoid overwhelming server
    - Fail fast after max retries

    Args:
        session: Neo4j session
        operation: Async function to execute in transaction
        max_retries: Max retry attempts
        retry_delay: Initial delay between retries (exponential backoff)

    Returns:
        Result from operation

    Raises:
        Exception: If operation fails after max retries

    Example:
        async def create_node(tx):
            result = await tx.run("CREATE (n:Node {id: $id}) RETURN n", id=123)
            return await result.single()

        node = await with_retry(session, create_node, max_retries=3)
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            async with session.begin_transaction() as tx:
                result = await operation(tx)
                await tx.commit()
                return result
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = retry_delay * (2**attempt)  # Exponential backoff
                await asyncio.sleep(delay)
                logger.warning(f"Retry {attempt + 1}/{max_retries} after error: {e}")
            else:
                logger.error(f"Operation failed after {max_retries} attempts")

    # Re-raise last error if all retries failed
    raise last_error


__all__ = ["chunked_transaction", "with_retry"]

"""Caching layer for graph embeddings to avoid expensive recomputation.

This module provides persistent storage for node embeddings using numpy's
.npz format, enabling fast loading for repeated abstractions and reducing
the computational overhead of node2vec training.
"""

import hashlib
import logging
from pathlib import Path
from typing import Dict, Optional

import numpy as np  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class GraphEmbeddingCache:
    """Persistent cache for node embeddings.

    Stores embeddings in .npz files with metadata validation to ensure
    cache consistency. Embeddings are keyed by tenant ID and configuration
    hash to handle parameter changes.
    """

    def __init__(self, cache_dir: Path | str = ".embeddings_cache"):
        """Initialize embedding cache.

        Args:
            cache_dir: Directory to store cached embeddings (default: .embeddings_cache)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(
        self,
        tenant_id: str,
        dimensions: int,
        walk_length: int,
        num_walks: int,
    ) -> Optional[Dict[str, np.ndarray]]:
        """Retrieve cached embeddings if available and valid.

        Args:
            tenant_id: Tenant ID
            dimensions: Embedding dimensions
            walk_length: Walk length parameter
            num_walks: Number of walks parameter

        Returns:
            Dictionary of embeddings if cache hit, None if cache miss
        """
        cache_key = self._compute_cache_key(
            tenant_id, dimensions, walk_length, num_walks
        )
        cache_file = self.cache_dir / f"{cache_key}.npz"

        if not cache_file.exists():
            logger.debug(str(f"Cache miss for tenant {tenant_id}"))
            return None

        try:
            # Load embeddings from .npz file
            data = np.load(cache_file, allow_pickle=True)

            # Validate metadata
            metadata = data["metadata"].item()
            if not self._validate_metadata(
                metadata, tenant_id, dimensions, walk_length, num_walks
            ):
                logger.warning(
                    str(f"Cache metadata mismatch for {tenant_id}, ignoring")
                )
                return None

            # Extract embeddings
            node_ids = data["node_ids"]
            vectors = data["vectors"]

            embeddings = {
                str(node_id): vector for node_id, vector in zip(node_ids, vectors)
            }

            logger.info(
                f"Cache hit: Loaded {len(embeddings)} embeddings for tenant {tenant_id}"
            )
            return embeddings

        except Exception as e:
            logger.warning(str(f"Failed to load cache for {tenant_id}: {e}"))
            return None

    def put(
        self,
        tenant_id: str,
        embeddings: Dict[str, np.ndarray],
        dimensions: int,
        walk_length: int,
        num_walks: int,
    ) -> None:
        """Store embeddings in cache.

        Args:
            tenant_id: Tenant ID
            embeddings: Dictionary of node embeddings
            dimensions: Embedding dimensions
            walk_length: Walk length parameter
            num_walks: Number of walks parameter
        """
        if not embeddings:
            logger.warning(
                str(f"Skipping cache storage for {tenant_id}: empty embeddings")
            )
            return

        cache_key = self._compute_cache_key(
            tenant_id, dimensions, walk_length, num_walks
        )
        cache_file = self.cache_dir / f"{cache_key}.npz"

        try:
            # Prepare data for storage
            node_ids = list(embeddings.keys())
            vectors = np.array([embeddings[node_id] for node_id in node_ids])

            metadata = {
                "tenant_id": tenant_id,
                "dimensions": dimensions,
                "walk_length": walk_length,
                "num_walks": num_walks,
                "num_nodes": len(embeddings),
            }

            # Save to .npz file
            np.savez_compressed(
                cache_file,
                node_ids=node_ids,
                vectors=vectors,
                metadata=np.array(metadata, dtype=object),
            )

            logger.info(
                str(f"Cached {len(embeddings)} embeddings for tenant {tenant_id}")
            )

        except Exception as e:
            logger.error(str(f"Failed to cache embeddings for {tenant_id}: {e}"))

    def clear(self, tenant_id: Optional[str] = None) -> int:
        """Clear cached embeddings.

        Args:
            tenant_id: If provided, clear only this tenant's cache.
                      If None, clear entire cache.

        Returns:
            Number of cache files deleted
        """
        deleted = 0

        if tenant_id:
            # Clear specific tenant caches (all parameter combinations)
            pattern = f"*{tenant_id}*"
            for cache_file in self.cache_dir.glob(pattern):
                cache_file.unlink()
                deleted += 1
            logger.info(str(f"Cleared {deleted} cache file(s) for tenant {tenant_id}"))
        else:
            # Clear all caches
            for cache_file in self.cache_dir.glob("*.npz"):
                cache_file.unlink()
                deleted += 1
            logger.info(str(f"Cleared all {deleted} cache file(s)"))

        return deleted

    def _compute_cache_key(
        self,
        tenant_id: str,
        dimensions: int,
        walk_length: int,
        num_walks: int,
    ) -> str:
        """Compute cache key from tenant and parameters.

        Args:
            tenant_id: Tenant ID
            dimensions: Embedding dimensions
            walk_length: Walk length parameter
            num_walks: Number of walks parameter

        Returns:
            Cache key string
        """
        # Create deterministic key from parameters
        params = f"{tenant_id}|{dimensions}|{walk_length}|{num_walks}"
        hash_obj = hashlib.sha256(params.encode())
        return hash_obj.hexdigest()[:16]

    def _validate_metadata(
        self,
        metadata: Dict,
        tenant_id: str,
        dimensions: int,
        walk_length: int,
        num_walks: int,
    ) -> bool:
        """Validate cached metadata matches requested parameters.

        Args:
            metadata: Cached metadata dictionary
            tenant_id: Requested tenant ID
            dimensions: Requested dimensions
            walk_length: Requested walk length
            num_walks: Requested num walks

        Returns:
            True if metadata valid, False otherwise
        """
        return (
            metadata.get("tenant_id") == tenant_id
            and metadata.get("dimensions") == dimensions
            and metadata.get("walk_length") == walk_length
            and metadata.get("num_walks") == num_walks
        )

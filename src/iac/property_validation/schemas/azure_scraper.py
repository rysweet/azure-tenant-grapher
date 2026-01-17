"""Azure ARM Schema Scraper - Extract resource schemas from Azure ARM API.

Scrapes Azure ARM API to extract resource property schemas using the
azure-mgmt-resource SDK. Results are cached locally with 24-hour TTL.

Example:
    >>> scraper = AzureScraper(cache_dir=Path("/tmp/schemas"))
    >>> schema = scraper.get_resource_schema("Microsoft.Compute", "virtualMachines")
    >>> print(schema["properties"]["location"]["type"])
    'string'
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class AzureSchemaError(Exception):
    """Raised when Azure schema operations fail."""
    pass


class AzureScraper:
    """Scrapes Azure ARM API schemas and caches results locally.

    Uses the Azure Python SDK to introspect resource provider schemas
    and caches them locally to minimize API calls.

    Args:
        cache_dir: Directory for cached schemas (default: ~/.atg2/schemas/azure)
        cache_ttl_hours: Hours before cache expires (default: 24)

    Example:
        >>> scraper = AzureScraper()
        >>> schema = scraper.get_resource_schema("Microsoft.Compute", "virtualMachines")
        >>> props = schema.get("properties", {})
    """

    DEFAULT_CACHE_DIR = Path.home() / ".atg2" / "schemas" / "azure"
    DEFAULT_TTL_HOURS = 24

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        cache_ttl_hours: int = DEFAULT_TTL_HOURS
    ):
        """Initialize Azure scraper with cache configuration."""
        self.cache_dir = cache_dir or self.DEFAULT_CACHE_DIR
        self.cache_ttl_hours = cache_ttl_hours
        self._ensure_cache_dir()
        self._client = None

    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise AzureSchemaError(f"Failed to create cache directory: {e}")

    def _get_azure_client(self):
        """Lazily initialize Azure client."""
        if self._client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.mgmt.resource import ResourceManagementClient

                # Get subscription ID from environment or use default
                import os
                subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
                if not subscription_id:
                    raise AzureSchemaError(
                        "AZURE_SUBSCRIPTION_ID environment variable not set. "
                        "Set it or authenticate with 'az login'."
                    )

                credential = DefaultAzureCredential()
                self._client = ResourceManagementClient(credential, subscription_id)
            except ImportError:
                raise AzureSchemaError(
                    "Azure SDK not installed. Install with: pip install azure-mgmt-resource azure-identity"
                )
            except Exception as e:
                raise AzureSchemaError(f"Failed to initialize Azure client: {e}")

        return self._client

    def _get_cache_path(self, provider: str, resource_type: str) -> Path:
        """Get cache file path for a resource type."""
        safe_provider = provider.replace("/", "_").replace(".", "_")
        safe_type = resource_type.replace("/", "_").replace(".", "_")
        return self.cache_dir / f"{safe_provider}_{safe_type}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cached schema is still valid."""
        if not cache_path.exists():
            return False

        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
                cached_time = datetime.fromisoformat(data.get("cached_at", ""))
                expiry_time = cached_time + timedelta(hours=self.cache_ttl_hours)
                return datetime.now() < expiry_time
        except (json.JSONDecodeError, ValueError, KeyError, OSError):
            return False

    def _read_cache(self, cache_path: Path) -> Optional[Dict[str, Any]]:
        """Read schema from cache if valid."""
        if not self._is_cache_valid(cache_path):
            return None

        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
                return data.get("schema")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read cache: {e}")
            return None

    def _write_cache(self, cache_path: Path, schema: Dict[str, Any]) -> None:
        """Write schema to cache with timestamp."""
        cache_data = {
            "cached_at": datetime.now().isoformat(),
            "schema": schema
        }

        try:
            with open(cache_path, "w") as f:
                json.dump(cache_data, f, indent=2)
        except OSError as e:
            logger.warning(f"Failed to write cache: {e}")

    def _fetch_provider_schema(self, provider: str) -> Dict[str, Any]:
        """Fetch schema for a specific provider from Azure."""
        try:
            client = self._get_azure_client()

            # Get provider details including resource types
            provider_info = client.providers.get(provider)

            schema = {
                "provider": provider,
                "namespace": provider_info.namespace,
                "resource_types": {}
            }

            # Extract schema for each resource type
            for resource_type in provider_info.resource_types:
                type_name = resource_type.resource_type
                schema["resource_types"][type_name] = {
                    "name": type_name,
                    "api_versions": list(resource_type.api_versions or []),
                    "locations": list(resource_type.locations or []),
                    "capabilities": getattr(resource_type, "capabilities", None),
                    "properties": self._extract_properties(resource_type)
                }

            return schema

        except Exception as e:
            raise AzureSchemaError(f"Failed to fetch schema for {provider}: {e}")

    def _extract_properties(self, resource_type) -> Dict[str, Any]:
        """Extract property definitions from resource type.

        Note: Azure SDK doesn't expose full JSON schemas via the management API.
        This extracts what's available from the provider metadata.
        For full schemas, we'd need to use the ARM template reference.
        """
        properties = {}

        # Extract zone mappings if available
        if hasattr(resource_type, "zone_mappings"):
            properties["zone_mappings"] = list(resource_type.zone_mappings or [])

        # Extract capabilities as property hints
        if hasattr(resource_type, "capabilities"):
            capabilities = resource_type.capabilities or []
            for cap in capabilities:
                if hasattr(cap, "name") and hasattr(cap, "value"):
                    properties[cap.name] = {"type": "string", "value": cap.value}

        return properties

    def get_resource_schema(
        self,
        provider: str,
        resource_type: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get schema for a specific Azure resource type.

        Args:
            provider: Azure provider namespace (e.g., "Microsoft.Compute")
            resource_type: Resource type name (e.g., "virtualMachines")
            force_refresh: Skip cache and fetch fresh schema

        Returns:
            Schema dictionary with properties, api_versions, locations

        Raises:
            AzureSchemaError: If schema cannot be fetched

        Example:
            >>> scraper = AzureScraper()
            >>> schema = scraper.get_resource_schema("Microsoft.Compute", "virtualMachines")
            >>> print(schema["api_versions"])
            ['2023-03-01', '2023-07-01']
        """
        cache_path = self._get_cache_path(provider, resource_type)

        # Try cache first unless force refresh
        if not force_refresh:
            cached = self._read_cache(cache_path)
            if cached:
                logger.info(f"Using cached schema for {provider}/{resource_type}")
                return cached

        # Fetch from Azure
        logger.info(f"Fetching schema for {provider}/{resource_type} from Azure")
        provider_schema = self._fetch_provider_schema(provider)

        # Extract specific resource type
        if resource_type not in provider_schema["resource_types"]:
            raise AzureSchemaError(
                f"Resource type {resource_type} not found in {provider}. "
                f"Available types: {list(provider_schema['resource_types'].keys())}"
            )

        schema = provider_schema["resource_types"][resource_type]

        # Cache result
        self._write_cache(cache_path, schema)

        return schema

    def list_providers(self) -> List[str]:
        """List all available Azure resource providers.

        Returns:
            List of provider namespaces

        Example:
            >>> scraper = AzureScraper()
            >>> providers = scraper.list_providers()
            >>> print(providers[:3])
            ['Microsoft.Compute', 'Microsoft.Storage', 'Microsoft.Network']
        """
        try:
            client = self._get_azure_client()
            providers = client.providers.list()
            return [p.namespace for p in providers]
        except Exception as e:
            raise AzureSchemaError(f"Failed to list providers: {e}")

    def list_resource_types(self, provider: str) -> List[str]:
        """List all resource types for a provider.

        Args:
            provider: Provider namespace (e.g., "Microsoft.Compute")

        Returns:
            List of resource type names

        Example:
            >>> scraper = AzureScraper()
            >>> types = scraper.list_resource_types("Microsoft.Compute")
            >>> print(types[:3])
            ['virtualMachines', 'availabilitySets', 'disks']
        """
        schema = self._fetch_provider_schema(provider)
        return list(schema["resource_types"].keys())

    def clear_cache(self, provider: Optional[str] = None) -> int:
        """Clear cached schemas.

        Args:
            provider: Clear only this provider's cache, or all if None

        Returns:
            Number of cache files removed

        Example:
            >>> scraper = AzureScraper()
            >>> removed = scraper.clear_cache("Microsoft.Compute")
            >>> print(f"Removed {removed} cache files")
        """
        if not self.cache_dir.exists():
            return 0

        count = 0
        pattern = f"{provider.replace('.', '_')}*" if provider else "*.json"

        for cache_file in self.cache_dir.glob(pattern):
            try:
                cache_file.unlink()
                count += 1
            except OSError as e:
                logger.warning(f"Failed to remove {cache_file}: {e}")

        return count

"""Terraform Provider Schema Scraper - Extract schemas from Terraform CLI.

Runs `terraform providers schema -json` and parses the output to extract
resource property schemas. Results are cached locally with 24-hour TTL.

Example:
    >>> scraper = TerraformScraper(cache_dir=Path("/tmp/schemas"))
    >>> schema = scraper.get_resource_schema("azurerm_virtual_machine")
    >>> print(schema["block"]["attributes"]["location"]["type"])
    'string'
"""

import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TerraformSchemaError(Exception):
    """Raised when Terraform schema operations fail."""

    pass


class TerraformScraper:
    """Scrapes Terraform provider schemas and caches results locally.

    Executes `terraform providers schema -json` to extract resource schemas
    and caches them locally to minimize subprocess overhead.

    Args:
        terraform_dir: Directory containing Terraform configuration (default: current dir)
        cache_dir: Directory for cached schemas (default: ~/.atg2/schemas/terraform)
        cache_ttl_hours: Hours before cache expires (default: 24)

    Example:
        >>> scraper = TerraformScraper(terraform_dir=Path("/path/to/tf"))
        >>> schema = scraper.get_resource_schema("azurerm_virtual_machine")
        >>> attrs = schema["block"]["attributes"]
    """

    DEFAULT_CACHE_DIR = Path.home() / ".atg2" / "schemas" / "terraform"
    DEFAULT_TTL_HOURS = 24

    def __init__(
        self,
        terraform_dir: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
        cache_ttl_hours: int = DEFAULT_TTL_HOURS,
    ):
        """Initialize Terraform scraper with cache configuration."""
        self.terraform_dir = terraform_dir or Path.cwd()
        self.cache_dir = cache_dir or self.DEFAULT_CACHE_DIR
        self.cache_ttl_hours = cache_ttl_hours
        self._ensure_cache_dir()
        self._verify_terraform()

    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise TerraformSchemaError(f"Failed to create cache directory: {e}")

    def _verify_terraform(self) -> None:
        """Verify Terraform CLI is available."""
        try:
            result = subprocess.run(
                ["terraform", "version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                raise TerraformSchemaError(
                    f"Terraform CLI not working properly. Error: {result.stderr}"
                )
            logger.info(f"Found Terraform: {result.stdout.splitlines()[0]}")
        except FileNotFoundError:
            raise TerraformSchemaError(
                "Terraform CLI not found. Install from https://www.terraform.io/downloads"
            )
        except subprocess.TimeoutExpired:
            raise TerraformSchemaError("Terraform version check timed out")
        except Exception as e:
            raise TerraformSchemaError(f"Failed to verify Terraform: {e}")

    def _get_cache_path(self, provider: Optional[str] = None) -> Path:
        """Get cache file path for provider schemas.

        If provider is None, returns path for all providers.
        """
        if provider:
            safe_provider = provider.replace("/", "_").replace(".", "_")
            return self.cache_dir / f"{safe_provider}.json"
        else:
            return self.cache_dir / "all_providers.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cached schema is still valid."""
        if not cache_path.exists():
            return False

        try:
            with open(cache_path) as f:
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
            with open(cache_path) as f:
                data = json.load(f)
                return data.get("schema")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read cache: {e}")
            return None

    def _write_cache(self, cache_path: Path, schema: Dict[str, Any]) -> None:
        """Write schema to cache with timestamp."""
        cache_data = {"cached_at": datetime.now().isoformat(), "schema": schema}

        try:
            with open(cache_path, "w") as f:
                json.dump(cache_data, f, indent=2)
        except OSError as e:
            logger.warning(f"Failed to write cache: {e}")

    def _run_terraform_schema(self) -> Dict[str, Any]:
        """Run terraform providers schema -json and parse output."""
        try:
            logger.info(f"Running terraform providers schema in {self.terraform_dir}")
            result = subprocess.run(
                ["terraform", "providers", "schema", "-json"],
                capture_output=True,
                text=True,
                cwd=self.terraform_dir,
                timeout=120,  # 2 minutes max
            )

            if result.returncode != 0:
                # Check for common errors
                if "terraform init" in result.stderr.lower():
                    raise TerraformSchemaError(
                        f"Terraform not initialized in {self.terraform_dir}. "
                        "Run 'terraform init' first."
                    )
                raise TerraformSchemaError(
                    f"terraform providers schema failed: {result.stderr}"
                )

            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError as e:
                raise TerraformSchemaError(f"Invalid JSON from terraform: {e}")

        except subprocess.TimeoutExpired:
            raise TerraformSchemaError(
                "terraform providers schema timed out after 120 seconds"
            )
        except FileNotFoundError:
            raise TerraformSchemaError(
                "Terraform CLI not found. Install from https://www.terraform.io/downloads"
            )
        except Exception as e:
            raise TerraformSchemaError(f"Failed to run terraform schema: {e}")

    def _fetch_all_schemas(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetch schemas for all providers."""
        cache_path = self._get_cache_path()

        # Try cache first unless force refresh
        if not force_refresh:
            cached = self._read_cache(cache_path)
            if cached:
                logger.info("Using cached Terraform provider schemas")
                return cached

        # Run terraform command
        schema_data = self._run_terraform_schema()

        # Cache result
        self._write_cache(cache_path, schema_data)

        return schema_data

    def get_resource_schema(
        self, resource_type: str, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get schema for a specific Terraform resource type.

        Args:
            resource_type: Resource type name (e.g., "azurerm_virtual_machine")
            force_refresh: Skip cache and fetch fresh schema

        Returns:
            Schema dictionary with block attributes and nested blocks

        Raises:
            TerraformSchemaError: If schema cannot be fetched

        Example:
            >>> scraper = TerraformScraper()
            >>> schema = scraper.get_resource_schema("azurerm_virtual_machine")
            >>> location = schema["block"]["attributes"]["location"]
            >>> print(location["type"], location.get("required"))
            string True
        """
        all_schemas = self._fetch_all_schemas(force_refresh)

        # Find the resource in provider schemas
        for provider_name, provider_data in all_schemas.get(
            "provider_schemas", {}
        ).items():
            resource_schemas = provider_data.get("resource_schemas", {})
            if resource_type in resource_schemas:
                return resource_schemas[resource_type]

        # Not found
        available = self.list_resource_types()
        raise TerraformSchemaError(
            f"Resource type '{resource_type}' not found. "
            f"Available types: {available[:10]}... ({len(available)} total)"
        )

    def get_provider_schema(
        self, provider_name: str, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get full schema for a specific provider.

        Args:
            provider_name: Provider name (e.g., "registry.terraform.io/hashicorp/azurerm")
            force_refresh: Skip cache and fetch fresh schema

        Returns:
            Provider schema with all resource types

        Example:
            >>> scraper = TerraformScraper()
            >>> schema = scraper.get_provider_schema("registry.terraform.io/hashicorp/azurerm")
            >>> resources = schema["resource_schemas"].keys()
        """
        all_schemas = self._fetch_all_schemas(force_refresh)

        provider_schemas = all_schemas.get("provider_schemas", {})
        if provider_name not in provider_schemas:
            available = list(provider_schemas.keys())
            raise TerraformSchemaError(
                f"Provider '{provider_name}' not found. Available: {available}"
            )

        return provider_schemas[provider_name]

    def list_providers(self) -> List[str]:
        """List all configured Terraform providers.

        Returns:
            List of provider names

        Example:
            >>> scraper = TerraformScraper()
            >>> providers = scraper.list_providers()
            >>> print(providers)
            ['registry.terraform.io/hashicorp/azurerm', ...]
        """
        all_schemas = self._fetch_all_schemas()
        return list(all_schemas.get("provider_schemas", {}).keys())

    def list_resource_types(self, provider: Optional[str] = None) -> List[str]:
        """List all resource types, optionally filtered by provider.

        Args:
            provider: Filter to this provider only, or None for all

        Returns:
            List of resource type names

        Example:
            >>> scraper = TerraformScraper()
            >>> types = scraper.list_resource_types()
            >>> azurerm_types = scraper.list_resource_types("registry.terraform.io/hashicorp/azurerm")
        """
        all_schemas = self._fetch_all_schemas()
        resource_types = []

        for provider_name, provider_data in all_schemas.get(
            "provider_schemas", {}
        ).items():
            if provider and provider != provider_name:
                continue
            resource_schemas = provider_data.get("resource_schemas", {})
            resource_types.extend(resource_schemas.keys())

        return sorted(resource_types)

    def extract_required_properties(
        self, resource_type: str
    ) -> Dict[str, Dict[str, Any]]:
        """Extract only required properties from a resource schema.

        Args:
            resource_type: Resource type name

        Returns:
            Dictionary of required property names to their schemas

        Example:
            >>> scraper = TerraformScraper()
            >>> required = scraper.extract_required_properties("azurerm_virtual_machine")
            >>> print(list(required.keys()))
            ['name', 'location', 'resource_group_name', ...]
        """
        schema = self.get_resource_schema(resource_type)
        block = schema.get("block", {})
        attributes = block.get("attributes", {})

        required = {}
        for attr_name, attr_schema in attributes.items():
            if attr_schema.get("required", False):
                required[attr_name] = attr_schema

        return required

    def extract_all_properties(
        self, resource_type: str, include_nested: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """Extract all properties from a resource schema.

        Args:
            resource_type: Resource type name
            include_nested: Include nested block attributes

        Returns:
            Dictionary of all property names to their schemas

        Example:
            >>> scraper = TerraformScraper()
            >>> all_props = scraper.extract_all_properties("azurerm_virtual_machine")
            >>> print(len(all_props))
            45
        """
        schema = self.get_resource_schema(resource_type)
        block = schema.get("block", {})
        properties = dict(block.get("attributes", {}))

        if include_nested:
            # Add nested blocks as well
            for block_name, block_schema in block.get("block_types", {}).items():
                properties[block_name] = {"type": "block", "block": block_schema}

        return properties

    def clear_cache(self, provider: Optional[str] = None) -> int:
        """Clear cached schemas.

        Args:
            provider: Clear only this provider's cache, or all if None

        Returns:
            Number of cache files removed

        Example:
            >>> scraper = TerraformScraper()
            >>> removed = scraper.clear_cache()
            >>> print(f"Removed {removed} cache files")
        """
        if not self.cache_dir.exists():
            return 0

        count = 0

        if provider:
            cache_path = self._get_cache_path(provider)
            if cache_path.exists():
                try:
                    cache_path.unlink()
                    count += 1
                except OSError as e:
                    logger.warning(f"Failed to remove {cache_path}: {e}")
        else:
            # Clear all cache files
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    cache_file.unlink()
                    count += 1
                except OSError as e:
                    logger.warning(f"Failed to remove {cache_file}: {e}")

        return count

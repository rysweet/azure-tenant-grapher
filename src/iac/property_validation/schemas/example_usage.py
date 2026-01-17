"""Example usage of schema scrapers.

This demonstrates how to use AzureScraper and TerraformScraper to extract
resource property schemas for validation purposes.
"""

from pathlib import Path
from azure_scraper import AzureScraper, AzureSchemaError
from terraform_scraper import TerraformScraper, TerraformSchemaError


def demo_azure_scraper():
    """Demonstrate Azure schema scraping."""
    print("=== Azure Schema Scraper Demo ===\n")

    try:
        # Initialize scraper
        scraper = AzureScraper()
        print(f"Cache directory: {scraper.cache_dir}")
        print(f"Cache TTL: {scraper.cache_ttl_hours} hours\n")

        # List available providers (this requires Azure authentication)
        print("Listing providers requires Azure credentials...")
        print("Set AZURE_SUBSCRIPTION_ID and authenticate with 'az login'\n")

        # Example: Get schema for a resource type
        print("Example usage:")
        print(">>> scraper = AzureScraper()")
        print(">>> schema = scraper.get_resource_schema('Microsoft.Compute', 'virtualMachines')")
        print(">>> print(schema['api_versions'])")
        print("['2023-03-01', '2023-07-01', ...]")
        print()
        print(">>> print(schema['locations'])")
        print("['eastus', 'westus', 'westeurope', ...]")
        print()

        # Clear cache example
        print("Cache management:")
        print(">>> scraper.clear_cache('Microsoft.Compute')  # Clear specific provider")
        print(">>> scraper.clear_cache()  # Clear all cached schemas")
        print()

    except AzureSchemaError as e:
        print(f"Azure scraper error: {e}\n")


def demo_terraform_scraper():
    """Demonstrate Terraform schema scraping."""
    print("=== Terraform Schema Scraper Demo ===\n")

    try:
        # Initialize scraper
        scraper = TerraformScraper()
        print(f"Terraform directory: {scraper.terraform_dir}")
        print(f"Cache directory: {scraper.cache_dir}")
        print(f"Cache TTL: {scraper.cache_ttl_hours} hours\n")

        print("Example usage:")
        print(">>> scraper = TerraformScraper(terraform_dir=Path('/path/to/terraform'))")
        print(">>> schema = scraper.get_resource_schema('azurerm_virtual_machine')")
        print(">>> attrs = schema['block']['attributes']")
        print(">>> print(attrs['location']['type'])")
        print("'string'")
        print()
        print(">>> print(attrs['location']['required'])")
        print("True")
        print()

        # List providers
        print("List available providers:")
        print(">>> providers = scraper.list_providers()")
        print(">>> print(providers)")
        print("['registry.terraform.io/hashicorp/azurerm', ...]")
        print()

        # List resource types
        print("List resource types:")
        print(">>> types = scraper.list_resource_types()")
        print(">>> print(types[:5])")
        print("['azurerm_virtual_machine', 'azurerm_storage_account', ...]")
        print()

        # Extract required properties
        print("Extract only required properties:")
        print(">>> required = scraper.extract_required_properties('azurerm_virtual_machine')")
        print(">>> print(list(required.keys()))")
        print("['name', 'location', 'resource_group_name', ...]")
        print()

        # Cache management
        print("Cache management:")
        print(">>> scraper.clear_cache()  # Clear all cached schemas")
        print(">>> schema = scraper.get_resource_schema('azurerm_vm', force_refresh=True)")
        print()

    except TerraformSchemaError as e:
        print(f"Terraform scraper error: {e}\n")


def demo_validation_workflow():
    """Demonstrate using scrapers for property validation."""
    print("=== Property Validation Workflow ===\n")

    print("Typical validation workflow:")
    print()
    print("1. Initialize scrapers:")
    print("   azure_scraper = AzureScraper()")
    print("   tf_scraper = TerraformScraper(terraform_dir=Path('./terraform'))")
    print()
    print("2. Get schemas for comparison:")
    print("   azure_schema = azure_scraper.get_resource_schema('Microsoft.Compute', 'virtualMachines')")
    print("   tf_schema = tf_scraper.get_resource_schema('azurerm_virtual_machine')")
    print()
    print("3. Extract properties:")
    print("   azure_props = azure_schema['properties']")
    print("   tf_required = tf_scraper.extract_required_properties('azurerm_virtual_machine')")
    print()
    print("4. Validate Terraform config against schemas:")
    print("   for prop_name, prop_value in tf_config.items():")
    print("       if prop_name in tf_required:")
    print("           # Validate required property")
    print("           validate_type(prop_value, tf_required[prop_name]['type'])")
    print()
    print("5. Cross-reference with Azure ARM:")
    print("   if prop_name in azure_props:")
    print("       # Validate against Azure constraints")
    print("       validate_azure_constraints(prop_value, azure_props[prop_name])")
    print()


def demo_caching_behavior():
    """Demonstrate cache behavior."""
    print("=== Cache Behavior Demo ===\n")

    print("Cache TTL and refresh:")
    print()
    print("# Default: 24-hour cache")
    print(">>> scraper = TerraformScraper(cache_ttl_hours=24)")
    print(">>> schema = scraper.get_resource_schema('azurerm_vm')  # Fetches from Terraform")
    print(">>> schema = scraper.get_resource_schema('azurerm_vm')  # Uses cache (fast!)")
    print()
    print("# After 24 hours, cache expires and is refreshed automatically")
    print()
    print("# Force refresh to get latest schemas:")
    print(">>> schema = scraper.get_resource_schema('azurerm_vm', force_refresh=True)")
    print()
    print("# Custom cache directory:")
    print(">>> scraper = TerraformScraper(cache_dir=Path('/custom/cache/dir'))")
    print()


def main():
    """Run all demos."""
    demo_azure_scraper()
    print("-" * 60)
    print()

    demo_terraform_scraper()
    print("-" * 60)
    print()

    demo_validation_workflow()
    print("-" * 60)
    print()

    demo_caching_behavior()
    print("-" * 60)
    print()

    print("\n✓ See module docstrings for full API documentation")


if __name__ == "__main__":
    main()

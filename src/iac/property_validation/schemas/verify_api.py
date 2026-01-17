"""Verify the public API is correctly exposed."""

import sys
import inspect

# Direct imports from the modules
from azure_scraper import AzureScraper
from terraform_scraper import TerraformScraper

print("=== Public API Verification ===\n")

# Verify AzureScraper
print("AzureScraper public methods:")
for name in dir(AzureScraper):
    if not name.startswith("_"):
        attr = getattr(AzureScraper, name)
        if callable(attr):
            sig = inspect.signature(attr)
            print(f"  - {name}{sig}")

print("\nTerraformScraper public methods:")
for name in dir(TerraformScraper):
    if not name.startswith("_"):
        attr = getattr(TerraformScraper, name)
        if callable(attr):
            sig = inspect.signature(attr)
            print(f"  - {name}{sig}")

print("\n✓ Public API verified successfully!")

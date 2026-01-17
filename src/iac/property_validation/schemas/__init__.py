"""Schema Scrapers - Extract and cache resource schemas from Azure and Terraform.

This module provides scrapers that fetch resource property schemas from:
- Azure ARM API (using azure-mgmt-resource SDK)
- Terraform providers (via CLI schema export)

Philosophy:
- Self-contained scraping with local caching
- 24-hour cache TTL to balance freshness and performance
- Standard library only except for necessary HTTP/SDK calls
- Fail-fast with clear error messages

Public API (the "studs"):
    AzureScraper: Scrapes Azure ARM API schemas
    TerraformScraper: Parses Terraform provider schemas
    SchemaCache: Manages local schema caching
"""

from .azure_scraper import AzureScraper
from .terraform_scraper import TerraformScraper

__all__ = ["AzureScraper", "TerraformScraper"]

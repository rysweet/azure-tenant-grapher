"""
API Routers for ATG Remote Service.

Philosophy:
- Modular router organization
- Clear separation of concerns
- Each router handles one domain

Public API:
    health: Health check endpoints
    scan: Scan operation endpoints
    generate: IaC generation endpoints
    operations: Operation management endpoints
    reset: Tenant reset endpoints
"""

__all__ = ["generate", "health", "operations", "reset", "scan"]

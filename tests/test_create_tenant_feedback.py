"""
Test for create-tenant command feedback improvements (Issue #208)
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from scripts.cli import cli


@pytest.fixture
def sample_tenant_spec():
    """Sample tenant spec with various resources for testing."""
    return {
        "tenant": {
            "id": "test-tenant-001",
            "display_name": "Test Tenant",
            "subscriptions": [
                {
                    "id": "sub-001",
                    "name": "Production",
                    "resource_groups": [
                        {
                            "id": "rg-001",
                            "name": "prod-rg",
                            "location": "eastus",
                            "resources": [
                                {
                                    "id": "vm-001",
                                    "name": "prod-vm",
                                    "type": "Microsoft.Compute/virtualMachines",
                                    "location": "eastus",
                                    "properties": {}
                                },
                                {
                                    "id": "storage-001",
                                    "name": "prod-storage",
                                    "type": "Microsoft.Storage/storageAccounts",
                                    "location": "eastus",
                                    "properties": {}
                                }
                            ]
                        }
                    ]
                }
            ],
            "users": [
                {"id": "user-001", "display_name": "John Doe"},
                {"id": "user-002", "display_name": "Jane Smith"}
            ],
            "groups": [
                {"id": "group-001", "display_name": "Admins"}
            ],
            "service_principals": [
                {"id": "sp-001", "display_name": "App Service"}
            ],
            "rbac_assignments": [
                {
                    "principal_id": "user-001",
                    "role": "Owner",
                    "scope": "sub-001"
                }
            ],
            "relationships": [
                {
                    "source_id": "user-001",
                    "target_id": "group-001",
                    "type": "MEMBER_OF"
                }
            ]
        }
    }


@pytest.fixture
def mock_tenant_creator(sample_tenant_spec):
    """Mock TenantCreator that returns statistics."""
    
    async def mock_ingest_to_graph(spec, is_llm_generated=False):
        """Mock method that returns creation statistics."""
        return {
            "tenant": 1,
            "subscriptions": 1,
            "resource_groups": 1,
            "resources": 2,
            "users": 2,
            "groups": 1,
            "service_principals": 1,
            "managed_identities": 0,
            "admin_units": 0,
            "rbac_assignments": 1,
            "relationships": 1,
            "total": 11
        }
    
    mock = MagicMock()
    mock.ingest_to_graph = mock_ingest_to_graph
    return mock


def test_create_tenant_displays_success_message(mock_tenant_creator, sample_tenant_spec):
    """Test that create-tenant command displays clear success message."""
    runner = CliRunner()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        # Write sample tenant spec as JSON in markdown
        f.write("# Test Tenant Spec\n\n")
        f.write("```json\n")
        json.dump(sample_tenant_spec, f, indent=2)
        f.write("\n```\n")
        temp_file = f.name
    
    try:
        with patch('src.cli_commands.ensure_neo4j_running'), \
             patch('src.llm_descriptions.create_llm_generator'), \
             patch('src.tenant_creator.TenantCreator') as MockCreator, \
             patch('src.tenant_creator.get_default_session_manager'):
            
            # Setup mock to return our statistics
            MockCreator.return_value = mock_tenant_creator
            mock_tenant_creator.create_from_markdown = AsyncMock(return_value=MagicMock())
            
            result = runner.invoke(cli, ['create-tenant', temp_file])
            
            # Check for success message
            assert '✅ Tenant successfully created in Neo4j!' in result.output
            assert result.exit_code == 0
    
    finally:
        Path(temp_file).unlink()


def test_create_tenant_displays_resource_counts(mock_tenant_creator, sample_tenant_spec):
    """Test that create-tenant command displays resource count breakdown."""
    runner = CliRunner()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        # Write sample tenant spec as JSON in markdown
        f.write("# Test Tenant Spec\n\n")
        f.write("```json\n")
        json.dump(sample_tenant_spec, f, indent=2)
        f.write("\n```\n")
        temp_file = f.name
    
    try:
        with patch('src.cli_commands.ensure_neo4j_running'), \
             patch('src.llm_descriptions.create_llm_generator'), \
             patch('src.tenant_creator.TenantCreator') as MockCreator, \
             patch('src.tenant_creator.get_default_session_manager'):
            
            # Setup mock to return our statistics
            MockCreator.return_value = mock_tenant_creator
            mock_tenant_creator.create_from_markdown = AsyncMock(return_value=MagicMock())
            
            result = runner.invoke(cli, ['create-tenant', temp_file])
            
            # Check for resource counts
            assert '📊 Resources created:' in result.output
            assert '• Tenant: 1' in result.output
            assert '• Subscriptions: 1' in result.output
            assert '• Resource Groups: 1' in result.output
            assert '• Resources: 2' in result.output
            assert '• Users: 2' in result.output
            assert '• Groups: 1' in result.output
            assert '• Service Principals: 1' in result.output
            assert '• RBAC Assignments: 1' in result.output
            assert '• Relationships: 1' in result.output
            assert 'Total entities: 11' in result.output
    
    finally:
        Path(temp_file).unlink()


def test_create_tenant_displays_next_steps(mock_tenant_creator, sample_tenant_spec):
    """Test that create-tenant command displays helpful next steps."""
    runner = CliRunner()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        # Write sample tenant spec as JSON in markdown
        f.write("# Test Tenant Spec\n\n")
        f.write("```json\n")
        json.dump(sample_tenant_spec, f, indent=2)
        f.write("\n```\n")
        temp_file = f.name
    
    try:
        with patch('src.cli_commands.ensure_neo4j_running'), \
             patch('src.llm_descriptions.create_llm_generator'), \
             patch('src.tenant_creator.TenantCreator') as MockCreator, \
             patch('src.tenant_creator.get_default_session_manager'):
            
            # Setup mock to return our statistics
            MockCreator.return_value = mock_tenant_creator
            mock_tenant_creator.create_from_markdown = AsyncMock(return_value=MagicMock())
            
            result = runner.invoke(cli, ['create-tenant', temp_file])
            
            # Check for next steps
            assert '💡 Next steps:' in result.output
            assert "• Run 'atg visualize' to see the graph" in result.output
            assert "• Run 'atg build' to enrich with more data" in result.output
    
    finally:
        Path(temp_file).unlink()


def test_create_tenant_handles_failure_gracefully():
    """Test that create-tenant command displays clear error message on failure."""
    runner = CliRunner()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Invalid Spec\nThis is not valid JSON")
        temp_file = f.name
    
    try:
        with patch('src.cli_commands.ensure_neo4j_running'), \
             patch('src.llm_descriptions.create_llm_generator'), \
             patch('src.tenant_creator.TenantCreator') as MockCreator:
            
            # Setup mock to raise an exception
            MockCreator.return_value.create_from_markdown = AsyncMock(
                side_effect=ValueError("Invalid JSON format")
            )
            
            result = runner.invoke(cli, ['create-tenant', temp_file])
            
            # Check for error message
            assert '❌ Failed to create tenant:' in result.output
            assert result.exit_code == 1
    
    finally:
        Path(temp_file).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
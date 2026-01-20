"""Pytest configuration and shared fixtures for multi-tenant Sentinel tests.

Philosophy:
- Provide reusable test fixtures for all test types
- Mock external dependencies (Azure, Neo4j)
- Support testing pyramid (60% unit, 30% integration, 10% E2E)

"""

import json
import sys
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, Mock

import pytest

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def sample_delegations() -> List[Dict]:
    """Load sample delegation data from fixtures."""
    fixtures_path = Path(__file__).parent / "fixtures" / "sample_delegations.json"
    with open(fixtures_path) as f:
        data = json.load(f)
    return data["delegations"]


@pytest.fixture
def active_delegation(sample_delegations) -> Dict:
    """Get a sample active delegation."""
    return next(d for d in sample_delegations if d["status"] == "active")


@pytest.fixture
def pending_delegation(sample_delegations) -> Dict:
    """Get a sample pending delegation."""
    return next(d for d in sample_delegations if d["status"] == "pending")


@pytest.fixture
def revoked_delegation(sample_delegations) -> Dict:
    """Get a sample revoked delegation."""
    return next(d for d in sample_delegations if d["status"] == "revoked")


@pytest.fixture
def error_delegation(sample_delegations) -> Dict:
    """Get a sample error delegation."""
    return next(d for d in sample_delegations if d["status"] == "error")


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture
def managing_tenant_id() -> str:
    """Test MSSP managing tenant ID."""
    return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture
def customer_tenant_id() -> str:
    """Test customer tenant ID."""
    return "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def customer_tenant_name() -> str:
    """Test customer tenant name."""
    return "Acme Corp"


@pytest.fixture
def subscription_id() -> str:
    """Test subscription ID."""
    return "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def resource_group() -> str:
    """Test resource group name."""
    return "rg-sentinel-test"


@pytest.fixture
def default_authorizations() -> List[Dict]:
    """Default RBAC authorizations for Lighthouse."""
    return [
        {
            "principalId": "test-principal-id",
            "roleDefinitionId": "ab8e14d6-4a74-4a29-9ba8-549422addade",  # Sentinel Contributor
            "principalIdDisplayName": "Sentinel MSSP Management",
        },
        {
            "principalId": "test-principal-id",
            "roleDefinitionId": "acdd72a7-3385-48ef-bd42-f606fba81ae7",  # Security Reader
            "principalIdDisplayName": "Security Operations Team",
        },
    ]


# ============================================================================
# Mock Azure SDK Fixtures
# ============================================================================


@pytest.fixture
def mock_azure_credential():
    """Mock Azure credential object."""
    mock_cred = Mock()
    mock_cred.get_token.return_value = Mock(token="test-access-token")
    return mock_cred


@pytest.fixture
def mock_managed_services_client():
    """Mock Azure ManagedServicesClient."""
    mock_client = MagicMock()

    # Mock registration definitions
    mock_reg_def = Mock()
    mock_reg_def.id = "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationDefinitions/test-def-id"
    mock_reg_def.properties.managed_by_tenant_id = (
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )
    mock_reg_def.properties.registration_definition_name = "Test Delegation"

    mock_client.registration_definitions.get.return_value = mock_reg_def
    mock_client.registration_definitions.list.return_value = [mock_reg_def]

    # Mock registration assignments
    mock_reg_assign = Mock()
    mock_reg_assign.id = "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationAssignments/test-assign-id"
    mock_reg_assign.properties.registration_definition_id = mock_reg_def.id

    mock_client.registration_assignments.get.return_value = mock_reg_assign
    mock_client.registration_assignments.list.return_value = [mock_reg_assign]
    mock_client.registration_assignments.delete.return_value = None

    return mock_client


@pytest.fixture
def mock_resource_client():
    """Mock Azure ResourceManagementClient for resource listing."""
    mock_client = MagicMock()

    # Mock resources.list() for verification
    mock_resource = Mock()
    mock_resource.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace"
    mock_resource.name = "test-workspace"
    mock_resource.type = "Microsoft.OperationalInsights/workspaces"

    mock_client.resources.list.return_value = [mock_resource]

    return mock_client


# ============================================================================
# Mock Neo4j Fixtures
# ============================================================================


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for unit tests."""
    mock_driver = MagicMock()
    mock_session = MagicMock()

    # Mock session context manager
    mock_driver.session.return_value.__enter__.return_value = mock_session
    mock_driver.session.return_value.__exit__.return_value = None

    # Mock transaction
    mock_tx = MagicMock()
    mock_session.begin_transaction.return_value.__enter__.return_value = mock_tx
    mock_session.begin_transaction.return_value.__exit__.return_value = None

    # Default query result (empty)
    mock_result = Mock()
    mock_result.single.return_value = None
    mock_result.data.return_value = []
    mock_tx.run.return_value = mock_result

    return mock_driver


@pytest.fixture
def mock_neo4j_session(mock_neo4j_driver):
    """Get mock Neo4j session from driver."""
    return mock_neo4j_driver.session().__enter__()


@pytest.fixture
def neo4j_query_result():
    """Factory fixture for creating mock Neo4j query results."""

    def _create_result(data: List[Dict]) -> Mock:
        mock_result = Mock()
        mock_result.data.return_value = data
        if len(data) == 1:
            mock_result.single.return_value = data[0]
        elif len(data) == 0:
            mock_result.single.return_value = None
        return mock_result

    return _create_result


# ============================================================================
# File System Fixtures
# ============================================================================


@pytest.fixture
def temp_bicep_output_dir(tmp_path):
    """Temporary directory for Bicep template output."""
    output_dir = tmp_path / "bicep_output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def sample_bicep_template() -> str:
    """Sample Bicep template content."""
    return """targetScope = 'subscription'

@description('Managing tenant ID (MSSP)')
param managingTenantId string = '{MANAGING_TENANT_ID}'

@description('Customer organization name')
param customerName string = '{CUSTOMER_NAME}'

@description('Authorizations')
param authorizations array = {AUTHORIZATIONS_JSON}

resource lighthouseRegistration 'Microsoft.ManagedServices/registrationDefinitions@2022-10-01' = {
  name: guid(subscription().subscriptionId, managingTenantId)
  properties: {
    registrationDefinitionName: '${customerName} - Sentinel MSSP Delegation'
    description: 'Azure Lighthouse delegation for ${customerName} Sentinel management'
    managedByTenantId: managingTenantId
    authorizations: authorizations
  }
}

resource lighthouseAssignment 'Microsoft.ManagedServices/registrationAssignments@2022-10-01' = {
  name: guid(subscription().subscriptionId, managingTenantId, 'assignment')
  properties: {
    registrationDefinitionId: lighthouseRegistration.id
  }
}

output registrationId string = lighthouseRegistration.id
output assignmentId string = lighthouseAssignment.id
"""


# ============================================================================
# LighthouseManager Fixtures
# ============================================================================


@pytest.fixture
def lighthouse_manager_config(managing_tenant_id, temp_bicep_output_dir):
    """Configuration dict for LighthouseManager initialization."""
    return {
        "managing_tenant_id": managing_tenant_id,
        "bicep_output_dir": str(temp_bicep_output_dir),
    }


# ============================================================================
# Test Markers
# ============================================================================


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, heavily mocked)")
    config.addinivalue_line(
        "markers", "integration: Integration tests (multiple components)"
    )
    config.addinivalue_line("markers", "e2e: End-to-end tests (complete workflows)")
    config.addinivalue_line(
        "markers", "requires_neo4j: Tests requiring real Neo4j instance"
    )
    config.addinivalue_line(
        "markers", "requires_azure: Tests requiring Azure credentials"
    )

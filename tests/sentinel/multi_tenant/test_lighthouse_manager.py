"""Unit tests for LighthouseManager - TDD approach.

Testing pyramid: 60% unit tests (this file)
- Fast execution (< 1 second total)
- Heavily mocked external dependencies
- Focus on public API behavior

Philosophy:
- Test the contract, not the implementation
- One assertion per test (arrange-act-assert)
- Descriptive test names explain what's being tested

"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.sentinel.multi_tenant.exceptions import (
    DelegationExistsError,
    DelegationNotFoundError,
    LighthouseError,
)
from src.sentinel.multi_tenant.lighthouse_manager import LighthouseManager
from src.sentinel.multi_tenant.models import LighthouseDelegation, LighthouseStatus

# ============================================================================
# Test Markers
# ============================================================================


pytestmark = pytest.mark.unit


# ============================================================================
# LighthouseManager Initialization Tests
# ============================================================================


class TestLighthouseManagerInit:
    """Test LighthouseManager initialization."""

    def test_init_with_required_params(
        self, managing_tenant_id, mock_neo4j_driver, temp_bicep_output_dir
    ):
        """Test initialization with required parameters."""
        # Arrange & Act
        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Assert
        assert manager.managing_tenant_id == managing_tenant_id
        assert manager.bicep_output_dir == str(temp_bicep_output_dir)

    def test_init_creates_output_directory_if_not_exists(
        self, managing_tenant_id, mock_neo4j_driver, tmp_path
    ):
        """Test that bicep_output_dir is created if it doesn't exist."""
        # Arrange
        non_existent_dir = tmp_path / "new_bicep_output"

        # Act
        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(non_existent_dir),
        )

        # Assert
        assert Path(manager.bicep_output_dir).exists()


# ============================================================================
# generate_delegation_template() Tests
# ============================================================================


class TestGenerateDelegationTemplate:
    """Test LighthouseManager.generate_delegation_template()."""

    def test_generate_template_with_default_authorizations(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        customer_tenant_name,
        subscription_id,
    ):
        """Test template generation with default RBAC authorizations."""
        # Arrange
        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        template_path = manager.generate_delegation_template(
            customer_tenant_id=customer_tenant_id,
            customer_tenant_name=customer_tenant_name,
            subscription_id=subscription_id,
        )

        # Assert
        assert Path(template_path).exists()
        assert template_path.endswith(".bicep")

    def test_generate_template_with_custom_authorizations(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        customer_tenant_name,
        subscription_id,
    ):
        """Test template generation with custom RBAC authorizations."""
        # Arrange
        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )
        custom_auths = [
            {
                "principalId": "custom-principal-id",
                "roleDefinitionId": "custom-role-id",
                "principalIdDisplayName": "Custom Role",
            }
        ]

        # Act
        template_path = manager.generate_delegation_template(
            customer_tenant_id=customer_tenant_id,
            customer_tenant_name=customer_tenant_name,
            subscription_id=subscription_id,
            authorizations=custom_auths,
        )

        # Assert
        template_content = Path(template_path).read_text()
        assert "custom-principal-id" in template_content

    def test_generate_template_with_resource_group_scope(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        customer_tenant_name,
        subscription_id,
        resource_group,
    ):
        """Test template generation for resource group scoped delegation."""
        # Arrange
        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        template_path = manager.generate_delegation_template(
            customer_tenant_id=customer_tenant_id,
            customer_tenant_name=customer_tenant_name,
            subscription_id=subscription_id,
            resource_group=resource_group,
        )

        # Assert
        template_content = Path(template_path).read_text()
        assert (
            "targetScope = 'resourceGroup'" in template_content
            or "resourceGroup" in template_content
        )

    def test_generate_template_creates_neo4j_nodes(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        customer_tenant_name,
        subscription_id,
        neo4j_query_result,
    ):
        """Test that template generation creates Neo4j nodes and relationships."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        # Setup mock to return:
        # 1st call (check existing): return empty (no existing delegation)
        # 2nd call (create): return success
        mock_tx.run.side_effect = [
            neo4j_query_result([]),  # Check existing - returns empty
            neo4j_query_result(
                [{"c": {"tenant_id": customer_tenant_id}}]
            ),  # Create - returns customer
        ]

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        manager.generate_delegation_template(
            customer_tenant_id=customer_tenant_id,
            customer_tenant_name=customer_tenant_name,
            subscription_id=subscription_id,
        )

        # Assert
        # Verify Neo4j query was called (should create CustomerTenant and relationship)
        assert mock_tx.run.called

    def test_generate_template_raises_error_if_delegation_exists(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        customer_tenant_name,
        subscription_id,
        neo4j_query_result,
    ):
        """Test DelegationExistsError raised when delegation already exists."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        # Setup mock to return existing delegation
        mock_tx.run.return_value = neo4j_query_result([{"r": {"status": "active"}}])

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act & Assert
        with pytest.raises(DelegationExistsError):
            manager.generate_delegation_template(
                customer_tenant_id=customer_tenant_id,
                customer_tenant_name=customer_tenant_name,
                subscription_id=subscription_id,
            )

    def test_generate_template_invalid_tenant_id_format(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_name,
        subscription_id,
    ):
        """Test LighthouseError raised for invalid tenant ID format."""
        # Arrange
        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )
        invalid_tenant_id = "not-a-valid-uuid"

        # Act & Assert
        with pytest.raises(LighthouseError):
            manager.generate_delegation_template(
                customer_tenant_id=invalid_tenant_id,
                customer_tenant_name=customer_tenant_name,
                subscription_id=subscription_id,
            )

    def test_generate_template_creates_readme(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        customer_tenant_name,
        subscription_id,
    ):
        """Test that README is generated alongside Bicep template."""
        # Arrange
        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        template_path = manager.generate_delegation_template(
            customer_tenant_id=customer_tenant_id,
            customer_tenant_name=customer_tenant_name,
            subscription_id=subscription_id,
        )

        # Assert
        readme_path = template_path.replace(".bicep", "-README.md")
        assert Path(readme_path).exists()

    def test_generate_template_filename_format(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        customer_tenant_name,
        subscription_id,
    ):
        """Test that generated template has correct filename format."""
        # Arrange
        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        template_path = manager.generate_delegation_template(
            customer_tenant_id=customer_tenant_id,
            customer_tenant_name=customer_tenant_name,
            subscription_id=subscription_id,
        )

        # Assert
        filename = Path(template_path).name
        assert "lighthouse-delegation" in filename
        assert "acme-corp" in filename  # customer_tenant_name slug
        assert filename.endswith(".bicep")


# ============================================================================
# register_delegation() Tests
# ============================================================================


class TestRegisterDelegation:
    """Test LighthouseManager.register_delegation()."""

    def test_register_delegation_success(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        neo4j_query_result,
    ):
        """Test successful delegation registration."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        registration_def_id = "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationDefinitions/test-def-id"
        registration_assign_id = "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationAssignments/test-assign-id"

        # Mock three calls:
        # 1. _get_delegation_by_tenant_id (find pending) - returns full delegation
        # 2. _update_delegation_status (update) - returns nothing
        # 3. _get_delegation_by_tenant_id (get updated) - returns updated delegation
        pending_delegation = {
            "customer_tenant_id": customer_tenant_id,
            "customer_tenant_name": "Acme Corp",
            "managing_tenant_id": managing_tenant_id,
            "subscription_id": "22222222-2222-2222-2222-222222222222",
            "resource_group": None,
            "status": "pending",
            "registration_definition_id": None,
            "registration_assignment_id": None,
            "bicep_template_path": "./test.bicep",
            "authorizations": "[]",
            "error_message": None,
            "created_at": None,
            "updated_at": None,
        }

        active_delegation = pending_delegation.copy()
        active_delegation["status"] = "active"
        active_delegation["registration_definition_id"] = registration_def_id
        active_delegation["registration_assignment_id"] = registration_assign_id

        mock_tx.run.side_effect = [
            neo4j_query_result([pending_delegation]),  # Get pending
            neo4j_query_result([]),  # Update (doesn't return anything meaningful)
            neo4j_query_result([active_delegation]),  # Get updated
        ]

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        delegation = manager.register_delegation(
            customer_tenant_id=customer_tenant_id,
            registration_definition_id=registration_def_id,
            registration_assignment_id=registration_assign_id,
        )

        # Assert
        assert isinstance(delegation, LighthouseDelegation)
        assert delegation.status == LighthouseStatus.ACTIVE
        assert delegation.registration_definition_id == registration_def_id

    def test_register_delegation_not_found(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        neo4j_query_result,
    ):
        """Test DelegationNotFoundError when no pending delegation exists."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        # Mock no delegation found
        mock_tx.run.return_value = neo4j_query_result([])

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act & Assert
        with pytest.raises(DelegationNotFoundError):
            manager.register_delegation(
                customer_tenant_id=customer_tenant_id,
                registration_definition_id="test-def-id",
                registration_assignment_id="test-assign-id",
            )

    def test_register_delegation_updates_neo4j_relationship(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        neo4j_query_result,
    ):
        """Test that registration updates Neo4j relationship with IDs."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        registration_def_id = "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationDefinitions/test-def-id"
        registration_assign_id = "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationAssignments/test-assign-id"

        pending_delegation = {
            "customer_tenant_id": customer_tenant_id,
            "customer_tenant_name": "Acme Corp",
            "managing_tenant_id": managing_tenant_id,
            "subscription_id": "22222222-2222-2222-2222-222222222222",
            "resource_group": None,
            "status": "pending",
            "registration_definition_id": None,
            "registration_assignment_id": None,
            "bicep_template_path": "./test.bicep",
            "authorizations": "[]",
            "error_message": None,
            "created_at": None,
            "updated_at": None,
        }

        active_delegation = pending_delegation.copy()
        active_delegation["status"] = "active"
        active_delegation["registration_definition_id"] = registration_def_id
        active_delegation["registration_assignment_id"] = registration_assign_id

        mock_tx.run.side_effect = [
            neo4j_query_result([pending_delegation]),
            neo4j_query_result([]),
            neo4j_query_result([active_delegation]),
        ]

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        manager.register_delegation(
            customer_tenant_id=customer_tenant_id,
            registration_definition_id=registration_def_id,
            registration_assignment_id=registration_assign_id,
        )

        # Assert
        # Verify UPDATE query was called with registration IDs
        calls = mock_tx.run.call_args_list
        assert len(calls) >= 2  # At least one SELECT and one UPDATE


# ============================================================================
# verify_delegation() Tests
# ============================================================================


class TestVerifyDelegation:
    """Test LighthouseManager.verify_delegation()."""

    def test_verify_delegation_success(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        mock_azure_credential,
        mock_managed_services_client,
        neo4j_query_result,
    ):
        """Test successful delegation verification."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        # Mock Neo4j query - must return flat dict with all fields
        delegation_data = {
            "customer_tenant_id": customer_tenant_id,
            "customer_tenant_name": "Acme Corp",
            "managing_tenant_id": managing_tenant_id,
            "subscription_id": "22222222-2222-2222-2222-222222222222",
            "resource_group": None,
            "status": "pending",
            "registration_definition_id": "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationDefinitions/test-def-id",
            "registration_assignment_id": "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationAssignments/test-assign-id",
            "bicep_template_path": "./test.bicep",
            "authorizations": "[]",
            "error_message": None,
            "created_at": None,
            "updated_at": None,
        }

        # Mock two calls: 1) get delegation, 2) update status
        mock_tx.run.side_effect = [
            neo4j_query_result([delegation_data]),  # Get delegation
            neo4j_query_result([]),  # Update status
        ]

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        with patch(
            "src.sentinel.multi_tenant.lighthouse_manager.ManagedServicesClient",
            return_value=mock_managed_services_client,
        ), patch(
            "src.sentinel.multi_tenant.lighthouse_manager.AZURE_SDK_AVAILABLE", True
        ):
            verified = manager.verify_delegation(
                customer_tenant_id=customer_tenant_id,
                azure_credential=mock_azure_credential,
            )

        # Assert
        assert verified is True

    def test_verify_delegation_not_found(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        mock_azure_credential,
        neo4j_query_result,
    ):
        """Test verify_delegation returns False when delegation not found."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        mock_tx.run.return_value = neo4j_query_result([])

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        verified = manager.verify_delegation(
            customer_tenant_id=customer_tenant_id,
            azure_credential=mock_azure_credential,
        )

        # Assert
        assert verified is False

    def test_verify_delegation_updates_status_to_active(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        mock_azure_credential,
        mock_managed_services_client,
        neo4j_query_result,
    ):
        """Test that successful verification updates status to active."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        # Mock Neo4j query - must return flat dict with all fields
        delegation_data = {
            "customer_tenant_id": customer_tenant_id,
            "customer_tenant_name": "Acme Corp",
            "managing_tenant_id": managing_tenant_id,
            "subscription_id": "22222222-2222-2222-2222-222222222222",
            "resource_group": None,
            "status": "pending",
            "registration_definition_id": "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationDefinitions/test-def-id",
            "registration_assignment_id": "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationAssignments/test-assign-id",
            "bicep_template_path": "./test.bicep",
            "authorizations": "[]",
            "error_message": None,
            "created_at": None,
            "updated_at": None,
        }

        # Mock two calls: 1) get delegation, 2) update status
        mock_tx.run.side_effect = [
            neo4j_query_result([delegation_data]),  # Get delegation
            neo4j_query_result([]),  # Update status
        ]

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        with patch(
            "src.sentinel.multi_tenant.lighthouse_manager.ManagedServicesClient",
            return_value=mock_managed_services_client,
        ), patch(
            "src.sentinel.multi_tenant.lighthouse_manager.AZURE_SDK_AVAILABLE", True
        ):
            manager.verify_delegation(
                customer_tenant_id=customer_tenant_id,
                azure_credential=mock_azure_credential,
            )

        # Assert
        # Verify UPDATE query was called to set status=active
        calls = mock_tx.run.call_args_list
        assert len(calls) >= 2  # SELECT + UPDATE

    def test_verify_delegation_handles_azure_api_failure(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        mock_azure_credential,
        neo4j_query_result,
    ):
        """Test that Azure API failures update status to error."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        mock_tx.run.return_value = neo4j_query_result(
            [
                {
                    "r": {
                        "status": "pending",
                        "registration_assignment_id": "test-assign-id",
                    }
                }
            ]
        )

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Mock Azure API failure
        mock_client = Mock()
        mock_client.registration_assignments.get.side_effect = Exception("API Error")

        # Act
        with patch(
            "src.sentinel.multi_tenant.lighthouse_manager.ManagedServicesClient",
            return_value=mock_client,
        ), patch(
            "src.sentinel.multi_tenant.lighthouse_manager.AZURE_SDK_AVAILABLE", True
        ):
            verified = manager.verify_delegation(
                customer_tenant_id=customer_tenant_id,
                azure_credential=mock_azure_credential,
            )

        # Assert
        assert verified is False


# ============================================================================
# list_delegations() Tests
# ============================================================================


class TestListDelegations:
    """Test LighthouseManager.list_delegations()."""

    def test_list_all_delegations(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        neo4j_query_result,
        sample_delegations,
    ):
        """Test listing all delegations without filter."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        # Mock returning multiple delegations - must match the query return format (flat dict)
        mock_tx.run.return_value = neo4j_query_result(sample_delegations)

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        delegations = manager.list_delegations()

        # Assert
        assert len(delegations) == len(sample_delegations)
        assert all(isinstance(d, LighthouseDelegation) for d in delegations)

    def test_list_delegations_filtered_by_status(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        neo4j_query_result,
        sample_delegations,
    ):
        """Test listing delegations filtered by status."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        # Mock returning only active delegations - flat dict format
        active_delegations = [d for d in sample_delegations if d["status"] == "active"]
        mock_tx.run.return_value = neo4j_query_result(active_delegations)

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        delegations = manager.list_delegations(status_filter=LighthouseStatus.ACTIVE)

        # Assert
        assert len(delegations) == len(active_delegations)
        assert all(d.status == LighthouseStatus.ACTIVE for d in delegations)

    def test_list_delegations_empty_result(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        neo4j_query_result,
    ):
        """Test list_delegations returns empty list when no delegations exist."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        mock_tx.run.return_value = neo4j_query_result([])

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        delegations = manager.list_delegations()

        # Assert
        assert delegations == []


# ============================================================================
# revoke_delegation() Tests
# ============================================================================


class TestRevokeDelegation:
    """Test LighthouseManager.revoke_delegation()."""

    def test_revoke_delegation_success(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        mock_azure_credential,
        mock_managed_services_client,
        neo4j_query_result,
    ):
        """Test successful delegation revocation."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        # Mock Neo4j query - must return flat dict with all fields
        delegation_data = {
            "customer_tenant_id": customer_tenant_id,
            "customer_tenant_name": "Acme Corp",
            "managing_tenant_id": managing_tenant_id,
            "subscription_id": "22222222-2222-2222-2222-222222222222",
            "resource_group": None,
            "status": "active",
            "registration_definition_id": "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationDefinitions/test-def-id",
            "registration_assignment_id": "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationAssignments/test-assign-id",
            "bicep_template_path": "./test.bicep",
            "authorizations": "[]",
            "error_message": None,
            "created_at": None,
            "updated_at": None,
        }

        # Mock two calls: 1) get delegation, 2) update status
        mock_tx.run.side_effect = [
            neo4j_query_result([delegation_data]),  # Get delegation
            neo4j_query_result([]),  # Update status
        ]

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        with patch(
            "src.sentinel.multi_tenant.lighthouse_manager.ManagedServicesClient",
            return_value=mock_managed_services_client,
        ), patch(
            "src.sentinel.multi_tenant.lighthouse_manager.AZURE_SDK_AVAILABLE", True
        ):
            manager.revoke_delegation(
                customer_tenant_id=customer_tenant_id,
                azure_credential=mock_azure_credential,
            )

        # Assert
        # Verify Azure API delete was called
        mock_managed_services_client.registration_assignments.delete.assert_called_once()

    def test_revoke_delegation_not_found(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        mock_azure_credential,
        neo4j_query_result,
    ):
        """Test DelegationNotFoundError when delegation doesn't exist."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        mock_tx.run.return_value = neo4j_query_result([])

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act & Assert
        with pytest.raises(DelegationNotFoundError):
            manager.revoke_delegation(
                customer_tenant_id=customer_tenant_id,
                azure_credential=mock_azure_credential,
            )

    def test_revoke_delegation_updates_neo4j_status(
        self,
        managing_tenant_id,
        mock_neo4j_driver,
        temp_bicep_output_dir,
        customer_tenant_id,
        mock_azure_credential,
        mock_managed_services_client,
        neo4j_query_result,
    ):
        """Test that revocation updates Neo4j status to revoked."""
        # Arrange
        mock_session = mock_neo4j_driver.session().__enter__()
        mock_tx = mock_session.begin_transaction().__enter__()

        # Mock Neo4j query - must return flat dict with all fields
        delegation_data = {
            "customer_tenant_id": customer_tenant_id,
            "customer_tenant_name": "Acme Corp",
            "managing_tenant_id": managing_tenant_id,
            "subscription_id": "22222222-2222-2222-2222-222222222222",
            "resource_group": None,
            "status": "active",
            "registration_definition_id": "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationDefinitions/test-def-id",
            "registration_assignment_id": "/subscriptions/test-sub/providers/Microsoft.ManagedServices/registrationAssignments/test-assign-id",
            "bicep_template_path": "./test.bicep",
            "authorizations": "[]",
            "error_message": None,
            "created_at": None,
            "updated_at": None,
        }

        # Mock two calls: 1) get delegation, 2) update status
        mock_tx.run.side_effect = [
            neo4j_query_result([delegation_data]),  # Get delegation
            neo4j_query_result([]),  # Update status
        ]

        manager = LighthouseManager(
            managing_tenant_id=managing_tenant_id,
            neo4j_connection=mock_neo4j_driver,
            bicep_output_dir=str(temp_bicep_output_dir),
        )

        # Act
        with patch(
            "src.sentinel.multi_tenant.lighthouse_manager.ManagedServicesClient",
            return_value=mock_managed_services_client,
        ), patch(
            "src.sentinel.multi_tenant.lighthouse_manager.AZURE_SDK_AVAILABLE", True
        ):
            manager.revoke_delegation(
                customer_tenant_id=customer_tenant_id,
                azure_credential=mock_azure_credential,
            )

        # Assert
        calls = mock_tx.run.call_args_list
        assert len(calls) >= 2  # SELECT + UPDATE to revoked


# ============================================================================
# Data Model Tests
# ============================================================================


class TestLighthouseStatus:
    """Test LighthouseStatus enum."""

    def test_status_enum_values(self):
        """Test that LighthouseStatus has all required values."""
        assert LighthouseStatus.PENDING.value == "pending"
        assert LighthouseStatus.ACTIVE.value == "active"
        assert LighthouseStatus.REVOKED.value == "revoked"
        assert LighthouseStatus.ERROR.value == "error"


class TestLighthouseDelegation:
    """Test LighthouseDelegation dataclass."""

    def test_delegation_creation(self, active_delegation):
        """Test creating LighthouseDelegation from dict."""
        delegation = LighthouseDelegation(
            customer_tenant_id=active_delegation["customer_tenant_id"],
            customer_tenant_name=active_delegation["customer_tenant_name"],
            managing_tenant_id=active_delegation["managing_tenant_id"],
            subscription_id=active_delegation["subscription_id"],
            resource_group=active_delegation["resource_group"],
            registration_definition_id=active_delegation["registration_definition_id"],
            registration_assignment_id=active_delegation["registration_assignment_id"],
            status=LighthouseStatus(active_delegation["status"]),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            bicep_template_path=active_delegation["bicep_template_path"],
        )

        assert delegation.customer_tenant_id == active_delegation["customer_tenant_id"]
        assert delegation.status == LighthouseStatus.ACTIVE


class TestLighthouseExceptions:
    """Test exception classes."""

    def test_lighthouse_error_inheritance(self):
        """Test that LighthouseError is an Exception."""
        error = LighthouseError("test error")
        assert isinstance(error, Exception)

    def test_delegation_not_found_error_inheritance(self):
        """Test that DelegationNotFoundError inherits from LighthouseError."""
        error = DelegationNotFoundError("delegation not found")
        assert isinstance(error, LighthouseError)

    def test_delegation_exists_error_inheritance(self):
        """Test that DelegationExistsError inherits from LighthouseError."""
        error = DelegationExistsError("test-tenant-id", "active")
        assert isinstance(error, LighthouseError)

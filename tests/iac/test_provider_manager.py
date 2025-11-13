"""Tests for Azure Resource Provider Manager."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.iac.provider_manager import (
    ProviderCheckReport,
    ProviderManager,
    ProviderState,
    ProviderStatus,
)


@pytest.fixture
def mock_credential():
    """Create a mock Azure credential."""
    return Mock()


@pytest.fixture
def provider_manager(mock_credential):
    """Create a ProviderManager instance with mock credential."""
    return ProviderManager(
        subscription_id="test-subscription-id",
        credential=mock_credential,
    )


@pytest.fixture
def sample_terraform_config():
    """Sample Terraform configuration for testing."""
    return {
        "resource": {
            "azurerm_virtual_network": {
                "main": {
                    "name": "test-vnet",
                    "location": "eastus",
                    "address_space": ["10.0.0.0/16"],
                }
            },
            "azurerm_storage_account": {
                "main": {
                    "name": "teststorage",
                    "location": "eastus",
                    "account_tier": "Standard",
                }
            },
            "azurerm_linux_virtual_machine": {
                "main": {
                    "name": "test-vm",
                    "location": "eastus",
                    "size": "Standard_B2s",
                }
            },
        }
    }


class TestProviderManager:
    """Tests for ProviderManager class."""

    def test_init(self, mock_credential):
        """Test ProviderManager initialization."""
        manager = ProviderManager(
            subscription_id="test-sub",
            credential=mock_credential,
        )
        assert manager.subscription_id == "test-sub"
        assert manager.credential == mock_credential

    def test_map_resource_to_provider(self, provider_manager):
        """Test mapping Terraform resource types to Azure providers."""
        # Test known resource types
        assert (
            provider_manager._map_resource_to_provider("azurerm_virtual_network")
            == "Microsoft.Network"
        )
        assert (
            provider_manager._map_resource_to_provider("azurerm_storage_account")
            == "Microsoft.Storage"
        )
        assert (
            provider_manager._map_resource_to_provider("azurerm_linux_virtual_machine")
            == "Microsoft.Compute"
        )
        assert (
            provider_manager._map_resource_to_provider("azurerm_key_vault")
            == "Microsoft.KeyVault"
        )
        assert (
            provider_manager._map_resource_to_provider("azurerm_mssql_database")
            == "Microsoft.Sql"
        )

        # Test unknown resource type
        assert provider_manager._map_resource_to_provider("unknown_resource") is None

    def test_extract_providers_from_config(
        self, provider_manager, sample_terraform_config
    ):
        """Test extracting providers from Terraform config."""
        providers = provider_manager._extract_providers_from_config(
            sample_terraform_config
        )

        assert "Microsoft.Network" in providers
        assert "Microsoft.Storage" in providers
        assert "Microsoft.Compute" in providers
        assert len(providers) == 3

    def test_extract_providers_from_files(self, provider_manager, tmp_path):
        """Test extracting providers from Terraform files."""
        # Create sample .tf file
        tf_file = tmp_path / "main.tf"
        tf_content = """
        resource "azurerm_virtual_network" "main" {
          name                = "test-vnet"
          location            = "eastus"
          resource_group_name = azurerm_resource_group.main.name
          address_space       = ["10.0.0.0/16"]
        }

        resource "azurerm_subnet" "main" {
          name                 = "test-subnet"
          resource_group_name  = azurerm_resource_group.main.name
          virtual_network_name = azurerm_virtual_network.main.name
          address_prefixes     = ["10.0.1.0/24"]
        }

        resource "azurerm_key_vault" "main" {
          name                = "test-kv"
          location            = "eastus"
          resource_group_name = azurerm_resource_group.main.name
        }
        """
        tf_file.write_text(tf_content)

        providers = provider_manager._extract_providers_from_files(tmp_path)

        assert "Microsoft.Network" in providers
        assert "Microsoft.KeyVault" in providers
        assert len(providers) >= 2

    def test_get_required_providers_from_config(
        self, provider_manager, sample_terraform_config
    ):
        """Test getting required providers from config."""
        required = provider_manager.get_required_providers(
            terraform_config=sample_terraform_config
        )

        # Should include extracted providers plus core providers
        assert "Microsoft.Network" in required
        assert "Microsoft.Storage" in required
        assert "Microsoft.Compute" in required
        assert "Microsoft.Resources" in required  # Core provider
        assert "Microsoft.Authorization" in required  # Core provider

    def test_get_required_providers_from_files(self, provider_manager, tmp_path):
        """Test getting required providers from Terraform files."""
        # Create sample .tf file
        tf_file = tmp_path / "main.tf"
        tf_content = """
        resource "azurerm_storage_account" "main" {
          name = "teststorage"
        }
        """
        tf_file.write_text(tf_content)

        required = provider_manager.get_required_providers(terraform_path=tmp_path)

        assert "Microsoft.Storage" in required
        assert "Microsoft.Resources" in required
        assert "Microsoft.Authorization" in required

    @pytest.mark.asyncio
    async def test_check_provider_status_registered(self, provider_manager):
        """Test checking status of registered providers."""
        mock_client = Mock()
        mock_provider = Mock()
        mock_provider.registration_state = "Registered"
        mock_client.providers.get.return_value = mock_provider

        # Mock the private _client attribute instead of the property
        provider_manager._client = mock_client
        status_map = await provider_manager.check_provider_status(
            {"Microsoft.Network", "Microsoft.Storage"}
        )

        assert len(status_map) == 2
        assert status_map["Microsoft.Network"].state == ProviderState.REGISTERED
        assert status_map["Microsoft.Storage"].state == ProviderState.REGISTERED

    @pytest.mark.asyncio
    async def test_check_provider_status_not_registered(self, provider_manager):
        """Test checking status of not registered providers."""
        mock_client = Mock()

        def mock_get(namespace):
            mock_provider = Mock()
            if namespace == "Microsoft.Network":
                mock_provider.registration_state = "Registered"
            else:
                mock_provider.registration_state = "NotRegistered"
            return mock_provider

        mock_client.providers.get.side_effect = mock_get

        provider_manager._client = mock_client
        status_map = await provider_manager.check_provider_status(
            {"Microsoft.Network", "Microsoft.Compute"}
        )

        assert status_map["Microsoft.Network"].state == ProviderState.REGISTERED
        assert status_map["Microsoft.Compute"].state == ProviderState.NOT_REGISTERED

    @pytest.mark.asyncio
    async def test_register_providers_auto(self, provider_manager):
        """Test auto-registering providers without prompting."""
        mock_client = Mock()
        mock_client.providers.register = Mock()

        provider_manager._client = mock_client
        results = await provider_manager.register_providers(
            ["Microsoft.Network", "Microsoft.Storage"],
            auto=True,
        )

        assert results["Microsoft.Network"] is True
        assert results["Microsoft.Storage"] is True
        assert mock_client.providers.register.call_count == 2

    @pytest.mark.asyncio
    async def test_register_providers_with_prompt_accepted(self, provider_manager):
        """Test registering providers with user prompt (accepted)."""
        mock_client = Mock()
        mock_client.providers.register = Mock()

        with (
            patch("click.confirm", return_value=True),
            patch("click.echo"),
        ):
            provider_manager._client = mock_client
            results = await provider_manager.register_providers(
                ["Microsoft.Network"],
                auto=False,
            )

        assert results["Microsoft.Network"] is True
        mock_client.providers.register.assert_called_once_with("Microsoft.Network")

    @pytest.mark.asyncio
    async def test_register_providers_with_prompt_declined(self, provider_manager):
        """Test registering providers with user prompt (declined)."""
        mock_client = Mock()
        mock_client.providers.register = Mock()

        with (
            patch("click.confirm", return_value=False),
            patch("click.echo"),
        ):
            provider_manager._client = mock_client
            results = await provider_manager.register_providers(
                ["Microsoft.Network"],
                auto=False,
            )

        assert results["Microsoft.Network"] is False
        mock_client.providers.register.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_and_register_providers_all_registered(self, provider_manager):
        """Test check and register when all providers are already registered."""
        mock_client = Mock()
        mock_provider = Mock()
        mock_provider.registration_state = "Registered"
        mock_client.providers.get.return_value = mock_provider

        with patch("click.echo"):
            provider_manager._client = mock_client
            report = await provider_manager.check_and_register_providers(
                required_providers={"Microsoft.Network", "Microsoft.Storage"},
                auto=True,
            )

        assert len(report.required_providers) == 2
        assert len(report.registered_providers) == 0  # None newly registered
        assert len(report.failed_providers) == 0
        assert report.subscription_id == "test-subscription-id"

    @pytest.mark.asyncio
    async def test_check_and_register_providers_needs_registration(
        self, provider_manager
    ):
        """Test check and register when providers need registration."""
        mock_client = Mock()

        def mock_get(namespace):
            mock_provider = Mock()
            mock_provider.registration_state = "NotRegistered"
            return mock_provider

        mock_client.providers.get.side_effect = mock_get
        mock_client.providers.register = Mock()

        with patch("click.echo"):
            provider_manager._client = mock_client
            report = await provider_manager.check_and_register_providers(
                required_providers={"Microsoft.Network"},
                auto=True,
            )

        assert len(report.required_providers) == 1
        assert len(report.registered_providers) == 1
        assert "Microsoft.Network" in report.registered_providers

    @pytest.mark.asyncio
    async def test_validate_before_deploy(self, provider_manager, tmp_path):
        """Test validate_before_deploy integration."""
        # Create sample Terraform file
        tf_file = tmp_path / "main.tf"
        tf_content = """
        resource "azurerm_virtual_network" "main" {
          name = "test-vnet"
        }
        """
        tf_file.write_text(tf_content)

        # Mock provider as registered
        mock_client = Mock()
        mock_provider = Mock()
        mock_provider.registration_state = "Registered"
        mock_client.providers.get.return_value = mock_provider

        with patch("click.echo"):
            provider_manager._client = mock_client
            report = await provider_manager.validate_before_deploy(
                terraform_path=tmp_path,
                auto_register=True,
            )

        assert report is not None
        assert "Microsoft.Network" in report.required_providers
        assert "Microsoft.Resources" in report.required_providers

    def test_provider_check_report_format(self):
        """Test ProviderCheckReport formatting."""
        report = ProviderCheckReport(
            subscription_id="test-sub",
            required_providers={"Microsoft.Network", "Microsoft.Storage"},
            checked_providers={
                "Microsoft.Network": ProviderStatus(
                    namespace="Microsoft.Network",
                    state=ProviderState.REGISTERED,
                ),
                "Microsoft.Storage": ProviderStatus(
                    namespace="Microsoft.Storage",
                    state=ProviderState.NOT_REGISTERED,
                ),
            },
            registered_providers=["Microsoft.Storage"],
            failed_providers=[],
            skipped_providers=[],
        )

        formatted = report.format_report()
        assert "AZURE RESOURCE PROVIDER CHECK REPORT" in formatted
        assert "test-sub" in formatted
        assert "Microsoft.Network" in formatted
        assert "Microsoft.Storage" in formatted
        assert "Newly Registered (1)" in formatted


class TestProviderManagerResourceMappings:
    """Tests for resource type to provider mappings."""

    def test_compute_resources(self, provider_manager):
        """Test Compute provider mappings."""
        compute_resources = [
            "azurerm_virtual_machine",
            "azurerm_linux_virtual_machine",
            "azurerm_windows_virtual_machine",
            "azurerm_managed_disk",
            "azurerm_availability_set",
        ]
        for resource_type in compute_resources:
            assert (
                provider_manager._map_resource_to_provider(resource_type)
                == "Microsoft.Compute"
            )

    def test_network_resources(self, provider_manager):
        """Test Network provider mappings."""
        network_resources = [
            "azurerm_virtual_network",
            "azurerm_subnet",
            "azurerm_network_interface",
            "azurerm_public_ip",
            "azurerm_network_security_group",
            "azurerm_load_balancer",
            "azurerm_application_gateway",
        ]
        for resource_type in network_resources:
            assert (
                provider_manager._map_resource_to_provider(resource_type)
                == "Microsoft.Network"
            )

    def test_storage_resources(self, provider_manager):
        """Test Storage provider mappings."""
        storage_resources = [
            "azurerm_storage_account",
            "azurerm_storage_container",
            "azurerm_storage_blob",
            "azurerm_storage_queue",
        ]
        for resource_type in storage_resources:
            assert (
                provider_manager._map_resource_to_provider(resource_type)
                == "Microsoft.Storage"
            )

    def test_keyvault_resources(self, provider_manager):
        """Test KeyVault provider mappings."""
        keyvault_resources = [
            "azurerm_key_vault",
            "azurerm_key_vault_secret",
            "azurerm_key_vault_key",
            "azurerm_key_vault_certificate",
        ]
        for resource_type in keyvault_resources:
            assert (
                provider_manager._map_resource_to_provider(resource_type)
                == "Microsoft.KeyVault"
            )

    def test_sql_resources(self, provider_manager):
        """Test SQL provider mappings."""
        sql_resources = [
            "azurerm_sql_server",
            "azurerm_mssql_server",
            "azurerm_mssql_database",
            "azurerm_sql_database",
        ]
        for resource_type in sql_resources:
            assert (
                provider_manager._map_resource_to_provider(resource_type)
                == "Microsoft.Sql"
            )

    def test_web_resources(self, provider_manager):
        """Test Web/App Service provider mappings."""
        web_resources = [
            "azurerm_app_service",
            "azurerm_app_service_plan",
            "azurerm_linux_web_app",
            "azurerm_windows_web_app",
            "azurerm_function_app",
        ]
        for resource_type in web_resources:
            assert (
                provider_manager._map_resource_to_provider(resource_type)
                == "Microsoft.Web"
            )

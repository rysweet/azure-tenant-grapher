"""Integration tests for Lighthouse CLI commands.

Tests the CLI layer integration with LighthouseManager.
Uses Click's CliRunner for isolated command testing.

Issue #588: Azure Lighthouse Foundation (Phase 1)
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from click.testing import CliRunner

from src.commands.lighthouse import (
    lighthouse,
    list_delegations,
    setup,
    verify,
    revoke,
)
from sentinel.multi_tenant.models import LighthouseStatus, LighthouseDelegation
from sentinel.multi_tenant.exceptions import (
    DelegationAlreadyExistsError,
    DelegationNotFoundError,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def cli_runner():
    """Provide Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_lighthouse_manager():
    """Mock LighthouseManager for CLI tests."""
    manager = MagicMock()

    # Mock successful delegation
    delegation = LighthouseDelegation(
        customer_tenant_id="22222222-2222-2222-2222-222222222222",
        customer_tenant_name="Acme Corp",
        managing_tenant_id="11111111-1111-1111-1111-111111111111",
        subscription_id="33333333-3333-3333-3333-333333333333",
        resource_group=None,
        status=LighthouseStatus.PENDING,
        bicep_template_path="./test.bicep",
        authorizations=[]
    )

    manager.generate_delegation_template.return_value = delegation
    manager.list_delegations.return_value = [delegation]
    manager.verify_delegation.return_value = True
    manager.revoke_delegation.return_value = None

    return manager


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver."""
    driver = MagicMock()
    return driver


@pytest.fixture
def mock_azure_credential():
    """Mock Azure credential."""
    return MagicMock()


@pytest.fixture
def env_vars(monkeypatch):
    """Set required environment variables."""
    monkeypatch.setenv("AZURE_LIGHTHOUSE_MANAGING_TENANT_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("AZURE_LIGHTHOUSE_BICEP_DIR", "./test_bicep")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "test")


# ============================================================================
# lighthouse setup tests
# ============================================================================


class TestLighthouseSetup:
    """Test 'atg lighthouse setup' command."""

    def test_setup_success(
        self,
        cli_runner,
        mock_lighthouse_manager,
        mock_neo4j_driver,
        env_vars
    ):
        """Test successful delegation setup."""
        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            with patch("src.commands.lighthouse.ensure_neo4j_running"):
                result = cli_runner.invoke(
                    setup,
                    [
                        "--customer-tenant-id", "22222222-2222-2222-2222-222222222222",
                        "--customer-tenant-name", "Acme Corp",
                        "--subscription-id", "33333333-3333-3333-3333-333333333333",
                        "--role", "Contributor",
                        "--principal-id", "44444444-4444-4444-4444-444444444444"
                    ]
                )

                assert result.exit_code == 0
                assert "template generated successfully" in result.output
                assert "Next steps" in result.output
                mock_lighthouse_manager.generate_delegation_template.assert_called_once()

    def test_setup_missing_principal_id(self, cli_runner, env_vars):
        """Test setup fails without principal ID."""
        result = cli_runner.invoke(
            setup,
            [
                "--customer-tenant-id", "22222222-2222-2222-2222-222222222222",
                "--customer-tenant-name", "Acme Corp",
                "--subscription-id", "33333333-3333-3333-3333-333333333333",
                "--role", "Contributor"
            ]
        )

        assert result.exit_code == 1
        assert "at least one --principal-id must be specified" in result.output

    def test_setup_delegation_already_exists(
        self,
        cli_runner,
        mock_lighthouse_manager,
        env_vars
    ):
        """Test setup with existing delegation."""
        mock_lighthouse_manager.generate_delegation_template.side_effect = DelegationAlreadyExistsError(
            "Delegation already exists"
        )

        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            with patch("src.commands.lighthouse.ensure_neo4j_running"):
                result = cli_runner.invoke(
                    setup,
                    [
                        "--customer-tenant-id", "22222222-2222-2222-2222-222222222222",
                        "--customer-tenant-name", "Acme Corp",
                        "--subscription-id", "33333333-3333-3333-3333-333333333333",
                        "--role", "Contributor",
                        "--principal-id", "44444444-4444-4444-4444-444444444444"
                    ]
                )

                assert result.exit_code == 1
                assert "Delegation already exists" in result.output

    def test_setup_missing_env_var(self, cli_runner):
        """Test setup fails without required environment variable."""
        with patch("src.commands.lighthouse.ensure_neo4j_running"):
            result = cli_runner.invoke(
                setup,
                [
                    "--customer-tenant-id", "22222222-2222-2222-2222-222222222222",
                    "--customer-tenant-name", "Acme Corp",
                    "--subscription-id", "33333333-3333-3333-3333-333333333333",
                    "--role", "Contributor",
                    "--principal-id", "44444444-4444-4444-4444-444444444444"
                ]
            )

            assert result.exit_code == 1
            assert "AZURE_LIGHTHOUSE_MANAGING_TENANT_ID" in result.output


# ============================================================================
# lighthouse list tests
# ============================================================================


class TestLighthouseList:
    """Test 'atg lighthouse list' command."""

    def test_list_table_format(
        self,
        cli_runner,
        mock_lighthouse_manager,
        env_vars
    ):
        """Test list with default table format."""
        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            result = cli_runner.invoke(list_delegations, [])

            assert result.exit_code == 0
            assert "Azure Lighthouse Delegations" in result.output
            assert "Acme Corp" in result.output
            mock_lighthouse_manager.list_delegations.assert_called_once()

    def test_list_json_format(
        self,
        cli_runner,
        mock_lighthouse_manager,
        env_vars
    ):
        """Test list with JSON format."""
        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            result = cli_runner.invoke(list_delegations, ["--format", "json"])

            assert result.exit_code == 0
            # Parse JSON output
            output_json = json.loads(result.output)
            assert len(output_json) == 1
            assert output_json[0]["customer_tenant_name"] == "Acme Corp"

    def test_list_filter_by_status(
        self,
        cli_runner,
        mock_lighthouse_manager,
        env_vars
    ):
        """Test list filtered by status."""
        # Create delegation with active status
        active_delegation = LighthouseDelegation(
            customer_tenant_id="22222222-2222-2222-2222-222222222222",
            customer_tenant_name="Acme Corp",
            managing_tenant_id="11111111-1111-1111-1111-111111111111",
            subscription_id="33333333-3333-3333-3333-333333333333",
            resource_group=None,
            status=LighthouseStatus.ACTIVE,
            bicep_template_path="./test.bicep",
            authorizations=[]
        )

        mock_lighthouse_manager.list_delegations.return_value = [active_delegation]

        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            result = cli_runner.invoke(list_delegations, ["--status", "active"])

            assert result.exit_code == 0
            assert "Acme Corp" in result.output

    def test_list_empty(
        self,
        cli_runner,
        mock_lighthouse_manager,
        env_vars
    ):
        """Test list with no delegations."""
        mock_lighthouse_manager.list_delegations.return_value = []

        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            result = cli_runner.invoke(list_delegations, [])

            assert result.exit_code == 0
            assert "No delegations found" in result.output


# ============================================================================
# lighthouse verify tests
# ============================================================================


class TestLighthouseVerify:
    """Test 'atg lighthouse verify' command."""

    def test_verify_success(
        self,
        cli_runner,
        mock_lighthouse_manager,
        mock_azure_credential,
        env_vars
    ):
        """Test successful delegation verification."""
        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            with patch("src.commands.lighthouse.get_azure_credential", return_value=mock_azure_credential):
                result = cli_runner.invoke(
                    verify,
                    ["--customer-tenant-id", "22222222-2222-2222-2222-222222222222"]
                )

                assert result.exit_code == 0
                assert "Delegation is ACTIVE" in result.output
                mock_lighthouse_manager.verify_delegation.assert_called_once()

    def test_verify_not_found(
        self,
        cli_runner,
        mock_lighthouse_manager,
        mock_azure_credential,
        env_vars
    ):
        """Test verify with non-existent delegation."""
        mock_lighthouse_manager.verify_delegation.side_effect = DelegationNotFoundError(
            "Delegation not found"
        )

        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            with patch("src.commands.lighthouse.get_azure_credential", return_value=mock_azure_credential):
                result = cli_runner.invoke(
                    verify,
                    ["--customer-tenant-id", "99999999-9999-9999-9999-999999999999"]
                )

                assert result.exit_code == 1
                assert "Delegation not found" in result.output

    def test_verify_failed(
        self,
        cli_runner,
        mock_lighthouse_manager,
        mock_azure_credential,
        env_vars
    ):
        """Test verify when delegation verification fails."""
        mock_lighthouse_manager.verify_delegation.return_value = False

        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            with patch("src.commands.lighthouse.get_azure_credential", return_value=mock_azure_credential):
                result = cli_runner.invoke(
                    verify,
                    ["--customer-tenant-id", "22222222-2222-2222-2222-222222222222"]
                )

                assert result.exit_code == 0
                assert "verification failed" in result.output


# ============================================================================
# lighthouse revoke tests
# ============================================================================


class TestLighthouseRevoke:
    """Test 'atg lighthouse revoke' command."""

    def test_revoke_with_confirm_flag(
        self,
        cli_runner,
        mock_lighthouse_manager,
        mock_azure_credential,
        env_vars
    ):
        """Test revoke with --confirm flag."""
        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            with patch("src.commands.lighthouse.get_azure_credential", return_value=mock_azure_credential):
                result = cli_runner.invoke(
                    revoke,
                    [
                        "--customer-tenant-id", "22222222-2222-2222-2222-222222222222",
                        "--confirm"
                    ]
                )

                assert result.exit_code == 0
                assert "revoked successfully" in result.output
                mock_lighthouse_manager.revoke_delegation.assert_called_once()

    def test_revoke_with_confirmation_yes(
        self,
        cli_runner,
        mock_lighthouse_manager,
        mock_azure_credential,
        env_vars
    ):
        """Test revoke with interactive confirmation (yes)."""
        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            with patch("src.commands.lighthouse.get_azure_credential", return_value=mock_azure_credential):
                result = cli_runner.invoke(
                    revoke,
                    ["--customer-tenant-id", "22222222-2222-2222-2222-222222222222"],
                    input="y\n"
                )

                assert result.exit_code == 0
                assert "revoked successfully" in result.output

    def test_revoke_with_confirmation_no(
        self,
        cli_runner,
        mock_lighthouse_manager,
        mock_azure_credential,
        env_vars
    ):
        """Test revoke with interactive confirmation (no)."""
        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            with patch("src.commands.lighthouse.get_azure_credential", return_value=mock_azure_credential):
                result = cli_runner.invoke(
                    revoke,
                    ["--customer-tenant-id", "22222222-2222-2222-2222-222222222222"],
                    input="n\n"
                )

                assert result.exit_code == 0
                assert "Cancelled" in result.output
                mock_lighthouse_manager.revoke_delegation.assert_not_called()

    def test_revoke_not_found(
        self,
        cli_runner,
        mock_lighthouse_manager,
        mock_azure_credential,
        env_vars
    ):
        """Test revoke with non-existent delegation."""
        mock_lighthouse_manager.revoke_delegation.side_effect = DelegationNotFoundError(
            "Delegation not found"
        )

        with patch("src.commands.lighthouse.get_lighthouse_manager", return_value=mock_lighthouse_manager):
            with patch("src.commands.lighthouse.get_azure_credential", return_value=mock_azure_credential):
                result = cli_runner.invoke(
                    revoke,
                    [
                        "--customer-tenant-id", "99999999-9999-9999-9999-999999999999",
                        "--confirm"
                    ]
                )

                assert result.exit_code == 1
                assert "Delegation not found" in result.output

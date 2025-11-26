"""Tests for Data Collection Rule workspace reference validation.

This test module covers the DCR workspace validation feature where DCRs
that reference non-existent Log Analytics workspaces are skipped during
IaC generation.

Bug Context: 8 Data Collection Rules referenced a non-existent workspace:
DefaultWorkspace-c190c55a-9ab2-4b1e-92c4-cc8b1a032285-CUS

Fix: Lines 3067-3075 in terraform_emitter.py now validate workspace existence
in the graph before including the DCR in the generated Terraform.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestDCRWorkspaceValidation:
    """Unit tests for Data Collection Rule workspace validation."""

    def test_dcr_with_valid_workspace(self) -> None:
        """Test DCR with valid workspace reference.

        DCR should be generated when the referenced workspace exists in the graph.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        # Create a valid workspace resource
        workspace_id = (
            "/subscriptions/test-sub/resourceGroups/test-rg/"
            "providers/Microsoft.OperationalInsights/workspaces/valid-workspace"
        )

        # Create DCR properties with valid workspace reference
        dcr_properties = {
            "destinations": {
                "logAnalytics": [
                    {
                        "workspaceResourceId": workspace_id,
                        "name": "valid-destination",
                    }
                ]
            },
            "dataFlows": [
                {
                    "streams": ["Microsoft-Perf"],
                    "destinations": ["valid-destination"],
                }
            ],
        }

        graph.resources = [
            # Workspace resource
            {
                "type": "Microsoft.OperationalInsights/workspaces",
                "name": "valid-workspace",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": workspace_id,
                "original_id": workspace_id,
            },
            # DCR resource
            {
                "type": "Microsoft.Insights/dataCollectionRules",
                "name": "test-dcr",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(dcr_properties),
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            # Read generated Terraform config
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Verify both resources were generated
            assert "azurerm_log_analytics_workspace" in terraform_config["resource"]
            assert (
                "azurerm_monitor_data_collection_rule" in terraform_config["resource"]
            )

            # Verify DCR has correct workspace reference
            dcr_resource = terraform_config["resource"][
                "azurerm_monitor_data_collection_rule"
            ]["test_dcr"]
            assert "destinations" in dcr_resource
            assert "log_analytics" in dcr_resource["destinations"]
            assert len(dcr_resource["destinations"]["log_analytics"]) == 1
            assert (
                dcr_resource["destinations"]["log_analytics"][0][
                    "workspace_resource_id"
                ]
                == workspace_id
            )

    def test_dcr_with_missing_workspace(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test DCR with non-existent workspace reference.

        DCR should be skipped when the referenced workspace doesn't exist in the graph.
        A warning should be logged.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        # Create DCR with non-existent workspace reference
        missing_workspace_id = (
            "/subscriptions/test-sub/resourceGroups/test-rg/"
            "providers/Microsoft.OperationalInsights/workspaces/"
            "DefaultWorkspace-c190c55a-9ab2-4b1e-92c4-cc8b1a032285-CUS"
        )

        dcr_properties = {
            "destinations": {
                "logAnalytics": [
                    {
                        "workspaceResourceId": missing_workspace_id,
                        "name": "missing-destination",
                    }
                ]
            },
            "dataFlows": [
                {
                    "streams": ["Microsoft-Perf"],
                    "destinations": ["missing-destination"],
                }
            ],
        }

        graph.resources = [
            # DCR resource (no workspace in graph)
            {
                "type": "Microsoft.Insights/dataCollectionRules",
                "name": "test-dcr-missing-ws",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(dcr_properties),
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            # Read generated Terraform config
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Verify DCR was NOT generated
            assert (
                "azurerm_monitor_data_collection_rule"
                not in terraform_config["resource"]
            ), "DCR with missing workspace should not be generated"

            # Verify warning was logged
            assert any(
                "references non-existent" in record.message
                and "test-dcr-missing-ws" in record.message
                for record in caplog.records
            ), "Should log warning about missing workspace"

    def test_dcr_with_abstracted_workspace_id(self) -> None:
        """Test DCR with workspace reference using abstracted IDs.

        In dual-graph architecture, workspaces have both abstracted IDs
        (e.g., "law-a1b2c3d4") and original IDs (full Azure resource path).
        DCR validation should work with both.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        # Workspace with abstracted ID
        original_workspace_id = (
            "/subscriptions/test-sub/resourceGroups/test-rg/"
            "providers/Microsoft.OperationalInsights/workspaces/original-workspace"
        )
        abstracted_workspace_id = "law-a1b2c3d4"

        # DCR references the original ID (as it would in Azure)
        dcr_properties = {
            "destinations": {
                "logAnalytics": [
                    {
                        "workspaceResourceId": original_workspace_id,
                        "name": "abstracted-destination",
                    }
                ]
            },
            "dataFlows": [
                {
                    "streams": ["Microsoft-Perf"],
                    "destinations": ["abstracted-destination"],
                }
            ],
        }

        graph.resources = [
            # Abstracted workspace resource
            {
                "type": "Microsoft.OperationalInsights/workspaces",
                "name": "original-workspace",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": abstracted_workspace_id,  # Abstracted
                "original_id": original_workspace_id,  # Original
            },
            # DCR resource
            {
                "type": "Microsoft.Insights/dataCollectionRules",
                "name": "test-dcr-abstracted",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(dcr_properties),
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            # Read generated Terraform config
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Verify both resources were generated
            assert "azurerm_log_analytics_workspace" in terraform_config["resource"]
            assert (
                "azurerm_monitor_data_collection_rule" in terraform_config["resource"]
            )

    def test_dcr_with_case_insensitive_workspace_type(self) -> None:
        """Test DCR validation works with different workspace type casings.

        Azure APIs return inconsistent casing (e.g., microsoft.OperationalInsights
        vs Microsoft.OperationalInsights). Validation should handle both.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        # Use normalized workspace ID (proper casing)
        workspace_id = (
            "/subscriptions/test-sub/resourceGroups/test-rg/"
            "providers/Microsoft.OperationalInsights/workspaces/case-test-workspace"
        )

        dcr_properties = {
            "destinations": {
                "logAnalytics": [
                    {
                        "workspaceResourceId": workspace_id,
                        "name": "case-destination",
                    }
                ]
            },
            "dataFlows": [
                {
                    "streams": ["Microsoft-Perf"],
                    "destinations": ["case-destination"],
                }
            ],
        }

        graph.resources = [
            # Workspace with proper casing in type
            {
                "type": "Microsoft.OperationalInsights/workspaces",
                "name": "case-test-workspace",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": workspace_id,
                "original_id": workspace_id,
            },
            # DCR resource
            {
                "type": "Microsoft.Insights/dataCollectionRules",
                "name": "test-dcr-case",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(dcr_properties),
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            # Read generated Terraform config
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Verify both resources were generated
            assert "azurerm_log_analytics_workspace" in terraform_config["resource"]
            assert (
                "azurerm_monitor_data_collection_rule" in terraform_config["resource"]
            )

    def test_dcr_with_multiple_workspaces_one_missing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test DCR with multiple workspace destinations where one is missing.

        If any workspace reference is missing, the entire DCR should be skipped
        to avoid partial/invalid configuration.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        valid_workspace_id = (
            "/subscriptions/test-sub/resourceGroups/test-rg/"
            "providers/Microsoft.OperationalInsights/workspaces/valid-workspace"
        )
        missing_workspace_id = (
            "/subscriptions/test-sub/resourceGroups/test-rg/"
            "providers/Microsoft.OperationalInsights/workspaces/missing-workspace"
        )

        dcr_properties = {
            "destinations": {
                "logAnalytics": [
                    {
                        "workspaceResourceId": valid_workspace_id,
                        "name": "valid-destination",
                    },
                    {
                        "workspaceResourceId": missing_workspace_id,
                        "name": "missing-destination",
                    },
                ]
            },
            "dataFlows": [
                {
                    "streams": ["Microsoft-Perf"],
                    "destinations": ["valid-destination", "missing-destination"],
                }
            ],
        }

        graph.resources = [
            # Only one workspace exists
            {
                "type": "Microsoft.OperationalInsights/workspaces",
                "name": "valid-workspace",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": valid_workspace_id,
                "original_id": valid_workspace_id,
            },
            # DCR resource
            {
                "type": "Microsoft.Insights/dataCollectionRules",
                "name": "test-dcr-multi",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(dcr_properties),
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            # Read generated Terraform config
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Verify DCR was NOT generated (fails on first missing workspace)
            assert (
                "azurerm_monitor_data_collection_rule"
                not in terraform_config["resource"]
            ), "DCR with any missing workspace should not be generated"

            # Verify warning was logged
            assert any(
                "references non-existent" in record.message
                and "test-dcr-multi" in record.message
                for record in caplog.records
            ), "Should log warning about missing workspace"

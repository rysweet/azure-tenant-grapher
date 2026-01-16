#!/usr/bin/env python3
"""
Azure Sentinel Multi-Tenant Query Tool

Queries multiple Sentinel workspaces across tenants via Azure Lighthouse
and aggregates security incidents.

Requirements:
    pip install azure-identity azure-mgmt-loganalytics azure-monitor-query pandas
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import List

import pandas as pd
from azure.identity import DefaultAzureCredential
from azure.mgmt.loganalytics import LogAnalyticsManagementClient
from azure.monitor.query import LogsQueryClient, LogsQueryStatus


@dataclass
class TenantWorkspace:
    """Represents a tenant's Sentinel workspace"""

    tenant_id: str
    subscription_id: str
    workspace_name: str
    workspace_id: str


class SentinelMultiTenantQuery:
    """Query multiple Sentinel workspaces across tenants"""

    def __init__(self):
        # Authenticate with service principal via environment variables:
        # AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
        self.credential = DefaultAzureCredential(
            additionally_allowed_tenants=["*"]  # Enable cross-tenant access
        )
        self.logs_client = LogsQueryClient(self.credential)

    def discover_workspaces(self, subscription_ids: List[str]) -> List[TenantWorkspace]:
        """Discover all Sentinel workspaces across subscriptions"""
        workspaces = []

        for sub_id in subscription_ids:
            try:
                mgmt_client = LogAnalyticsManagementClient(self.credential, sub_id)

                for workspace in mgmt_client.workspaces.list():
                    # Check if Sentinel is enabled
                    try:
                        solutions = mgmt_client.intelligence_packs.list(
                            resource_group_name=workspace.id.split("/")[4],
                            workspace_name=workspace.name,
                        )

                        sentinel_enabled = any(
                            s.name == "SecurityInsights" and s.enabled
                            for s in solutions
                        )

                        if sentinel_enabled:
                            workspaces.append(
                                TenantWorkspace(
                                    tenant_id=workspace.customer_id,
                                    subscription_id=sub_id,
                                    workspace_name=workspace.name,
                                    workspace_id=workspace.customer_id,
                                )
                            )
                            print(f"✓ Found Sentinel workspace: {workspace.name}")
                    except Exception:
                        continue

            except Exception as e:
                print(f"✗ Error discovering workspaces in {sub_id}: {e}")
                continue

        return workspaces

    def query_workspace(
        self, workspace_id: str, kql_query: str, timespan: timedelta
    ) -> pd.DataFrame:
        """Execute KQL query against a single workspace"""
        try:
            response = self.logs_client.query_workspace(
                workspace_id=workspace_id, query=kql_query, timespan=timespan
            )

            if response.status == LogsQueryStatus.SUCCESS:
                data = response.tables[0]
                df = pd.DataFrame(data.rows, columns=[col.name for col in data.columns])
                return df
            else:
                print(f"⚠ Partial failure for workspace {workspace_id}")
                return pd.DataFrame()

        except Exception as e:
            print(f"✗ Error querying workspace {workspace_id}: {e}")
            return pd.DataFrame()

    def query_all_workspaces(
        self,
        workspaces: List[TenantWorkspace],
        kql_query: str,
        timespan: timedelta = timedelta(days=7),
    ) -> pd.DataFrame:
        """Query all workspaces and aggregate results"""
        all_results = []

        for workspace in workspaces:
            print(f"Querying workspace: {workspace.workspace_name}...")

            # Add workspace context to query
            contextual_query = f"""
            {kql_query}
            | extend WorkspaceId = '{workspace.workspace_id}'
            | extend WorkspaceName = '{workspace.workspace_name}'
            | extend TenantId = '{workspace.tenant_id}'
            """

            df = self.query_workspace(
                workspace.workspace_id, contextual_query, timespan
            )

            if not df.empty:
                all_results.append(df)

        # Combine all results
        if all_results:
            return pd.concat(all_results, ignore_index=True)
        else:
            return pd.DataFrame()


def main():
    """Example usage: Query security incidents across all tenants"""

    # Initialize multi-tenant query client
    client = SentinelMultiTenantQuery()

    # List of subscription IDs (delegated via Azure Lighthouse)
    subscription_ids = [
        "00000000-0000-0000-0000-000000000001",  # Tenant 1
        "00000000-0000-0000-0000-000000000002",  # Tenant 2
        # Add all delegated subscription IDs here
    ]

    # Discover all Sentinel workspaces
    print("Discovering Sentinel workspaces across tenants...")
    workspaces = client.discover_workspaces(subscription_ids)
    print(f"\n✓ Found {len(workspaces)} Sentinel workspaces\n")

    if not workspaces:
        print("No Sentinel workspaces found. Exiting.")
        return

    # Define KQL query for security incidents
    kql_query = """
    SecurityIncident
    | where TimeGenerated > ago(7d)
    | summarize
        TotalIncidents = count(),
        HighSeverity = countif(Severity == "High"),
        MediumSeverity = countif(Severity == "Medium"),
        LowSeverity = countif(Severity == "Low")
        by bin(TimeGenerated, 1d)
    | order by TimeGenerated desc
    """

    # Query all workspaces
    print("Querying all workspaces for security incidents...\n")
    results = client.query_all_workspaces(
        workspaces, kql_query, timespan=timedelta(days=7)
    )

    if results.empty:
        print("No results found.")
        return

    # Display summary statistics
    print("\n" + "=" * 70)
    print("Multi-Tenant Security Incident Summary (Last 7 Days)")
    print("=" * 70)

    # Aggregate by workspace
    summary = (
        results.groupby(["WorkspaceName", "TenantId"])
        .agg(
            {
                "TotalIncidents": "sum",
                "HighSeverity": "sum",
                "MediumSeverity": "sum",
                "LowSeverity": "sum",
            }
        )
        .reset_index()
    )

    print(summary.to_string(index=False))

    # Export to CSV
    output_file = (
        f"sentinel_incidents_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    results.to_csv(output_file, index=False)
    print(f"\n✓ Detailed results exported to: {output_file}")


if __name__ == "__main__":
    main()

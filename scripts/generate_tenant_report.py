#!/usr/bin/env python3
"""
Parallel Azure Tenant Report Generator
Generates comprehensive inventory report using 20+ parallel threads.

Tenant: 3cd87a41-1f61-4aef-a212-cefdecd9a2d1
"""

import asyncio
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from azure.identity import DefaultAzureCredential
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.resource import ResourceManagementClient, SubscriptionClient
from dotenv import load_dotenv

# Use existing project services
from src.services.aad_graph_service import AADGraphService

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(str(f"📄 Loaded environment from {env_path}"))


@dataclass
class TenantInventory:
    """Complete tenant inventory data"""

    tenant_id: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Subscriptions
    subscriptions: List[Dict[str, Any]] = field(default_factory=list)
    subscription_count: int = 0

    # Entra ID
    users_count: int = 0
    groups_count: int = 0
    service_principals_count: int = 0
    managed_identities_count: int = 0

    # Resources
    total_resources: int = 0
    resources_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    resources_by_region: Dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    resources_by_subscription: Dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )

    # Role Assignments
    total_role_assignments: int = 0
    role_assignments_by_scope: Dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    top_roles: List[tuple] = field(default_factory=list)

    # Cost (optional)
    estimated_monthly_cost: float = 0.0
    cost_available: bool = False
    cost_error: str = ""

    # Errors
    errors: List[str] = field(default_factory=list)


class ParallelTenantReporter:
    """Collects tenant data using 20+ parallel threads"""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.inventory = TenantInventory(tenant_id=tenant_id)
        self.credential = DefaultAzureCredential()
        self.aad_service = None

    async def __aenter__(self):
        # Initialize AAD Graph service (reuses existing project service)
        self.aad_service = AADGraphService(use_mock=False)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass  # Cleanup if needed

    async def collect_all_data(self) -> TenantInventory:
        """Orchestrate parallel data collection across 20+ threads"""
        print(
            str(f"🏴‍☠️ Starting parallel data collection for tenant: {self.tenant_id}")
        )
        print("⚓ Deploying at least 20 parallel threads...\n")

        # Phase 1: Discover subscriptions first (needed for other operations)
        print("📋 Phase 1: Discovering subscriptions...")
        await self.discover_subscriptions()
        print(str(f"   ✓ Found {self.inventory.subscription_count} subscriptions\n"))

        # Phase 2: Launch 20+ parallel collection tasks
        print("🚀 Phase 2: Launching parallel data collection (20+ threads)...")

        tasks = []

        # Entra ID Collection (4 parallel threads)
        tasks.append(self.collect_users())
        tasks.append(self.collect_groups())
        tasks.append(self.collect_service_principals())
        tasks.append(self.collect_managed_identities())

        # Per-Subscription Collection (3 tasks per subscription)
        for sub in self.inventory.subscriptions:
            sub_id = sub["subscription_id"]
            sub_name = sub.get("name", "Unknown")

            # Resources
            tasks.append(self.collect_resources_in_subscription(sub_id, sub_name))

            # Role Assignments
            tasks.append(
                self.collect_role_assignments_in_subscription(sub_id, sub_name)
            )

            # Cost Data (optional)
            tasks.append(self.collect_cost_data_for_subscription(sub_id, sub_name))

        print(str(f"   Launched {len(tasks)} parallel tasks"))
        print("   Breakdown:")
        print("     - Entra ID: 4 tasks")
        print(
            f"     - Per-subscription: {len(self.inventory.subscriptions)} subs x 3 = {len(self.inventory.subscriptions) * 3} tasks"
        )
        print(str(f"   Total: {len(tasks)} concurrent threads\n"))

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.inventory.errors.append(f"Task {i} failed: {result!s}")

        # Extract managed identities count from resources
        mi_type = "Microsoft.ManagedIdentity/userAssignedIdentities"
        self.inventory.managed_identities_count = self.inventory.resources_by_type.get(
            mi_type, 0
        )

        print("✅ Data collection complete!\n")
        return self.inventory

    async def discover_subscriptions(self):
        """Discover all subscriptions in tenant"""

        def _sync_discover():
            client = SubscriptionClient(self.credential)
            subs = []
            for sub in client.subscriptions.list():
                subs.append(
                    {
                        "subscription_id": sub.subscription_id,
                        "name": sub.display_name,
                        "state": sub.state,
                    }
                )
            return subs

        try:
            subs = await asyncio.to_thread(_sync_discover)
            self.inventory.subscriptions = subs
            self.inventory.subscription_count = len(subs)
        except Exception as e:
            self.inventory.errors.append(f"Failed to discover subscriptions: {e}")

    # ========== Entra ID Collection (4 parallel threads) ==========

    async def collect_users(self):
        """Collect Entra ID users using AADGraphService"""
        try:
            print("   [Thread 1] Collecting users...")
            users = await self.aad_service.get_users()
            self.inventory.users_count = len(users)
            print(str(f"   [Thread 1] ✓ Users: {len(users)}"))
        except Exception as e:
            error_msg = f"Failed to collect users: {e}"
            self.inventory.errors.append(error_msg)
            print(str(f"   [Thread 1] ⚠️  {error_msg}"))

    async def collect_groups(self):
        """Collect Entra ID groups using AADGraphService"""
        try:
            print("   [Thread 2] Collecting groups...")
            groups = await self.aad_service.get_groups()
            self.inventory.groups_count = len(groups)
            print(str(f"   [Thread 2] ✓ Groups: {len(groups)}"))
        except Exception as e:
            error_msg = f"Failed to collect groups: {e}"
            self.inventory.errors.append(error_msg)
            print(str(f"   [Thread 2] ⚠️  {error_msg}"))

    async def collect_service_principals(self):
        """Collect service principals using AADGraphService"""
        try:
            print("   [Thread 3] Collecting service principals...")
            sps = await self.aad_service.get_service_principals()
            self.inventory.service_principals_count = len(sps)
            print(str(f"   [Thread 3] ✓ Service Principals: {len(sps)}"))
        except Exception as e:
            error_msg = f"Failed to collect service principals: {e}"
            self.inventory.errors.append(error_msg)
            print(str(f"   [Thread 3] ⚠️  {error_msg}"))

    async def collect_managed_identities(self):
        """Collect managed identities (user-assigned MIs from Azure resources)"""
        try:
            print("   [Thread 4] Collecting managed identities...")
            # Count managed identities from resources (more reliable than Graph API filter)
            # We'll count resources of type Microsoft.ManagedIdentity/userAssignedIdentities
            # This gets populated during resource collection, so for now just mark as pending
            # The actual count will come from resources_by_type
            print("   [Thread 4] ⚠️  Managed identities counted from resource discovery")
        except Exception as e:
            error_msg = f"Failed to collect managed identities: {e}"
            self.inventory.errors.append(error_msg)
            print(str(f"   [Thread 4] ⚠️  {error_msg}"))

    # ========== Per-Subscription Collection (3 threads per sub) ==========

    async def collect_resources_in_subscription(
        self, subscription_id: str, sub_name: str
    ):
        """Collect all resources in a subscription"""

        def _sync_collect():
            client = ResourceManagementClient(self.credential, subscription_id)
            resources = list(client.resources.list())

            # Aggregate counts
            results = {
                "total": 0,
                "by_type": defaultdict(int),
                "by_region": defaultdict(int),
            }

            for resource in resources:
                results["total"] += 1
                results["by_type"][resource.type] += 1
                results["by_region"][resource.location or "global"] += 1

            return results

        try:
            print(
                str(f"   [Thread] Collecting resources in subscription: {sub_name}...")
            )
            results = await asyncio.to_thread(_sync_collect)

            self.inventory.total_resources += results["total"]
            for rtype, count in results["by_type"].items():
                self.inventory.resources_by_type[rtype] += count
            for region, count in results["by_region"].items():
                self.inventory.resources_by_region[region] += count
            self.inventory.resources_by_subscription[sub_name] = results["total"]

            print(f"   [Thread] ✓ {sub_name}: {results['total']} resources")
        except Exception as e:
            error_msg = f"Failed to collect resources in {sub_name}: {e}"
            self.inventory.errors.append(error_msg)
            print(str(f"   [Thread] ⚠️  {error_msg}"))

    async def collect_role_assignments_in_subscription(
        self, subscription_id: str, sub_name: str
    ):
        """Collect role assignments in a subscription"""

        def _sync_collect():
            scope = f"/subscriptions/{subscription_id}"
            client = AuthorizationManagementClient(self.credential, subscription_id)
            assignments = list(client.role_assignments.list_for_scope(scope))

            # Count by scope type
            by_scope = defaultdict(int)
            for assignment in assignments:
                scope_type = self._get_scope_type(assignment.scope)
                by_scope[scope_type] += 1

            return len(assignments), by_scope

        try:
            print(str(f"   [Thread] Collecting role assignments in: {sub_name}..."))
            count, by_scope = await asyncio.to_thread(_sync_collect)

            self.inventory.total_role_assignments += count
            for scope_type, scope_count in by_scope.items():
                self.inventory.role_assignments_by_scope[scope_type] += scope_count

            print(str(f"   [Thread] ✓ {sub_name}: {count} role assignments"))
        except Exception as e:
            error_msg = f"Failed to collect role assignments in {sub_name}: {e}"
            self.inventory.errors.append(error_msg)
            print(str(f"   [Thread] ⚠️  {error_msg}"))

    async def collect_cost_data_for_subscription(
        self, subscription_id: str, sub_name: str
    ):
        """Collect cost data for a subscription (optional)"""

        def _sync_collect():
            # Cost Management API requires specific setup
            # For MVP, we'll mark as not available
            # Real implementation would use CostManagementClient
            return None

        try:
            print(str(f"   [Thread] Collecting cost data for: {sub_name}..."))
            await asyncio.to_thread(_sync_collect)

            # Mark as unavailable for now
            if not self.inventory.cost_available:
                self.inventory.cost_error = "Cost Management API not implemented in MVP"

            print(str(f"   [Thread] ⚠️  Cost API not implemented yet for {sub_name}"))

        except Exception as e:
            error_msg = f"Failed to collect cost data in {sub_name}: {e}"
            self.inventory.errors.append(error_msg)
            print(str(f"   [Thread] ⚠️  {error_msg}"))

    # ========== Helper Methods ==========

    def _get_scope_type(self, scope: str) -> str:
        """Determine scope type from scope string"""
        if not scope:
            return "Unknown"
        scope_lower = scope.lower()
        if "/managementgroups/" in scope_lower:
            return "Management Group"
        elif "/subscriptions/" in scope_lower and "/resourcegroups/" not in scope_lower:
            return "Subscription"
        elif "/resourcegroups/" in scope_lower and scope_lower.count("/") == 4:
            return "Resource Group"
        elif "/providers/" in scope_lower:
            return "Resource"
        else:
            return "Other"

    def generate_markdown_report(self) -> str:
        """Generate markdown report"""
        report = []

        report.append("# 🏴‍☠️ Azure Tenant Inventory Report")
        report.append("")
        report.append(f"**Tenant ID**: `{self.inventory.tenant_id}`")
        report.append(f"**Generated**: {self.inventory.generated_at} UTC")
        report.append("")

        # Summary Table
        report.append("## 📊 Summary")
        report.append("")
        report.append("| Category | Count/Value |")
        report.append("|----------|-------------|")
        report.append(f"| **Subscriptions** | {self.inventory.subscription_count} |")
        report.append(f"| **Entra ID Users** | {self.inventory.users_count:,} |")
        report.append(
            f"| **Service Principals** | {self.inventory.service_principals_count:,} |"
        )
        report.append(
            f"| **Managed Identities** | {self.inventory.managed_identities_count:,} |"
        )
        report.append(f"| **Groups** | {self.inventory.groups_count:,} |")
        report.append(f"| **Total Resources** | {self.inventory.total_resources:,} |")
        report.append(
            f"| **Unique Resource Types** | {len(self.inventory.resources_by_type)} |"
        )
        report.append(
            f"| **Azure Regions Used** | {len(self.inventory.resources_by_region)} |"
        )
        report.append(
            f"| **Role Assignments** | {self.inventory.total_role_assignments:,} |"
        )

        if self.inventory.cost_available:
            report.append(
                f"| **Estimated Monthly Cost** | **${self.inventory.estimated_monthly_cost:,.2f}** |"
            )
        else:
            report.append(
                f"| **Estimated Monthly Cost** | N/A ({self.inventory.cost_error}) |"
            )
        report.append("")

        # Subscriptions
        report.append("## 📦 Subscriptions")
        report.append("")
        report.append("| Subscription Name | Subscription ID | State | Resources |")
        report.append("|-------------------|-----------------|-------|-----------|")
        for sub in self.inventory.subscriptions:
            sub_name = sub.get("name", "Unknown")
            resource_count = self.inventory.resources_by_subscription.get(sub_name, 0)
            report.append(
                f"| {sub_name} | `{sub['subscription_id']}` | {sub.get('state', 'Unknown')} | {resource_count:,} |"
            )
        report.append("")

        # Resources by Type (Top 20)
        report.append("## 🔧 Resources by Type (Top 20)")
        report.append("")
        report.append("| Resource Type | Count |")
        report.append("|---------------|-------|")
        sorted_types = sorted(
            self.inventory.resources_by_type.items(), key=lambda x: x[1], reverse=True
        )[:20]
        for resource_type, count in sorted_types:
            report.append(f"| `{resource_type}` | {count:,} |")
        report.append("")

        # Resources by Region
        report.append("## 🌍 Resources by Region")
        report.append("")
        report.append("| Region | Count |")
        report.append("|--------|-------|")
        sorted_regions = sorted(
            self.inventory.resources_by_region.items(), key=lambda x: x[1], reverse=True
        )
        for region, count in sorted_regions:
            report.append(f"| {region} | {count:,} |")
        report.append("")

        # Role Assignments by Scope
        report.append("## 🔐 Role Assignments by Scope")
        report.append("")
        report.append("| Scope Type | Count |")
        report.append("|------------|-------|")
        for scope_type, count in sorted(
            self.inventory.role_assignments_by_scope.items()
        ):
            report.append(f"| {scope_type} | {count:,} |")
        report.append("")

        # Errors
        if self.inventory.errors:
            report.append("## ⚠️  Errors Encountered")
            report.append("")
            for error in self.inventory.errors:
                report.append(f"- {error}")
            report.append("")

        return "\n".join(report)


async def main():
    """Main entry point"""
    tenant_id = "3cd87a41-1f61-4aef-a212-cefdecd9a2d1"

    print("=" * 80)
    print("🏴‍☠️  AZURE TENANT REPORT GENERATOR")
    print("=" * 80)
    print()

    async with ParallelTenantReporter(tenant_id) as reporter:
        # Collect all data in parallel
        inventory = await reporter.collect_all_data()

        # Generate report
        print("\n" + "=" * 80)
        print("📄 GENERATING REPORT")
        print("=" * 80 + "\n")

        markdown_report = reporter.generate_markdown_report()
        print(markdown_report)

        # Save to file
        report_filename = f"tenant_report_{tenant_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_filename, "w") as f:
            f.write(markdown_report)

        print("\n" + "=" * 80)
        print(str(f"✅ Report saved to: {report_filename}"))
        print("=" * 80)

        # Also save JSON
        json_filename = report_filename.replace(".md", ".json")
        with open(json_filename, "w") as f:
            json.dump(
                {
                    "tenant_id": inventory.tenant_id,
                    "generated_at": inventory.generated_at,
                    "subscription_count": inventory.subscription_count,
                    "users_count": inventory.users_count,
                    "groups_count": inventory.groups_count,
                    "service_principals_count": inventory.service_principals_count,
                    "managed_identities_count": inventory.managed_identities_count,
                    "total_resources": inventory.total_resources,
                    "resources_by_type": dict(inventory.resources_by_type),
                    "resources_by_region": dict(inventory.resources_by_region),
                    "resources_by_subscription": dict(
                        inventory.resources_by_subscription
                    ),
                    "total_role_assignments": inventory.total_role_assignments,
                    "role_assignments_by_scope": dict(
                        inventory.role_assignments_by_scope
                    ),
                    "cost_available": inventory.cost_available,
                    "estimated_monthly_cost": inventory.estimated_monthly_cost,
                    "errors": inventory.errors,
                },
                f,
                indent=2,
            )
        print(str(f"📊 JSON data saved to: {json_filename}\n"))


if __name__ == "__main__":
    asyncio.run(main())

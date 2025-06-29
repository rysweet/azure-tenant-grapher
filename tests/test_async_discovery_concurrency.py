"""
Tests for concurrency-limited resource discovery across subscriptions.

These tests assert that `AzureDiscoveryService.discover_resources_across_subscriptions`
honours the configured concurrency limit when launching tasks.
"""

import asyncio
from typing import List
from unittest.mock import Mock, patch

import pytest

from src.services.azure_discovery_service import AzureDiscoveryService


@pytest.mark.asyncio
async def test_discover_resources_across_subscriptions_respects_concurrency_limit() -> (
    None
):
    """Ensure concurrency limit is not exceeded during resource discovery."""
    mock_config = Mock()
    mock_config.tenant_id = "tenant"

    # Create service with minimal dependencies
    service = AzureDiscoveryService(mock_config, credential=Mock())

    concurrency_limit = 3
    subscription_ids = [f"sub-{i}" for i in range(10)]

    max_running_tasks = 0
    current_running_tasks = 0

    async def fake_discover_resources_in_subscription(sub_id: str) -> List[dict]:
        """Fake implementation that records concurrency."""
        nonlocal max_running_tasks, current_running_tasks
        current_running_tasks += 1
        max_running_tasks = max(max_running_tasks, current_running_tasks)
        # Simulate I/O
        await asyncio.sleep(0.01)
        current_running_tasks -= 1
        return [{"id": f"{sub_id}-resource"}]

    # Monkey-patch the instance method
    with patch.object(
        service,
        "discover_resources_in_subscription",
        side_effect=fake_discover_resources_in_subscription,
    ):
        results = await service.discover_resources_across_subscriptions(
            subscription_ids, concurrency=concurrency_limit
        )

    assert max_running_tasks <= concurrency_limit
    assert len(results) == len(subscription_ids)

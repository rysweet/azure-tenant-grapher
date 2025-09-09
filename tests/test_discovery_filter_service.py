"""Tests for DiscoveryFilterService"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Import directly to avoid azure dependencies
try:
    from src.models.filter_config import FilterConfig
    from src.services.discovery_filter_service import DiscoveryFilterService
except ImportError:
    # Fallback to direct import if services.__init__ has issues
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "discovery_filter_service",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src/services/discovery_filter_service.py",
        ),
    )
    discovery_filter_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(discovery_filter_module)
    DiscoveryFilterService = discovery_filter_module.DiscoveryFilterService
    from src.models.filter_config import FilterConfig


class TestDiscoveryFilterService:
    """Test cases for the DiscoveryFilterService."""

    def test_no_filters(self):
        """Test service with no filters configured."""
        service = DiscoveryFilterService()

        # Should pass everything through
        subs = [{"id": "sub1"}, {"id": "sub2"}]
        assert service.filter_subscriptions(subs) == subs

        resources = [{"id": "r1", "resource_group": "rg1"}]
        assert service.filter_resources(resources) == resources
        assert service.should_include_resource(resources[0]) is True

    def test_subscription_filter(self):
        """Test subscription filtering."""
        sub1 = "11111111-1111-1111-1111-111111111111"
        sub2 = "22222222-2222-2222-2222-222222222222"
        sub3 = "33333333-3333-3333-3333-333333333333"
        sub4 = "44444444-4444-4444-4444-444444444444"
        
        config = FilterConfig(subscription_ids=[sub1, sub3])
        service = DiscoveryFilterService(config)

        subs = [{"id": sub1}, {"id": sub2}, {"id": sub3}, {"id": sub4}]

        filtered = service.filter_subscriptions(subs)
        assert len(filtered) == 2
        assert filtered[0]["id"] == sub1
        assert filtered[1]["id"] == sub3

    def test_resource_group_filter_exact_match(self):
        """Test resource group filtering with exact match."""
        config = FilterConfig(resource_group_names=["test-rg", "TEST-RG", "Test-RG"])
        service = DiscoveryFilterService(config)

        # Test exact match (case-sensitive)
        assert service.should_include_resource({"resource_group": "test-rg"}) is True
        assert service.should_include_resource({"resource_group": "TEST-RG"}) is True
        assert service.should_include_resource({"resource_group": "Test-RG"}) is True
        assert service.should_include_resource({"resource_group": "other-rg"}) is False

    def test_resource_group_filter_wildcard(self):
        """Test resource group filtering with multiple resource groups."""
        config = FilterConfig(resource_group_names=["test-dev", "test-prod", "TEST-QA"])
        service = DiscoveryFilterService(config)

        # Test exact matching from list
        assert service.should_include_resource({"resource_group": "test-dev"}) is True
        assert service.should_include_resource({"resource_group": "test-prod"}) is True
        assert service.should_include_resource({"resource_group": "TEST-QA"}) is True
        assert service.should_include_resource({"resource_group": "prod-test"}) is False
        assert service.should_include_resource({"resource_group": "testing"}) is False

        resources = [
            {"id": "r1", "resource_group": "test-dev"},
            {"id": "r2", "resource_group": "test-prod"},
            {"id": "r3", "resource_group": "prod-test"},
            {"id": "r4", "resource_group": "other"},
        ]

        filtered = service.filter_resources(resources)
        assert len(filtered) == 2
        assert filtered[0]["id"] == "r1"
        assert filtered[1]["id"] == "r2"

    def test_combined_filters(self):
        """Test combined subscription and resource group filters."""
        sub1 = "11111111-1111-1111-1111-111111111111"
        sub2 = "22222222-2222-2222-2222-222222222222"
        config = FilterConfig(
            subscription_ids=[sub1, sub2], resource_group_names=["prod-web", "prod-api"]
        )
        service = DiscoveryFilterService(config)

        assert service.is_subscription_included(sub1) is True
        assert service.is_subscription_included(sub2) is True
        assert service.is_subscription_included("33333333-3333-3333-3333-333333333333") is False
        assert service.should_include_resource({"resource_group": "prod-web"}) is True
        assert service.should_include_resource({"resource_group": "dev-web"}) is False

    def test_empty_resource_group(self):
        """Test handling of resources without resource group."""
        config = FilterConfig(resource_group_names=["test-rg"])
        service = DiscoveryFilterService(config)

        # Resource without resource_group field should be excluded
        assert service.should_include_resource({"id": "r1"}) is False
        assert (
            service.should_include_resource({"id": "r2", "resource_group": ""}) is False
        )
        assert (
            service.should_include_resource({"id": "r3", "resource_group": None})
            is False
        )

    def test_filter_summary(self):
        """Test filter summary generation."""
        # No filters
        service = DiscoveryFilterService()
        assert (
            service.get_filter_summary()
            == "No filters configured - discovering all resources"
        )

        # Subscription filter only
        sub1 = "11111111-1111-1111-1111-111111111111"
        config = FilterConfig(subscription_ids=[sub1])
        service = DiscoveryFilterService(config)
        summary = service.get_filter_summary()
        assert "11111111" in summary

        # Resource group filter only
        config = FilterConfig(resource_group_names=["test-dev", "test-prod"])
        service = DiscoveryFilterService(config)
        summary = service.get_filter_summary()
        assert "Resource groups:" in summary
        assert "test-dev" in summary

        # Both filters
        sub1 = "11111111-1111-1111-1111-111111111111"
        sub2 = "22222222-2222-2222-2222-222222222222"
        config = FilterConfig(
            subscription_ids=[sub1, sub2], resource_group_names=["prod-web", "prod-api"]
        )
        service = DiscoveryFilterService(config)
        summary = service.get_filter_summary()
        assert "11111111" in summary
        assert "22222222" in summary
        assert "prod-web" in summary

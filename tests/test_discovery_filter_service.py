"""Tests for DiscoveryFilterService"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

# Import directly to avoid azure dependencies
try:
    from src.config_manager import FilterConfig
    from src.services.discovery_filter_service import DiscoveryFilterService
except ImportError:
    # Fallback to direct import if services.__init__ has issues
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "discovery_filter_service", 
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                     "src/services/discovery_filter_service.py")
    )
    discovery_filter_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(discovery_filter_module)
    DiscoveryFilterService = discovery_filter_module.DiscoveryFilterService
    from src.config_manager import FilterConfig


class TestDiscoveryFilterService:
    """Test cases for the DiscoveryFilterService."""

    def test_no_filters(self):
        """Test service with no filters configured."""
        service = DiscoveryFilterService()
        
        # Should pass everything through
        subs = [{'id': 'sub1'}, {'id': 'sub2'}]
        assert service.filter_subscriptions(subs) == subs
        
        resources = [{'id': 'r1', 'resource_group': 'rg1'}]
        assert service.filter_resources(resources) == resources
        assert service.should_include_resource(resources[0]) is True

    def test_subscription_filter(self):
        """Test subscription filtering."""
        config = FilterConfig(subscription_ids=['sub1', 'sub3'])
        service = DiscoveryFilterService(config)
        
        subs = [
            {'id': 'sub1'},
            {'id': 'sub2'},
            {'id': 'sub3'},
            {'id': 'sub4'}
        ]
        
        filtered = service.filter_subscriptions(subs)
        assert len(filtered) == 2
        assert filtered[0]['id'] == 'sub1'
        assert filtered[1]['id'] == 'sub3'

    def test_resource_group_filter_exact_match(self):
        """Test resource group filtering with exact match."""
        config = FilterConfig(resource_group_filter='test-rg')
        service = DiscoveryFilterService(config)
        
        # Test exact match (case-insensitive)
        assert service.should_include_resource({'resource_group': 'test-rg'}) is True
        assert service.should_include_resource({'resource_group': 'TEST-RG'}) is True
        assert service.should_include_resource({'resource_group': 'Test-RG'}) is True
        assert service.should_include_resource({'resource_group': 'other-rg'}) is False

    def test_resource_group_filter_wildcard(self):
        """Test resource group filtering with wildcards."""
        config = FilterConfig(resource_group_filter='test-*')
        service = DiscoveryFilterService(config)
        
        # Test wildcard matching
        assert service.should_include_resource({'resource_group': 'test-dev'}) is True
        assert service.should_include_resource({'resource_group': 'test-prod'}) is True
        assert service.should_include_resource({'resource_group': 'TEST-QA'}) is True
        assert service.should_include_resource({'resource_group': 'prod-test'}) is False
        assert service.should_include_resource({'resource_group': 'testing'}) is False
        
        resources = [
            {'id': 'r1', 'resource_group': 'test-dev'},
            {'id': 'r2', 'resource_group': 'test-prod'},
            {'id': 'r3', 'resource_group': 'prod-test'},
            {'id': 'r4', 'resource_group': 'other'},
        ]
        
        filtered = service.filter_resources(resources)
        assert len(filtered) == 2
        assert filtered[0]['id'] == 'r1'
        assert filtered[1]['id'] == 'r2'

    def test_combined_filters(self):
        """Test combined subscription and resource group filters."""
        config = FilterConfig(
            subscription_ids=['sub1', 'sub2'],
            resource_group_filter='prod-*'
        )
        service = DiscoveryFilterService(config)
        
        summary = service.get_filter_summary()
        assert 'sub1' in summary
        assert 'sub2' in summary
        assert 'prod-*' in summary

    def test_empty_resource_group(self):
        """Test handling of resources without resource group."""
        config = FilterConfig(resource_group_filter='test-rg')
        service = DiscoveryFilterService(config)
        
        # Resource without resource_group field should be excluded
        assert service.should_include_resource({'id': 'r1'}) is False
        assert service.should_include_resource({'id': 'r2', 'resource_group': ''}) is False
        assert service.should_include_resource({'id': 'r3', 'resource_group': None}) is False

    def test_filter_summary(self):
        """Test filter summary generation."""
        # No filters
        service = DiscoveryFilterService()
        assert service.get_filter_summary() == "No filters configured - discovering all resources"
        
        # Subscription filter only
        config = FilterConfig(subscription_ids=['sub1'])
        service = DiscoveryFilterService(config)
        summary = service.get_filter_summary()
        assert "Subscriptions: sub1" in summary
        
        # Resource group filter only
        config = FilterConfig(resource_group_filter='test-*')
        service = DiscoveryFilterService(config)
        summary = service.get_filter_summary()
        assert "Resource group filter: test-*" in summary
        
        # Both filters
        config = FilterConfig(
            subscription_ids=['sub1', 'sub2'],
            resource_group_filter='prod-*'
        )
        service = DiscoveryFilterService(config)
        summary = service.get_filter_summary()
        assert "sub1, sub2" in summary
        assert "prod-*" in summary
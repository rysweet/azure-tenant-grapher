"""Tests for ResourceExistenceValidator.

Tests the resource existence validation for smart import blocks (Issue #422).
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import (
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)

from src.iac.validators.resource_existence_validator import (
    ResourceExistenceResult,
    ResourceExistenceValidator,
)


class TestResourceExistenceValidator:
    """Test cases for ResourceExistenceValidator."""

    @pytest.fixture
    def mock_credential(self):
        """Create a mock Azure credential."""
        return MagicMock()

    @pytest.fixture
    def validator(self, mock_credential):
        """Create a ResourceExistenceValidator instance for testing."""
        return ResourceExistenceValidator(
            subscription_id="test-sub-id",
            credential=mock_credential,
            max_retries=3,
            cache_ttl=300,
        )

    def test_initialization(self, validator):
        """Test that validator initializes correctly."""
        assert validator.subscription_id == "test-sub-id"
        assert validator.max_retries == 3
        assert validator.cache_ttl == 300
        assert len(validator._cache) == 0

    def test_check_resource_exists_success(self, validator):
        """Test checking a resource that exists."""
        resource_id = (
            "/subscriptions/test-sub/resourceGroups/test-rg/providers/"
            "Microsoft.Storage/storageAccounts/teststorage"
        )

        # Mock the resource client
        mock_response = MagicMock()
        mock_response.id = resource_id
        mock_client = MagicMock()
        mock_client.resources.get_by_id.return_value = mock_response

        # Patch the private attribute directly
        validator._resource_client = mock_client

        result = validator.check_resource_exists(resource_id)

        assert isinstance(result, ResourceExistenceResult)
        assert result.resource_id == resource_id
        assert result.exists is True
        assert result.error is None
        assert result.cached is False

        # Verify API was called
        mock_client.resources.get_by_id.assert_called_once()

    def test_check_resource_not_found(self, validator):
        """Test checking a resource that doesn't exist (404)."""
        resource_id = "/subscriptions/test-sub/resourceGroups/nonexistent-rg"

        mock_client = MagicMock()
        mock_client.resources.get_by_id.side_effect = ResourceNotFoundError()
        validator._resource_client = mock_client

        result = validator.check_resource_exists(resource_id)

        assert result.resource_id == resource_id
        assert result.exists is False
        assert result.error is None

    def test_check_resource_http_404(self, validator):
        """Test checking a resource that returns HTTP 404."""
        resource_id = "/subscriptions/test-sub/resourceGroups/test-rg"

        mock_client = MagicMock()
        error = HttpResponseError()
        error.status_code = 404
        mock_client.resources.get_by_id.side_effect = error
        validator._resource_client = mock_client

        result = validator.check_resource_exists(resource_id)

        assert result.exists is False
        assert result.error is None

    def test_check_resource_transient_error_then_success(self, validator):
        """Test retry logic with transient error then success."""
        resource_id = "/subscriptions/test-sub/resourceGroups/test-rg"

        mock_client = MagicMock()
        # First call raises transient error, second succeeds
        mock_response = MagicMock()
        mock_client.resources.get_by_id.side_effect = [
            ServiceRequestError("Transient error"),
            mock_response,
        ]
        validator._resource_client = mock_client

        with patch("time.sleep"):  # Speed up test
            result = validator.check_resource_exists(resource_id)

        assert result.exists is True
        assert result.error is None
        # Should have retried once
        assert mock_client.resources.get_by_id.call_count == 2

    def test_check_resource_max_retries_exceeded(self, validator):
        """Test that max retries are respected."""
        resource_id = "/subscriptions/test-sub/resourceGroups/test-rg"

        mock_client = MagicMock()
        # Always raise transient error
        mock_client.resources.get_by_id.side_effect = ServiceRequestError(
            "Persistent error"
        )
        validator._resource_client = mock_client

        with patch("time.sleep"):  # Speed up test
            result = validator.check_resource_exists(resource_id)

        assert result.exists is False
        assert result.error is not None
        assert "Max retries exceeded" in result.error
        # Should have tried max_retries times
        assert mock_client.resources.get_by_id.call_count == 3

    def test_check_resource_caching(self, validator):
        """Test that results are cached."""
        resource_id = "/subscriptions/test-sub/resourceGroups/test-rg"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_client.resources.get_by_id.return_value = mock_response
        validator._resource_client = mock_client

        # First call
        result1 = validator.check_resource_exists(resource_id)
        assert result1.exists is True
        assert result1.cached is False

        # Second call should use cache
        result2 = validator.check_resource_exists(resource_id)
        assert result2.exists is True
        assert result2.cached is True

        # API should only be called once
        mock_client.resources.get_by_id.assert_called_once()

    def test_cache_expiration(self, validator):
        """Test that cache expires after TTL."""
        resource_id = "/subscriptions/test-sub/resourceGroups/test-rg"
        validator.cache_ttl = 1  # 1 second TTL

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_client.resources.get_by_id.return_value = mock_response
        validator._resource_client = mock_client

        # First call
        result1 = validator.check_resource_exists(resource_id)
        assert result1.cached is False

        # Wait for cache to expire
        time.sleep(1.1)

        # Second call should hit API again
        result2 = validator.check_resource_exists(resource_id)
        assert result2.cached is False

        # API should be called twice
        assert mock_client.resources.get_by_id.call_count == 2

    def test_clear_cache(self, validator):
        """Test clearing the cache."""
        resource_id = "/subscriptions/test-sub/resourceGroups/test-rg"

        # Add to cache
        validator._cache[resource_id] = (True, time.time())
        assert len(validator._cache) == 1

        # Clear cache
        validator.clear_cache()
        assert len(validator._cache) == 0

    def test_get_cache_stats(self, validator):
        """Test cache statistics."""
        # Add some valid cache entries
        validator._cache["/resource1"] = (True, time.time())
        validator._cache["/resource2"] = (False, time.time())

        # Add expired entry
        validator._cache["/resource3"] = (True, time.time() - 400)

        stats = validator.get_cache_stats()

        assert stats["total"] == 3
        assert stats["valid"] == 2
        assert stats["expired"] == 1

    def test_batch_check_resources(self, validator):
        """Test batch checking multiple resources."""
        resource_ids = [
            "/subscriptions/test-sub/resourceGroups/rg1",
            "/subscriptions/test-sub/resourceGroups/rg2",
            "/subscriptions/test-sub/resourceGroups/rg3",
        ]

        mock_client = MagicMock()
        # First exists, second doesn't, third exists
        mock_response = MagicMock()
        mock_client.resources.get_by_id.side_effect = [
            mock_response,
            ResourceNotFoundError(),
            mock_response,
        ]
        validator._resource_client = mock_client

        results = validator.batch_check_resources(resource_ids)

        assert len(results) == 3
        assert results[resource_ids[0]].exists is True
        assert results[resource_ids[1]].exists is False
        assert results[resource_ids[2]].exists is True

    def test_get_api_version_resource_group(self, validator):
        """Test API version selection for resource groups."""
        resource_id = "/subscriptions/test-sub/resourceGroups/test-rg"
        api_version = validator._get_api_version(resource_id)
        assert api_version == "2021-04-01"

    def test_get_api_version_storage_account(self, validator):
        """Test API version selection for storage accounts."""
        resource_id = (
            "/subscriptions/test-sub/resourceGroups/test-rg/providers/"
            "Microsoft.Storage/storageAccounts/teststorage"
        )
        api_version = validator._get_api_version(resource_id)
        assert api_version == "2023-01-01"

    def test_get_api_version_virtual_machine(self, validator):
        """Test API version selection for virtual machines."""
        resource_id = (
            "/subscriptions/test-sub/resourceGroups/test-rg/providers/"
            "Microsoft.Compute/virtualMachines/testvm"
        )
        api_version = validator._get_api_version(resource_id)
        assert api_version == "2023-03-01"

    def test_get_api_version_unknown_type(self, validator):
        """Test API version fallback for unknown resource types."""
        resource_id = (
            "/subscriptions/test-sub/resourceGroups/test-rg/providers/"
            "Microsoft.Custom/unknownType/resource"
        )
        api_version = validator._get_api_version(resource_id)
        assert api_version == "2021-04-01"  # Fallback

    def test_unexpected_error_handling(self, validator):
        """Test handling of unexpected errors."""
        resource_id = "/subscriptions/test-sub/resourceGroups/test-rg"

        mock_client = MagicMock()
        # Raise unexpected exception
        mock_client.resources.get_by_id.side_effect = ValueError("Unexpected error")
        validator._resource_client = mock_client

        result = validator.check_resource_exists(resource_id)

        assert result.exists is False
        assert result.error is not None
        assert "Unexpected error" in result.error

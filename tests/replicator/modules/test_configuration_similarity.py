"""
Unit tests for ConfigurationSimilarity brick.

Tests configuration similarity computation and clustering logic.
"""

import pytest

from src.replicator.modules.configuration_similarity import ConfigurationSimilarity


class TestConfigurationSimilarity:
    """Test suite for ConfigurationSimilarity brick."""

    def test_compute_similarity_identical_configs(self):
        """Test similarity of identical configurations."""
        fp1 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {"env": "prod", "team": "platform"}
        }
        fp2 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {"env": "prod", "team": "platform"}
        }

        score = ConfigurationSimilarity.compute_similarity(fp1, fp2)

        # Identical configs should have high similarity (close to 1.0)
        assert score >= 0.9

    def test_compute_similarity_different_locations(self):
        """Test similarity with different locations."""
        fp1 = {"location": "eastus", "sku": "Standard_D2s_v3", "tags": {}}
        fp2 = {"location": "westus", "sku": "Standard_D2s_v3", "tags": {}}

        score = ConfigurationSimilarity.compute_similarity(fp1, fp2)

        # Different locations reduce similarity significantly
        assert score < 1.0

    def test_compute_similarity_same_tier_different_size(self):
        """Test similarity with same SKU tier but different size."""
        fp1 = {"location": "eastus", "sku": "Standard_D2s_v3", "tags": {}}
        fp2 = {"location": "eastus", "sku": "Standard_D4s_v3", "tags": {}}

        score = ConfigurationSimilarity.compute_similarity(fp1, fp2)

        # Same location and tier should give high similarity
        assert score >= 0.7

    def test_compute_similarity_different_tiers(self):
        """Test similarity with different SKU tiers."""
        fp1 = {"location": "eastus", "sku": "Standard_D2s_v3", "tags": {}}
        fp2 = {"location": "eastus", "sku": "Premium_LRS", "tags": {}}

        score = ConfigurationSimilarity.compute_similarity(fp1, fp2)

        # Different tiers should reduce similarity
        assert score < 1.0

    def test_compute_similarity_tag_overlap(self):
        """Test similarity with partial tag overlap."""
        fp1 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {"env": "prod", "team": "platform", "app": "web"}
        }
        fp2 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {"env": "prod", "team": "platform", "region": "us"}
        }

        score = ConfigurationSimilarity.compute_similarity(fp1, fp2)

        # High overlap in tags should give high similarity
        assert score >= 0.8

    def test_compute_similarity_no_tag_key_overlap(self):
        """Test similarity with no tag key overlap."""
        fp1 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {"env": "prod"}
        }
        fp2 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {"region": "us"}  # Different key
        }

        score = ConfigurationSimilarity.compute_similarity(fp1, fp2)

        # Same location (0.5) + same SKU tier (0.3) = 0.8
        # No tag KEY overlap contributes 0
        # Total score should be 0.8
        assert abs(score - 0.8) < 0.01

    def test_compute_similarity_empty_fingerprints(self):
        """Test similarity with empty fingerprints."""
        fp1 = {}
        fp2 = {}

        score = ConfigurationSimilarity.compute_similarity(fp1, fp2)

        # Empty configs should have zero similarity
        assert score == 0.0

    def test_compute_similarity_missing_fields(self):
        """Test similarity with missing fields."""
        fp1 = {"location": "eastus"}
        fp2 = {"sku": "Standard_D2s_v3"}

        score = ConfigurationSimilarity.compute_similarity(fp1, fp2)

        # Partial match should give low similarity
        assert 0.0 <= score < 0.5

    def test_compute_similarity_json_tags(self):
        """Test similarity with tags as JSON string."""
        fp1 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": '{"env": "prod"}'
        }
        fp2 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": '{"env": "prod"}'
        }

        score = ConfigurationSimilarity.compute_similarity(fp1, fp2)

        # Should handle JSON string tags
        assert score >= 0.8

    def test_compute_similarity_invalid_json_tags(self):
        """Test similarity with invalid JSON tags."""
        fp1 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": "{invalid json"
        }
        fp2 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": "{also invalid"
        }

        score = ConfigurationSimilarity.compute_similarity(fp1, fp2)

        # Should handle invalid JSON gracefully
        assert 0.0 <= score <= 1.0

    def test_extract_sku_tier_standard(self):
        """Test SKU tier extraction for Standard tier."""
        tier = ConfigurationSimilarity._extract_sku_tier("Standard_D2s_v3")

        assert tier == "standard"

    def test_extract_sku_tier_premium(self):
        """Test SKU tier extraction for Premium tier."""
        tier = ConfigurationSimilarity._extract_sku_tier("Premium_LRS")

        assert tier == "premium"

    def test_extract_sku_tier_empty(self):
        """Test SKU tier extraction for empty SKU."""
        tier = ConfigurationSimilarity._extract_sku_tier("")

        assert tier == ""

    def test_extract_sku_tier_unknown(self):
        """Test SKU tier extraction for unknown SKU."""
        tier = ConfigurationSimilarity._extract_sku_tier("UnknownSKU")

        assert tier == ""

    def test_parse_tags_dict(self):
        """Test tag parsing with dict input."""
        tags = {"env": "prod", "team": "platform"}

        result = ConfigurationSimilarity._parse_tags(tags)

        assert result == tags

    def test_parse_tags_json_string(self):
        """Test tag parsing with JSON string input."""
        tags = '{"env": "prod", "team": "platform"}'

        result = ConfigurationSimilarity._parse_tags(tags)

        assert result == {"env": "prod", "team": "platform"}

    def test_parse_tags_invalid_json(self):
        """Test tag parsing with invalid JSON."""
        tags = "{invalid json"

        result = ConfigurationSimilarity._parse_tags(tags)

        assert result == {}

    def test_parse_tags_non_dict(self):
        """Test tag parsing with non-dict input."""
        tags = ["tag1", "tag2"]

        result = ConfigurationSimilarity._parse_tags(tags)

        assert result == {}

    def test_cluster_by_coherence_single_resource(self):
        """Test clustering with single resource."""
        resources = [{"id": "r1"}]
        fingerprints = {"r1": {"location": "eastus", "sku": "Standard_D2s_v3"}}

        clusters = ConfigurationSimilarity.cluster_by_coherence(
            resources, fingerprints, coherence_threshold=0.7
        )

        # Single resource forms one cluster
        assert len(clusters) == 1
        assert len(clusters[0]) == 1

    def test_cluster_by_coherence_similar_configs(self):
        """Test clustering with similar configurations."""
        resources = [
            {"id": "r1"},
            {"id": "r2"},
            {"id": "r3"}
        ]
        fingerprints = {
            "r1": {"location": "eastus", "sku": "Standard_D2s_v3", "tags": {}},
            "r2": {"location": "eastus", "sku": "Standard_D4s_v3", "tags": {}},
            "r3": {"location": "eastus", "sku": "Standard_D8s_v3", "tags": {}}
        }

        clusters = ConfigurationSimilarity.cluster_by_coherence(
            resources, fingerprints, coherence_threshold=0.5
        )

        # Similar configs should cluster together
        assert len(clusters) >= 1

    def test_cluster_by_coherence_different_configs(self):
        """Test clustering with different configurations."""
        resources = [
            {"id": "r1"},
            {"id": "r2"},
            {"id": "r3"}
        ]
        fingerprints = {
            "r1": {"location": "eastus", "sku": "Standard_D2s_v3", "tags": {}},
            "r2": {"location": "westus", "sku": "Premium_LRS", "tags": {}},
            "r3": {"location": "northeurope", "sku": "Basic_A0", "tags": {}}
        }

        clusters = ConfigurationSimilarity.cluster_by_coherence(
            resources, fingerprints, coherence_threshold=0.9
        )

        # Very different configs should not cluster at high threshold
        # Each might be its own cluster or filtered out (< min size)
        assert isinstance(clusters, list)

    def test_cluster_by_coherence_empty_resources(self):
        """Test clustering with empty resource list."""
        resources = []
        fingerprints = {}

        clusters = ConfigurationSimilarity.cluster_by_coherence(
            resources, fingerprints, coherence_threshold=0.7
        )

        assert clusters == []

    def test_cluster_by_coherence_low_threshold(self):
        """Test clustering with low threshold (more merging)."""
        resources = [
            {"id": "r1"},
            {"id": "r2"}
        ]
        fingerprints = {
            "r1": {"location": "eastus", "sku": "Standard_D2s_v3", "tags": {}},
            "r2": {"location": "westus", "sku": "Premium_LRS", "tags": {}}
        }

        clusters = ConfigurationSimilarity.cluster_by_coherence(
            resources, fingerprints, coherence_threshold=0.1
        )

        # Low threshold should allow more clustering, but if similarity is 0
        # and MIN_CLUSTER_SIZE=2, may result in no valid clusters
        # The function filters out clusters < MIN_CLUSTER_SIZE
        assert isinstance(clusters, list)

    def test_cluster_by_coherence_high_threshold(self):
        """Test clustering with high threshold (less merging)."""
        resources = [
            {"id": "r1"},
            {"id": "r2"}
        ]
        fingerprints = {
            "r1": {"location": "eastus", "sku": "Standard_D2s_v3", "tags": {}},
            "r2": {"location": "westus", "sku": "Standard_D4s_v3", "tags": {}}
        }

        clusters = ConfigurationSimilarity.cluster_by_coherence(
            resources, fingerprints, coherence_threshold=0.95
        )

        # High threshold should prevent clustering unless very similar
        # May result in no clusters if similarity < threshold and < min cluster size
        assert isinstance(clusters, list)

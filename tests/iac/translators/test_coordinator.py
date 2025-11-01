"""
Tests for TranslationCoordinator.

Tests the orchestration of multiple translators and comprehensive
report generation.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.iac.translators.coordinator import (
    TranslationContext,
    TranslationCoordinator,
)


@pytest.fixture
def translation_context():
    """Create a basic translation context for testing."""
    return TranslationContext(
        source_subscription_id="source-sub-123",
        target_subscription_id="target-sub-456",
        available_resources={
            "azurerm_storage_account": {
                "storage1": {"id": "/subscriptions/target-sub-456/..."}
            }
        },
    )


@pytest.fixture
def mock_translator():
    """Create a mock translator for testing."""
    translator = MagicMock()
    translator.__class__.__name__ = "MockTranslator"
    translator.can_translate.return_value = True
    translator.translate.side_effect = lambda r: r  # Return unchanged
    translator.get_report.return_value = {
        "translator": "MockTranslator",
        "total_resources_processed": 5,
        "translations_performed": 3,
        "warnings": 1,
        "missing_targets": 0,
        "results": [],
    }
    return translator


class TestTranslationContext:
    """Tests for TranslationContext dataclass."""

    def test_context_creation_minimal(self):
        """Test creating context with minimal required fields."""
        context = TranslationContext(
            source_subscription_id=None,
            target_subscription_id="target-sub-123",
        )

        assert context.source_subscription_id is None
        assert context.target_subscription_id == "target-sub-123"
        assert context.source_tenant_id is None
        assert context.target_tenant_id is None
        assert context.available_resources == {}
        assert context.identity_mapping_file is None
        assert context.strict_mode is False

    def test_context_creation_full(self):
        """Test creating context with all fields."""
        resources = {"azurerm_storage_account": {}}

        context = TranslationContext(
            source_subscription_id="source-123",
            target_subscription_id="target-456",
            source_tenant_id="tenant-source",
            target_tenant_id="tenant-target",
            available_resources=resources,
            identity_mapping_file="/path/to/mapping.json",
            strict_mode=True,
        )

        assert context.source_subscription_id == "source-123"
        assert context.target_subscription_id == "target-456"
        assert context.source_tenant_id == "tenant-source"
        assert context.target_tenant_id == "tenant-target"
        assert context.available_resources is resources
        assert context.identity_mapping_file == "/path/to/mapping.json"
        assert context.strict_mode is True


class TestTranslationCoordinatorInitialization:
    """Tests for coordinator initialization."""

    def test_initialization_with_no_translators(self, translation_context):
        """Test coordinator initializes gracefully with no translators."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=[],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[],
            ):
                coordinator = TranslationCoordinator(translation_context)

                assert coordinator.context == translation_context
                assert coordinator.translators == []
                assert coordinator._resources_processed == 0
                assert coordinator._resources_translated == 0

    def test_initialization_with_translators(
        self, translation_context, mock_translator
    ):
        """Test coordinator initializes with registered translators."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=["MockTranslator"],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[mock_translator],
            ):
                coordinator = TranslationCoordinator(translation_context)

                assert len(coordinator.translators) == 1
                assert coordinator.translators[0] is mock_translator

    def test_initialization_handles_registry_import_error(self, translation_context):
        """Test coordinator handles registry import failures gracefully."""
        # Patch the import to raise an error
        with patch.dict("sys.modules", {"src.iac.translators.registry": None}):
            coordinator = TranslationCoordinator(translation_context)

            # Should initialize with empty translator list
            assert coordinator.translators == []


class TestResourceTranslation:
    """Tests for resource translation methods."""

    def test_translate_resource_no_translators(self, translation_context):
        """Test translating resource with no translators returns unchanged."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=[],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[],
            ):
                coordinator = TranslationCoordinator(translation_context)

                resource = {"type": "azurerm_storage_account", "name": "storage1"}
                result = coordinator.translate_resource(resource)

                assert result == resource

    def test_translate_resource_with_applicable_translator(
        self, translation_context, mock_translator
    ):
        """Test resource is translated by applicable translator."""

        # Configure mock to modify resource
        def translate_func(resource):
            modified = resource.copy()
            modified["translated"] = True
            return modified

        mock_translator.translate.side_effect = translate_func

        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=["MockTranslator"],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[mock_translator],
            ):
                coordinator = TranslationCoordinator(translation_context)

                resource = {"type": "azurerm_storage_account", "name": "storage1"}
                result = coordinator.translate_resource(resource)

                assert result["translated"] is True
                mock_translator.can_translate.assert_called_once()
                mock_translator.translate.assert_called_once()

    def test_translate_resource_skips_non_applicable_translator(
        self, translation_context, mock_translator
    ):
        """Test translator is skipped when can_translate returns False."""
        mock_translator.can_translate.return_value = False

        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=["MockTranslator"],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[mock_translator],
            ):
                coordinator = TranslationCoordinator(translation_context)

                resource = {"type": "azurerm_key_vault", "name": "kv1"}
                result = coordinator.translate_resource(resource)

                assert result == resource
                mock_translator.can_translate.assert_called_once()
                mock_translator.translate.assert_not_called()

    def test_translate_resource_handles_translator_error(
        self, translation_context, mock_translator
    ):
        """Test coordinator handles translator errors gracefully."""
        mock_translator.translate.side_effect = ValueError("Translation failed")

        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=["MockTranslator"],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[mock_translator],
            ):
                coordinator = TranslationCoordinator(translation_context)

                resource = {"type": "azurerm_storage_account", "name": "storage1"}
                result = coordinator.translate_resource(resource)

                # Should return original resource on error
                assert result == resource
                assert coordinator._total_errors == 1

    def test_translate_resources_empty_list(self, translation_context):
        """Test translating empty resource list."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=[],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[],
            ):
                coordinator = TranslationCoordinator(translation_context)

                result = coordinator.translate_resources([])

                assert result == []
                assert coordinator._resources_processed == 0

    def test_translate_resources_batch(self, translation_context, mock_translator):
        """Test translating multiple resources."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=["MockTranslator"],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[mock_translator],
            ):
                coordinator = TranslationCoordinator(translation_context)

                resources = [
                    {"type": "azurerm_storage_account", "name": "storage1"},
                    {"type": "azurerm_storage_account", "name": "storage2"},
                    {"type": "azurerm_key_vault", "name": "kv1"},
                ]

                result = coordinator.translate_resources(resources)

                assert len(result) == 3
                assert coordinator._resources_processed == 3
                assert mock_translator.can_translate.call_count == 3


class TestReportGeneration:
    """Tests for report generation methods."""

    def test_get_translation_statistics_no_translators(self, translation_context):
        """Test statistics with no translators."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=[],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[],
            ):
                coordinator = TranslationCoordinator(translation_context)

                stats = coordinator.get_translation_statistics()

                assert stats["total_translators"] == 0
                assert stats["resources_processed"] == 0
                assert stats["resources_translated"] == 0
                assert stats["total_warnings"] == 0
                assert stats["total_errors"] == 0
                assert stats["translators"] == []

    def test_get_translation_statistics_with_translators(
        self, translation_context, mock_translator
    ):
        """Test statistics collection from translators."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=["MockTranslator"],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[mock_translator],
            ):
                coordinator = TranslationCoordinator(translation_context)

                # Process some resources to update stats
                resources = [
                    {"type": "azurerm_storage_account", "name": "storage1"},
                    {"type": "azurerm_storage_account", "name": "storage2"},
                ]
                coordinator.translate_resources(resources)

                stats = coordinator.get_translation_statistics()

                assert stats["total_translators"] == 1
                assert stats["resources_processed"] == 2
                assert len(stats["translators"]) == 1
                assert stats["translators"][0]["translator"] == "MockTranslator"

    def test_get_translation_report(self, translation_context, mock_translator):
        """Test report generation."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=["MockTranslator"],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[mock_translator],
            ):
                coordinator = TranslationCoordinator(translation_context)

                report = coordinator.get_translation_report()

                assert "summary" in report
                assert "translators" in report
                assert report["summary"]["total_translators"] == 1
                assert isinstance(report["translators"], list)

    def test_format_translation_report_no_translations(self, translation_context):
        """Test formatting report when no translations occurred."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=[],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[],
            ):
                coordinator = TranslationCoordinator(translation_context)

                report_text = coordinator.format_translation_report()

                assert "Cross-Tenant Translation Report" in report_text
                assert "Total Translators: 0" in report_text
                assert "No translations were performed" in report_text

    def test_format_translation_report_with_translations(
        self, translation_context, mock_translator
    ):
        """Test formatting report with translation data."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=["MockTranslator"],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[mock_translator],
            ):
                coordinator = TranslationCoordinator(translation_context)

                # Process resources
                resources = [{"type": "azurerm_storage_account", "name": "storage1"}]
                coordinator.translate_resources(resources)

                report_text = coordinator.format_translation_report()

                assert "Cross-Tenant Translation Report" in report_text
                assert "MockTranslator:" in report_text
                assert "Processed:" in report_text
                assert "Translated:" in report_text


class TestReportSaving:
    """Tests for saving reports to files."""

    def test_save_translation_report_text_format(self, translation_context, tmp_path):
        """Test saving report in text format."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=[],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[],
            ):
                coordinator = TranslationCoordinator(translation_context)

                output_path = tmp_path / "report.txt"
                coordinator.save_translation_report(str(output_path), format="text")

                assert output_path.exists()
                content = output_path.read_text()
                assert "Cross-Tenant Translation Report" in content

    def test_save_translation_report_json_format(self, translation_context, tmp_path):
        """Test saving report in JSON format."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=[],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[],
            ):
                coordinator = TranslationCoordinator(translation_context)

                output_path = tmp_path / "report.json"
                coordinator.save_translation_report(str(output_path), format="json")

                assert output_path.exists()
                content = output_path.read_text()
                assert '"summary"' in content
                assert '"translators"' in content

    def test_save_translation_report_invalid_format(self, translation_context):
        """Test saving report with invalid format raises error."""
        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=[],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[],
            ):
                coordinator = TranslationCoordinator(translation_context)

                with pytest.raises(ValueError, match="Unsupported format"):
                    coordinator.save_translation_report("/tmp/report.txt", format="xml")


class TestMultipleTranslators:
    """Tests for coordinating multiple translators."""

    def test_multiple_translators_sequential_application(self, translation_context):
        """Test multiple translators are applied sequentially."""
        # Create two mock translators
        translator1 = MagicMock()
        translator1.__class__.__name__ = "Translator1"
        translator1.can_translate.return_value = True
        translator1.translate.side_effect = lambda r: {**r, "translated_by": "t1"}
        translator1.get_report.return_value = {
            "translator": "Translator1",
            "total_resources_processed": 1,
            "translations_performed": 1,
            "warnings": 0,
            "missing_targets": 0,
        }

        translator2 = MagicMock()
        translator2.__class__.__name__ = "Translator2"
        translator2.can_translate.return_value = True
        translator2.translate.side_effect = lambda r: {**r, "also_by": "t2"}
        translator2.get_report.return_value = {
            "translator": "Translator2",
            "total_resources_processed": 1,
            "translations_performed": 1,
            "warnings": 0,
            "missing_targets": 0,
        }

        with patch(
            "src.iac.translators.registry.TranslatorRegistry.get_registered_translators",
            return_value=["Translator1", "Translator2"],
        ):
            with patch(
                "src.iac.translators.registry.TranslatorRegistry.create_translators",
                return_value=[translator1, translator2],
            ):
                coordinator = TranslationCoordinator(translation_context)

                resource = {"type": "azurerm_storage_account", "name": "storage1"}
                result = coordinator.translate_resource(resource)

                # Both translators should have been called
                assert result["translated_by"] == "t1"
                assert result["also_by"] == "t2"
                translator1.can_translate.assert_called_once()
                translator2.can_translate.assert_called_once()

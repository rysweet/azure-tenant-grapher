"""
Unit tests for TranslatorRegistry.

Tests the decorator-based registration system, thread-safety,
and translator discovery functionality.
"""

import threading
from typing import Any, Dict, List

import pytest

from src.iac.translators.registry import (
    TranslatorRegistry,
    register_translator,
)


# Mock translator classes for testing
class MockTranslator:
    """Mock translator that implements required interface."""

    supported_resource_types = ["Microsoft.Storage/storageAccounts"]

    def __init__(self, context):
        self.context = context
        self.translation_results = []

    def can_translate(self, resource: Dict[str, Any]) -> bool:
        return resource.get("type") in self.supported_resource_types

    def translate(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        return resource

    def get_translation_results(self) -> List[Any]:
        return self.translation_results


class AnotherMockTranslator:
    """Another mock translator for testing multiple registrations."""

    supported_resource_types = ["Microsoft.Network/privateEndpoints"]

    def __init__(self, context):
        self.context = context
        self.translation_results = []

    def can_translate(self, resource: Dict[str, Any]) -> bool:
        return resource.get("type") in self.supported_resource_types

    def translate(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        return resource

    def get_translation_results(self) -> List[Any]:
        return self.translation_results


class BrokenTranslator:
    """Translator that fails during instantiation."""

    supported_resource_types = ["Microsoft.Broken/resource"]

    def __init__(self, context):
        raise RuntimeError("Intentional failure for testing")

    def can_translate(self, resource: Dict[str, Any]) -> bool:
        return True

    def translate(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        return resource

    def get_translation_results(self) -> List[Any]:
        return []


class InvalidTranslator:
    """Translator missing required methods."""

    def __init__(self, context):
        self.context = context


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear the registry before and after each test."""
    TranslatorRegistry.clear()
    yield
    TranslatorRegistry.clear()


@pytest.fixture
def mock_context():
    """Create a mock translation context."""

    class MockContext:
        source_subscription_id = "source-sub-id"
        target_subscription_id = "target-sub-id"

    return MockContext()


class TestTranslatorRegistry:
    """Test suite for TranslatorRegistry."""

    def test_register_translator_decorator(self):
        """Test @register_translator decorator registers class."""

        @register_translator
        class TestTranslator(MockTranslator):
            pass

        assert TranslatorRegistry.count() == 1
        assert "TestTranslator" in TranslatorRegistry.get_registered_translators()

    def test_register_multiple_translators(self):
        """Test registering multiple translators."""

        @register_translator
        class FirstTranslator(MockTranslator):
            pass

        @register_translator
        class SecondTranslator(AnotherMockTranslator):
            pass

        assert TranslatorRegistry.count() == 2
        names = TranslatorRegistry.get_registered_translators()
        assert "FirstTranslator" in names
        assert "SecondTranslator" in names

    def test_register_duplicate_translator_ignored(self):
        """Test registering the same translator twice is ignored."""

        @register_translator
        class DuplicateTranslator(MockTranslator):
            pass

        initial_count = TranslatorRegistry.count()

        # Try to register again
        TranslatorRegistry.register(DuplicateTranslator)

        # Count should remain the same
        assert TranslatorRegistry.count() == initial_count

    def test_register_invalid_translator_raises_error(self):
        """Test registering invalid translator raises TypeError."""
        with pytest.raises(TypeError, match="missing required methods"):
            TranslatorRegistry.register(InvalidTranslator)

    def test_register_non_class_raises_error(self):
        """Test registering non-class raises TypeError."""
        with pytest.raises(TypeError, match="Expected a class"):
            TranslatorRegistry.register("not a class")  # type: ignore

    def test_get_all_translators(self):
        """Test getting all registered translators."""

        @register_translator
        class Trans1(MockTranslator):
            pass

        @register_translator
        class Trans2(AnotherMockTranslator):
            pass

        all_translators = TranslatorRegistry.get_all_translators()
        assert len(all_translators) == 2
        assert Trans1 in all_translators
        assert Trans2 in all_translators

    def test_get_translator_by_resource_type(self):
        """Test getting translator by resource type."""

        @register_translator
        class StorageTranslator(MockTranslator):
            supported_resource_types = ["Microsoft.Storage/storageAccounts"]

        translator_class = TranslatorRegistry.get_translator(
            "Microsoft.Storage/storageAccounts"
        )
        assert translator_class == StorageTranslator

    def test_get_translator_not_found(self):
        """Test getting translator for unsupported resource type."""

        @register_translator
        class StorageTranslator(MockTranslator):
            supported_resource_types = ["Microsoft.Storage/storageAccounts"]

        translator_class = TranslatorRegistry.get_translator(
            "Microsoft.Compute/virtualMachines"
        )
        assert translator_class is None

    def test_create_translators(self, mock_context):
        """Test creating translator instances."""

        @register_translator
        class Trans1(MockTranslator):
            pass

        @register_translator
        class Trans2(AnotherMockTranslator):
            pass

        translators = TranslatorRegistry.create_translators(mock_context)

        assert len(translators) == 2
        assert all(hasattr(t, "context") for t in translators)
        assert all(t.context == mock_context for t in translators)

    def test_create_translator_instance(self, mock_context):
        """Test creating single translator instance by resource type."""

        @register_translator
        class StorageTranslator(MockTranslator):
            supported_resource_types = ["Microsoft.Storage/storageAccounts"]

        translator = TranslatorRegistry.create_translator_instance(
            "Microsoft.Storage/storageAccounts", mock_context
        )

        assert translator is not None
        assert isinstance(translator, StorageTranslator)
        assert translator.context == mock_context

    def test_create_translator_instance_not_found(self, mock_context):
        """Test creating translator instance for unsupported resource type."""
        translator = TranslatorRegistry.create_translator_instance(
            "Microsoft.Compute/virtualMachines", mock_context
        )
        assert translator is None

    def test_create_translators_handles_instantiation_failure(
        self, mock_context, caplog
    ):
        """Test that broken translator doesn't prevent others from instantiating."""

        @register_translator
        class GoodTranslator(MockTranslator):
            pass

        @register_translator
        class BadTranslator(BrokenTranslator):
            pass

        translators = TranslatorRegistry.create_translators(mock_context)

        # Should have 1 successful translator
        assert len(translators) == 1
        assert isinstance(translators[0], GoodTranslator)

        # Should log error for broken translator
        assert "Failed to instantiate translator BadTranslator" in caplog.text

    def test_get_supported_resource_types(self):
        """Test getting all supported resource types."""

        @register_translator
        class StorageTranslator(MockTranslator):
            supported_resource_types = ["Microsoft.Storage/storageAccounts"]

        @register_translator
        class NetworkTranslator(AnotherMockTranslator):
            supported_resource_types = ["Microsoft.Network/privateEndpoints"]

        supported_types = TranslatorRegistry.get_supported_resource_types()

        assert len(supported_types) == 2
        assert "Microsoft.Storage/storageAccounts" in supported_types
        assert "Microsoft.Network/privateEndpoints" in supported_types

    def test_clear_registry(self):
        """Test clearing the registry."""

        @register_translator
        class TestTranslator(MockTranslator):
            pass

        assert TranslatorRegistry.count() == 1

        TranslatorRegistry.clear()

        assert TranslatorRegistry.count() == 0
        assert len(TranslatorRegistry.get_all_translators()) == 0

    def test_thread_safety(self, mock_context):
        """Test that registry operations are thread-safe."""
        registration_errors = []
        instantiation_errors = []

        def register_translator_thread(translator_class):
            try:
                TranslatorRegistry.register(translator_class)
            except Exception as e:
                registration_errors.append(e)

        def create_translators_thread():
            try:
                TranslatorRegistry.create_translators(mock_context)
            except Exception as e:
                instantiation_errors.append(e)

        # Create translator classes dynamically
        translator_classes = []
        for i in range(10):

            class DynamicTranslator(MockTranslator):
                supported_resource_types = [f"Microsoft.Test/resource{i}"]

            DynamicTranslator.__name__ = f"Translator{i}"
            translator_classes.append(DynamicTranslator)

        # Start threads for registration
        threads = []
        for translator_class in translator_classes:
            thread = threading.Thread(
                target=register_translator_thread, args=(translator_class,)
            )
            threads.append(thread)
            thread.start()

        # Also start threads for instantiation
        for _ in range(5):
            thread = threading.Thread(target=create_translators_thread)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check no errors occurred
        assert len(registration_errors) == 0, (
            f"Registration errors: {registration_errors}"
        )
        assert len(instantiation_errors) == 0, (
            f"Instantiation errors: {instantiation_errors}"
        )

        # Verify all translators were registered
        assert TranslatorRegistry.count() == 10

    def test_decorator_returns_class_unmodified(self):
        """Test that @register_translator doesn't modify the class."""

        @register_translator
        class TestTranslator(MockTranslator):
            custom_attribute = "test_value"

        # Class should be unmodified
        assert hasattr(TestTranslator, "custom_attribute")
        assert TestTranslator.custom_attribute == "test_value"

        # Should still be instantiable
        instance = TestTranslator({"test": "context"})
        assert hasattr(instance, "context")

    def test_empty_registry_warnings(self, mock_context, caplog):
        """Test warnings when registry is empty."""
        translators = TranslatorRegistry.create_translators(mock_context)

        assert len(translators) == 0
        assert "No translators were successfully instantiated" in caplog.text

    def test_multiple_resource_types_per_translator(self):
        """Test translator supporting multiple resource types."""

        @register_translator
        class MultiTypeTranslator(MockTranslator):
            supported_resource_types = [
                "Microsoft.Storage/storageAccounts",
                "Microsoft.Storage/blobServices",
            ]

        supported_types = TranslatorRegistry.get_supported_resource_types()

        assert len(supported_types) == 2
        assert "Microsoft.Storage/storageAccounts" in supported_types
        assert "Microsoft.Storage/blobServices" in supported_types

        # Both types should resolve to the same translator
        translator1 = TranslatorRegistry.get_translator(
            "Microsoft.Storage/storageAccounts"
        )
        translator2 = TranslatorRegistry.get_translator(
            "Microsoft.Storage/blobServices"
        )
        assert translator1 == translator2
        assert translator1 == MultiTypeTranslator


class TestRegistryIntegration:
    """Integration tests for registry with realistic scenarios."""

    def test_complete_workflow(self, mock_context):
        """Test complete workflow from registration to instantiation."""

        # Step 1: Register translators via decorator
        @register_translator
        class StorageTranslator(MockTranslator):
            supported_resource_types = ["Microsoft.Storage/storageAccounts"]

        @register_translator
        class NetworkTranslator(AnotherMockTranslator):
            supported_resource_types = ["Microsoft.Network/privateEndpoints"]

        # Step 2: Verify registration
        assert TranslatorRegistry.count() == 2
        names = TranslatorRegistry.get_registered_translators()
        assert "StorageTranslator" in names
        assert "NetworkTranslator" in names

        # Step 3: Query supported types
        supported = TranslatorRegistry.get_supported_resource_types()
        assert len(supported) == 2

        # Step 4: Get specific translator
        storage_class = TranslatorRegistry.get_translator(
            "Microsoft.Storage/storageAccounts"
        )
        assert storage_class == StorageTranslator

        # Step 5: Create all translators
        translators = TranslatorRegistry.create_translators(mock_context)
        assert len(translators) == 2

        # Step 6: Use translators
        storage_resource = {"type": "Microsoft.Storage/storageAccounts"}
        network_resource = {"type": "Microsoft.Network/privateEndpoints"}

        for translator in translators:
            if translator.can_translate(storage_resource):
                result = translator.translate(storage_resource)
                assert result == storage_resource

            if translator.can_translate(network_resource):
                result = translator.translate(network_resource)
                assert result == network_resource

    def test_no_translators_registered(self, mock_context):
        """Test behavior when no translators are registered."""
        assert TranslatorRegistry.count() == 0

        translators = TranslatorRegistry.create_translators(mock_context)
        assert len(translators) == 0

        translator = TranslatorRegistry.get_translator(
            "Microsoft.Storage/storageAccounts"
        )
        assert translator is None

        supported = TranslatorRegistry.get_supported_resource_types()
        assert len(supported) == 0

"""Unit Tests for Layer Management Module Refactoring"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from src.services.layer.crud import LayerCRUDService, InvalidLayerIdError
from src.services.layer.query import LayerQueryService
from src.services.layer.validation import LayerValidationService
from src.services.layer.metadata import LayerMetadataService, LayerMetadata, LayerType
from src.services.layer_management_service import LayerManagementService


class TestLayerValidationService:
    """Tests for LayerValidationService"""

    def test_validate_layer_id_format_valid(self):
        """Test that valid layer IDs pass validation"""
        mock_session_manager = Mock()
        service = LayerValidationService(mock_session_manager)

        assert service.validate_layer_id_format("valid-layer-id") is True
        assert service.validate_layer_id_format("a" * 200) is True

    def test_validate_layer_id_format_invalid(self):
        """Test that invalid layer IDs fail validation"""
        mock_session_manager = Mock()
        service = LayerValidationService(mock_session_manager)

        assert service.validate_layer_id_format("") is False
        assert service.validate_layer_id_format("a" * 201) is False
        assert service.validate_layer_id_format(None) is False


class TestLayerMetadataService:
    """Tests for LayerMetadataService"""

    def test_node_to_layer_metadata_conversion(self):
        """Test converting Neo4j node to LayerMetadata"""
        mock_session_manager = Mock()
        service = LayerMetadataService(mock_session_manager)

        mock_node = {
            "layer_id": "test-layer",
            "name": "Test Layer",
            "description": "Test description",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": None,
            "created_by": "test",
            "parent_layer_id": None,
            "is_active": True,
            "is_baseline": False,
            "is_locked": False,
            "tenant_id": "test-tenant",
            "subscription_ids": [],
            "node_count": 100,
            "relationship_count": 50,
            "layer_type": "experimental",
            "metadata": "{}",
            "tags": [],
        }

        metadata = service.node_to_layer_metadata(mock_node)

        assert metadata.layer_id == "test-layer"
        assert metadata.name == "Test Layer"
        assert metadata.node_count == 100
        assert metadata.relationship_count == 50
        assert metadata.is_active is True
        assert metadata.layer_type == LayerType.EXPERIMENTAL


class TestLayerQueryService:
    """Tests for LayerQueryService"""

    @pytest.mark.asyncio
    async def test_get_layer_not_found(self):
        """Test querying non-existent layer returns None"""
        mock_session_manager = MagicMock()
        mock_session = MagicMock()
        mock_result = Mock()
        mock_result.single.return_value = None

        mock_session.run.return_value = mock_result
        mock_session_manager.session.return_value = mock_session
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        mock_metadata_service = Mock()
        service = LayerQueryService(mock_session_manager, mock_metadata_service)

        result = await service.get_layer("non-existent")

        assert result is None


class TestLayerCRUDService:
    """Tests for LayerCRUDService"""

    @pytest.mark.asyncio
    async def test_create_layer_invalid_id(self):
        """Test creating layer with invalid ID raises error"""
        mock_session_manager = MagicMock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value = mock_session
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        mock_validation_service = Mock()
        mock_validation_service.validate_layer_id_format.return_value = False

        mock_metadata_service = Mock()
        mock_query_service = Mock()

        service = LayerCRUDService(
            mock_session_manager,
            mock_validation_service,
            mock_metadata_service,
            mock_query_service,
        )

        with pytest.raises(InvalidLayerIdError):
            await service.create_layer(
                layer_id="",
                name="Test",
                description="Test",
                created_by="test",
            )


class TestBackwardCompatibility:
    """Tests for backward compatibility facade"""

    def test_layer_management_service_initialization(self):
        """Test that LayerManagementService initializes correctly"""
        mock_session_manager = MagicMock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value = mock_session
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        service = LayerManagementService(mock_session_manager)

        # Verify all sub-services are initialized
        assert service.validation_service is not None
        assert service.metadata_service is not None
        assert service.query_service is not None
        assert service.crud_service is not None
        assert service.session_manager is mock_session_manager

    def test_layer_management_service_has_all_methods(self):
        """Test that facade exposes all expected methods"""
        mock_session_manager = MagicMock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value = mock_session
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        service = LayerManagementService(mock_session_manager)

        # Verify all public methods exist
        assert hasattr(service, "create_layer")
        assert hasattr(service, "update_layer")
        assert hasattr(service, "delete_layer")
        assert hasattr(service, "get_layer")
        assert hasattr(service, "list_layers")
        assert hasattr(service, "get_active_layer")
        assert hasattr(service, "set_active_layer")
        assert hasattr(service, "copy_layer")
        assert hasattr(service, "compare_layers")
        assert hasattr(service, "validate_layer_integrity")
        assert hasattr(service, "refresh_layer_stats")
        assert hasattr(service, "archive_layer")
        assert hasattr(service, "restore_layer")


class TestLayerMetadataModel:
    """Tests for LayerMetadata data model"""

    def test_layer_metadata_creation(self):
        """Test creating LayerMetadata instance"""
        metadata = LayerMetadata(
            layer_id="test",
            name="Test Layer",
            description="Test",
            created_at=datetime.utcnow(),
            layer_type=LayerType.BASELINE,
        )

        assert metadata.layer_id == "test"
        assert metadata.name == "Test Layer"
        assert metadata.layer_type == LayerType.BASELINE
        assert metadata.node_count == 0
        assert metadata.relationship_count == 0

    def test_layer_metadata_to_dict(self):
        """Test converting LayerMetadata to dictionary"""
        created_at = datetime.utcnow()
        metadata = LayerMetadata(
            layer_id="test",
            name="Test Layer",
            description="Test",
            created_at=created_at,
            layer_type=LayerType.EXPERIMENTAL,
        )

        data = metadata.to_dict()

        assert data["layer_id"] == "test"
        assert data["name"] == "Test Layer"
        assert data["layer_type"] == "experimental"
        assert "created_at" in data

    def test_layer_metadata_from_dict(self):
        """Test creating LayerMetadata from dictionary"""
        data = {
            "layer_id": "test",
            "name": "Test Layer",
            "description": "Test",
            "created_at": "2024-01-01T00:00:00",
            "layer_type": "baseline",
        }

        metadata = LayerMetadata.from_dict(data)

        assert metadata.layer_id == "test"
        assert metadata.name == "Test Layer"
        assert metadata.layer_type == LayerType.BASELINE


def test_module_imports():
    """Test that all modules can be imported"""
    from src.services.layer import (
        LayerCRUDService,
        LayerQueryService,
        LayerValidationService,
        LayerMetadataService,
    )
    from src.services.layer_management_service import LayerManagementService

    assert LayerCRUDService is not None
    assert LayerQueryService is not None
    assert LayerValidationService is not None
    assert LayerMetadataService is not None
    assert LayerManagementService is not None


def test_all_exports_present():
    """Test that __all__ exports are complete"""
    from src.services import layer

    expected_exports = [
        "LayerCRUDService",
        "LayerQueryService",
        "LayerValidationService",
        "LayerMetadataService",
        "LayerMetadata",
        "LayerType",
        "LayerDiff",
        "LayerValidationReport",
        "LayerError",
        "LayerNotFoundError",
        "LayerAlreadyExistsError",
    ]

    for export in expected_exports:
        assert hasattr(layer, export), f"Missing export: {export}"

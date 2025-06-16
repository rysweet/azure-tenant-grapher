"""Tests for IaC emitters and registry functionality.

Tests the emitter base class, registry, and stub implementations.
"""

import pytest
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.iac.emitters import get_emitter_registry, get_emitter, register_emitter
from src.iac.emitters.base import IaCEmitter
from src.iac.traverser import TenantGraph


class MockEmitter(IaCEmitter):
    """Mock emitter implementation for testing."""
    
    def emit(self, graph: TenantGraph, out_dir: Path) -> List[Path]:
        """Mock emit method."""
        # Just create a dummy file
        dummy_file = out_dir / "mock.json"
        dummy_file.parent.mkdir(parents=True, exist_ok=True)
        dummy_file.write_text('{"format": "mock"}')
        return [dummy_file]
    
    async def emit_template(
        self,
        tenant_graph: TenantGraph,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Mock template emission."""
        return {
            "format": "mock",
            "resources": len(tenant_graph.resources),
            "output_path": output_path
        }
    
    def get_supported_resource_types(self) -> List[str]:
        """Mock supported resource types."""
        return ["Microsoft.Test/mockResource"]
    
    def validate_template(self, template_data: Dict[str, Any]) -> bool:
        """Mock template validation."""
        return "format" in template_data


class TestEmitterRegistry:
    """Test cases for emitter registry functionality."""
    
    def test_register_emitter(self) -> None:
        """Test registering a new emitter."""
        # Register mock emitter
        register_emitter("mock", MockEmitter)
        
        # Verify it's in registry
        registry = get_emitter_registry()
        assert "mock" in registry
        assert registry["mock"] == MockEmitter
    
    def test_get_emitter(self) -> None:
        """Test retrieving registered emitter."""
        # Register mock emitter
        register_emitter("test-format", MockEmitter)
        
        # Get emitter
        emitter_class = get_emitter("test-format")
        assert emitter_class == MockEmitter
    
    def test_get_emitter_case_insensitive(self) -> None:
        """Test that emitter lookup is case insensitive."""
        register_emitter("CaseTest", MockEmitter)
        
        # Should work with different cases
        assert get_emitter("casetest") == MockEmitter
        assert get_emitter("CASETEST") == MockEmitter
        assert get_emitter("CaseTest") == MockEmitter
    
    def test_get_emitter_not_found(self) -> None:
        """Test that get_emitter raises KeyError for unknown format."""
        with pytest.raises(KeyError, match="No emitter registered for format 'nonexistent'"):
            get_emitter("nonexistent")
    
    def test_registry_copy(self) -> None:
        """Test that get_emitter_registry returns a copy."""
        original_registry = get_emitter_registry()
        registry_copy = get_emitter_registry()
        
        # Modify copy
        registry_copy["test"] = MockEmitter
        
        # Original should be unchanged
        new_original = get_emitter_registry()
        assert "test" not in new_original


class TestMockEmitter:
    """Test cases for mock emitter implementation."""
    
    @pytest.mark.asyncio
    async def test_mock_emitter_emit_template(self) -> None:
        """Test mock emitter template generation."""
        emitter = MockEmitter()
        tenant_graph = TenantGraph()
        tenant_graph.resources = [{"id": "test1"}, {"id": "test2"}]
        
        result = await emitter.emit_template(tenant_graph, "/test/output")
        
        assert result["format"] == "mock"
        assert result["resources"] == 2
        assert result["output_path"] == "/test/output"
    
    def test_mock_emitter_supported_types(self) -> None:
        """Test mock emitter supported resource types."""
        emitter = MockEmitter()
        types = emitter.get_supported_resource_types()
        
        assert len(types) == 1
        assert "Microsoft.Test/mockResource" in types
    
    def test_mock_emitter_validation(self) -> None:
        """Test mock emitter template validation."""
        emitter = MockEmitter()
        
        # Valid template
        valid_template = {"format": "mock", "data": "test"}
        assert emitter.validate_template(valid_template) is True
        
        # Invalid template
        invalid_template = {"data": "test"}
        assert emitter.validate_template(invalid_template) is False
    
    def test_mock_emitter_format_name(self) -> None:
        """Test mock emitter format name extraction."""
        emitter = MockEmitter()
        assert emitter.get_format_name() == "mock"


class TestEmitterDispatch:
    """Test cases for emitter dispatch functionality."""
    
    def test_emitter_dispatch_works(self) -> None:
        """Test that emitter registration and dispatch works correctly."""
        # Register mock emitter
        register_emitter("dispatch-test", MockEmitter)
        
        # Get emitter class
        emitter_class = get_emitter("dispatch-test")
        
        # Create instance
        emitter = emitter_class()
        
        # Verify it's the right type
        assert isinstance(emitter, MockEmitter)
        assert isinstance(emitter, IaCEmitter)
    
    def test_multiple_emitters_registration(self) -> None:
        """Test registering multiple emitters."""
        class AnotherMockEmitter(MockEmitter):
            def get_format_name(self) -> str:
                return "another"
        
        # Register multiple emitters
        register_emitter("mock1", MockEmitter)
        register_emitter("mock2", AnotherMockEmitter)
        
        # Both should be available
        registry = get_emitter_registry()
        assert "mock1" in registry
        assert "mock2" in registry
        assert registry["mock1"] == MockEmitter
        assert registry["mock2"] == AnotherMockEmitter
"""Tests for IaC transformation engine.

Tests the TransformationEngine class and related functionality.
"""

import tempfile
from pathlib import Path

import pytest

from src.iac.engine import TransformationEngine, TransformationRule


class TestTransformationEngine:
    """Test cases for TransformationEngine class."""
    
    def test_engine_initialization(self) -> None:
        """Test that engine initializes correctly."""
        engine = TransformationEngine()
        assert engine.rules == []
    
    def test_engine_initialization_with_rules_file(self) -> None:
        """Test that engine initializes with rules file."""
        # Create a temporary rules file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
rules:
  - resource_type: "Microsoft.Compute/virtualMachines"
    actions:
      rename:
        pattern: "vm-{orig}-renamed"
      region:
        target: "West US"
            """)
            f.flush()
            
            engine = TransformationEngine(f.name)
            assert len(engine.rules) == 1
            assert engine.rules[0].resource_type == "Microsoft.Compute/virtualMachines"
            
        # Clean up
        Path(f.name).unlink()
    
    def test_transformation_rule_initialization(self) -> None:
        """Test TransformationRule initialization with defaults."""
        rule = TransformationRule(
            resource_type="Microsoft.Storage/storageAccounts"
        )
        
        assert rule.resource_type == "Microsoft.Storage/storageAccounts"
        assert rule.actions == {}
    
    def test_transformation_rule_with_actions(self) -> None:
        """Test TransformationRule with custom actions."""
        actions = {
            "rename": {"pattern": "storage-{orig}"},
            "tag": {"add": {"environment": "test"}}
        }
        rule = TransformationRule(
            resource_type="Microsoft.Storage/storageAccounts",
            actions=actions
        )
        
        assert rule.resource_type == "Microsoft.Storage/storageAccounts"
        assert rule.actions == actions


class TestTransformationEngineApply:
    """Test cases for transformation rule application."""
    
    def test_apply_rename_transformation(self) -> None:
        """Test applying rename transformation."""
        engine = TransformationEngine()
        rule = TransformationRule(
            resource_type="Microsoft.Compute/virtualMachines",
            actions={
                "rename": {"pattern": "vm-{orig}-renamed"}
            }
        )
        engine.rules.append(rule)
        
        resource = {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "test-vm",
            "location": "East US"
        }
        
        result = engine.apply(resource)
        assert result["name"] == "vm-test-vm-renamed"
        assert result["type"] == "Microsoft.Compute/virtualMachines"
        assert result["location"] == "East US"
    
    def test_apply_region_transformation(self) -> None:
        """Test applying region transformation."""
        engine = TransformationEngine()
        rule = TransformationRule(
            resource_type="Microsoft.Storage/storageAccounts",
            actions={
                "region": {"target": "West US 2"}
            }
        )
        engine.rules.append(rule)
        
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "teststorage",
            "location": "East US"
        }
        
        result = engine.apply(resource)
        assert result["location"] == "West US 2"
        assert result["name"] == "teststorage"
    
    def test_apply_tag_transformation(self) -> None:
        """Test applying tag transformation."""
        engine = TransformationEngine()
        rule = TransformationRule(
            resource_type="*",  # Wildcard to match all
            actions={
                "tag": {"add": {"environment": "production", "owner": "team-a"}}
            }
        )
        engine.rules.append(rule)
        
        resource = {
            "type": "Microsoft.Web/sites",
            "name": "webapp",
            "tags": {"existing": "tag"}
        }
        
        result = engine.apply(resource)
        assert result["tags"]["existing"] == "tag"
        assert result["tags"]["environment"] == "production"
        assert result["tags"]["owner"] == "team-a"
    
    def test_apply_no_matching_rules(self) -> None:
        """Test applying transformation with no matching rules."""
        engine = TransformationEngine()
        rule = TransformationRule(
            resource_type="Microsoft.Compute/virtualMachines",
            actions={"rename": {"pattern": "vm-{orig}"}}
        )
        engine.rules.append(rule)
        
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage"
        }
        
        result = engine.apply(resource)
        # Should return unchanged copy
        assert result == resource
        assert result is not resource  # Should be a copy
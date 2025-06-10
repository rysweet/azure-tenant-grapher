#!/usr/bin/env python3
"""
Test script to validate the new modular structure of Azure Tenant Grapher
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

def test_imports():
    """Test that all modules can be imported successfully."""
    print("🧪 Testing imports...")
    
    try:
        from src.config_manager import create_config_from_env, AzureTenantGrapherConfig
        print("✅ config_manager imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import config_manager: {e}")
        return False
    
    try:
        from src.resource_processor import create_resource_processor, ResourceProcessor
        print("✅ resource_processor imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import resource_processor: {e}")
        return False
    
    try:
        from src.llm_descriptions import create_llm_generator
        print("✅ llm_descriptions imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import llm_descriptions: {e}")
        return False
    
    return True

def test_config_creation():
    """Test configuration creation and validation."""
    print("\n🧪 Testing configuration creation...")
    
    try:
        # Test with dummy tenant ID
        from src.config_manager import create_config_from_env
        config = create_config_from_env("dummy-tenant-id", resource_limit=10)
        print("✅ Configuration created successfully")
        
        # Test configuration summary
        config.log_configuration_summary()
        print("✅ Configuration summary logged successfully")
        
        return True
    except Exception as e:
        print(f"❌ Failed to create configuration: {e}")
        return False

def test_resource_processor():
    """Test resource processor creation (without actual Neo4j)."""
    print("\n🧪 Testing resource processor...")
    
    try:
        # Mock session object for testing
        class MockSession:
            def run(self, query, **kwargs):
                return MockResult()
        
        class MockResult:
            def single(self):
                return {'count': 0}
        
        session = MockSession()
        
        # Test processor creation
        from src.resource_processor import create_resource_processor
        processor = create_resource_processor(session, None, 5)
        print("✅ Resource processor created successfully")
        
        # Test stats initialization
        print(f"✅ Processor stats initialized: {processor.stats.to_dict()}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to create resource processor: {e}")
        return False

def main():
    """Main test function."""
    print("🔧 Azure Tenant Grapher - Modular Structure Test")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_config_creation,
        test_resource_processor
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"🎯 TEST SUMMARY: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! The modular structure is working correctly.")
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

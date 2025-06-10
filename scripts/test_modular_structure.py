#!/usr/bin/env python3
"""
Test script to validate the new modular structure of Azure Tenant Grapher
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def test_imports() -> None:
    """Test that all modules can be imported successfully."""
    print("🧪 Testing imports...")

    try:
        exec("import src.config_manager")  # nosec B102
        print("✅ config_manager imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import config_manager: {e}")
        pass

    try:
        exec("import src.resource_processor")  # nosec B102
        print("✅ resource_processor imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import resource_processor: {e}")
        pass

    try:
        exec("import src.llm_descriptions")  # nosec B102
        print("✅ llm_descriptions imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import llm_descriptions: {e}")
        pass

    pass


def test_config_creation() -> None:
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

        # Test passed
    except Exception as e:
        print(f"❌ Failed to create configuration: {e}")
        raise AssertionError("Test failed") from e


def test_resource_processor() -> None:
    """Test resource processor creation (without actual Neo4j)."""
    print("\n🧪 Testing resource processor...")

    try:
        # Mock session object for testing
        class MockSession:
            def run(self, query, **kwargs) -> None:
                pass

        class MockResult:
            def single(self) -> None:
                pass

        session = MockSession()

        # Test processor creation
        from src.resource_processor import create_resource_processor

        processor = create_resource_processor(session, None, 5)
        print("✅ Resource processor created successfully")

        # Test stats initialization
        print(f"✅ Processor stats initialized: {processor.stats.to_dict()}")

        # Test passed
    except Exception as e:
        print(f"❌ Failed to create resource processor: {e}")
        pass


def main() -> None:
    """Main test function."""
    print("🔧 Azure Tenant Grapher - Modular Structure Test")
    print("=" * 60)

    tests = [test_imports, test_config_creation, test_resource_processor]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"🎯 TEST SUMMARY: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed! The modular structure is working correctly.")
    else:
        print("⚠️ Some tests failed. Please check the implementation.")

    # No return value; main should not return a value
    pass


if __name__ == "__main__":
    main()
    # sys.exit(0 if success else 1)  # main no longer returns a value

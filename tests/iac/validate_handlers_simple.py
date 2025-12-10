#!/usr/bin/env python3
"""Simple standalone handler validation script.

This script validates handler registration without requiring pytest or heavy dependencies.
Run with: python tests/iac/validate_handlers_simple.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def validate_handler_registration():
    """Validate that all handlers are registered correctly."""
    print("=" * 70)
    print("HANDLER REGISTRATION VALIDATION")
    print("=" * 70)

    try:
        from src.iac.emitters.terraform.handlers import (
            HandlerRegistry,
            ensure_handlers_registered,
        )

        # Force registration
        ensure_handlers_registered()

        # Get all handlers
        handlers = HandlerRegistry.get_all_handlers()
        supported_types = HandlerRegistry.get_all_supported_types()

        print("\n✅ Registration successful!")
        print(f"   - Handlers registered: {len(handlers)}")
        print(f"   - Azure types supported: {len(supported_types)}")

        # List all handlers
        print(f"\n📋 Registered Handlers ({len(handlers)}):")
        for i, handler_class in enumerate(
            sorted(handlers, key=lambda h: h.__name__), 1
        ):
            types_handled = ", ".join(sorted(handler_class.HANDLED_TYPES))
            print(f"   {i:2d}. {handler_class.__name__:40s} → {types_handled}")

        # Check for common types
        print("\n🔍 Common Resource Type Coverage:")
        common_types = [
            "Microsoft.Compute/virtualMachines",
            "Microsoft.Network/virtualNetworks",
            "Microsoft.Storage/storageAccounts",
            "Microsoft.Network/networkSecurityGroups",
            "Microsoft.ManagedIdentity/userAssignedIdentities",
        ]

        supported_lower = {t.lower() for t in supported_types}
        for azure_type in common_types:
            status = "✅" if azure_type.lower() in supported_lower else "❌"
            print(f"   {status} {azure_type}")

        # Check for duplicates
        print("\n🔎 Checking for duplicate handlers...")
        type_to_handlers = {}
        for handler_class in handlers:
            for azure_type in handler_class.HANDLED_TYPES:
                azure_type_lower = azure_type.lower()
                if azure_type_lower not in type_to_handlers:
                    type_to_handlers[azure_type_lower] = []
                type_to_handlers[azure_type_lower].append(handler_class.__name__)

        duplicates = {
            azure_type: handler_names
            for azure_type, handler_names in type_to_handlers.items()
            if len(handler_names) > 1
        }

        if duplicates:
            print(f"   ⚠️  Found {len(duplicates)} duplicate registrations:")
            for azure_type, handler_names in duplicates.items():
                print(f"      - {azure_type}: {', '.join(handler_names)}")
        else:
            print("   ✅ No duplicate handlers found")

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY:")
        print(f"  - Total handlers: {len(handlers)}")
        print(f"  - Azure types covered: {len(supported_types)}")
        print(f"  - Duplicate conflicts: {len(duplicates)}")
        print("=" * 70)

        return len(handlers) >= 50 and len(duplicates) == 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def validate_handler_structure():
    """Validate that handlers have correct structure."""
    print("\n" + "=" * 70)
    print("HANDLER STRUCTURE VALIDATION")
    print("=" * 70)

    try:
        from src.iac.emitters.terraform.handlers import (
            HandlerRegistry,
            ensure_handlers_registered,
        )

        ensure_handlers_registered()
        handlers = HandlerRegistry.get_all_handlers()

        issues = []

        for handler_class in handlers:
            # Check HANDLED_TYPES
            if not hasattr(handler_class, "HANDLED_TYPES"):
                issues.append(f"{handler_class.__name__} missing HANDLED_TYPES")
            elif len(handler_class.HANDLED_TYPES) == 0:
                issues.append(f"{handler_class.__name__} has empty HANDLED_TYPES")

            # Check TERRAFORM_TYPES
            if not hasattr(handler_class, "TERRAFORM_TYPES"):
                issues.append(f"{handler_class.__name__} missing TERRAFORM_TYPES")

            # Check emit method
            if not hasattr(handler_class, "emit"):
                issues.append(f"{handler_class.__name__} missing emit() method")

        if issues:
            print(f"\n⚠️  Found {len(issues)} structure issues:")
            for issue in issues[:10]:  # Show first 10
                print(f"   - {issue}")
            if len(issues) > 10:
                print(f"   ... and {len(issues) - 10} more")
            return False
        else:
            print(f"\n✅ All {len(handlers)} handlers have correct structure")
            return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "🔧" * 35)
    print("TERRAFORM HANDLER VALIDATION SUITE")
    print("🔧" * 35)

    registration_ok = validate_handler_registration()
    structure_ok = validate_handler_structure()

    print("\n" + "=" * 70)
    print("FINAL RESULT:")
    print(f"  Registration: {'✅ PASS' if registration_ok else '❌ FAIL'}")
    print(f"  Structure:    {'✅ PASS' if structure_ok else '❌ FAIL'}")
    print("=" * 70)

    sys.exit(0 if (registration_ok and structure_ok) else 1)

"""Example usage of the Code Analyzer brick.

This demonstrates how to use the handler analyzer to extract
property mappings from handler files.
"""

from pathlib import Path

from .handler_analyzer import HandlerAnalyzer, analyze_handler


def analyze_single_handler(handler_path: Path) -> None:
    """Analyze a single handler file.

    Args:
        handler_path: Path to handler Python file
    """
    print(f"Analyzing: {handler_path.name}")
    print("=" * 60)

    # Use convenience function
    result = analyze_handler(handler_path)

    if not result:
        print("❌ Failed to analyze handler")
        return

    # Display results
    print(f"\nHandler: {result.handler_class}")
    print(f"Azure Types: {', '.join(result.handled_types)}")
    print(f"Terraform Types: {', '.join(result.terraform_types)}")

    print(f"\n📊 Property Analysis:")
    print(f"  • Total properties: {len(result.properties)}")
    print(f"  • Terraform writes: {len(result.terraform_writes)}")
    print(f"  • Azure reads: {len(result.azure_reads)}")
    print(f"  • Bidirectional mappings: {len(result.bidirectional_mappings)}")

    # Show Terraform config keys
    if result.terraform_writes:
        print(f"\n✍️  Terraform Config Keys:")
        for key in sorted(result.terraform_writes):
            print(f"  • {key}")

    # Show Azure property keys
    if result.azure_reads:
        print(f"\n📖 Azure Property Keys:")
        for key in sorted(result.azure_reads):
            print(f"  • {key}")

    # Show bidirectional mappings
    if result.bidirectional_mappings:
        print(f"\n🔄 Bidirectional Mappings:")
        for tf_key, azure_key in sorted(result.bidirectional_mappings.items()):
            print(f"  • {tf_key:30} <- {azure_key}")


def analyze_handler_directory(handlers_dir: Path) -> None:
    """Analyze all handler files in a directory.

    Args:
        handlers_dir: Directory containing handler files
    """
    handler_files = list(handlers_dir.rglob("*.py"))
    handler_files = [
        f
        for f in handler_files
        if f.name != "__init__.py"
        and not f.name.startswith("test_")
        and not f.name.startswith("base_")
    ]

    print(f"Found {len(handler_files)} handler files")
    print("=" * 60)

    results = []
    for handler_file in handler_files:
        result = analyze_handler(handler_file)
        if result and result.handler_class:
            results.append(result)

    # Summary statistics
    print(f"\n📊 Summary Statistics:")
    print(f"  • Handlers analyzed: {len(results)}")
    print(f"  • Total Terraform keys: {sum(len(r.terraform_writes) for r in results)}")
    print(f"  • Total Azure keys: {sum(len(r.azure_reads) for r in results)}")
    print(f"  • Total mappings: {sum(len(r.bidirectional_mappings) for r in results)}")

    # List handlers by resource count
    print(f"\n📋 Handlers by Property Count:")
    for result in sorted(results, key=lambda r: len(r.properties), reverse=True):
        print(
            f"  • {result.handler_class:40} - {len(result.properties):3} properties"
        )


def compare_handlers(handler1_path: Path, handler2_path: Path) -> None:
    """Compare property usage between two handlers.

    Args:
        handler1_path: First handler file
        handler2_path: Second handler file
    """
    result1 = analyze_handler(handler1_path)
    result2 = analyze_handler(handler2_path)

    if not result1 or not result2:
        print("❌ Failed to analyze one or both handlers")
        return

    print(f"Comparing: {result1.handler_class} vs {result2.handler_class}")
    print("=" * 60)

    # Common Terraform keys
    common_tf_keys = result1.terraform_writes & result2.terraform_writes
    print(f"\n🔗 Common Terraform Keys ({len(common_tf_keys)}):")
    for key in sorted(common_tf_keys):
        print(f"  • {key}")

    # Common Azure keys
    common_azure_keys = result1.azure_reads & result2.azure_reads
    print(f"\n🔗 Common Azure Keys ({len(common_azure_keys)}):")
    for key in sorted(common_azure_keys):
        print(f"  • {key}")

    # Unique to handler 1
    unique_tf_1 = result1.terraform_writes - result2.terraform_writes
    if unique_tf_1:
        print(f"\n🎯 Unique to {result1.handler_class} ({len(unique_tf_1)}):")
        for key in sorted(unique_tf_1):
            print(f"  • {key}")

    # Unique to handler 2
    unique_tf_2 = result2.terraform_writes - result1.terraform_writes
    if unique_tf_2:
        print(f"\n🎯 Unique to {result2.handler_class} ({len(unique_tf_2)}):")
        for key in sorted(unique_tf_2):
            print(f"  • {key}")


if __name__ == "__main__":
    # Example: Analyze storage account handler
    handler_path = (
        Path(__file__).parents[3]
        / "emitters"
        / "terraform"
        / "handlers"
        / "storage"
        / "storage_account.py"
    )

    if handler_path.exists():
        analyze_single_handler(handler_path)
    else:
        print(f"Handler not found: {handler_path}")

    # Example: Analyze all handlers in a directory
    # handlers_dir = Path(__file__).parents[3] / "emitters" / "terraform" / "handlers"
    # if handlers_dir.exists():
    #     analyze_handler_directory(handlers_dir)

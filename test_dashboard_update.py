#!/usr/bin/env python
"""Test the updated dashboard with max_llm_threads and max_build_threads."""

from src.rich_dashboard import RichDashboard

# Test configuration
config = {
    "tenant_id": "test-tenant-123",
    "environment": "production",
    "region": "eastus",
}

# Test 1: Using new parameters
print("Test 1: Creating dashboard with new parameters...")
dashboard = RichDashboard(config=config, max_llm_threads=10, max_build_threads=25)
assert dashboard.max_llm_threads == 10, (
    f"Expected max_llm_threads=10, got {dashboard.max_llm_threads}"
)
assert dashboard.max_build_threads == 25, (
    f"Expected max_build_threads=25, got {dashboard.max_build_threads}"
)
assert dashboard.max_concurrency == 10, (
    f"Expected max_concurrency=10 (backward compat), got {dashboard.max_concurrency}"
)
print("✅ New parameters work correctly")

# Test 2: Backward compatibility with max_concurrency
print("\nTest 2: Testing backward compatibility...")
dashboard_old = RichDashboard(config=config, max_concurrency=15)
assert dashboard_old.max_llm_threads == 15, (
    f"Expected max_llm_threads=15, got {dashboard_old.max_llm_threads}"
)
assert dashboard_old.max_build_threads == 20, (
    f"Expected max_build_threads=20 (default), got {dashboard_old.max_build_threads}"
)
assert dashboard_old.max_concurrency == 15, (
    f"Expected max_concurrency=15, got {dashboard_old.max_concurrency}"
)
print("✅ Backward compatibility maintained")

# Test 3: Render config panel to verify display
print("\nTest 3: Testing panel rendering...")
try:
    config_panel = dashboard._render_config_panel()  # type: ignore[reportPrivateUsage]
    # Convert panel to string to check content
    import io

    from rich.console import Console

    console = Console(file=io.StringIO(), force_terminal=True)
    console.print(config_panel)
    output = console.file.getvalue()  # type: ignore[attr-defined]

    assert "Max LLM Threads" in output, "Max LLM Threads not found in config panel"
    assert "Max Build Threads" in output, "Max Build Threads not found in config panel"
    assert "Max Concurrency" not in output, (
        "Old Max Concurrency still shown in config panel"
    )
    print("✅ Config panel displays correctly")
except Exception as e:
    print(f"❌ Error rendering config panel: {e}")

# Test 4: Render progress panel to verify Max Concurrency removed
print("\nTest 4: Testing progress panel...")
try:
    dashboard.progress_stats = {
        "processed": 10,
        "total": 100,
        "successful": 8,
        "failed": 1,
        "skipped": 1,
        "llm_generated": 5,
        "llm_skipped": 3,
        "llm_in_flight": 2,
    }
    dashboard.processing = True

    progress_panel = dashboard._render_progress_panel()  # type: ignore[reportPrivateUsage]
    import io

    from rich.console import Console

    console = Console(file=io.StringIO(), force_terminal=True)
    console.print(progress_panel)
    output = console.file.getvalue()  # type: ignore[attr-defined]

    # Check that Max Concurrency is NOT in the progress panel
    lines = output.split("\n")
    progress_lines = [line for line in lines if "Concurrency" in line]

    if progress_lines:
        print(f"❌ Max Concurrency still appears in progress panel: {progress_lines}")
    else:
        print("✅ Max Concurrency removed from progress panel")

except Exception as e:
    print(f"❌ Error rendering progress panel: {e}")

print("\n🎉 All dashboard tests passed!")

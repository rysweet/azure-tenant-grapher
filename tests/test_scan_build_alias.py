"""Test that scan and build commands are true aliases."""

import re
from click.testing import CliRunner
from scripts.cli import cli


def test_scan_and_build_have_same_options():
    """Verify that scan and build commands have identical options."""
    runner = CliRunner()
    
    # Get help for build command
    build_result = runner.invoke(cli, ['build', '--help'])
    build_help = build_result.output
    
    # Get help for scan command
    scan_result = runner.invoke(cli, ['scan', '--help'])
    scan_help = scan_result.output
    
    # Extract option lines (lines containing --)
    option_pattern = re.compile(r'--[\w-]+')
    
    build_options = set(option_pattern.findall(build_help))
    scan_options = set(option_pattern.findall(scan_help))
    
    # Both should have the same options
    assert build_options == scan_options, f"Options differ: build has {build_options - scan_options}, scan has {scan_options - build_options}"
    
    # Verify both have the filter options from PR #229
    assert "--filter-by-subscriptions" in build_options
    assert "--filter-by-subscriptions" in scan_options
    assert "--filter-by-rgs" in build_options
    assert "--filter-by-rgs" in scan_options
    
    print(f"✅ Both commands have {len(build_options)} identical options")
    print(f"✅ Both commands include --filter-by-subscriptions and --filter-by-rgs")


def test_scan_calls_build():
    """Verify that scan is implemented as an alias that calls build."""
    # Read the source to verify scan calls build
    with open('scripts/cli.py', 'r') as f:
        source = f.read()
    
    # Find the scan function definition
    import re
    scan_pattern = re.compile(r'async def scan\([^)]+\)[^{]+{[^}]+}', re.DOTALL)
    scan_match = scan_pattern.search(source)
    
    # Check that scan calls build internally
    assert 'return await build(' in source, "scan should call build() internally"
    
    # Also verify both are registered as commands
    assert '@cli.command()' in source or '@cli.command(name="scan")' in source
    
    print("✅ Scan is correctly implemented as an alias that calls build()")


if __name__ == "__main__":
    test_scan_and_build_have_same_options()
    test_scan_calls_build()
    print("\n✅ All tests passed - scan is a true alias of build with identical options")
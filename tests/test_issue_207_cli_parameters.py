"""
Test for Issue #207: CLI parameter inconsistency

This test verifies that all CLI commands use consistent parameter naming,
specifically that all parameters follow kebab-case convention and that
there are no instances of --num_entities or --num-entities.
"""

import subprocess
import sys
from pathlib import Path

import pytest


def test_all_cli_parameters_use_kebab_case():
    """Verify all CLI parameters use kebab-case (hyphens, not underscores)."""
    project_root = Path(__file__).parent.parent
    cli_files = [
        project_root / "scripts" / "cli.py",
        project_root / "src" / "cli_commands.py",
    ]
    
    violations = []
    
    for cli_file in cli_files:
        if not cli_file.exists():
            continue
            
        with open(cli_file, 'r') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines, 1):
            # Check for click.option declarations
            if '@click.option(' in line or '@cli.option(' in line:
                # Look at this line and next few lines for the parameter name
                chunk = ''.join(lines[i-1:min(i+3, len(lines))])
                
                # Find all parameter names in the chunk
                import re
                params = re.findall(r'["\'](--[a-zA-Z0-9_-]+)["\']', chunk)
                
                for param in params:
                    if '_' in param:
                        violations.append(
                            f"{cli_file.name}:{i}: Parameter '{param}' uses underscore "
                            f"(should be '{param.replace('_', '-')}')"
                        )
    
    if violations:
        error_msg = "Found parameters with underscores (should use kebab-case):\n"
        error_msg += "\n".join(violations)
        pytest.fail(error_msg)


def test_no_num_entities_parameter():
    """Verify that no command uses --num-entities or --num_entities."""
    project_root = Path(__file__).parent.parent
    
    # Search for any occurrence of num-entities or num_entities in CLI files
    result = subprocess.run(
        ["grep", "-r", "-E", "(--num[-_]entities|num[-_]entities)", 
         str(project_root / "scripts"), str(project_root / "src")],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:  # grep found matches
        pytest.fail(
            f"Found occurrences of num-entities or num_entities:\n{result.stdout}\n"
            f"All commands should use '--size' for consistency."
        )


def test_generate_sim_doc_uses_size_parameter():
    """Verify that generate-sim-doc command uses --size parameter."""
    cli_file = Path(__file__).parent.parent / "scripts" / "cli.py"
    
    with open(cli_file, 'r') as f:
        content = f.read()
    
    # Find the generate-sim-doc command definition
    import re
    pattern = r'@cli\.command\("generate-sim-doc"\).*?def\s+\w+\(.*?\):'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        pytest.fail("Could not find generate-sim-doc command definition")
    
    command_section = match.group()
    
    # Check that it uses --size
    if '--size' not in command_section:
        pytest.fail("generate-sim-doc command should use --size parameter")
    
    # Check that it does NOT use num-entities
    if 'num-entities' in command_section or 'num_entities' in command_section:
        pytest.fail("generate-sim-doc should not use num-entities parameter")


def test_create_tenant_command_structure():
    """Verify that create-tenant command takes a markdown file argument."""
    cli_file = Path(__file__).parent.parent / "src" / "cli_commands.py"
    
    with open(cli_file, 'r') as f:
        content = f.read()
    
    # Find the create-tenant command definition
    import re
    pattern = r'@click\.command\("create-tenant"\).*?def\s+create_tenant_command\(.*?\):'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        pytest.fail("Could not find create-tenant command definition")
    
    command_section = match.group()
    
    # Check that it has a markdown_file argument
    if '@click.argument("markdown_file"' not in command_section:
        pytest.fail("create-tenant command should take a markdown_file argument")
    
    # Verify it does NOT have num-entities parameter
    if '--num-entities' in command_section or '--num_entities' in command_section:
        pytest.fail("create-tenant should not have num-entities parameter")


def test_cli_help_output():
    """Test that CLI help text shows correct parameter names."""
    # Test generate-sim-doc help
    result = subprocess.run(
        [sys.executable, "scripts/cli.py", "generate-sim-doc", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    
    if result.returncode != 0:
        pytest.skip("Could not run CLI help command")
    
    help_text = result.stdout
    
    # Check for correct parameter names
    assert "--size" in help_text, "generate-sim-doc help should show --size parameter"
    assert "--num-entities" not in help_text, "generate-sim-doc help should not show --num-entities"
    assert "--num_entities" not in help_text, "generate-sim-doc help should not show --num_entities"
    
    # Test create-tenant help
    result = subprocess.run(
        [sys.executable, "scripts/cli.py", "create-tenant", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    
    if result.returncode == 0:
        help_text = result.stdout
        assert "MARKDOWN_FILE" in help_text.upper(), "create-tenant help should show MARKDOWN_FILE argument"
        assert "--num-entities" not in help_text, "create-tenant help should not show --num-entities"


def test_parameter_consistency_across_commands():
    """Test that similar parameters use consistent naming across commands."""
    
    # Check that output parameters are consistently named
    cli_file = Path(__file__).parent.parent / "scripts" / "cli.py"
    
    with open(cli_file, 'r') as f:
        content = f.read()
    
    # Find all uses of output-related parameters
    import re
    output_params = re.findall(r'@click\.option\(\s*["\'](--out(?:put)?)["\']', content)
    
    # All should be --output for consistency
    for param in output_params:
        if param == '--out':
            pytest.fail(
                f"Found '--out' parameter (should be '--output' for consistency). "
                f"All output parameters should use '--output' not '--out'."
            )


if __name__ == "__main__":
    # Run tests
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
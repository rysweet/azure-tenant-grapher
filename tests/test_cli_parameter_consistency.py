"""
Test CLI Parameter Consistency

This test ensures that all CLI parameters use kebab-case (e.g., --tenant-id)
and none use underscores (e.g., --tenant_id).
"""

import ast
import os
import re
from pathlib import Path
from typing import List, Tuple


def find_python_files(directory: Path, pattern: str = "*.py") -> List[Path]:
    """Find all Python files in a directory recursively."""
    return list(directory.rglob(pattern))


def extract_click_options_from_file(file_path: Path) -> List[Tuple[str, int, str]]:
    """
    Extract all @click.option() and @click.argument() decorators from a Python file.
    
    Returns a list of tuples: (parameter_name, line_number, file_path)
    """
    parameters = []
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Find all @click.option decorators with their first string argument
        # Pattern matches @click.option("--parameter-name", ...) or @click.option('--parameter-name', ...)
        option_pattern = r'@click\.option\s*\(\s*["\']([^"\']+)["\']'
        
        for line_num, line in enumerate(content.splitlines(), 1):
            match = re.search(option_pattern, line)
            if match:
                param = match.group(1)
                if param.startswith('--'):
                    parameters.append((param, line_num, str(file_path)))
                    
        # Also check for multiline @click.option where the parameter is on the next line
        multiline_pattern = r'@click\.option\s*\(\s*\n\s*["\']([^"\']+)["\']'
        matches = re.finditer(multiline_pattern, content)
        for match in matches:
            param = match.group(1)
            if param.startswith('--'):
                # Find the line number
                line_num = content[:match.start()].count('\n') + 1
                parameters.append((param, line_num, str(file_path)))
                
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        
    return parameters


def test_cli_parameters_use_kebab_case():
    """Test that all CLI parameters use kebab-case, not underscores."""
    
    # Find the project root (where scripts/ directory is)
    current_dir = Path(__file__).parent.parent
    
    # Directories to check for CLI commands
    directories_to_check = [
        current_dir / "scripts",
        current_dir / "src",
    ]
    
    all_parameters = []
    
    # Collect all CLI parameters
    for directory in directories_to_check:
        if directory.exists():
            for py_file in find_python_files(directory):
                # Skip test files
                if 'test' in py_file.name.lower():
                    continue
                    
                parameters = extract_click_options_from_file(py_file)
                all_parameters.extend(parameters)
    
    # Check for underscore usage
    underscore_params = []
    for param, line_num, file_path in all_parameters:
        # Remove the -- prefix for checking
        param_name = param[2:] if param.startswith('--') else param
        
        # Check if parameter name contains underscores
        if '_' in param_name:
            underscore_params.append((param, line_num, file_path))
    
    # Report findings
    if underscore_params:
        print("\n❌ Found CLI parameters with underscores (should use kebab-case):")
        for param, line_num, file_path in underscore_params:
            relative_path = os.path.relpath(file_path, current_dir)
            print(f"  {relative_path}:{line_num} - {param}")
            # Suggest the kebab-case version
            suggested = param.replace('_', '-')
            print(f"    Suggested: {suggested}")
        
        assert False, f"Found {len(underscore_params)} CLI parameters with underscores"
    else:
        print(f"\n✅ All {len(all_parameters)} CLI parameters use kebab-case correctly")
        
    # Also verify we found some parameters (sanity check)
    assert len(all_parameters) > 0, "No CLI parameters found - check the test configuration"
    
    # Print summary of checked parameters
    print(f"\nChecked {len(all_parameters)} CLI parameters across {len(set(p[2] for p in all_parameters))} files")
    
    # Show a sample of parameters for verification
    print("\nSample of CLI parameters found (first 10):")
    for param, _, file_path in all_parameters[:10]:
        relative_path = os.path.relpath(file_path, current_dir)
        print(f"  {relative_path}: {param}")


def test_no_python_variables_with_hyphens():
    """Test that Python function parameters don't use hyphens (they should use underscores)."""
    
    current_dir = Path(__file__).parent.parent
    
    # This is correct - Python variables should use underscores, not hyphens
    # This test just ensures we're following Python naming conventions
    
    directories_to_check = [
        current_dir / "scripts",
        current_dir / "src",
    ]
    
    hyphen_variables = []
    
    for directory in directories_to_check:
        if directory.exists():
            for py_file in find_python_files(directory):
                # Skip test files
                if 'test' in py_file.name.lower():
                    continue
                    
                try:
                    with open(py_file, 'r') as f:
                        content = f.read()
                    
                    # Parse the AST to find function definitions
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            for arg in node.args.args:
                                if '-' in arg.arg:
                                    line_num = node.lineno
                                    hyphen_variables.append((arg.arg, line_num, str(py_file)))
                                    
                except Exception as e:
                    # Skip files that can't be parsed
                    continue
    
    if hyphen_variables:
        print("\n❌ Found Python function parameters with hyphens (should use underscores):")
        for var_name, line_num, file_path in hyphen_variables:
            relative_path = os.path.relpath(file_path, current_dir)
            print(f"  {relative_path}:{line_num} - {var_name}")
            suggested = var_name.replace('-', '_')
            print(f"    Suggested: {suggested}")
        
        assert False, f"Found {len(hyphen_variables)} Python parameters with hyphens"
    else:
        print("\n✅ All Python function parameters use underscores correctly (no hyphens)")


if __name__ == "__main__":
    print("Testing CLI Parameter Consistency...")
    print("=" * 60)
    
    test_cli_parameters_use_kebab_case()
    print("\n" + "=" * 60)
    test_no_python_variables_with_hyphens()
    
    print("\n" + "=" * 60)
    print("✅ All CLI parameter consistency tests passed!")
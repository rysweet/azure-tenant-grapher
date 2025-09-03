"""Test CLI parameter naming consistency across all commands."""

import ast
import re
from pathlib import Path
from typing import Dict, List, Set

import pytest


class ClickOptionVisitor(ast.NodeVisitor):
    """AST visitor to extract Click option definitions."""

    def __init__(self):
        self.commands: Dict[str, List[str]] = {}
        self.current_command = None
        self.issues: List[str] = []
        self.in_function = False
        self.function_stack = []

    def visit_FunctionDef(self, node):
        """Visit function definitions to track current command."""
        # Save previous command context
        self.function_stack.append((self.current_command, self.in_function))
        self.in_function = True
        
        # Check if this is a command handler or has @cli.command decorator
        for decorator in node.decorator_list:
            # Extract options from decorators first
            if isinstance(decorator, ast.Call):
                if (isinstance(decorator.func, ast.Attribute) and 
                    decorator.func.attr == 'option'):
                    # This is an option decorator, save for current function
                    if node.name not in self.commands:
                        self.commands[node.name] = []
                    self._extract_option_from_decorator(decorator, node.name)
                elif (isinstance(decorator.func, ast.Name) and 
                      decorator.func.id == 'option'):
                    if node.name not in self.commands:
                        self.commands[node.name] = []
                    self._extract_option_from_decorator(decorator, node.name)
            elif isinstance(decorator, ast.Attribute) and decorator.attr == 'option':
                # Direct @click.option usage
                pass  # Will be handled in visit_Call
                
        # Check if this function is a command
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if (isinstance(decorator.func, ast.Attribute) and 
                    decorator.func.attr == 'command'):
                    # Extract command name from decorator arguments
                    if decorator.args:
                        if isinstance(decorator.args[0], ast.Constant):
                            self.current_command = decorator.args[0].value
                        elif isinstance(decorator.args[0], ast.Str):
                            self.current_command = decorator.args[0].s
                    else:
                        # Use function name if no explicit command name
                        self.current_command = node.name.replace('_', '-')
                elif (isinstance(decorator.func, ast.Name) and 
                      decorator.func.id == 'command'):
                    # Handle @command("name") style
                    if decorator.args:
                        if isinstance(decorator.args[0], ast.Constant):
                            self.current_command = decorator.args[0].value
                        elif isinstance(decorator.args[0], ast.Str):
                            self.current_command = decorator.args[0].s
            elif isinstance(decorator, ast.Attribute) and decorator.attr == 'command':
                # Direct @cli.command usage
                self.current_command = node.name.replace('_', '-')
        
        # Continue visiting the function body
        self.generic_visit(node)
        
        # Restore previous command context
        prev = self.function_stack.pop()
        self.current_command = prev[0]
        self.in_function = prev[1]
        
    def _extract_option_from_decorator(self, decorator, command_name):
        """Extract option names from a decorator call."""
        if decorator.args:
            for arg in decorator.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    option_name = arg.value
                elif isinstance(arg, ast.Str):
                    option_name = arg.s
                else:
                    continue
                
                if option_name.startswith('--'):
                    self.commands[command_name].append(option_name)
                    
                    # Check for consistency issues
                    if '_' in option_name:
                        self.issues.append(
                            f"Command '{command_name}' uses underscore in parameter '{option_name}' "
                            f"(should be '{option_name.replace('_', '-')}')"
                        )

    def visit_Call(self, node):
        """Visit function calls to find click.option decorators."""
        if self.current_command:
            # Check if this is a click.option call
            is_click_option = False
            
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == 'option':
                    is_click_option = True
            elif isinstance(node.func, ast.Name):
                if node.func.id == 'option':
                    is_click_option = True
            
            if is_click_option and node.args:
                # Extract option names
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        option_name = arg.value
                    elif isinstance(arg, ast.Str):
                        option_name = arg.s
                    else:
                        continue
                    
                    if option_name.startswith('--'):
                        if self.current_command not in self.commands:
                            self.commands[self.current_command] = []
                        self.commands[self.current_command].append(option_name)
                        
                        # Check for consistency issues
                        if '_' in option_name:
                            self.issues.append(
                                f"Command '{self.current_command}' uses underscore in parameter '{option_name}' "
                                f"(should be '{option_name.replace('_', '-')}')"
                            )
        
        self.generic_visit(node)


def extract_cli_parameters(file_path: Path) -> tuple[Dict[str, List[str]], List[str]]:
    """Extract all CLI command parameters from a Python file."""
    with open(file_path, 'r') as f:
        tree = ast.parse(f.read())
    
    visitor = ClickOptionVisitor()
    visitor.visit(tree)
    
    return visitor.commands, visitor.issues


def test_cli_parameter_consistency():
    """Test that all CLI parameters use consistent kebab-case naming."""
    # Find CLI files
    project_root = Path(__file__).parent.parent
    cli_files = [
        project_root / "scripts" / "cli.py",
        project_root / "src" / "cli_commands.py",
    ]
    
    all_commands = {}
    all_issues = []
    
    for cli_file in cli_files:
        if cli_file.exists():
            commands, issues = extract_cli_parameters(cli_file)
            all_commands.update(commands)
            all_issues.extend(issues)
    
    # Check for underscore usage in parameter names
    underscore_params = []
    for command, params in all_commands.items():
        for param in params:
            if '_' in param:
                underscore_params.append(f"{command}: {param}")
    
    # Check for inconsistent parameter naming across commands
    param_variations = {}
    for command, params in all_commands.items():
        for param in params:
            # Normalize to identify variations (remove -- and convert to lowercase)
            normalized = param[2:].lower().replace('-', '').replace('_', '')
            if normalized not in param_variations:
                param_variations[normalized] = []
            param_variations[normalized].append((command, param))
    
    # Find parameters with multiple naming styles
    inconsistent_params = {}
    for normalized, occurrences in param_variations.items():
        unique_styles = set(param for _, param in occurrences)
        if len(unique_styles) > 1:
            inconsistent_params[normalized] = occurrences
    
    # Generate detailed error report
    error_messages = []
    
    if underscore_params:
        error_messages.append("Parameters using underscores (should use kebab-case):")
        for param in underscore_params:
            error_messages.append(f"  - {param}")
    
    if inconsistent_params:
        error_messages.append("\nParameters with inconsistent naming across commands:")
        for normalized, occurrences in inconsistent_params.items():
            error_messages.append(f"  Parameter '{normalized}' has multiple styles:")
            for cmd, param in occurrences:
                error_messages.append(f"    - {cmd}: {param}")
    
    if all_issues:
        error_messages.append("\nAdditional consistency issues found:")
        for issue in all_issues:
            error_messages.append(f"  - {issue}")
    
    # Print summary for debugging
    print("\n=== CLI Parameter Analysis ===")
    print(f"Total commands found: {len(all_commands)}")
    for cmd, params in sorted(all_commands.items()):
        if params:  # Only show commands with parameters
            print(f"\n{cmd}:")
            for param in sorted(params):
                print(f"  {param}")
    
    # Assert all parameters follow kebab-case convention
    if error_messages:
        pytest.fail("\n".join(error_messages))


def test_preferred_parameter_naming():
    """Test that common parameters use preferred naming conventions."""
    # Define preferred naming for common parameters
    preferred_names = {
        'tenant-id': ['--tenant-id'],  # Not --tenant_id
        'output': ['--output', '-o'],  # Not --out
        'format': ['--format', '-f'],  # Not --fmt
        'verbose': ['--verbose', '-v'],  # Not --verb
        'debug': ['--debug'],  # Not --dbg
        'size': ['--size'],  # Not --num-entities or --num_entities
        'limit': ['--limit'],  # Not --max or --maximum
        'force': ['--force', '-f'],  # Not --skip-confirmation
        'path': ['--path', '-p'],  # Standard path parameter
    }
    
    project_root = Path(__file__).parent.parent
    cli_files = [
        project_root / "scripts" / "cli.py",
        project_root / "src" / "cli_commands.py",
    ]
    
    all_commands = {}
    for cli_file in cli_files:
        if cli_file.exists():
            commands, _ = extract_cli_parameters(cli_file)
            all_commands.update(commands)
    
    violations = []
    
    for param_type, preferred in preferred_names.items():
        for command, params in all_commands.items():
            for param in params:
                # Check if this parameter seems to be of this type
                param_lower = param.lower()
                
                # Skip if it matches preferred naming
                if param in preferred:
                    continue
                
                # Check for variations that should use the preferred name
                if param_type == 'tenant-id' and 'tenant' in param_lower and 'id' in param_lower:
                    if param not in preferred:
                        violations.append(
                            f"{command}: '{param}' should be '--tenant-id'"
                        )
                elif param_type == 'size' and ('num' in param_lower and 'entit' in param_lower):
                    violations.append(
                        f"{command}: '{param}' should be '--size' for consistency"
                    )
    
    if violations:
        error_msg = "Parameters not using preferred naming conventions:\n"
        error_msg += "\n".join(f"  - {v}" for v in violations)
        pytest.fail(error_msg)


def test_no_num_entities_parameter():
    """Test that no command uses --num-entities or --num_entities (should use --size)."""
    project_root = Path(__file__).parent.parent
    cli_files = [
        project_root / "scripts" / "cli.py",
        project_root / "src" / "cli_commands.py",
    ]
    
    all_commands = {}
    for cli_file in cli_files:
        if cli_file.exists():
            commands, _ = extract_cli_parameters(cli_file)
            all_commands.update(commands)
    
    violations = []
    
    for command, params in all_commands.items():
        for param in params:
            param_lower = param.lower()
            if 'num-entities' in param_lower or 'num_entities' in param_lower:
                violations.append(f"{command}: uses '{param}' (should use '--size' for consistency)")
    
    if violations:
        error_msg = "Found deprecated --num-entities parameter usage:\n"
        error_msg += "\n".join(f"  - {v}" for v in violations)
        pytest.fail(error_msg)


def test_all_commands_documented():
    """Test that all CLI commands are properly documented in help text."""
    # This is a placeholder for documentation testing
    # In a real scenario, we'd check that each command has a docstring
    pass


if __name__ == "__main__":
    # Run the tests directly for debugging
    test_cli_parameter_consistency()
    print("\n" + "="*50 + "\n")
    test_preferred_parameter_naming()
    print("\n" + "="*50 + "\n")
    test_no_num_entities_parameter()
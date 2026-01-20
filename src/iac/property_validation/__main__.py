"""CLI entry point for property validation system.

This module allows the package to be run as:
    python -m iac.property_validation <command>

Philosophy:
- Simple entry point delegation
- Proper exit code handling
- Clean error handling
"""

import sys

from .cli import main

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)  # Standard Unix exit code for SIGINT
    except Exception as e:
        print(f"\nFatal error: {e}", file=sys.stderr)
        sys.exit(1)

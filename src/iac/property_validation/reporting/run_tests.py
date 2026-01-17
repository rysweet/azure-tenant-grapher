#!/usr/bin/env python3
"""Standalone test runner for coverage reporting.

This runner can be executed directly without pytest or complex imports.
"""

import sys
from pathlib import Path

# Add the src directory to the path
src_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_dir))

# Now import and run tests
from iac.property_validation.reporting.tests.test_reporting import run_all_tests

if __name__ == "__main__":
    run_all_tests()

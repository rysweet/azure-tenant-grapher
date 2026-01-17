#!/usr/bin/env python3
"""Standalone property coverage validation script.

This script runs the property validation system without requiring
the full iac module dependencies.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iac.property_validation.cli import main

if __name__ == "__main__":
    sys.exit(main())

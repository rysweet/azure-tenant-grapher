"""IaC format detection for deployment orchestration.

This module provides format detection capabilities for Infrastructure as Code
templates (Terraform, Bicep, ARM).

Philosophy:
- Single responsibility: Format detection only
- Standard library focus: Minimal dependencies
- Self-contained and regeneratable
"""

import json
import logging
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

IaCFormat = Literal["terraform", "bicep", "arm"]


def detect_iac_format(iac_dir: Path) -> Optional[IaCFormat]:
    """Auto-detect IaC format from directory contents.

    Examines files in the directory to determine which IaC format is being used.
    Detection order:
    1. Terraform (.tf or .tf.json files)
    2. Bicep (.bicep files)
    3. ARM templates (.json files with deployment schema)

    Args:
        iac_dir: Directory containing IaC files

    Returns:
        Detected format ('terraform', 'bicep', 'arm') or None if unknown

    Example:
        >>> from pathlib import Path
        >>> detect_iac_format(Path("/path/to/terraform"))
        'terraform'
    """
    if not iac_dir.exists() or not iac_dir.is_dir():
        logger.debug(f"Path does not exist or is not a directory: {iac_dir}")
        return None

    # Check for Terraform files (both .tf and .tf.json)
    if list(iac_dir.glob("*.tf")) or list(iac_dir.glob("*.tf.json")):
        logger.info(f"Detected Terraform format in {iac_dir}")
        return "terraform"

    # Check for Bicep files
    if list(iac_dir.glob("*.bicep")):
        logger.info(f"Detected Bicep format in {iac_dir}")
        return "bicep"

    # Check for ARM templates (JSON with deployment schema)
    for json_file in iac_dir.glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
                if "$schema" in data and "deploymentTemplate" in data.get("$schema", ""):
                    logger.info(f"Detected ARM template format in {iac_dir}")
                    return "arm"
        except Exception as e:
            logger.debug(f"Failed to parse {json_file}: {e}")
            continue

    logger.warning(f"Could not detect IaC format in {iac_dir}")
    return None


__all__ = ["detect_iac_format", "IaCFormat"]

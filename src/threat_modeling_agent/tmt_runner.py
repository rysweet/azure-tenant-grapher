"""
Microsoft Threat Modeling Tool (TMT) runner module.
Provides a stub for invoking TMT CLI or Docker and parsing output.
"""

import csv
import logging
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional


def run_tmt(
    dfd_artifact: str, logger: Optional[logging.Logger] = None
) -> List[Dict[str, Any]]:
    """
    Invoke the Microsoft Threat Modeling Tool (TMT) on a DFD artifact (.tm7 file).
    Args:
        dfd_artifact (str): Path to the .tm7 file representing the DFD.
        logger (logging.Logger, optional): Logger for logging errors and info.
    Returns:
        list: List of threats (dicts).
    """
    if logger is None:
        logger = logging.getLogger("TMTRunner")

    try:
        # Check if dfd_artifact ends with .tm7
        if not dfd_artifact.lower().endswith(".tm7"):
            logger.error(
                "TMT requires a .tm7 file as input. Received: %s", dfd_artifact
            )
            return []

        # Prepare output file for threats
        with tempfile.TemporaryDirectory() as tmpdir:
            threats_csv = os.path.join(tmpdir, "threats.csv")
            tmt_exe = os.environ.get("TMT_EXE", "TMT.exe")  # Path to TMT CLI
            cmd = [tmt_exe, "-input", dfd_artifact, "-exportThreats", threats_csv]

            logger.info(f"Invoking TMT CLI: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                logger.info(f"TMT CLI output: {result.stdout}")
                if result.stderr:
                    logger.warning(f"TMT CLI stderr: {result.stderr}")
            except subprocess.CalledProcessError as e:
                logger.error(f"TMT CLI failed: {e.stderr or e}")
                return []

            # Parse the threats CSV
            threats = []
            if os.path.exists(threats_csv):
                with open(threats_csv, encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        threats.append(
                            {
                                "id": row.get("Id") or row.get("id"),
                                "title": row.get("Title") or row.get("title"),
                                "description": row.get("Description")
                                or row.get("description"),
                                "severity": row.get("Severity") or row.get("severity"),
                                "category": row.get("Category") or row.get("category"),
                                "element": row.get("Element") or row.get("element"),
                            }
                        )
                logger.info(f"TMT invocation successful. {len(threats)} threats found.")
            else:
                logger.error("TMT did not produce a threats CSV output.")
            return threats
    except Exception as e:
        logger.error(f"TMT invocation failed: {e}")
    return []


def enumerate_threats(threats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stub: enumerate threats for testing."""
    return threats


def map_controls(threats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stub: map controls for testing."""
    for threat in threats:
        threat["asb_controls"] = [{"control_id": "ASB-DS-4"}]
    return threats

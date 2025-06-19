import logging
from typing import Any, Dict, List, Optional


def enumerate_threats(
    tmt_output: Any, logger: Optional[logging.Logger] = None
) -> List[Dict[str, Any]]:
    """
    Process TMT output and produce a structured threat list.
    This is a stub implementation; real logic will be added later.

    Args:
        tmt_output: Output from the TMT runner (list of threats or DataFrame).
        logger: Optional logger for error reporting.

    Returns:
        List of structured threat dicts.
    """
    if logger is None:
        logger = logging.getLogger("ThreatEnumerator")

    try:
        if not tmt_output or not isinstance(tmt_output, list):
            logger.warning(
                "TMT output is empty or not a list. Returning empty threat list."
            )
            return []

        # Deduplicate threats by (title, description, severity)
        seen = set()
        structured_threats = []
        for threat in tmt_output:
            title = threat.get("title", "")
            description = threat.get("description", "")
            severity = threat.get("severity", "unknown")
            dedup_key = (
                title.strip().lower(),
                description.strip().lower(),
                severity.strip().lower(),
            )
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Optionally map TMT category to STRIDE
            tmt_category = threat.get("category", "") or threat.get("Category", "")
            stride_map = {
                "Spoofing": "S",
                "Tampering": "T",
                "Repudiation": "R",
                "Information Disclosure": "I",
                "Denial of Service": "D",
                "Elevation of Privilege": "E",
            }
            stride = stride_map.get(tmt_category, "")

            structured_threats.append(
                {
                    "id": threat.get("id", threat.get("Id", "unknown")),
                    "title": title,
                    "description": description,
                    "severity": severity,
                    "category": tmt_category,
                    "stride": stride,
                    "element": threat.get("element", threat.get("Element", "")),
                    "raw": threat,
                }
            )
        logger.info(f"Enumerated {len(structured_threats)} unique threats.")
        return structured_threats

    except Exception as e:
        logger.error(f"Threat enumeration failed: {e}")
        return []

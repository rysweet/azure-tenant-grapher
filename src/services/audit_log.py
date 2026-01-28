"""
Tamper-Proof Audit Log for Tenant Reset Operations (Issue #627).

This module implements a cryptographic hash chain for audit logging,
ensuring that no entries can be modified or deleted without detection.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class AuditEntry:
    """Single audit log entry."""

    event: str
    timestamp: float
    tenant_id: str
    details: Dict
    previous_hash: str
    hash: str


class TamperProofAuditLog:
    """
    Tamper-proof audit log using cryptographic hash chain.

    Each entry contains:
    - event: Event name
    - timestamp: Unix timestamp
    - tenant_id: Azure tenant ID
    - details: Event-specific data
    - previous_hash: Hash of previous entry (forms chain)
    - hash: SHA-256 hash of current entry

    Security:
    - Entries form a cryptographic chain
    - Any modification breaks the chain
    - Genesis entry starts with "0" * 64 as previous_hash
    """

    def __init__(self, log_path: Path):
        """
        Initialize audit log.

        Args:
            log_path: Path to audit log file (.jsonl format)
        """
        self.log_path = log_path
        self._initialize_if_needed()

    def _initialize_if_needed(self):
        """Initialize audit log with genesis entry if it doesn't exist."""
        if not self.log_path.exists():
            genesis_entry = {
                "event": "audit_log_initialized",
                "timestamp": time.time(),
                "tenant_id": "system",
                "details": {},
                "previous_hash": "0" * 64,  # Genesis hash
            }
            genesis_entry["hash"] = self._compute_entry_hash(genesis_entry)

            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "w") as f:
                f.write(json.dumps(genesis_entry) + "\n")

    def _compute_entry_hash(self, entry: Dict) -> str:
        """
        Compute SHA-256 hash of audit log entry.

        Args:
            entry: Audit log entry (without 'hash' field)

        Returns:
            Hexadecimal hash string
        """
        # Create copy without 'hash' field
        entry_copy = {k: v for k, v in entry.items() if k != "hash"}
        entry_json = json.dumps(entry_copy, sort_keys=True)
        return hashlib.sha256(entry_json.encode()).hexdigest()

    def append(self, event: str, tenant_id: str, details: Dict) -> str:
        """
        Append tamper-proof entry to audit log.

        Args:
            event: Event name
            tenant_id: Azure tenant ID
            details: Event-specific details

        Returns:
            Hash of appended entry
        """
        # Read last entry to get previous hash
        with open(self.log_path) as f:
            lines = f.readlines()
            last_entry = json.loads(lines[-1]) if lines else None
            previous_hash = last_entry["hash"] if last_entry else "0" * 64

        # Create new entry
        entry = {
            "event": event,
            "timestamp": time.time(),
            "tenant_id": tenant_id,
            "details": details,
            "previous_hash": previous_hash,
        }
        entry["hash"] = self._compute_entry_hash(entry)

        # Append to log
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return entry["hash"]

    def verify_integrity(self) -> bool:
        """
        Verify integrity of entire audit log chain.

        Returns:
            True if chain is valid, False if tampered

        Raises:
            ValueError: If audit log is corrupted
        """
        with open(self.log_path) as f:
            lines = f.readlines()

        if not lines:
            return True  # Empty log is valid

        previous_hash = None

        for i, line in enumerate(lines):
            entry = json.loads(line)

            # Verify hash
            stored_hash = entry["hash"]
            computed_hash = self._compute_entry_hash(entry)

            if stored_hash != computed_hash:
                raise ValueError(
                    f"AUDIT LOG TAMPERING DETECTED: Entry {i} hash mismatch. "
                    f"Expected: {stored_hash}, Computed: {computed_hash}"
                )

            # Verify chain
            if i == 0:
                # Genesis entry
                if entry["previous_hash"] != "0" * 64:
                    raise ValueError(
                        "AUDIT LOG TAMPERING DETECTED: Genesis entry has invalid previous_hash"
                    )
            else:
                if entry["previous_hash"] != previous_hash:
                    raise ValueError(
                        f"AUDIT LOG TAMPERING DETECTED: Entry {i} previous_hash mismatch. "
                        f"Expected: {previous_hash}, Found: {entry['previous_hash']}"
                    )

            previous_hash = stored_hash

        return True

    def get_entries(
        self, event: Optional[str] = None, tenant_id: Optional[str] = None
    ) -> List[AuditEntry]:
        """
        Get audit log entries, optionally filtered.

        Args:
            event: Filter by event name (optional)
            tenant_id: Filter by tenant ID (optional)

        Returns:
            List of audit entries
        """
        with open(self.log_path) as f:
            lines = f.readlines()

        entries = []
        for line in lines:
            entry_dict = json.loads(line)

            # Apply filters
            if event and entry_dict["event"] != event:
                continue
            if tenant_id and entry_dict["tenant_id"] != tenant_id:
                continue

            entries.append(
                AuditEntry(
                    event=entry_dict["event"],
                    timestamp=entry_dict["timestamp"],
                    tenant_id=entry_dict["tenant_id"],
                    details=entry_dict["details"],
                    previous_hash=entry_dict["previous_hash"],
                    hash=entry_dict["hash"],
                )
            )

        return entries

    def get_last_entry(self) -> Optional[AuditEntry]:
        """
        Get the most recent audit log entry.

        Returns:
            Last audit entry, or None if log is empty
        """
        with open(self.log_path) as f:
            lines = f.readlines()

        if not lines:
            return None

        entry_dict = json.loads(lines[-1])
        return AuditEntry(
            event=entry_dict["event"],
            timestamp=entry_dict["timestamp"],
            tenant_id=entry_dict["tenant_id"],
            details=entry_dict["details"],
            previous_hash=entry_dict["previous_hash"],
            hash=entry_dict["hash"],
        )

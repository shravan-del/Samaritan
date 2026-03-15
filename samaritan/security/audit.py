"""
audit.py - SHA-256 hash-chained tamper-evident audit log.

Every Guardian decision, Nova call, and skill execution is logged
with timestamp, role, action, outcome, and chain hash.

Exposes log via FastAPI route (integrated in ui/server.py).
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class AuditLog:
    """
    Append-only tamper-evident audit log.

    Each entry contains:
      - seq: sequence number
      - timestamp: Unix timestamp
      - role: user role
      - action: what was attempted
      - outcome: result (success/denied/error/blocked)
      - details: arbitrary dict
      - prev_hash: hash of previous entry
      - hash: SHA-256 of this entry's fields
    """

    def __init__(
        self,
        persist_path: Optional[str] = None,
        max_memory_entries: int = 10000,
    ):
        self._entries: list[dict] = []
        self._lock = threading.Lock()
        self._seq = 0
        self._prev_hash = "0" * 64  # genesis hash
        self._max_entries = max_memory_entries
        self._persist_path = Path(persist_path) if persist_path else None

        if self._persist_path:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            if self._persist_path.exists():
                self._load_from_disk()

        logger.info(
            "AuditLog initialized | persist=%s entries=%d",
            self._persist_path,
            len(self._entries),
        )

    def _load_from_disk(self):
        """Load existing log from disk."""
        try:
            with open(self._persist_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = json.loads(line)
                        self._entries.append(entry)
                        self._seq = entry.get("seq", self._seq) + 1
                        self._prev_hash = entry.get("hash", self._prev_hash)
            logger.info("Loaded %d audit entries from disk.", len(self._entries))
        except Exception as e:
            logger.warning("Failed to load audit log: %s", e)

    def _persist_entry(self, entry: dict):
        """Append entry to disk log."""
        if self._persist_path:
            try:
                with open(self._persist_path, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception as e:
                logger.warning("Failed to persist audit entry: %s", e)

    def log(
        self,
        role: str,
        action: str,
        outcome: str,
        details: Optional[dict] = None,
    ) -> dict:
        """
        Append a new audit entry.

        Parameters
        ----------
        role    : User role (attorney, paralegal, etc.)
        action  : What was attempted (guardian_check, nova_call, skill_execute, etc.)
        outcome : Result string (allow, block, success, error, denied, etc.)
        details : Optional additional context.

        Returns the created entry dict.
        """
        with self._lock:
            seq = self._seq
            timestamp = time.time()

            # Build entry content for hashing
            entry_data = {
                "seq": seq,
                "timestamp": timestamp,
                "role": role,
                "action": action,
                "outcome": outcome,
                "details": details or {},
                "prev_hash": self._prev_hash,
            }

            # Compute entry hash (chain link)
            content_str = json.dumps(entry_data, sort_keys=True)
            entry_hash = _sha256(content_str)

            entry = {**entry_data, "hash": entry_hash}

            # Enforce memory limit (circular buffer)
            if len(self._entries) >= self._max_entries:
                self._entries.pop(0)

            self._entries.append(entry)
            self._prev_hash = entry_hash
            self._seq += 1

        self._persist_entry(entry)
        logger.debug("Audit: [%d] %s | %s | %s", seq, role, action, outcome)
        return entry

    def verify_chain(self) -> tuple[bool, Optional[str]]:
        """
        Verify the integrity of the entire audit chain.

        Returns (True, None) if valid, (False, reason) if tampered.
        """
        if not self._entries:
            return True, None

        prev_hash = "0" * 64

        for i, entry in enumerate(self._entries):
            # Reconstruct expected content
            entry_data = {
                "seq": entry["seq"],
                "timestamp": entry["timestamp"],
                "role": entry["role"],
                "action": entry["action"],
                "outcome": entry["outcome"],
                "details": entry["details"],
                "prev_hash": prev_hash,
            }
            expected_hash = _sha256(json.dumps(entry_data, sort_keys=True))

            if entry["hash"] != expected_hash:
                return False, f"Chain broken at entry {i} (seq={entry['seq']})"

            if entry["prev_hash"] != prev_hash:
                return False, f"Prev hash mismatch at entry {i}"

            prev_hash = entry["hash"]

        return True, None

    def get_entries(
        self,
        limit: int = 100,
        role_filter: Optional[str] = None,
        action_filter: Optional[str] = None,
        offset: int = 0,
    ) -> list[dict]:
        """Return filtered audit entries (newest first)."""
        entries = list(reversed(self._entries))

        if role_filter:
            entries = [e for e in entries if e.get("role") == role_filter]
        if action_filter:
            entries = [e for e in entries if e.get("action") == action_filter]

        return entries[offset: offset + limit]

    def get_summary(self) -> dict:
        """Return summary statistics."""
        total = len(self._entries)
        by_outcome: dict[str, int] = {}
        by_action: dict[str, int] = {}

        for entry in self._entries:
            outcome = entry.get("outcome", "unknown")
            action = entry.get("action", "unknown")
            by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
            by_action[action] = by_action.get(action, 0) + 1

        chain_valid, chain_error = self.verify_chain()

        return {
            "total_entries": total,
            "by_outcome": by_outcome,
            "by_action": by_action,
            "chain_valid": chain_valid,
            "chain_error": chain_error,
            "current_seq": self._seq,
        }

    def to_api_response(self, limit: int = 100) -> dict:
        """Serialize for API response."""
        summary = self.get_summary()
        entries = self.get_entries(limit=limit)
        return {
            "summary": summary,
            "entries": entries,
        }

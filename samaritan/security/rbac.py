"""
rbac.py - Role-Based Access Control for Veritas.

Roles: admin, attorney, paralegal, clinician, analyst, reviewer

Each role has:
  - allowed_skills: set of skill names
  - confirmation_required: skills requiring explicit user confirmation
  - memory_namespace: namespace prefix for vector memory
  - file_ops: bool - whether file system operations are allowed
  - network_ops: bool - whether network/web operations are allowed
  - matter_scoped: bool - whether memory is scoped per matter/case
  - phi_access: bool - whether PHI (Protected Health Information) access is logged specially
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default RBAC definitions (overridable via permissions.yaml)
DEFAULT_ROLES: dict[str, dict] = {
    "attorney": {
        "allowed_skills": [
            "case_lookup",
            "draft_motion",
            "document_search",
            "calendar",
            "billing",
        ],
        "confirmation_required": ["draft_motion", "billing"],
        "memory_namespace": "attorney",
        "description": "Full access to all legal tools.",
    },
    "paralegal": {
        "allowed_skills": [
            "case_lookup",
            "document_search",
            "calendar",
            "billing",
        ],
        "confirmation_required": ["billing"],
        "memory_namespace": "paralegal",
        "description": "Access to case and document tools; no motion drafting.",
    },
    "clinician": {
        "allowed_skills": [
            "case_lookup",
            "document_search",
        ],
        "confirmation_required": [],
        "memory_namespace": "clinician",
        "description": "Read-only clinical case access.",
    },
    "analyst": {
        "allowed_skills": [
            "case_lookup",
            "document_search",
            "billing",
        ],
        "confirmation_required": ["billing"],
        "memory_namespace": "analyst",
        "description": "Analytics and billing review access.",
    },
    "reviewer": {
        "allowed_skills": [
            "case_lookup",
            "document_search",
        ],
        "confirmation_required": [],
        "memory_namespace": "reviewer",
        "description": "Read-only review access.",
    },
}

DEFAULT_ROLES["admin"] = {
    "allowed_skills": [
        "case_lookup", "draft_motion", "document_search",
        "calendar", "billing", "web_search", "browser", "mcp",
    ],
    "confirmation_required": ["draft_motion", "billing", "mcp"],
    "memory_namespace": "admin",
    "file_ops": True,
    "network_ops": True,
    "matter_scoped": False,
    "phi_access": False,
    "description": "Full system access including MCP and browser automation.",
}

VALID_ROLES = set(DEFAULT_ROLES.keys())


class RBAC:
    """
    Role-Based Access Control enforcer.

    Loaded from config but falls back to DEFAULT_ROLES.
    Enforced at skill dispatch time in agent.py.
    """

    def __init__(self, roles_config: Optional[dict] = None):
        self._roles = {**DEFAULT_ROLES}
        if roles_config:
            self._merge_config(roles_config)
        logger.info("RBAC initialized with roles: %s", list(self._roles.keys()))

    def _merge_config(self, config: dict):
        """Merge external config into role definitions."""
        for role_name, role_data in config.items():
            if role_name in self._roles:
                self._roles[role_name].update(role_data)
            else:
                self._roles[role_name] = role_data
                logger.info("RBAC: added custom role '%s'", role_name)

    def is_valid_role(self, role: str) -> bool:
        return role in self._roles

    def can_use_skill(self, role: str, skill_name: str) -> bool:
        """Return True if role is allowed to use the given skill."""
        if role not in self._roles:
            logger.warning("RBAC: unknown role '%s'", role)
            return False
        allowed = self._roles[role].get("allowed_skills", [])
        permitted = skill_name in allowed
        if not permitted:
            logger.debug("RBAC denied: role=%s skill=%s", role, skill_name)
        return permitted

    def requires_confirmation(self, role: str, skill_name: str) -> bool:
        """Return True if this action requires explicit user confirmation."""
        if role not in self._roles:
            return True  # default deny
        return skill_name in self._roles[role].get("confirmation_required", [])

    def get_memory_namespace(self, role: str) -> str:
        """Return memory namespace prefix for this role."""
        if role not in self._roles:
            return "unknown"
        return self._roles[role].get("memory_namespace", role)

    def get_allowed_skills(self, role: str) -> list[str]:
        """Return list of skills allowed for this role."""
        if role not in self._roles:
            return []
        return list(self._roles[role].get("allowed_skills", []))

    def get_role_info(self, role: str) -> Optional[dict]:
        """Return full role config dict."""
        return self._roles.get(role)

    def is_matter_scoped(self, role: str) -> bool:
        """Return True if this role uses per-matter memory namespacing."""
        return bool(self._roles.get(role, {}).get("matter_scoped", False))

    def requires_phi_audit(self, role: str) -> bool:
        """Return True if this role requires PHI-level audit logging."""
        return bool(self._roles.get(role, {}).get("phi_access", False))

    def allows_network_ops(self, role: str) -> bool:
        """Return True if this role may perform network/web operations."""
        return bool(self._roles.get(role, {}).get("network_ops", False))

    def allows_file_ops(self, role: str) -> bool:
        """Return True if this role may perform file system operations."""
        return bool(self._roles.get(role, {}).get("file_ops", False))

    def list_roles(self) -> list[str]:
        return list(self._roles.keys())

    def enforce(self, role: str, skill_name: str) -> None:
        """
        Enforce RBAC. Raises PermissionError if denied.
        """
        if not self.can_use_skill(role, skill_name):
            raise PermissionError(
                f"Role '{role}' is not authorized to use skill '{skill_name}'."
            )

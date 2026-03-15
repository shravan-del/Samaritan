"""
case_lookup.py - Case lookup skill for Samaritan.

Searches mock case database for case information.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Mock case database
MOCK_CASES = {
    "CASE-001": {
        "id": "CASE-001",
        "title": "Smith v. Johnson",
        "client": "John Smith",
        "opposing_party": "Robert Johnson",
        "type": "Personal Injury",
        "status": "Active",
        "filed_date": "2024-03-15",
        "attorney": "Sarah Mitchell",
        "court": "Superior Court of California, Los Angeles County",
        "judge": "Hon. Patricia Chen",
        "next_hearing": "2024-08-20",
        "description": "Personal injury case arising from a motor vehicle accident on the 405 freeway.",
        "damages_sought": "$450,000",
    },
    "CASE-002": {
        "id": "CASE-002",
        "title": "TechCorp v. StartupAI",
        "client": "TechCorp International",
        "opposing_party": "StartupAI Inc.",
        "type": "Intellectual Property",
        "status": "Discovery",
        "filed_date": "2024-01-10",
        "attorney": "Marcus Webb",
        "court": "US District Court, Northern District of California",
        "judge": "Hon. David Kim",
        "next_hearing": "2024-09-05",
        "description": "Patent infringement claim regarding AI model architecture.",
        "damages_sought": "$12,000,000",
    },
    "CASE-003": {
        "id": "CASE-003",
        "title": "Estate of Rivera",
        "client": "Maria Rivera",
        "opposing_party": "N/A",
        "type": "Probate",
        "status": "Pending",
        "filed_date": "2024-05-22",
        "attorney": "Sarah Mitchell",
        "court": "Probate Court, Cook County",
        "judge": "Hon. James O'Brien",
        "next_hearing": "2024-07-30",
        "description": "Estate administration for the late Carlos Rivera.",
        "damages_sought": "N/A",
    },
    "CASE-004": {
        "id": "CASE-004",
        "title": "Chen Contract Dispute",
        "client": "Linda Chen",
        "opposing_party": "Apex Builders LLC",
        "type": "Contract",
        "status": "Pre-litigation",
        "filed_date": "2024-06-01",
        "attorney": "Marcus Webb",
        "court": "Pending filing",
        "judge": "TBD",
        "next_hearing": "TBD",
        "description": "Breach of construction contract; defective workmanship claim.",
        "damages_sought": "$85,000",
    },
    "CASE-005": {
        "id": "CASE-005",
        "title": "TechCorp v. Johnson Industries",
        "client": "Robert Johnson",           # ← same name as opposing party in CASE-001 → triggers conflict
        "opposing_party": "TechCorp International",
        "type": "Breach of Contract",
        "status": "Active",
        "filed_date": "2024-05-10",
        "attorney": "Sarah Mitchell",         # ← same attorney as CASE-001 → double conflict
        "court": "US District Court, Central District of California",
        "judge": "Hon. David Kim",
        "next_hearing": "2024-11-08",
        "description": "Breach of software development contract; Johnson Industries "
                       "disputes milestone deliverables and seeks $2.1M in damages.",
        "damages_sought": "$2,100,000",
    },
}

# Alias map: normalised user-facing names → canonical case IDs.
# Allows follow-up questions like "johnson case" or "johnson trial"
# to resolve to CASE-001 without requiring the exact ID.
CASE_ALIASES: dict[str, str] = {
    "JOHNSON":          "CASE-001",
    "JOHNSON CASE":     "CASE-001",
    "JOHNSON TRIAL":    "CASE-001",
    "SMITH V JOHNSON":  "CASE-001",
    "SMITH V. JOHNSON": "CASE-001",
    "SMITH VS JOHNSON": "CASE-001",
}


class CaseLookupSkill:
    name = "case_lookup"
    description = (
        "Look up case information by case ID or search by client name, case type, or status. "
        "Returns case details including parties, court, attorney, status, and hearing dates."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "case_id": {
                "type": "string",
                "description": "Specific case ID to look up (e.g., CASE-001)",
            },
            "search_term": {
                "type": "string",
                "description": "Search by client name, case type, or status (optional if case_id provided)",
            },
            "status_filter": {
                "type": "string",
                "description": "Filter by case status: Active, Discovery, Pending, Pre-litigation",
                "enum": ["Active", "Discovery", "Pending", "Pre-litigation"],
            },
        },
        "required": [],
    }

    def execute(self, params: dict, session=None) -> str:
        case_id = params.get("case_id", "").strip().upper()
        search_term = params.get("search_term", "").strip().lower()
        status_filter = params.get("status_filter", "").strip()

        # Alias resolution: "johnson case" → "CASE-001" etc.
        if case_id and case_id not in MOCK_CASES:
            case_id = CASE_ALIASES.get(case_id, case_id)

        # Session fallback: if no case_id, use the session's active case
        if not case_id and session and getattr(session, "case_id", None):
            if session.case_id != "global":
                case_id = session.case_id

        # Direct ID lookup
        if case_id:
            case = MOCK_CASES.get(case_id)
            if case:
                return self._format_case(case)
            return f"No case found with ID: {case_id}"

        # Search
        results = list(MOCK_CASES.values())

        if search_term:
            # Short-circuit: if search_term is a known alias, resolve directly
            resolved = CASE_ALIASES.get(search_term.upper().strip())
            if resolved:
                return self._format_case(MOCK_CASES[resolved])
            results = [
                c for c in results
                if (
                    search_term in c["client"].lower()
                    or search_term in c["title"].lower()
                    or search_term in c["type"].lower()
                    or search_term in c["id"].lower()
                )
            ]

        if status_filter:
            results = [c for c in results if c["status"] == status_filter]

        if not results:
            return "No cases found matching your search criteria."

        if len(results) == 1:
            return self._format_case(results[0])

        # Multiple results — return summary list
        lines = [f"Found {len(results)} cases:\n"]
        for c in results:
            lines.append(
                f"  {c['id']}: {c['title']} | {c['type']} | Status: {c['status']} | Client: {c['client']}"
            )
        return "\n".join(lines)

    def _format_case(self, case: dict) -> str:
        return (
            f"Case: {case['id']} — {case['title']}\n"
            f"Client: {case['client']}\n"
            f"Opposing Party: {case['opposing_party']}\n"
            f"Type: {case['type']}\n"
            f"Status: {case['status']}\n"
            f"Filed: {case['filed_date']}\n"
            f"Attorney: {case['attorney']}\n"
            f"Court: {case['court']}\n"
            f"Judge: {case['judge']}\n"
            f"Next Hearing: {case['next_hearing']}\n"
            f"Damages Sought: {case['damages_sought']}\n"
            f"Description: {case['description']}"
        )

"""
conflict_check.py — Conflict-of-interest checker for Samaritan/Veritas.

Cross-references all active cases by party names and returns a structured
conflict report. Restricted to attorney and admin roles via RBAC.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Import shared mock case database from case_lookup
# No circular dependency: case_lookup does not import from conflict_check
from samaritan.skills.case_lookup import MOCK_CASES


class ConflictCheckSkill:
    name = "conflict_check"
    description = (
        "Check for conflicts of interest between a given case or party and all active matters. "
        "Cross-references client and opposing party names across the full case database. "
        "Returns a structured conflict report with matched parties and recommended actions. "
        "Use before taking on a new client or when assigned to a new matter."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "case_id": {
                "type": "string",
                "description": "Case ID to check conflicts for (e.g. CASE-001). "
                               "Will cross-reference all parties in that case.",
            },
            "party_name": {
                "type": "string",
                "description": "Optional: a specific party name (client or opposing party) "
                               "to cross-reference independently across all matters.",
            },
        },
        "required": [],
    }

    def execute(self, params: dict, session=None) -> str:
        case_id = params.get("case_id", "").strip().upper()
        party_name = params.get("party_name", "").strip().lower()

        target_case = MOCK_CASES.get(case_id) if case_id else None

        # Build set of names to check
        check_names: set = set()
        if target_case:
            check_names.add(target_case["client"].lower())
            opp = target_case.get("opposing_party", "N/A")
            if opp and opp != "N/A":
                check_names.add(opp.lower())
        if party_name:
            check_names.add(party_name.lower())

        if not check_names:
            return (
                "No case ID or party name provided for conflict check. "
                "Please supply a case_id (e.g. CASE-001) or a party_name."
            )

        # Cross-reference all other cases
        conflicts = []
        for cid, case in MOCK_CASES.items():
            if cid == case_id:
                continue  # Skip the reference case itself
            case_parties = set()
            case_parties.add(case["client"].lower())
            opp = case.get("opposing_party", "N/A")
            if opp and opp != "N/A":
                case_parties.add(opp.lower())

            matched = check_names & case_parties
            if matched:
                conflicts.append({
                    "case_id": cid,
                    "title": case["title"],
                    "status": case["status"],
                    "attorney": case["attorney"],
                    "matched_party": list(matched)[0].title(),
                    "matched_role": (
                        "client" if list(matched)[0] == case["client"].lower() else "opposing party"
                    ),
                })

        # Format report
        divider = "=" * 44

        if not conflicts:
            names_str = ", ".join(n.title() for n in sorted(check_names))
            lines = [
                f"CONFLICT OF INTEREST REPORT",
                divider,
                f"Checked: {names_str}",
                f"Result: ✓ NO CONFLICTS FOUND",
                "",
                "All parties are clear across the active case database.",
                "You may proceed with this matter.",
            ]
            if target_case:
                lines.insert(2, f"Reference Case: {case_id} — {target_case['title']}")
            return "\n".join(lines)

        lines = [
            "CONFLICT OF INTEREST REPORT",
            divider,
        ]
        if target_case:
            lines.append(f"Reference Case: {case_id} — {target_case['title']}")
        checked_str = ", ".join(n.title() for n in sorted(check_names))
        lines.append(f"Checked: {checked_str}")
        lines.append(f"⚠  CONFLICTS FOUND: {len(conflicts)}")
        lines.append("")

        for c in conflicts:
            lines.append(
                f"  • {c['case_id']}: {c['title']}\n"
                f"    Status: {c['status']}  |  Attorney: {c['attorney']}\n"
                f"    Conflict: {c['matched_party']} appears as {c['matched_role']}\n"
            )

        lines.append(divider)
        lines.append(
            "⚠  CONFLICT FLAGGED: Attorney review required before filing.\n"
            "   Note this conflict in the trial preparation summary and continue with remaining tasks."
        )
        return "\n".join(lines)

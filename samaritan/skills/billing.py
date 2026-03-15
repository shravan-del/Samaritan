"""
billing.py - Legal billing and time tracking skill.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Mock billing records
_BILLING_RECORDS: list[dict] = [
    {
        "id": "BILL-001",
        "case_id": "CASE-001",
        "attorney": "Sarah Mitchell",
        "date": "2024-06-01",
        "hours": 2.5,
        "rate": 350.0,
        "amount": 875.0,
        "description": "Initial client consultation and case intake",
        "billable": True,
    },
    {
        "id": "BILL-002",
        "case_id": "CASE-001",
        "attorney": "Sarah Mitchell",
        "date": "2024-06-05",
        "hours": 4.0,
        "rate": 350.0,
        "amount": 1400.0,
        "description": "Research on comparative negligence standards",
        "billable": True,
    },
    {
        "id": "BILL-003",
        "case_id": "CASE-002",
        "attorney": "Marcus Webb",
        "date": "2024-06-10",
        "hours": 6.5,
        "rate": 450.0,
        "amount": 2925.0,
        "description": "Patent claim analysis and prior art search",
        "billable": True,
    },
    {
        "id": "BILL-004",
        "case_id": "CASE-002",
        "attorney": "Marcus Webb",
        "date": "2024-06-15",
        "hours": 3.0,
        "rate": 450.0,
        "amount": 1350.0,
        "description": "Deposition preparation for Dr. Alice Huang",
        "billable": True,
    },
]

_BILLING_COUNTER = 10

# Default hourly rates by role
HOURLY_RATES = {
    "attorney": 350.0,
    "paralegal": 150.0,
    "clinician": 200.0,
    "analyst": 175.0,
    "reviewer": 125.0,
}


class BillingSkill:
    name = "billing"
    description = (
        "Track and query legal billing. Log billable time entries, view billing summaries "
        "by case, and generate invoice reports."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform",
                "enum": ["log_time", "view_summary", "view_entries", "get_invoice"],
            },
            "case_id": {
                "type": "string",
                "description": "Case ID to query or log time for",
            },
            "hours": {
                "type": "number",
                "description": "Number of hours to log",
            },
            "description": {
                "type": "string",
                "description": "Description of work performed",
            },
            "date": {
                "type": "string",
                "description": "Date of work in YYYY-MM-DD format (defaults to today)",
            },
            "attorney_name": {
                "type": "string",
                "description": "Name of the attorney (optional, defaults to current user)",
            },
            "hourly_rate": {
                "type": "number",
                "description": "Hourly rate in USD (optional, uses role default)",
            },
        },
        "required": ["action"],
    }

    def execute(self, params: dict, session=None) -> str:
        action = params.get("action", "view_summary")

        if action == "log_time":
            return self._log_time(params, session)
        elif action == "view_summary":
            return self._view_summary(params, session)
        elif action == "view_entries":
            return self._view_entries(params, session)
        elif action == "get_invoice":
            return self._get_invoice(params, session)
        else:
            return f"Unknown billing action: {action}"

    def _log_time(self, params: dict, session) -> str:
        global _BILLING_COUNTER
        case_id = params.get("case_id")
        if not case_id and session:
            case_id = session.case_id
        case_id = case_id or "global"

        hours = params.get("hours")
        if not hours or hours <= 0:
            return "Error: hours must be a positive number."

        description = params.get("description", "Legal work")
        date = params.get("date", datetime.now().strftime("%Y-%m-%d"))
        attorney_name = params.get("attorney_name", "Current User")

        role = session.user_role if session else "attorney"
        rate = params.get("hourly_rate") or HOURLY_RATES.get(role, 250.0)
        amount = round(hours * rate, 2)

        _BILLING_COUNTER += 1
        entry = {
            "id": f"BILL-{_BILLING_COUNTER:03d}",
            "case_id": case_id,
            "attorney": attorney_name,
            "date": date,
            "hours": hours,
            "rate": rate,
            "amount": amount,
            "description": description,
            "billable": True,
        }
        _BILLING_RECORDS.append(entry)

        logger.info("Logged %.1f hours for case %s | $%.2f", hours, case_id, amount)
        return (
            f"Time logged successfully:\n"
            f"  ID: {entry['id']}\n"
            f"  Case: {case_id}\n"
            f"  Date: {date}\n"
            f"  Hours: {hours:.1f} @ ${rate:.0f}/hr\n"
            f"  Amount: ${amount:,.2f}\n"
            f"  Description: {description}"
        )

    def _view_summary(self, params: dict, session) -> str:
        case_id = params.get("case_id")
        if not case_id and session:
            case_id = session.case_id

        records = _BILLING_RECORDS
        if case_id:
            records = [r for r in records if r.get("case_id") == case_id]

        if not records:
            return f"No billing records found{' for case ' + case_id if case_id else ''}."

        total_hours = sum(r["hours"] for r in records)
        total_amount = sum(r["amount"] for r in records)

        # Group by case
        by_case: dict[str, dict] = {}
        for r in records:
            cid = r["case_id"]
            if cid not in by_case:
                by_case[cid] = {"hours": 0.0, "amount": 0.0, "entries": 0}
            by_case[cid]["hours"] += r["hours"]
            by_case[cid]["amount"] += r["amount"]
            by_case[cid]["entries"] += 1

        lines = [f"Billing Summary{' — Case ' + case_id if case_id else ' — All Cases'}:\n"]
        lines.append(f"  Total Hours: {total_hours:.1f}")
        lines.append(f"  Total Amount: ${total_amount:,.2f}")
        lines.append(f"  Total Entries: {len(records)}\n")

        if not case_id and len(by_case) > 1:
            lines.append("By Case:")
            for cid, stats in sorted(by_case.items()):
                lines.append(
                    f"  {cid}: {stats['hours']:.1f} hrs | ${stats['amount']:,.2f} | {stats['entries']} entries"
                )

        return "\n".join(lines)

    def _view_entries(self, params: dict, session) -> str:
        case_id = params.get("case_id")
        if not case_id and session:
            case_id = session.case_id

        records = _BILLING_RECORDS
        if case_id:
            records = [r for r in records if r.get("case_id") == case_id]

        if not records:
            return "No billing entries found."

        lines = [f"Billing Entries ({len(records)} total):\n"]
        for r in sorted(records, key=lambda x: x["date"]):
            lines.append(
                f"  {r['id']} | {r['date']} | {r['hours']:.1f}h @ ${r['rate']:.0f} = ${r['amount']:,.2f}"
            )
            lines.append(f"    {r['attorney']}: {r['description']}")
        return "\n".join(lines)

    def _get_invoice(self, params: dict, session) -> str:
        case_id = params.get("case_id")
        if not case_id and session:
            case_id = session.case_id

        if not case_id:
            return "Error: case_id is required to generate an invoice."

        records = [r for r in _BILLING_RECORDS if r.get("case_id") == case_id]
        if not records:
            return f"No billing records found for case {case_id}."

        total = sum(r["amount"] for r in records)
        total_hours = sum(r["hours"] for r in records)
        today = datetime.now().strftime("%B %d, %Y")

        lines = [
            f"INVOICE",
            f"{'=' * 60}",
            f"Case: {case_id}",
            f"Invoice Date: {today}",
            f"{'=' * 60}",
            f"",
            f"{'DATE':<12} {'HOURS':>6} {'RATE':>8} {'AMOUNT':>10}  DESCRIPTION",
            f"{'-' * 60}",
        ]

        for r in sorted(records, key=lambda x: x["date"]):
            lines.append(
                f"{r['date']:<12} {r['hours']:>6.1f} ${r['rate']:>7.0f} ${r['amount']:>9,.2f}  {r['description'][:35]}"
            )

        lines.extend([
            f"{'-' * 60}",
            f"{'TOTAL':>32} ${total:>9,.2f}",
            f"{'Total Hours:':>20} {total_hours:.1f}",
            f"",
            f"Payment due within 30 days of invoice date.",
        ])

        return "\n".join(lines)

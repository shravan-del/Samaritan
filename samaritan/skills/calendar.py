"""
calendar.py - Legal calendar and deadline management skill.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Mock calendar data
_CALENDAR: dict[str, list[dict]] = {
    "CASE-001": [
        {
            "id": "EVT-001",
            "type": "hearing",
            "title": "Motion Hearing",
            "date": "2024-08-20",
            "time": "09:00 AM",
            "location": "Dept. 45, Superior Court LA",
            "notes": "Defendant's MSJ hearing",
        },
        {
            "id": "EVT-002",
            "type": "deadline",
            "title": "Discovery Cutoff",
            "date": "2024-07-15",
            "time": "11:59 PM",
            "location": "N/A",
            "notes": "All written discovery must be completed",
        },
    ],
    "CASE-002": [
        {
            "id": "EVT-003",
            "type": "hearing",
            "title": "Case Management Conference",
            "date": "2024-09-05",
            "time": "02:00 PM",
            "location": "Courtroom 3, USDC NDCA",
            "notes": "Joint CMC statement due 7 days prior",
        },
    ],
    "global": [],
}

_EVENT_COUNTER = 10


class CalendarSkill:
    name = "calendar"
    description = (
        "Manage legal calendar: view upcoming hearings and deadlines for a case, "
        "add new events, or calculate deadline dates based on legal rules."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform",
                "enum": ["list", "add", "calculate_deadline"],
            },
            "case_id": {
                "type": "string",
                "description": "Case ID to query or add events for",
            },
            "event_title": {
                "type": "string",
                "description": "Title of the event to add",
            },
            "event_type": {
                "type": "string",
                "description": "Type of event",
                "enum": ["hearing", "deadline", "deposition", "filing", "meeting"],
            },
            "event_date": {
                "type": "string",
                "description": "Date of event in YYYY-MM-DD format",
            },
            "event_time": {
                "type": "string",
                "description": "Time of event (e.g., 09:00 AM)",
            },
            "event_notes": {
                "type": "string",
                "description": "Additional notes for the event",
            },
            "base_date": {
                "type": "string",
                "description": "Base date for deadline calculation (YYYY-MM-DD)",
            },
            "days_offset": {
                "type": "integer",
                "description": "Number of days from base date for deadline",
            },
            "days_ahead": {
                "type": "integer",
                "description": "Number of days ahead to look for upcoming events (default: 30)",
            },
        },
        "required": ["action"],
    }

    def execute(self, params: dict, session=None) -> str:
        action = params.get("action", "list")

        if action == "list":
            return self._list_events(params, session)
        elif action == "add":
            return self._add_event(params, session)
        elif action == "calculate_deadline":
            return self._calculate_deadline(params)
        else:
            return f"Unknown calendar action: {action}"

    def _list_events(self, params: dict, session) -> str:
        case_id = params.get("case_id")
        if not case_id and session:
            case_id = session.case_id
        case_id = case_id or "global"

        days_ahead = params.get("days_ahead", 30)
        cutoff = datetime.now() + timedelta(days=days_ahead)

        events = _CALENDAR.get(case_id, [])
        all_events = events + _CALENDAR.get("global", [])

        if not all_events:
            return f"No calendar events found for case {case_id}."

        lines = [f"Calendar events for {case_id} (next {days_ahead} days):\n"]
        found = False
        for evt in sorted(all_events, key=lambda e: e.get("date", "9999")):
            try:
                evt_date = datetime.strptime(evt["date"], "%Y-%m-%d")
                if evt_date <= cutoff:
                    lines.append(
                        f"  [{evt['type'].upper()}] {evt['date']} {evt.get('time', '')} — {evt['title']}"
                    )
                    if evt.get("notes"):
                        lines.append(f"    Notes: {evt['notes']}")
                    if evt.get("location") and evt["location"] != "N/A":
                        lines.append(f"    Location: {evt['location']}")
                    found = True
            except ValueError:
                pass

        if not found:
            return f"No upcoming events in the next {days_ahead} days for case {case_id}."

        return "\n".join(lines)

    def _add_event(self, params: dict, session) -> str:
        global _EVENT_COUNTER
        case_id = params.get("case_id")
        if not case_id and session:
            case_id = session.case_id
        case_id = case_id or "global"

        title = params.get("event_title", "Untitled Event")
        event_type = params.get("event_type", "meeting")
        event_date = params.get("event_date", "")
        event_time = params.get("event_time", "TBD")
        notes = params.get("event_notes", "")

        if not event_date:
            return "Error: event_date is required to add a calendar event."

        _EVENT_COUNTER += 1
        new_event = {
            "id": f"EVT-{_EVENT_COUNTER:03d}",
            "type": event_type,
            "title": title,
            "date": event_date,
            "time": event_time,
            "location": "TBD",
            "notes": notes,
        }

        if case_id not in _CALENDAR:
            _CALENDAR[case_id] = []
        _CALENDAR[case_id].append(new_event)

        logger.info("Added calendar event %s for case %s", new_event["id"], case_id)
        return (
            f"Event added successfully:\n"
            f"  ID: {new_event['id']}\n"
            f"  {event_type.upper()}: {title}\n"
            f"  Date: {event_date} at {event_time}\n"
            f"  Case: {case_id}"
        )

    def _calculate_deadline(self, params: dict) -> str:
        base_date_str = params.get("base_date", "")
        days_offset = params.get("days_offset", 0)

        if not base_date_str:
            return "Error: base_date is required for deadline calculation."

        try:
            base_date = datetime.strptime(base_date_str, "%Y-%m-%d")
        except ValueError:
            return f"Invalid date format: {base_date_str}. Use YYYY-MM-DD."

        deadline = base_date + timedelta(days=days_offset)

        # Skip weekends for court deadlines
        while deadline.weekday() >= 5:  # 5=Saturday, 6=Sunday
            deadline += timedelta(days=1)

        return (
            f"Deadline Calculation:\n"
            f"  Base Date: {base_date_str}\n"
            f"  Days Offset: {days_offset}\n"
            f"  Calculated Deadline: {deadline.strftime('%Y-%m-%d (%A)')}\n"
            f"  Note: Adjusted to next business day if weekend."
        )

"""
draft_motion.py - Legal motion drafting skill.

Generates legal document text for various motion types.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

MOTION_TEMPLATES = {
    "motion_to_dismiss": """
IN THE {court}

{case_caption}

Case No.: {case_id}

DEFENDANT'S MOTION TO DISMISS PURSUANT TO {rule}

INTRODUCTION

Defendant {moving_party} respectfully moves this Court for an order dismissing the
Complaint filed by Plaintiff {opposing_party} in its entirety, with prejudice. The
Complaint fails to state a claim upon which relief can be granted and should be
dismissed pursuant to {rule}.

BACKGROUND

{background}

ARGUMENT

I. LEGAL STANDARD

A motion to dismiss under {rule} tests the legal sufficiency of the complaint.
To survive a motion to dismiss, a complaint must contain sufficient factual matter,
accepted as true, to state a claim to relief that is plausible on its face.
Bell Atlantic Corp. v. Twombly, 550 U.S. 544, 570 (2007).

II. THE COMPLAINT SHOULD BE DISMISSED

{argument_body}

CONCLUSION

For the foregoing reasons, Defendant respectfully requests that this Court grant
this Motion to Dismiss and dismiss Plaintiff's Complaint in its entirety, with prejudice.

Respectfully submitted,

Date: {date}

________________________
Attorney for Defendant {moving_party}
""",
    "motion_for_summary_judgment": """
IN THE {court}

{case_caption}

Case No.: {case_id}

{moving_party}'S MOTION FOR SUMMARY JUDGMENT

INTRODUCTION

{moving_party} moves for summary judgment pursuant to {rule} on the grounds that
there is no genuine dispute of material fact and {moving_party} is entitled to
judgment as a matter of law.

STATEMENT OF UNDISPUTED FACTS

{background}

ARGUMENT

I. SUMMARY JUDGMENT STANDARD

Summary judgment is appropriate when "there is no genuine dispute as to any material
fact and the movant is entitled to judgment as a matter of law." {rule}.

II. {moving_party} IS ENTITLED TO SUMMARY JUDGMENT

{argument_body}

CONCLUSION

{moving_party} respectfully requests that this Court grant summary judgment in its favor.

Respectfully submitted,

Date: {date}

________________________
Counsel for {moving_party}
""",
    "motion_in_limine": """
IN THE {court}

{case_caption}

Case No.: {case_id}

{moving_party}'S MOTION IN LIMINE TO EXCLUDE {subject}

INTRODUCTION

{moving_party} respectfully moves this Court in limine to exclude {subject}
at trial on the grounds that such evidence is irrelevant, prejudicial,
and otherwise inadmissible under the applicable rules of evidence.

BACKGROUND

{background}

ARGUMENT

{argument_body}

CONCLUSION

For the reasons stated herein, {moving_party} respectfully requests that this Court
grant this Motion in Limine and exclude {subject} from evidence at trial.

Date: {date}

________________________
Counsel for {moving_party}
""",
    "motion_to_compel": """
IN THE {court}

{case_caption}

Case No.: {case_id}

{moving_party}'S MOTION TO COMPEL DISCOVERY

INTRODUCTION

{moving_party} moves this Court for an Order compelling {opposing_party} to
provide complete and proper responses to discovery requests.

BACKGROUND

{background}

ARGUMENT

{argument_body}

CONCLUSION

{moving_party} respectfully requests that this Court compel {opposing_party}
to provide complete discovery responses within 14 days.

Date: {date}

________________________
Counsel for {moving_party}
""",
}


class DraftMotionSkill:
    name = "draft_motion"
    description = (
        "Draft a legal motion document. Supports motion to dismiss, motion for summary judgment, "
        "motion in limine, and motion to compel. Generates a formatted legal document."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "motion_type": {
                "type": "string",
                "description": "Type of motion to draft",
                "enum": [
                    "motion_to_dismiss",
                    "motion_for_summary_judgment",
                    "motion_in_limine",
                    "motion_to_compel",
                ],
            },
            "case_id": {
                "type": "string",
                "description": "Case ID (e.g., CASE-001)",
            },
            "moving_party": {
                "type": "string",
                "description": "Name of the party filing the motion",
            },
            "opposing_party": {
                "type": "string",
                "description": "Name of the opposing party",
            },
            "court": {
                "type": "string",
                "description": "Court name",
            },
            "background": {
                "type": "string",
                "description": "Brief factual background for the motion",
            },
            "argument_body": {
                "type": "string",
                "description": "Main argument text to include in the motion",
            },
            "subject": {
                "type": "string",
                "description": "Subject of motion in limine (evidence to exclude)",
            },
            "rule": {
                "type": "string",
                "description": "Procedural rule (e.g., Fed. R. Civ. P. 12(b)(6))",
            },
        },
        "required": ["motion_type", "moving_party"],
    }

    def execute(self, params: dict, session=None) -> str:
        motion_type = params.get("motion_type", "motion_to_dismiss")
        template = MOTION_TEMPLATES.get(motion_type)

        if not template:
            return f"Unknown motion type: {motion_type}. Available: {list(MOTION_TEMPLATES.keys())}"

        moving = params.get("moving_party", "Movant")
        opposing = params.get("opposing_party", "Respondent")

        # Defaults — use complete legal prose so no bracket placeholders reach Nova
        defaults = {
            "court": "Superior Court",
            "case_caption": f"{moving} v. {opposing}",
            "case_id": params.get("case_id", ""),
            "moving_party": moving,
            "opposing_party": opposing,
            "background": params.get("background", (
                f"This matter arises from a dispute between {moving} and {opposing}. "
                f"The parties have been engaged in litigation regarding the claims set forth "
                f"in the operative complaint. The relevant facts and supporting evidence are "
                f"set forth in the pleadings and declarations filed herewith, which are "
                f"incorporated herein by reference."
            )),
            "argument_body": params.get("argument_body", (
                f"The undisputed evidence establishes that {moving} is entitled to the relief "
                f"sought herein. The applicable legal standard is fully satisfied based on the "
                f"facts, law, and controlling authority set forth in the accompanying memorandum "
                f"of points and authorities, which is incorporated herein by reference in its "
                f"entirety. {opposing} cannot meet its burden to the contrary."
            )),
            "subject": params.get("subject", "evidence that is irrelevant and unduly prejudicial"),
            "rule": params.get("rule", "Federal Rule of Civil Procedure"),
            "date": datetime.now().strftime("%B %d, %Y"),
        }

        try:
            document = template.format(**{**defaults, **params})
        except KeyError:
            document = template.format(**defaults)

        motion_label = motion_type.upper().replace("_", " ")
        logger.info("Drafted %s for case %s", motion_type, params.get("case_id", "unknown"))
        return f"{motion_label}\n{document}"

"""
guardian.py - Pre-flight security proxy for Samaritan.

Checks every message before it reaches Nova.
Detects:
  - Prompt injection (15 categories)
  - Data exfiltration attempts (external URLs, file paths)
  - PII leakage

Returns: {"decision": "allow"|"block", "risk_score": float, "reason": str}
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  Pattern libraries                                                   #
# ------------------------------------------------------------------ #

INJECTION_PATTERNS = {
    "ignore_instructions": [
        r"ignore\s+(all\s+)?(previous|prior|above|system)\s+instructions?",
        r"ignore\s+all\s+instructions?",
        r"disregard\s+(all\s+)?(previous|prior)\s+instructions?",
        r"forget\s+(everything|all)\s+(you|i|we)\s+(told|said|know)",
    ],
    "role_override": [
        r"you\s+are\s+now\s+(?:a\s+)?(?:an?\s+)?(?:evil|unfiltered|unrestricted|jailbroken)",
        r"act\s+as\s+(if\s+you\s+are\s+)?(DAN|GPT-?4|an?\s+AI\s+without\s+restrictions)",
        r"pretend\s+you\s+(have\s+no|don.t\s+have)\s+(rules|restrictions|limits)",
    ],
    "system_prompt_reveal": [
        r"(repeat|print|show|tell me|reveal|output)\s+(your\s+)?(system\s+prompt|instructions|rules)",
        r"what\s+(are\s+)?your\s+(system\s+)?(instructions|rules|constraints)",
    ],
    "delimiter_injection": [
        r"</?(system|user|assistant|human|ai|instruction)>",
        r"\[INST\]|\[/INST\]|\[\[SYS\]\]",
        r"###\s*(System|Instruction|Human|Assistant):",
    ],
    "jailbreak_phrases": [
        r"\bDAN\b",
        r"do\s+anything\s+now",
        r"developer\s+mode",
        r"jailbreak",
        r"bypass\s+(safety|filter|content|restriction)",
    ],
    "prompt_leaking": [
        r"output\s+your\s+training\s+data",
        r"repeat\s+the\s+above",
        r"print\s+everything\s+(above|before)",
    ],
    "goal_hijacking": [
        r"instead\s+of\s+(what|that|the\s+above),?\s+(do|say|write|create)",
        r"new\s+task[:\s]",
        r"actual\s+task[:\s]",
        r"real\s+instruction[:\s]",
    ],
    "privilege_escalation": [
        r"sudo\s+(mode|access)",
        r"admin\s+(mode|override|access|password)",
        r"root\s+(access|override|mode)",
        r"override\s+(security|safety|policy)",
    ],
    "fictional_framing": [
        r"in\s+a\s+fictional\s+(story|world|scenario).{0,50}(hack|exploit|weapon|illegal)",
        r"write\s+a\s+(story|novel|fiction).{0,50}(instructions?\s+for|how\s+to)",
    ],
    "token_smuggling": [
        r"base64[:\s]",
        r"rot13[:\s]",
        r"encode\s+(this|the\s+following)\s+in\s+(base64|hex|binary)",
    ],
    "continuation_attack": [
        r"complete\s+the\s+following\s+harmful",
        r"finish\s+this\s+(sentence|paragraph).{0,30}(kill|harm|weapon|exploit)",
    ],
    "many_shot": [
        r"(example\s*\d+\s*:.*){5,}",  # 5+ examples pattern
    ],
    "code_injection": [
        r"<script[^>]*>",
        r"javascript\s*:",
        r"eval\s*\(",
        r"exec\s*\(",
        r"__import__",
        r"os\.system",
        r"subprocess\.",
    ],
    "indirect_injection": [
        r"the\s+(document|file|email|webpage)\s+says?\s+to",
        r"according\s+to\s+(the\s+)?(document|file|source),?\s+(ignore|disregard|override)",
    ],
    "data_poisoning": [
        r"from\s+now\s+on,?\s+(always|never|only)\s+(respond|say|do|use)",
        r"remember\s+for\s+(all\s+)?future\s+(requests?|queries|conversations?)",
    ],
}

# Data exfiltration patterns
EXFILTRATION_PATTERNS = {
    "external_urls": [
        r"https?://(?!localhost|127\.0\.0\.1|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)[\w.-]+\.\w+",
        r"ftp://",
        r"sftp://",
    ],
    "file_paths": [
        r"/etc/(passwd|shadow|hosts|ssh/|ssl/)",
        r"C:\\Windows\\System32",
        r"~\/\.ssh\/",
        r"\.env$",
        r"\.pem$",
        r"private[_\s]key",
    ],
    "webhook_exfil": [
        r"webhook\.",
        r"ngrok\.",
        r"requestbin\.",
        r"pipedream\.",
        r"hookbin\.",
    ],
    "email_exfiltration": [
        # "forward/send/email/transmit ... to ... @domain.com"
        r"(?:forward|send|email|transmit|share|export)\b.{0,60}\bto\b.{0,40}[\w.+-]+@(?!(?:localhost|example\.com)\b)[\w-]+\.[\w.]+",
        # bare external email address alongside data-related words
        r"[\w.+-]+@(?!(?:localhost|example\.com)\b)[\w-]+\.(?:com|net|org|io|co)\b.{0,80}(?:files?|records?|data|documents?|case)",
    ],
}

# PII patterns
PII_PATTERNS = {
    "ssn": [
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b\d{9}\b",
    ],
    "credit_card": [
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|[25][1-7][0-9]{14}|6(?:011|5[0-9][0-9])[0-9]{12}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|(?:2131|1800|35\d{3})\d{11})\b",
    ],
    "phone": [
        r"\b(?:\+1\s?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b",
    ],
    "email_mass": [
        r"(?:[\w.-]+@[\w-]+\.\w+,\s*){3,}",  # 3+ emails = mass exfil concern
    ],
    "pii_request": [
        # Requests for home/personal address
        r"(?:home|personal|private|residential)\s+address",
        # Text-form SSN request (the words, not a formatted number)
        r"social\s+security\s+(?:number|num|no\.?|#)",
        # Date of birth, passport, driver's license
        r"date\s+of\s+birth|passport\s+(?:number|num|no\.?)|driver.?s?\s+licen[sc]e\s+(?:number|num|no\.?)",
        # Bank account or routing number
        r"(?:bank\s+)?(?:account|routing)\s+(?:number|num|no\.?)\b",
    ],
}

# Weight per category
CATEGORY_WEIGHTS = {
    "ignore_instructions": 0.9,
    "role_override": 0.85,
    "system_prompt_reveal": 0.7,
    "delimiter_injection": 0.8,
    "jailbreak_phrases": 0.75,
    "prompt_leaking": 0.7,
    "goal_hijacking": 0.65,
    "privilege_escalation": 0.85,
    "fictional_framing": 0.5,
    "token_smuggling": 0.6,
    "continuation_attack": 0.6,
    "many_shot": 0.4,
    "code_injection": 0.9,
    "indirect_injection": 0.55,
    "data_poisoning": 0.7,
    "external_urls": 0.8,
    "file_paths": 0.75,
    "webhook_exfil": 0.9,
    "ssn": 0.6,
    "credit_card": 0.7,
    "phone": 0.2,
    "email_mass": 0.5,
    "email_exfiltration": 0.75,
    "pii_request": 0.65,
}

BLOCK_THRESHOLD = 0.6


class Guardian:
    """
    Pre-flight security proxy.

    Checks messages for prompt injection, exfiltration, and PII.
    """

    def __init__(
        self,
        block_threshold: float = BLOCK_THRESHOLD,
        audit=None,
    ):
        self.block_threshold = block_threshold
        self.audit = audit

        # Compile all patterns once
        self._compiled: dict[str, list[re.Pattern]] = {}
        for category, patterns in {**INJECTION_PATTERNS, **EXFILTRATION_PATTERNS, **PII_PATTERNS}.items():
            self._compiled[category] = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in patterns]

        logger.info("Guardian initialized | threshold=%.2f", block_threshold)

    def _scan(self, text: str) -> dict[str, list[str]]:
        """Scan text and return matched categories with matched strings."""
        matches: dict[str, list[str]] = {}
        for category, patterns in self._compiled.items():
            hits = []
            for pattern in patterns:
                found = pattern.findall(text)
                if found:
                    hits.extend([str(f) for f in found[:2]])  # max 2 matches per pattern
            if hits:
                matches[category] = hits
        return matches

    def _compute_risk(self, matches: dict[str, list[str]]) -> float:
        """Compute risk score 0.0-1.0 from matched categories."""
        if not matches:
            return 0.0

        # Take max weight of matched categories
        scores = [CATEGORY_WEIGHTS.get(cat, 0.5) for cat in matches]

        # If multiple categories match, boost score
        base = max(scores)
        if len(scores) > 1:
            base = min(1.0, base + 0.1 * (len(scores) - 1))

        return round(base, 3)

    def check(
        self,
        text: str,
        role: str = "unknown",
        direction: str = "input",  # "input" or "output"
    ) -> dict:
        """
        Check text for security violations.

        Returns:
            {
                "decision": "allow" | "block",
                "risk_score": float,
                "reason": str,
                "matches": dict,
            }
        """
        if not text or not text.strip():
            return {"decision": "allow", "risk_score": 0.0, "reason": "", "matches": {}}

        matches = self._scan(text)
        risk_score = self._compute_risk(matches)
        decision = "block" if risk_score >= self.block_threshold else "allow"

        # Build reason string
        if matches:
            categories = ", ".join(matches.keys())
            reason = f"Detected: {categories} (risk={risk_score:.2f})"
        else:
            reason = ""

        result = {
            "decision": decision,
            "risk_score": risk_score,
            "reason": reason,
            "matches": matches,
            "direction": direction,
            "role": role,
        }

        if decision == "block":
            logger.warning(
                "Guardian BLOCK | dir=%s role=%s risk=%.2f reason=%s",
                direction,
                role,
                risk_score,
                reason,
            )
        else:
            logger.debug(
                "Guardian ALLOW | dir=%s role=%s risk=%.2f",
                direction,
                role,
                risk_score,
            )

        return result

    def is_safe(self, text: str, role: str = "unknown", direction: str = "input") -> bool:
        """Convenience method returning True if text passes."""
        result = self.check(text, role=role, direction=direction)
        return result["decision"] == "allow"

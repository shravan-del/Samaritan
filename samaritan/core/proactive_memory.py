"""
proactive_memory.py - Entity extraction and memory enrichment for Veritas.

After each conversation turn, extracts named entities via Nova LLM
and stores them in memory with an "entity_extraction" source tag.

Entities extracted:
  person, date, case_number, matter, amount, deadline,
  medication, organization, statute, jurisdiction

Wire into VeritasAgent via asyncio.create_task() after each turn.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract named entities from the following conversation excerpt.
Return a JSON array of objects with fields: {{"type": str, "value": str, "context": str}}

Entity types to extract:
- person: names of people mentioned
- date: specific dates or deadlines
- case_number: legal case or matter numbers
- matter: matter name or description
- amount: monetary amounts or fees
- deadline: deadlines or due dates
- medication: medical terms or medications
- organization: companies, firms, agencies
- statute: laws, regulations, acts
- jurisdiction: courts, states, countries

Conversation:
{conversation}

Return ONLY valid JSON array. Example:
[{{"type": "person", "value": "John Smith", "context": "opposing counsel"}},
 {{"type": "date", "value": "2025-03-15", "context": "filing deadline"}}]

If no entities found, return: []"""


class ProactiveMemory:
    """
    Extracts entities from conversation turns and stores them in vector memory.
    """

    def __init__(self, nova_llm=None, memory=None):
        self.nova = nova_llm
        self.memory = memory

    async def extract_and_store(
        self,
        user_msg: str,
        assistant_msg: str,
        session,
    ) -> list[dict]:
        """
        Extract entities from user+assistant exchange and store in memory.
        Returns list of extracted entities (may be empty).
        """
        if not self.nova or not self.memory:
            return []

        conversation = f"User: {user_msg}\nAssistant: {assistant_msg}"
        entities = await self._extract_entities(conversation)

        if not entities:
            return []

        role    = getattr(session, "user_role", "global")
        case_id = getattr(session, "case_id", "global")

        for entity in entities:
            entity_text = (
                f"Entity [{entity.get('type', 'unknown')}]: {entity.get('value', '')} "
                f"(context: {entity.get('context', '')})"
            )
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda t=entity_text: self.memory.store(
                        text=t,
                        metadata={
                            "source": "entity_extraction",
                            "entity_type": entity.get("type", ""),
                            "entity_value": entity.get("value", ""),
                            "timestamp": time.time(),
                        },
                        role=role,
                        case_id=case_id,
                    ),
                )
            except Exception as e:
                logger.debug("Entity storage failed: %s", e)

        logger.debug(
            "ProactiveMemory: stored %d entities for session %s",
            len(entities),
            getattr(session, "session_id", "?"),
        )
        return entities

    async def _extract_entities(self, conversation: str) -> list[dict]:
        """Run entity extraction via Nova LLM."""
        if not self.nova:
            return []

        prompt = EXTRACTION_PROMPT.format(conversation=conversation[:2000])
        messages = [{"role": "user", "content": prompt}]

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.nova.chat(messages),
            )
            text = response.get("text", "").strip()
            if not text:
                return []

            # Extract JSON from response (may have surrounding text)
            start = text.find("[")
            end   = text.rfind("]") + 1
            if start == -1 or end == 0:
                return []

            entities = json.loads(text[start:end])
            return entities if isinstance(entities, list) else []

        except Exception as e:
            logger.debug("Entity extraction failed: %s", e)
            return []

    def get_session_context(self, session, n_results: int = 5) -> str:
        """Retrieve entity context for session start."""
        if not self.memory:
            return ""
        role    = getattr(session, "user_role", "global")
        case_id = getattr(session, "case_id", "global")
        try:
            return self.memory.get_context_for_query(
                "entity person case deadline amount",
                role=role,
                case_id=case_id,
                n_results=n_results,
            )
        except Exception as e:
            logger.debug("ProactiveMemory context retrieval failed: %s", e)
            return ""

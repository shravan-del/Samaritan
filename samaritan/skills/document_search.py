"""
document_search.py - Semantic document search skill.

Uses vector memory to find relevant documents for a query.
Falls back to keyword search on mock documents if memory not available.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Mock document store (used as fallback)
MOCK_DOCUMENTS = [
    {
        "id": "DOC-001",
        "case_id": "CASE-001",
        "title": "Accident Report - Interstate 405",
        "type": "evidence",
        "content": (
            "On March 3, 2024 at approximately 2:15 PM, a two-vehicle collision occurred "
            "on Interstate 405 northbound near the Wilshire Boulevard on-ramp. "
            "Vehicle 1, operated by John Smith, was rear-ended by Vehicle 2, operated by Robert Johnson. "
            "Police report #LAPD-2024-0303-0412. Both vehicles sustained significant damage. "
            "Mr. Smith reported neck pain and was transported to Cedars-Sinai Medical Center."
        ),
    },
    {
        "id": "DOC-002",
        "case_id": "CASE-001",
        "title": "Medical Records - Smith, John",
        "type": "medical",
        "content": (
            "Patient: John Smith, DOB: 1978-05-12. Admitted: 2024-03-03. "
            "Diagnosis: Cervical strain (whiplash), Grade II. "
            "Treatment: Physical therapy 3x/week for 8 weeks, cervical collar for 2 weeks. "
            "Prognosis: Full recovery expected in 3-6 months. "
            "Medical bills to date: $24,500."
        ),
    },
    {
        "id": "DOC-003",
        "case_id": "CASE-002",
        "title": "Patent US-10,987,654 - AI Model Architecture",
        "type": "patent",
        "content": (
            "United States Patent 10,987,654. Inventors: Dr. Alice Huang, Dr. Robert Chen. "
            "Assignee: TechCorp International. "
            "Title: System and Method for Multi-Layer Neural Network Inference Optimization. "
            "Claims: 1. A computer-implemented method comprising: receiving an input tensor; "
            "applying layer-wise relevance propagation; computing optimized attention masks. "
            "Filed: 2021-06-15. Issued: 2023-04-25."
        ),
    },
    {
        "id": "DOC-004",
        "case_id": "CASE-002",
        "title": "StartupAI Technical Report",
        "type": "technical",
        "content": (
            "StartupAI Model Architecture v2.3 — Internal Technical Report. "
            "Our inference engine employs a novel attention optimization technique "
            "using sparse relevance masks applied across transformer layers. "
            "Performance: 3.2x speedup over baseline. Memory reduction: 40%. "
            "This approach was independently developed by our engineering team in Q3 2023."
        ),
    },
    {
        "id": "DOC-005",
        "case_id": "CASE-003",
        "title": "Last Will and Testament - Carlos Rivera",
        "type": "legal",
        "content": (
            "I, Carlos Rivera, being of sound mind, declare this to be my Last Will. "
            "I bequeath my estate equally to my children: Maria Rivera and Eduardo Rivera. "
            "I appoint Maria Rivera as Executor of my estate. "
            "Executed: January 15, 2023. Witnessed by: Dr. Patricia Santos and James O'Malley."
        ),
    },
]


def _keyword_search(query: str, case_id: Optional[str] = None) -> list[dict]:
    """Simple keyword-based fallback search."""
    query_terms = query.lower().split()
    results = []

    docs = MOCK_DOCUMENTS
    if case_id:
        docs = [d for d in docs if d.get("case_id") == case_id]

    for doc in docs:
        text = (doc["title"] + " " + doc["content"]).lower()
        score = sum(1 for term in query_terms if term in text)
        if score > 0:
            results.append({**doc, "_score": score})

    results.sort(key=lambda x: x["_score"], reverse=True)
    return results


class DocumentSearchSkill:
    name = "document_search"
    description = (
        "Search case documents semantically. Finds relevant contracts, evidence, "
        "medical records, patents, and legal filings using natural language queries."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language query describing what you're looking for",
            },
            "case_id": {
                "type": "string",
                "description": "Limit search to a specific case ID",
            },
            "document_type": {
                "type": "string",
                "description": "Filter by document type: evidence, medical, patent, legal, technical",
                "enum": ["evidence", "medical", "patent", "legal", "technical"],
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 3)",
            },
        },
        "required": ["query"],
    }

    def __init__(self, memory=None):
        self._memory = memory

    def execute(self, params: dict, session=None) -> str:
        query = params.get("query", "")
        case_id = params.get("case_id")
        doc_type = params.get("document_type")
        max_results = params.get("max_results", 3)

        if not case_id and session:
            case_id = session.case_id

        role = session.user_role if session else "attorney"

        # Try vector memory first
        if self._memory:
            try:
                docs = self._memory.retrieve(
                    query,
                    role=role,
                    case_id=case_id or "global",
                    n_results=max_results,
                )
                if docs:
                    return self._format_vector_results(docs, query)
            except Exception as e:
                logger.warning("Vector search failed, falling back to keyword: %s", e)

        # Fallback: keyword search on mock docs
        results = _keyword_search(query, case_id=case_id)

        if doc_type:
            results = [r for r in results if r.get("type") == doc_type]

        results = results[:max_results]

        if not results:
            return f"No documents found matching: '{query}'"

        return self._format_mock_results(results, query)

    def _format_vector_results(self, docs: list[dict], query: str) -> str:
        lines = [f"Search results for: '{query}'\n"]
        for i, doc in enumerate(docs, 1):
            meta = doc.get("metadata", {})
            lines.append(f"Result {i}:")
            if meta.get("document_name"):
                lines.append(f"  Document: {meta['document_name']}")
            lines.append(f"  Excerpt: {doc['text'][:300]}...")
            lines.append("")
        return "\n".join(lines)

    def _format_mock_results(self, results: list[dict], query: str) -> str:
        lines = [f"Search results for: '{query}'\n"]
        for i, doc in enumerate(results, 1):
            lines.append(f"Result {i}: {doc['title']} [{doc['type']}]")
            lines.append(f"  Case: {doc.get('case_id', 'N/A')}")
            lines.append(f"  Excerpt: {doc['content'][:300]}...")
            lines.append("")
        return "\n".join(lines)

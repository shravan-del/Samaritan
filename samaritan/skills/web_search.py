"""
web_search.py - Web search skill for Veritas using SearXNG.

Connects to a local SearXNG instance at http://localhost:8080
and summarizes results via the Nova LLM.

SearXNG setup:
  docker run -p 8080:8080 searxng/searxng
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class WebSearchSkill:
    """
    Search the web via SearXNG and summarize results.
    """

    description = "Search the web for current information, news, legal updates, or any topic. Use when the user asks about recent events, current laws, or factual information you may not have."

    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to look up.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of search results to retrieve (default: 5).",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        searxng_url: str = "http://localhost:8080",
        nova_llm=None,
        guardian=None,
    ):
        self.searxng_url = searxng_url.rstrip("/")
        self.nova = nova_llm
        self.guardian = guardian

    def execute(self, params: dict, session=None) -> str:
        query = params.get("query", "").strip()
        max_results = int(params.get("max_results", 5))

        if not query:
            return "Error: search query is required."

        if self.guardian:
            try:
                check = self.guardian.check(query, role=getattr(session, "user_role", "attorney"), direction="input")
                if check.get("decision") == "block":
                    return f"Search blocked by security policy: {check.get('reason', 'policy violation')}"
            except Exception as e:
                logger.warning("Guardian check failed for web search: %s", e)

        results = self._fetch(query, max_results)
        if not results:
            return f"No results found for: {query}. (SearXNG may not be running at {self.searxng_url})"

        formatted = self._format_results(results)

        if self.nova:
            try:
                summary = self._summarize(query, formatted)
                if summary:
                    return f"Search results for: {query}\n\n{summary}"
            except Exception as e:
                logger.warning("Nova summarization failed: %s", e)

        return f"Search results for: {query}\n\n{formatted}"

    def _fetch(self, query: str, max_results: int) -> list[dict]:
        try:
            import httpx
            url = f"{self.searxng_url}/search"
            params = {
                "q": query,
                "format": "json",
                "engines": "google,bing,duckduckgo",
                "language": "en",
            }
            response = httpx.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            return results[:max_results]
        except ImportError:
            logger.error("httpx not installed. Run: pip install httpx")
            return []
        except Exception as e:
            logger.warning("SearXNG fetch failed: %s", e)
            return []

    def _format_results(self, results: list[dict]) -> str:
        lines = []
        for i, r in enumerate(results, 1):
            title   = r.get("title", "Untitled")
            url     = r.get("url", "")
            snippet = r.get("content", r.get("snippet", "No description available."))
            lines.append(f"{i}. {title}\n   {url}\n   {snippet}")
        return "\n\n".join(lines)

    def _summarize(self, query: str, results_text: str) -> Optional[str]:
        messages = [
            {
                "role": "user",
                "content": (
                    f"The user searched for: {query}\n\n"
                    f"Here are the search results:\n{results_text}\n\n"
                    "Please provide a concise, accurate summary of the most relevant information "
                    "from these results. Cite sources by number. Be professional and objective."
                ),
            }
        ]
        response = self.nova.chat(messages)
        return response.get("text", "").strip() or None

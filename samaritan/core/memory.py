"""
memory.py - Vector memory using Titan embeddings.

Stores and retrieves conversation context and case documents.
Namespaced by role and case ID.
Uses ChromaDB as the vector store backend.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

_chroma_available = False
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    _chroma_available = True
except ImportError:
    logger.warning("chromadb not available — memory will use in-memory fallback")


class _InMemoryStore:
    """Simple in-memory fallback when ChromaDB is unavailable."""

    def __init__(self):
        self._store: dict[str, list[dict]] = {}

    def _key(self, namespace: str) -> str:
        return namespace

    def add(self, namespace: str, text: str, metadata: dict, embedding: list[float]):
        key = self._key(namespace)
        if key not in self._store:
            self._store[key] = []
        self._store[key].append(
            {"text": text, "metadata": metadata, "embedding": embedding, "id": str(uuid.uuid4())}
        )

    def query(self, namespace: str, embedding: list[float], n_results: int = 5) -> list[dict]:
        import math

        key = self._key(namespace)
        docs = self._store.get(key, [])
        if not docs:
            return []

        def cosine_sim(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            mag_a = math.sqrt(sum(x ** 2 for x in a))
            mag_b = math.sqrt(sum(x ** 2 for x in b))
            if mag_a == 0 or mag_b == 0:
                return 0.0
            return dot / (mag_a * mag_b)

        ranked = sorted(docs, key=lambda d: cosine_sim(embedding, d["embedding"]), reverse=True)
        return ranked[:n_results]


class VectorMemory:
    """
    Vector memory store backed by ChromaDB (or in-memory fallback).

    Namespace format: "{role}:{case_id}" e.g. "attorney:CASE-001"
    """

    def __init__(
        self,
        nova_llm=None,
        persist_directory: str = "./chroma_db",
    ):
        self._nova = nova_llm

        if _chroma_available:
            try:
                self._client = chromadb.PersistentClient(path=persist_directory)
                self._use_chroma = True
                logger.info("VectorMemory: using ChromaDB at %s", persist_directory)
            except Exception as e:
                logger.warning("ChromaDB init failed (%s), using in-memory fallback", e)
                self._fallback = _InMemoryStore()
                self._use_chroma = False
        else:
            self._fallback = _InMemoryStore()
            self._use_chroma = False

        self._collections: dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _get_collection(self, namespace: str):
        """Get or create a ChromaDB collection for the namespace."""
        safe_name = namespace.replace(":", "_").replace("-", "_")
        if safe_name not in self._collections:
            self._collections[safe_name] = self._client.get_or_create_collection(
                name=safe_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[safe_name]

    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding vector for text."""
        if self._nova is None:
            # Return zero vector as placeholder
            return [0.0] * 1024
        try:
            return self._nova.embed(text)
        except Exception as e:
            logger.warning("Embed failed (%s), using zero vector", e)
            return [0.0] * 1024

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def store(
        self,
        text: str,
        role: str = "attorney",
        case_id: str = "global",
        metadata: Optional[dict] = None,
        doc_id: Optional[str] = None,
    ) -> str:
        """
        Store a text chunk in vector memory.

        Returns the document ID.
        """
        namespace = f"{role}:{case_id}"
        embedding = self._get_embedding(text)
        doc_id = doc_id or str(uuid.uuid4())
        meta = {
            "role": role,
            "case_id": case_id,
            "timestamp": time.time(),
            **(metadata or {}),
        }

        if self._use_chroma:
            collection = self._get_collection(namespace)
            collection.add(
                documents=[text],
                embeddings=[embedding],
                metadatas=[meta],
                ids=[doc_id],
            )
        else:
            self._fallback.add(namespace, text, meta, embedding)

        logger.debug("Memory stored | ns=%s id=%s len=%d", namespace, doc_id, len(text))
        return doc_id

    def retrieve(
        self,
        query: str,
        role: str = "attorney",
        case_id: str = "global",
        n_results: int = 5,
    ) -> list[dict]:
        """
        Retrieve semantically similar documents.

        Returns list of dicts: {text, metadata, distance}
        """
        namespace = f"{role}:{case_id}"
        embedding = self._get_embedding(query)

        if self._use_chroma:
            collection = self._get_collection(namespace)
            try:
                results = collection.query(
                    query_embeddings=[embedding],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                )
                docs = []
                for i, doc in enumerate(results.get("documents", [[]])[0]):
                    docs.append(
                        {
                            "text": doc,
                            "metadata": results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {},
                            "distance": results.get("distances", [[]])[0][i] if results.get("distances") else 0.0,
                        }
                    )
                return docs
            except Exception as e:
                logger.warning("ChromaDB query failed: %s", e)
                return []
        else:
            raw = self._fallback.query(namespace, embedding, n_results)
            return [{"text": d["text"], "metadata": d["metadata"], "distance": 0.0} for d in raw]

    def store_conversation_turn(
        self,
        role: str,
        case_id: str,
        user_msg: str,
        assistant_msg: str,
    ) -> None:
        """Convenience method to store a conversation exchange."""
        combined = f"User: {user_msg}\nAssistant: {assistant_msg}"
        self.store(
            text=combined,
            role=role,
            case_id=case_id,
            metadata={"type": "conversation"},
        )

    def store_document(
        self,
        role: str,
        case_id: str,
        document_text: str,
        document_name: str,
        chunk_size: int = 1000,
    ) -> list[str]:
        """
        Store a document in chunks.

        Returns list of stored chunk IDs.
        """
        chunks = [
            document_text[i: i + chunk_size]
            for i in range(0, len(document_text), chunk_size)
        ]
        ids = []
        for idx, chunk in enumerate(chunks):
            doc_id = str(uuid.uuid4())
            self.store(
                text=chunk,
                role=role,
                case_id=case_id,
                metadata={
                    "type": "document",
                    "document_name": document_name,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                },
                doc_id=doc_id,
            )
            ids.append(doc_id)
        logger.info("Stored document %s in %d chunks", document_name, len(chunks))
        return ids

    def get_context_for_query(
        self,
        query: str,
        role: str,
        case_id: str,
        n_results: int = 5,
    ) -> str:
        """
        Retrieve and format context as a string for injection into prompts.
        """
        docs = self.retrieve(query, role=role, case_id=case_id, n_results=n_results)
        if not docs:
            return ""
        parts = []
        for i, doc in enumerate(docs, 1):
            meta = doc.get("metadata", {})
            doc_type = meta.get("type", "unknown")
            parts.append(f"[Context {i} ({doc_type})]:\n{doc['text']}")
        return "\n\n".join(parts)

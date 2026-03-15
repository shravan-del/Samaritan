"""
session.py - Session management for Veritas.

Tracks active user sessions, conversation history,
role assignments, and case context.
Persists sessions to SQLite for recovery across restarts.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_use_id: Optional[str] = None
    tool_name: Optional[str] = None


@dataclass
class Session:
    session_id: str
    user_role: str  # attorney | paralegal | clinician | analyst | reviewer
    case_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    messages: list[Message] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add_message(
        self,
        role: str,
        content: str,
        tool_use_id: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> Message:
        msg = Message(
            role=role,
            content=content,
            tool_use_id=tool_use_id,
            tool_name=tool_name,
        )
        self.messages.append(msg)
        self.last_active = time.time()
        return msg

    def get_conversation_history(self, max_turns: int = 20) -> list[dict]:
        """Return conversation history in Nova message format."""
        history = []
        for msg in self.messages[-max_turns:]:
            if msg.role == "system":
                history.append({"role": "system", "content": msg.content})
            elif msg.role == "tool":
                # Tool result in Nova format
                history.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "toolResult": {
                                    "toolUseId": msg.tool_use_id or "",
                                    "content": [{"text": msg.content}],
                                }
                            }
                        ],
                    }
                )
            else:
                history.append({"role": msg.role, "content": msg.content})
        return history

    def clear_history(self) -> None:
        self.messages = []

    def is_expired(self, ttl_seconds: int = 3600) -> bool:
        return (time.time() - self.last_active) > ttl_seconds


class SessionManager:
    """
    Manages all active sessions.

    Sessions are keyed by session_id.
    Expired sessions are cleaned up automatically.
    Optionally persists sessions to SQLite for recovery across restarts.
    """

    def __init__(self, session_ttl: int = 3600, db_path: Optional[str] = None):
        self._sessions: dict[str, Session] = {}
        self._session_ttl = session_ttl
        self._lock = threading.Lock()
        self._db_path = Path(db_path).expanduser() if db_path else None
        if self._db_path:
            self._init_db()
            self._load_sessions()

    # ------------------------------------------------------------------ #
    #  SQLite persistence                                                  #
    # ------------------------------------------------------------------ #

    def _init_db(self):
        """Initialize SQLite sessions table."""
        if not self._db_path:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id    TEXT PRIMARY KEY,
                    user_id       TEXT NOT NULL DEFAULT '',
                    user_role     TEXT NOT NULL DEFAULT 'attorney',
                    case_id       TEXT NOT NULL DEFAULT 'global',
                    created_at    REAL NOT NULL,
                    last_active   REAL NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    context_json  TEXT DEFAULT '[]'
                )
            """)
            conn.commit()

    def _save_session(self, session: Session):
        """Persist a session to SQLite."""
        if not self._db_path:
            return
        try:
            # Store only the last 5 messages to keep DB lean
            recent = session.messages[-5:]
            context = [
                {
                    "role": m.role,
                    "content": m.content[:500],  # truncate for DB
                    "timestamp": m.timestamp,
                }
                for m in recent
                if m.role in ("user", "assistant")
            ]
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO sessions
                       (session_id, user_role, case_id, created_at, last_active, message_count, context_json)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        session.session_id,
                        session.user_role,
                        session.case_id,
                        session.created_at,
                        session.last_active,
                        len(session.messages),
                        json.dumps(context),
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.warning("Session persist failed: %s", e)

    def _load_sessions(self):
        """Load recently active sessions from SQLite (last 24h)."""
        if not self._db_path or not self._db_path.exists():
            return
        cutoff = time.time() - 86400  # last 24h
        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    "SELECT session_id, user_role, case_id, created_at, last_active FROM sessions WHERE last_active > ?",
                    (cutoff,),
                ).fetchall()
            restored = 0
            for row in rows:
                sid, role, case_id, created_at, last_active = row
                session = Session(
                    session_id=sid,
                    user_role=role,
                    case_id=case_id,
                    created_at=created_at,
                    last_active=last_active,
                )
                self._sessions[sid] = session
                restored += 1
            logger.info("SessionManager: restored %d sessions from DB", restored)
        except Exception as e:
            logger.warning("Session load failed: %s", e)

    def create_session(
        self,
        user_role: str = "attorney",
        case_id: str = "global",
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Session:
        sid = session_id or str(uuid.uuid4())
        session = Session(
            session_id=sid,
            user_role=user_role,
            case_id=case_id,
            metadata=metadata or {},
        )
        with self._lock:
            self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.is_expired(self._session_ttl):
                del self._sessions[session_id]
                return None
        return session

    def get_or_create(
        self,
        session_id: str,
        user_role: str = "attorney",
        case_id: str = "global",
    ) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.is_expired(self._session_ttl):
                del self._sessions[session_id]
                session = None
            if session is None:
                session = Session(
                    session_id=session_id,
                    user_role=user_role,
                    case_id=case_id,
                )
                self._sessions[session_id] = session
                self._save_session(session)
            elif case_id and case_id != "global" and session.case_id != case_id:
                # Upgrade to a real case_id; never clobber back to 'global'
                session.case_id = case_id
                self._save_session(session)
        return session

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def cleanup_expired(self) -> int:
        with self._lock:
            expired = [
                sid
                for sid, session in self._sessions.items()
                if session.is_expired(self._session_ttl)
            ]
            for sid in expired:
                del self._sessions[sid]
        return len(expired)

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._sessions)

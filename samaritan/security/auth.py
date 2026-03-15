"""
auth.py - Authentication manager for Veritas.

Features:
  - SQLite-backed users and tokens tables
  - bcrypt password hashing (falls back to SHA-256 if bcrypt unavailable)
  - HMAC-SHA256 tokens
  - Default admin user created on first boot (admin/changeme)
  - Secret key stored in ~/.veritas/auth_secret (chmod 600)

Usage:
  auth = AuthManager(db_path="~/.veritas/auth.db")
  token = auth.authenticate("admin", "changeme")
  user = auth.validate_token(token)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Token TTL: 7 days
TOKEN_TTL = 86400 * 7


def _hash_password(password: str) -> str:
    """Hash a password with bcrypt (preferred) or SHA-256 fallback."""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        salt = secrets.token_hex(16)
        digest = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return f"sha256:{salt}:{digest}"


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its stored hash."""
    try:
        import bcrypt
        if hashed.startswith("$2"):
            return bcrypt.checkpw(password.encode(), hashed.encode())
    except ImportError:
        pass
    if hashed.startswith("sha256:"):
        _, salt, digest = hashed.split(":", 2)
        expected = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return hmac.compare_digest(expected, digest)
    return False


class AuthManager:
    """
    Manages user authentication and token validation for Veritas.
    """

    def __init__(self, db_path: str = "~/.veritas/auth.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._secret = self._load_or_create_secret()
        self._init_db()
        self._ensure_default_admin()

    # ------------------------------------------------------------------ #
    #  Secret key                                                          #
    # ------------------------------------------------------------------ #

    def _load_or_create_secret(self) -> str:
        secret_path = self.db_path.parent / "auth_secret"
        if secret_path.exists():
            return secret_path.read_text().strip()
        secret = secrets.token_hex(32)
        secret_path.write_text(secret)
        try:
            os.chmod(secret_path, 0o600)
        except Exception:
            pass
        logger.info("Created new auth secret at %s", secret_path)
        return secret

    # ------------------------------------------------------------------ #
    #  Database setup                                                      #
    # ------------------------------------------------------------------ #

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id       TEXT PRIMARY KEY,
                    username      TEXT UNIQUE NOT NULL,
                    role          TEXT NOT NULL DEFAULT 'attorney',
                    password_hash TEXT NOT NULL,
                    created_at    REAL NOT NULL,
                    active        INTEGER NOT NULL DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    token_hash TEXT PRIMARY KEY,
                    user_id    TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.commit()

    def _ensure_default_admin(self):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT user_id FROM users WHERE username='admin'").fetchone()
        if not row:
            self.create_user("admin", "changeme", role="admin")
            logger.warning(
                "Default admin created (admin/changeme). Change immediately in production!"
            )

    # ------------------------------------------------------------------ #
    #  User management                                                     #
    # ------------------------------------------------------------------ #

    def create_user(self, username: str, password: str, role: str = "attorney") -> str:
        """Create a new user. Returns user_id."""
        user_id = str(uuid.uuid4())
        password_hash = _hash_password(password)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO users (user_id, username, role, password_hash, created_at) VALUES (?,?,?,?,?)",
                (user_id, username, role, password_hash, time.time()),
            )
            conn.commit()
        logger.info("User created: %s (role=%s)", username, role)
        return user_id

    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE users SET active=0 WHERE user_id=?", (user_id,))
            conn.commit()
        return True

    # ------------------------------------------------------------------ #
    #  Authentication                                                      #
    # ------------------------------------------------------------------ #

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate username/password.
        Returns token string on success, None on failure.
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT user_id, password_hash, active FROM users WHERE username=?",
                (username,),
            ).fetchone()

        if not row:
            return None

        user_id, password_hash, active = row
        if not active:
            return None

        if not _verify_password(password, password_hash):
            return None

        return self._create_token(user_id)

    def _create_token(self, user_id: str) -> str:
        """Create and store a token. Returns base64url-encoded token string."""
        random_part = secrets.token_hex(16)
        expires = time.time() + TOKEN_TTL
        token_string = f"{user_id}|{expires}|{random_part}"
        token_hash = hmac.new(
            self._secret.encode(),
            token_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM tokens WHERE expires_at < ?", (time.time(),))
            conn.execute(
                "INSERT INTO tokens (token_hash, user_id, expires_at, created_at) VALUES (?,?,?,?)",
                (token_hash, user_id, expires, time.time()),
            )
            conn.commit()

        token_b64 = base64.urlsafe_b64encode(token_string.encode()).decode()
        return token_b64

    def validate_token(self, token_b64: str) -> Optional[dict]:
        """
        Validate a token. Returns user info dict or None if invalid/expired.
        """
        try:
            token_string = base64.urlsafe_b64decode(token_b64.encode()).decode()
            token_hash = hmac.new(
                self._secret.encode(),
                token_string.encode(),
                hashlib.sha256,
            ).hexdigest()
        except Exception:
            return None

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT user_id, expires_at FROM tokens WHERE token_hash=?",
                (token_hash,),
            ).fetchone()

        if not row:
            return None

        user_id, expires_at = row
        if expires_at < time.time():
            return None

        with sqlite3.connect(self.db_path) as conn:
            user_row = conn.execute(
                "SELECT username, role, active FROM users WHERE user_id=?",
                (user_id,),
            ).fetchone()

        if not user_row or not user_row[2]:
            return None

        username, role, _ = user_row
        return {"user_id": user_id, "username": username, "role": role}

    def revoke_token(self, token_b64: str) -> bool:
        """Revoke a token."""
        try:
            token_string = base64.urlsafe_b64decode(token_b64.encode()).decode()
            token_hash = hmac.new(
                self._secret.encode(),
                token_string.encode(),
                hashlib.sha256,
            ).hexdigest()
        except Exception:
            return False

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM tokens WHERE token_hash=?", (token_hash,))
            conn.commit()
        return True

    def list_users(self) -> list[dict]:
        """List all users (admin use)."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT user_id, username, role, created_at, active FROM users"
            ).fetchall()
        return [
            {"user_id": r[0], "username": r[1], "role": r[2], "created_at": r[3], "active": bool(r[4])}
            for r in rows
        ]

"""
sandbox.py - Skill execution sandbox for Samaritan.

Provides a controlled execution environment for skills:
  - Timeout enforcement
  - Output size limits
  - Exception isolation
  - Resource tracking
"""

from __future__ import annotations

import functools
import logging
import signal
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0       # seconds
MAX_OUTPUT_CHARS = 10000     # max chars in skill output


class SandboxError(Exception):
    """Raised when sandbox enforcement fails."""


class TimeoutError(SandboxError):
    """Raised when skill execution times out."""


def _run_with_timeout(fn: Callable, args: tuple, kwargs: dict, timeout: float) -> Any:
    """
    Run fn(*args, **kwargs) with a timeout using threading.

    Raises TimeoutError if the function doesn't complete within timeout seconds.
    """
    result = [None]
    error = [None]

    def target():
        try:
            result[0] = fn(*args, **kwargs)
        except Exception as e:
            error[0] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        raise TimeoutError(f"Skill execution timed out after {timeout}s")

    if error[0] is not None:
        raise error[0]

    return result[0]


def _truncate_output(output: Any, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    """Convert output to string and truncate if needed."""
    if output is None:
        return ""
    text = str(output)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... [output truncated at {max_chars} chars]"
    return text


class Sandbox:
    """
    Controlled execution environment for skills.

    Enforces timeouts, output size limits, and exception isolation.
    """

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        max_output_chars: int = MAX_OUTPUT_CHARS,
        audit=None,
    ):
        self.timeout = timeout
        self.max_output_chars = max_output_chars
        self.audit = audit
        self._execution_count = 0
        self._error_count = 0

    def execute(
        self,
        skill_name: str,
        fn: Callable,
        args: tuple = (),
        kwargs: Optional[dict] = None,
        role: str = "unknown",
    ) -> str:
        """
        Execute a skill function in the sandbox.

        Parameters
        ----------
        skill_name : Name of the skill (for logging/audit).
        fn         : Callable to execute.
        args       : Positional arguments.
        kwargs     : Keyword arguments.
        role       : User role for audit logging.

        Returns output as a string.
        Raises SandboxError on timeout or other sandbox violations.
        """
        kwargs = kwargs or {}
        start = time.time()
        self._execution_count += 1

        logger.debug("Sandbox executing: %s | role=%s timeout=%.1fs", skill_name, role, self.timeout)

        try:
            raw_output = _run_with_timeout(fn, args, kwargs, self.timeout)
            output = _truncate_output(raw_output, self.max_output_chars)
            elapsed = time.time() - start

            logger.debug(
                "Sandbox OK: %s | elapsed=%.2fs output_len=%d",
                skill_name,
                elapsed,
                len(output),
            )

            if self.audit:
                self.audit.log(
                    role=role,
                    action=f"sandbox_execute:{skill_name}",
                    outcome="success",
                    details={"elapsed": round(elapsed, 3), "output_len": len(output)},
                )

            return output

        except TimeoutError:
            self._error_count += 1
            elapsed = time.time() - start
            logger.warning("Sandbox timeout: %s after %.1fs", skill_name, elapsed)

            if self.audit:
                self.audit.log(
                    role=role,
                    action=f"sandbox_execute:{skill_name}",
                    outcome="timeout",
                    details={"elapsed": round(elapsed, 3)},
                )

            return f"[Skill '{skill_name}' timed out after {self.timeout}s]"

        except PermissionError as e:
            self._error_count += 1
            logger.warning("Sandbox permission denied: %s | %s", skill_name, e)
            return f"[Access denied: {e}]"

        except Exception as e:
            self._error_count += 1
            logger.error("Sandbox error in %s: %s", skill_name, e, exc_info=True)

            if self.audit:
                self.audit.log(
                    role=role,
                    action=f"sandbox_execute:{skill_name}",
                    outcome="error",
                    details={"error": str(e)},
                )

            return f"[Skill '{skill_name}' encountered an error: {type(e).__name__}: {e}]"

    @property
    def stats(self) -> dict:
        return {
            "total_executions": self._execution_count,
            "total_errors": self._error_count,
            "error_rate": (
                self._error_count / self._execution_count
                if self._execution_count > 0
                else 0.0
            ),
        }


def sandboxed(timeout: float = DEFAULT_TIMEOUT):
    """
    Decorator to wrap a skill execute() method in the sandbox.

    Usage:
        @sandboxed(timeout=10)
        def execute(self, params, session=None):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            box = Sandbox(timeout=timeout)
            skill_name = getattr(args[0], "name", fn.__name__) if args else fn.__name__
            return box.execute(skill_name, fn, args=args, kwargs=kwargs)
        return wrapper
    return decorator

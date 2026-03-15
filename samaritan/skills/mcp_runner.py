"""
mcp_runner.py - MCP (Model Context Protocol) stdio runner for Veritas.

Runs MCP server processes via JSON-RPC 2.0 over stdio.
Admin/attorney role only. Explicit binary whitelist.

Supported MCP servers (must be installed separately):
  filesystem: /usr/local/bin/mcp-server-filesystem
  sqlite:     /usr/local/bin/mcp-server-sqlite

Install: npm install -g @modelcontextprotocol/server-filesystem
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Explicit whitelist — only these binaries may be launched
MCP_BINARY_WHITELIST: dict[str, str] = {
    "filesystem": "/usr/local/bin/mcp-server-filesystem",
    "sqlite":     "/usr/local/bin/mcp-server-sqlite",
}

ALLOWED_ROLES = {"admin", "attorney"}


class MCPRunnerSkill:
    """
    Execute MCP server methods via JSON-RPC 2.0 over stdio.
    """

    description = (
        "Execute operations via MCP (Model Context Protocol) servers. "
        "Supports: filesystem (list/read files), sqlite (query databases). "
        "Admin or attorney role required."
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "server": {
                "type": "string",
                "description": "MCP server name. One of: " + ", ".join(MCP_BINARY_WHITELIST.keys()),
                "enum": list(MCP_BINARY_WHITELIST.keys()),
            },
            "method": {
                "type": "string",
                "description": "JSON-RPC method name.",
            },
            "params": {
                "type": "object",
                "description": "Parameters for the method.",
            },
        },
        "required": ["server", "method"],
    }

    def __init__(self, guardian=None):
        self.guardian = guardian
        self._req_id = 0

    def execute(self, params: dict, session=None) -> str:
        role = getattr(session, "user_role", "reviewer")
        if role not in ALLOWED_ROLES:
            return f"Access denied: MCP requires admin or attorney role (current: {role})."

        server_name = params.get("server", "")
        method      = params.get("method", "")
        call_params = params.get("params", {})

        if server_name not in MCP_BINARY_WHITELIST:
            return f"Unknown server: {server_name}. Available: {list(MCP_BINARY_WHITELIST.keys())}"

        binary = MCP_BINARY_WHITELIST[server_name]
        if not os.path.exists(binary):
            return (
                f"MCP server '{server_name}' not found at {binary}. "
                f"Install with: npm install -g @modelcontextprotocol/server-{server_name}"
            )

        if self.guardian:
            try:
                check = self.guardian.check(
                    f"mcp:{server_name}:{method}", role=role, direction="input"
                )
                if check.get("decision") == "block":
                    return f"MCP blocked by security: {check.get('reason', '')}"
            except Exception as e:
                logger.warning("Guardian check failed: %s", e)

        try:
            result = asyncio.run(self._call_mcp(binary, method, call_params))
            return json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
        except Exception as e:
            logger.error("MCP call failed: %s", e)
            return f"MCP error: {str(e)}"

    async def _call_mcp(self, binary: str, method: str, params: dict) -> Any:
        self._req_id += 1
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": method,
            "params": params,
        }) + "\n"

        proc = await asyncio.create_subprocess_exec(
            binary,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=request.encode()),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return {"error": "MCP call timed out"}

        if not stdout:
            return {"error": "No response from MCP server"}

        try:
            resp = json.loads(stdout.decode())
            if "result" in resp:
                return resp["result"]
            if "error" in resp:
                return {"error": resp["error"]}
            return resp
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON from MCP server: {e}"}

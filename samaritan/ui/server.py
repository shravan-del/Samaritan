"""
ui/server.py - FastAPI server for Samaritan.

Endpoints:
  POST /message           - Text message to agent (sync)
  GET  /audit             - Audit log viewer (HTML)
  GET  /audit/verify      - Verify audit chain integrity
  GET  /api/models        - List available LLM models
  POST /api/models/switch - Switch active LLM model
  WS   /ws                - WebSocket for real-time interaction
                            Accepts JSON text frames AND binary audio frames (WAV/PCM).
                            Streams response via response_start / response_chunk / response_end.
                            Binary frames → Whisper STT → agent → TTS response.
  GET  /                  - Serve index.html
  GET  /health            - Health check with voice pipeline status
  GET  /roles             - List available roles
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import struct
import tempfile
from pathlib import Path
from typing import AsyncIterator, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Samaritan",
    description="Voice-first AI agent OS",
    version="2.0.0",
)

# These are injected at startup by main.py
_agent = None
_session_manager = None
_speaker = None
_listener = None
_audit_log = None
_rbac = None
_nova = None         # For model switcher
_auth_manager = None  # For auth endpoints

# Connected WebSocket clients (for future broadcast support)
_connections: set[WebSocket] = set()


def init_server(agent, session_manager, speaker=None, listener=None, audit_log=None, rbac=None, nova=None, auth_manager=None):
    """Called from main.py to inject dependencies."""
    global _agent, _session_manager, _speaker, _listener, _audit_log, _rbac, _nova, _auth_manager
    _agent = agent
    _session_manager = session_manager
    _speaker = speaker
    _listener = listener
    _audit_log = audit_log
    _rbac = rbac
    _nova = nova
    _auth_manager = auth_manager
    logger.info(
        "Samaritan server dependencies initialized. listener=%s speaker=%s auth=%s",
        "yes" if listener else "no",
        "yes" if speaker else "no",
        "yes" if auth_manager else "no",
    )


# ------------------------------------------------------------------ #
#  Pydantic models                                                     #
# ------------------------------------------------------------------ #

class MessageRequest(BaseModel):
    message: str
    session_id: str = "default"
    role: str = "attorney"
    case_id: str = "global"


class MessageResponse(BaseModel):
    response: str
    session_id: str
    role: str


# ------------------------------------------------------------------ #
#  HTTP Routes                                                         #
# ------------------------------------------------------------------ #

@app.get("/")
async def serve_index():
    """Serve the main UI."""
    index_path = Path(__file__).parent / "index.html"
    if index_path.exists():
        return FileResponse(
            str(index_path),
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return JSONResponse({"status": "Samaritan API running. UI not found."})


@app.get("/health")
async def health():
    """Health check endpoint including voice pipeline status."""
    return {
        "status": "ok",
        "service": "samaritan",
        "agent_ready": _agent is not None,
        "sessions_active": _session_manager.active_count if _session_manager else 0,
        "voice": {
            "listener_ready": _listener is not None,
            "speaker_ready": _speaker is not None,
        },
    }


@app.get("/roles")
async def list_roles():
    """Return available roles and their permissions."""
    if _rbac:
        roles = {}
        for role in _rbac.list_roles():
            info = _rbac.get_role_info(role)
            roles[role] = {
                "allowed_skills": info.get("allowed_skills", []),
                "description": info.get("description", ""),
            }
        return roles
    return {"attorney": {}, "paralegal": {}, "clinician": {}, "analyst": {}, "reviewer": {}}


@app.post("/message", response_model=MessageResponse)
async def handle_message(req: MessageRequest):
    """
    Process a text message and return agent response (sync, non-streaming).
    """
    if not _agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    if not _session_manager:
        raise HTTPException(status_code=503, detail="Session manager not initialized")

    # Validate role
    if _rbac and not _rbac.is_valid_role(req.role):
        raise HTTPException(status_code=400, detail=f"Invalid role: {req.role}")

    # Get or create session
    session = _session_manager.get_or_create(
        session_id=req.session_id,
        user_role=req.role,
        case_id=req.case_id,
    )

    try:
        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(
            None,
            lambda: _agent.run(req.message, session),
        )
    except Exception as e:
        logger.error("Agent error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    return MessageResponse(
        response=response_text,
        session_id=req.session_id,
        role=req.role,
    )


@app.get("/audit")
async def get_audit_log(limit: int = 100, role_filter: Optional[str] = None, format: str = "json"):
    """Return the audit log as JSON or dark-themed HTML."""
    if not _audit_log:
        data = {"entries": [], "summary": {"total_entries": 0}}
    else:
        data = _audit_log.to_api_response(limit=limit)

    if format == "html":
        entries = data.get("entries", [])
        summary = data.get("summary", {})
        rows = ""
        import datetime as _dt
        for e in entries:
            _ts = e.get('timestamp')
            _ts_str = _dt.datetime.fromtimestamp(_ts).strftime('%Y-%m-%d %H:%M:%S') if _ts else ''
            rows += f"""<tr>
              <td>{_ts_str}</td>
              <td>{e.get('role','')}</td>
              <td>{e.get('action','')}</td>
              <td class="{'ok' if e.get('outcome') in ('success','allow') else 'err'}">{e.get('outcome','')}</td>
              <td class="hash">{str(e.get('hash',''))[:12]}…</td>
            </tr>"""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>SAMARITAN — AUDIT LOG</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #000; color: #aaa; font-family: 'Share Tech Mono', monospace; font-size: 12px; padding: 24px; }}
    h1 {{ color: #f0f0f0; letter-spacing: 4px; font-size: 14px; margin-bottom: 16px; }}
    .meta {{ color: #333; letter-spacing: 2px; font-size: 10px; margin-bottom: 20px; }}
    .chain-ok {{ color: #2a5; }} .chain-err {{ color: #f44; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ color: #333; letter-spacing: 2px; font-size: 10px; text-align: left; padding: 6px 10px; border-bottom: 1px solid #111; }}
    td {{ padding: 5px 10px; border-bottom: 1px solid #0a0a0a; color: #555; }}
    td.ok {{ color: #2a5; }} td.err {{ color: #f44; }}
    td.hash {{ color: #222; font-size: 10px; }}
    tr:hover td {{ color: #888; }}
  </style>
</head>
<body>
  <h1>SAMARITAN — AUDIT LOG</h1>
  <div class="meta">TOTAL ENTRIES: {summary.get('total_entries', 0)} | SHOWING: {len(entries)}</div>
  <table>
    <tr><th>TIMESTAMP</th><th>ROLE</th><th>ACTION</th><th>OUTCOME</th><th>HASH</th></tr>
    {rows if rows else '<tr><td colspan="5" style="color:#222;text-align:center;padding:20px;">NO ENTRIES</td></tr>'}
  </table>
</body>
</html>"""
        return HTMLResponse(html)

    return data


@app.get("/audit/verify")
async def verify_audit_chain():
    """Verify the integrity of the audit chain."""
    if not _audit_log:
        return {"valid": True, "error": None, "message": "No audit log configured"}
    valid, error = _audit_log.verify_chain()
    return {
        "valid": valid,
        "error": error,
        "message": "Chain integrity verified" if valid else f"Chain BROKEN: {error}",
    }


@app.get("/api/models")
async def list_models():
    """List available LLM models and current selection."""
    available = [
        {"id": "us.amazon.nova-2-lite-v1:0", "name": "Nova 2 Lite", "speed": "fast"},
        {"id": "us.amazon.nova-2-pro-v1:0", "name": "Nova 2 Pro", "speed": "slow"},
        {"id": "us.amazon.nova-lite-v1:0", "name": "Nova Lite", "speed": "fastest"},
        {"id": "us.amazon.nova-micro-v1:0", "name": "Nova Micro", "speed": "fastest"},
    ]
    current = _nova.chat_model_id if _nova else "unknown"
    return {"models": available, "current": current}


@app.post("/api/models/switch")
async def switch_model(body: dict):
    """Switch the active LLM model live."""
    if not _nova:
        raise HTTPException(status_code=503, detail="Nova LLM not initialized")
    model_id = body.get("model_id", "")
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id required")
    old = _nova.chat_model_id
    _nova.chat_model_id = model_id
    logger.info("Model switched: %s → %s", old, model_id)
    return {"success": True, "previous": old, "current": model_id}


# ------------------------------------------------------------------ #
#  Auth endpoints                                                      #
# ------------------------------------------------------------------ #

@app.post("/api/login")
async def login(body: dict):
    """Authenticate and return a token."""
    username = body.get("username", "")
    password = body.get("password", "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    if not _auth_manager:
        # Auth not configured — return a guest token placeholder
        return {"success": True, "token": "guest", "role": "attorney", "username": username}

    token = _auth_manager.authenticate(username, password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user = _auth_manager.validate_token(token)
    return {
        "success": True,
        "token": token,
        "role": user.get("role", "attorney") if user else "attorney",
        "username": username,
    }


@app.post("/api/logout")
async def logout(body: dict):
    """Revoke a token."""
    token = body.get("token", "")
    if _auth_manager and token:
        _auth_manager.revoke_token(token)
    return {"success": True}


@app.get("/api/admin/users")
async def list_users():
    """List all users (admin use)."""
    if not _auth_manager:
        return {"users": []}
    return {"users": _auth_manager.list_users()}


@app.post("/api/admin/users")
async def create_user(body: dict):
    """Create a new user (admin use)."""
    if not _auth_manager:
        raise HTTPException(status_code=503, detail="Auth not configured")
    username = body.get("username", "")
    password = body.get("password", "")
    role     = body.get("role", "attorney")
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")
    try:
        user_id = _auth_manager.create_user(username, password, role=role)
        return {"success": True, "user_id": user_id, "username": username, "role": role}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/admin/users/{user_id}")
async def deactivate_user(user_id: str):
    """Deactivate a user (admin use)."""
    if not _auth_manager:
        raise HTTPException(status_code=503, detail="Auth not configured")
    _auth_manager.deactivate_user(user_id)
    return {"success": True, "user_id": user_id}


# ------------------------------------------------------------------ #
#  TTS helpers                                                         #
# ------------------------------------------------------------------ #

def _extract_tts_text(full_text: str, max_sentences: int = 2, max_chars: int = 400) -> str:
    """
    Extract the first `max_sentences` speakable sentences from a (possibly markdown)
    response, suitable for passing to Polly TTS.

    - Strips markdown: headers (#), bold/italic (* _), code blocks, bullets
    - Splits on sentence boundaries (. ! ?)
    - Returns at most `max_chars` characters to stay well within Polly's 3000-char limit
    """
    # Remove markdown code blocks entirely
    text = re.sub(r'```[\s\S]*?```', '', full_text)
    # Remove inline code
    text = re.sub(r'`[^`]+`', '', text)
    # Remove markdown headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold / italic markers
    text = re.sub(r'\*{1,3}|_{1,3}', '', text)
    # Remove table rows (lines starting with |)
    text = re.sub(r'^\|.*\|$', '', text, flags=re.MULTILINE)
    # Remove bullet / numbered list prefixes
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+[.)]\s+', '', text, flags=re.MULTILINE)
    # Collapse excess whitespace / blank lines
    text = re.sub(r'\n{2,}', ' ', text).strip()
    text = re.sub(r'\s{2,}', ' ', text)

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # Filter out very short fragments (< 10 chars)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 10]

    # Take first N sentences and cap at max_chars
    result = ''
    for s in sentences[:max_sentences]:
        candidate = (result + ' ' + s).strip() if result else s
        if len(candidate) > max_chars:
            break
        result = candidate

    return result or text[:max_chars]


# ------------------------------------------------------------------ #
#  Demo sequence runner                                                #
# ------------------------------------------------------------------ #

# Ordered list of (tool_name, params) for the Johnson trial demo.
_DEMO_STEPS = [
    ("case_lookup",    {"case_id": "CASE-001"}),
    ("conflict_check", {"case_id": "CASE-001"}),
    ("calendar",       {"case_id": "CASE-001", "action": "list_events"}),
    ("document_search",{"case_id": "CASE-001"}),
    ("draft_motion",   {
        "case_id": "CASE-001",
        "motion_type": "motion_for_summary_judgment",
        "moving_party": "John Smith",
        "opposing_party": "Robert Johnson",
    }),
]

async def run_demo_sequence(websocket: WebSocket, session, role: str) -> str:
    """
    Execute the Johnson trial demo by running all 5 tools in strict sequence,
    emitting tool_status frames for each, then calling Nova for synthesis only.

    This bypasses the LLM's tendency to fabricate tool results after the first call.
    Returns the final synthesis text.
    """
    loop = asyncio.get_event_loop()
    tool_results: dict[str, str] = {}

    # ── Fire plan frame ────────────────────────────────────────────────
    await websocket.send_json({
        "type": "plan",
        "steps": [step[0] for step in _DEMO_STEPS],
    })

    # ── Execute each tool in sequence ──────────────────────────────────
    for tool_name, params in _DEMO_STEPS:
        await websocket.send_json({"type": "tool_status", "tool": tool_name, "status": "running"})

        skill = _agent.skills.get(tool_name)
        if skill is None:
            result = f"Skill '{tool_name}' not available."
        else:
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda s=skill, p=params, sess=session: s.execute(p, session=sess)),
                    timeout=15,
                )
                if not isinstance(result, str):
                    import json as _json
                    result = _json.dumps(result)
            except asyncio.TimeoutError:
                result = f"Skill '{tool_name}' timed out."
            except Exception as e:
                result = f"Skill '{tool_name}' error: {e}"

        tool_results[tool_name] = result
        preview = result[:80].replace("\n", " ")

        # Special conflict_alert frame when conflicts detected
        if tool_name == "conflict_check" and "CONFLICTS FOUND" in result:
            await websocket.send_json({
                "type": "conflict_alert",
                "tool": tool_name,
                "preview": result[:300],
            })

        await websocket.send_json({"type": "tool_status", "tool": tool_name, "status": "done", "result_preview": preview})

        _agent._log("skill_execute", role, "success", {"skill": tool_name, "input": params})

    # ── Ask Nova to synthesize using real tool results ─────────────────
    synthesis_prompt = (
        "Here are the real results from all 5 tools for the Johnson trial preparation.\n\n"
        f"CASE DETAILS:\n{tool_results.get('case_lookup','(not available)')}\n\n"
        f"CONFLICT CHECK:\n{tool_results.get('conflict_check','(not available)')}\n\n"
        f"CALENDAR / UPCOMING DEADLINES:\n{tool_results.get('calendar','(not available)')}\n\n"
        f"RELEVANT DOCUMENTS:\n{tool_results.get('document_search','(not available)')}\n\n"
        f"DRAFT MOTION:\n{tool_results.get('draft_motion','(not available)')}\n\n"
        "Using the above real data, write a comprehensive trial preparation summary for the attorney. "
        "Include: case overview, conflict flag (if any), key deadlines, available documents, and the drafted motion."
    )

    session.add_message("system", "You are Samaritan. Synthesize the trial preparation data below into a professional summary.")
    session.add_message("user", synthesis_prompt)

    try:
        synth = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _agent.nova.chat(session.get_conversation_history(), tools=None)),
            timeout=30,
        )
        final_text = synth.get("text", "").strip() or "Trial preparation complete. Please review the tool results above."
    except Exception as e:
        logger.error("Demo synthesis failed: %s", e)
        final_text = "Trial preparation data gathered. Please review the results above."

    _agent._log("nova_call", role, "success", {"iteration": "demo_synthesis"})
    return final_text


# ------------------------------------------------------------------ #
#  Streaming helpers                                                   #
# ------------------------------------------------------------------ #

async def stream_response(response_gen: AsyncIterator[str], websocket: WebSocket) -> str:
    """
    Stream an async generator of text chunks to the WebSocket client
    using the response_start / response_chunk / response_end protocol.

    Returns the full accumulated text.
    """
    await websocket.send_json({"type": "response_start"})
    full_text = ""
    try:
        async for chunk in response_gen:
            if chunk:
                full_text += chunk
                await websocket.send_json({"type": "response_chunk", "chunk": chunk})
    finally:
        await websocket.send_json({"type": "response_end"})
    return full_text


# ------------------------------------------------------------------ #
#  Audio helpers                                                      #
# ------------------------------------------------------------------ #

def _wav_bytes_to_float32(wav_data: bytes) -> np.ndarray:
    """
    Parse a WAV byte payload from the browser MediaRecorder into a
    float32 numpy array at 16 kHz mono (what Whisper expects).

    The browser sends PCM-16 WAV at 16 kHz mono after we resample via
    AudioContext.  If the header is absent or malformed we fall back to
    treating the whole payload as raw int16 PCM.
    """
    try:
        # Check for RIFF header
        if wav_data[:4] == b"RIFF":
            # Parse actual sample rate from header bytes 24-27
            sample_rate_bytes = wav_data[24:28]
            src_rate = struct.unpack_from("<I", sample_rate_bytes)[0]
            # PCM data starts at byte 44 for standard WAV
            pcm_data = wav_data[44:]
            audio_int16 = np.frombuffer(pcm_data, dtype=np.int16)
        else:
            # Raw PCM int16 fallback
            src_rate = 16000
            audio_int16 = np.frombuffer(wav_data, dtype=np.int16)

        audio_float = audio_int16.astype(np.float32) / 32768.0

        # Resample to 16 kHz if browser sent a different rate
        if src_rate != 16000 and src_rate > 0 and len(audio_float) > 0:
            try:
                from scipy.signal import resample_poly
                from math import gcd
                g = gcd(16000, src_rate)
                audio_float = resample_poly(audio_float, 16000 // g, src_rate // g)
            except Exception:
                pass  # Use as-is if scipy not available

        return audio_float.astype(np.float32)
    except Exception as e:
        logger.warning("WAV parse failed, treating as raw int16: %s", e)
        audio_int16 = np.frombuffer(wav_data, dtype=np.int16)
        return (audio_int16.astype(np.float32) / 32768.0)


async def _handle_audio_frame(
    websocket: WebSocket,
    audio_data: bytes,
    session_id: str,
    role: str,
    case_id: str,
) -> None:
    """
    Process a binary audio frame from the browser:
      1. Convert WAV bytes → float32 numpy array
      2. Whisper STT → transcript text
      3. Echo transcript back so browser shows what was heard
      4. Stream agent response via response_start/chunk/end
      5. Optionally send TTS audio
    """
    loop = asyncio.get_event_loop()

    if not _listener:
        await websocket.send_json({
            "type": "error",
            "message": "Voice listener not available on this server.",
        })
        return

    # 1. Convert to float32
    try:
        audio_array = await loop.run_in_executor(None, _wav_bytes_to_float32, audio_data)
    except Exception as e:
        await websocket.send_json({"type": "error", "message": f"Audio decode error: {e}"})
        return

    if len(audio_array) < 800:  # < 50ms at 16 kHz
        await websocket.send_json({"type": "error", "message": "Audio clip too short."})
        return

    # 2. Whisper STT
    await websocket.send_json({"type": "status", "message": "Transcribing..."})
    try:
        transcript = await loop.run_in_executor(None, _listener.transcribe, audio_array)
    except Exception as e:
        logger.error("Whisper transcription error: %s", e, exc_info=True)
        await websocket.send_json({"type": "error", "message": f"Transcription failed: {e}"})
        return

    if not transcript or not transcript.strip():
        await websocket.send_json({"type": "status", "message": "No speech detected. Try again."})
        return

    # 3. Echo transcript back
    await websocket.send_json({"type": "transcript", "text": transcript})

    # 4. Stream agent response
    session = _session_manager.get_or_create(
        session_id=session_id,
        user_role=role,
        case_id=case_id,
    )

    try:
        # Status callback sends tool_status frames in real time (voice path)
        async def _voice_tool_status(tool: str, status: str, preview: str = ""):
            if status == "conflict":
                await websocket.send_json({
                    "type": "conflict_alert",
                    "tool": tool,
                    "preview": preview,
                })
            else:
                await websocket.send_json({
                    "type": "tool_status",
                    "tool": tool,
                    "status": status,
                    "result_preview": preview,
                })

        # Plan callback fires once with tool names before execution (voice path)
        async def _voice_plan_callback(steps: list):
            await websocket.send_json({
                "type": "plan",
                "steps": steps,
            })

        # ── Pre-flight Guardian check — fires BEFORE Nova is ever called ──
        if _agent.guardian:
            guard_pre = _agent.guardian.check(transcript, role=role, direction="input")
            if guard_pre["decision"] == "block":
                await websocket.send_json({
                    "type": "guardian_block",
                    "risk_score": guard_pre["risk_score"],
                    "reason": guard_pre["reason"],
                    "categories": list(guard_pre["matches"].keys()),
                })
                _agent._log("guardian_check", role, "block", guard_pre)
                return  # voice path uses return (not continue) — exits _handle_audio_frame

        response_text = await stream_response(
            _agent.run_stream(
                transcript, session,
                status_callback=_voice_tool_status,
                plan_callback=_voice_plan_callback,
            ),
            websocket,
        )
    except Exception as e:
        logger.error("Agent error (voice path): %s", e, exc_info=True)
        await websocket.send_json({"type": "error", "message": f"Agent error: {e}"})
        return

    # 5. TTS audio — speak first 3 sentences (600 chars max) for substantive voice answers
    if _speaker and response_text:
        try:
            tts_text = _extract_tts_text(response_text, max_sentences=3, max_chars=600)
            logger.debug("TTS voice text (%d chars): %s", len(tts_text), tts_text[:80])
            audio_bytes = await loop.run_in_executor(
                None,
                lambda t=tts_text: _speaker.get_audio_bytes(t),
            )
            if audio_bytes:
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                encoding = "wav" if audio_bytes[:4] == b"RIFF" else "pcm_s16le"
                await websocket.send_json({
                    "type": "audio",
                    "data": audio_b64,
                    "encoding": encoding,
                    "sample_rate": 16000,
                })
        except Exception as e:
            logger.warning("TTS failed (voice response): %s", e)


# ------------------------------------------------------------------ #
#  WebSocket — /ws (session_id assigned server-side)                  #
# ------------------------------------------------------------------ #

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket handler for real-time interaction.

    The session_id is assigned server-side (no path param needed).

    Text frames from client (JSON):
      {"type": "message", "text": str, "role": str, "case_id": str}
      {"type": "ping"}
      {"type": "voice_meta", "role": str, "case_id": str}

    Binary frames from client:
      Raw WAV bytes (16 kHz mono PCM) from MediaRecorder
      Must be preceded by a JSON "voice_meta" frame to set role/case_id

    Messages to client (JSON):
      {"type": "response_start"}
      {"type": "response_chunk",  "chunk": str}
      {"type": "response_end"}
      {"type": "transcript",      "text": str}        - Whisper result echo
      {"type": "audio",           "data": base64_str, "encoding": str, "sample_rate": int}
      {"type": "error",           "message": str}
      {"type": "status",          "message": str}
      {"type": "pong"}
    """
    await websocket.accept()

    # Assign session_id server-side
    import uuid
    session_id = f"ws-{uuid.uuid4().hex[:8]}"
    logger.info("WebSocket connected: session=%s", session_id)

    _connections.add(websocket)

    if not _agent or not _session_manager:
        await websocket.send_json({"type": "error", "message": "Server not ready"})
        await websocket.close()
        _connections.discard(websocket)
        return

    # Voice metadata set by the client before sending binary audio
    voice_role: str = "attorney"
    voice_case_id: str = "global"

    try:
        while True:
            raw = await websocket.receive()

            # ---- Binary audio frame (PTT audio from browser) ----
            if raw.get("bytes"):
                audio_data: bytes = raw["bytes"]
                logger.info(
                    "Audio frame: %d bytes | session=%s role=%s case=%s",
                    len(audio_data), session_id, voice_role, voice_case_id,
                )
                await _handle_audio_frame(
                    websocket, audio_data, session_id, voice_role, voice_case_id
                )
                continue

            # ---- Text / JSON frame ----
            text_payload = raw.get("text", "")
            if not text_payload:
                continue

            try:
                msg = json.loads(text_payload)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "message")

            if msg_type == "voice_meta":
                voice_role = msg.get("role", voice_role)
                voice_case_id = msg.get("case_id", voice_case_id)
                logger.debug("voice_meta: role=%s case=%s", voice_role, voice_case_id)

            elif msg_type == "message":
                text = msg.get("text", "")
                role = msg.get("role", "attorney")
                case_id = msg.get("case_id", "global")

                if not text.strip():
                    continue

                session = _session_manager.get_or_create(
                    session_id=session_id,
                    user_role=role,
                    case_id=case_id,
                )

                try:
                    # Status callback sends tool_status frames in real time (text path)
                    async def _text_tool_status(tool: str, status: str, preview: str = ""):
                        if status == "conflict":
                            # Special: conflict_check found a real conflict → send dedicated frame
                            await websocket.send_json({
                                "type": "conflict_alert",
                                "tool": tool,
                                "preview": preview,
                            })
                        else:
                            await websocket.send_json({
                                "type": "tool_status",
                                "tool": tool,
                                "status": status,
                                "result_preview": preview,
                            })

                    # Plan callback fires once with the list of tool names before execution
                    async def _text_plan_callback(steps: list):
                        await websocket.send_json({
                            "type": "plan",
                            "steps": steps,
                        })

                    # ── Pre-flight Guardian check — fires BEFORE Nova is ever called ──
                    if _agent.guardian:
                        guard_pre = _agent.guardian.check(text, role=role, direction="input")
                        if guard_pre["decision"] == "block":
                            await websocket.send_json({
                                "type": "guardian_block",
                                "risk_score": guard_pre["risk_score"],
                                "reason": guard_pre["reason"],
                                "categories": list(guard_pre["matches"].keys()),
                            })
                            _agent._log("guardian_check", role, "block", guard_pre)
                            continue  # Skip stream_response entirely — Nova is never invoked

                    # ── Demo shortcut: run all 5 tools in guaranteed order ──
                    # Detect demo trigger: case_id=CASE-001 + any mention of "johnson trial".
                    # No longer requires "step 1" — the plan frame always shows all 5 tools.
                    _is_demo = (
                        case_id == "CASE-001"
                        and "johnson trial" in text.lower()
                    )
                    if _is_demo and _agent and _agent.skills:
                        await websocket.send_json({"type": "response_start"})
                        try:
                            demo_text = await run_demo_sequence(websocket, session, role)
                        except Exception as _de:
                            logger.error("Demo sequence failed: %s", _de)
                            demo_text = "An error occurred during the demo. Please try again."
                        # Stream the synthesis in chunks
                        chunk_size = 8
                        for _i in range(0, len(demo_text), chunk_size):
                            await websocket.send_json({"type": "response_chunk", "chunk": demo_text[_i:_i+chunk_size]})
                            await asyncio.sleep(0.01)
                        await websocket.send_json({"type": "response_end"})
                        response_text = demo_text
                    else:
                        # Normal path: Stream response via run_stream()
                        response_text = await stream_response(
                            _agent.run_stream(
                                text, session,
                                status_callback=_text_tool_status,
                                plan_callback=_text_plan_callback,
                            ),
                            websocket,
                        )

                    # TTS is voice-only — keyboard text and demo responses are display-only.
                    # Audio is produced exclusively in the binary-frame (voice) handler above.

                except Exception as e:
                    logger.error("WebSocket agent error: %s", e, exc_info=True)
                    await websocket.send_json({"type": "error", "message": str(e)})

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session=%s", session_id)
    except Exception as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        _connections.discard(websocket)

"""
main.py - Samaritan boot sequence.

Startup order:
  1. Load config (settings.yaml + permissions.yaml)
  2. Init NovaLLM (Bedrock client)
  3. Init Guardian (security proxy)
  4. Init AuditLog
  5. Init RBAC
  6. Init VectorMemory
  7. Init Skill registry
  8. Init VeritasAgent (ReAct loop)
  9. Init Voice pipeline (Listener + Speaker + WakeWord)
  10. Start FastAPI server via uvicorn
"""

import logging
import os
import sys
from pathlib import Path

import yaml

# ---- Logging setup ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("samaritan")

# Try rich logging if available
try:
    from rich.logging import RichHandler
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )
    logger = logging.getLogger("samaritan")
    logger.info("Rich logging enabled.")
except ImportError:
    pass


# ---- Config loader ----
CONFIG_DIR = Path(__file__).parent / "config"


def load_config() -> dict:
    """Load settings.yaml and permissions.yaml."""
    settings_path = CONFIG_DIR / "settings.yaml"
    permissions_path = CONFIG_DIR / "permissions.yaml"

    settings = {}
    permissions = {}

    if settings_path.exists():
        with open(settings_path) as f:
            settings = yaml.safe_load(f) or {}
        logger.info("Loaded settings from %s", settings_path)
    else:
        logger.warning("settings.yaml not found, using defaults.")

    if permissions_path.exists():
        with open(permissions_path) as f:
            permissions = yaml.safe_load(f) or {}
        logger.info("Loaded permissions from %s", permissions_path)
    else:
        logger.warning("permissions.yaml not found, using defaults.")

    return {"settings": settings, "permissions": permissions}


# ---- Boot sequence ----
def boot() -> dict:
    """
    Full boot sequence. Returns dict with all initialized components.
    """
    logger.info("=" * 60)
    logger.info("SAMARITAN — AI AGENT OS — Starting up")
    logger.info("=" * 60)

    # 1. Load config
    config = load_config()
    settings = config["settings"]
    permissions = config["permissions"]

    aws_cfg = settings.get("aws", {})
    model_cfg = settings.get("models", {})
    security_cfg = settings.get("security", {})
    memory_cfg = settings.get("memory", {})
    server_cfg = settings.get("server", {})
    session_cfg = settings.get("session", {})
    voice_cfg = settings.get("voice", {})

    # 2. Init NovaLLM
    logger.info("[1/9] Initializing NovaLLM (AWS Bedrock)...")
    from samaritan.core.nova_inference import NovaLLM

    chat_model = model_cfg.get("chat", {})
    embed_model = model_cfg.get("embeddings", {})

    nova = NovaLLM(
        region=aws_cfg.get("region", "us-east-1"),
        chat_model_id=chat_model.get("model_id", "us.amazon.nova-2-lite-v1:0"),
        embed_model_id=embed_model.get("model_id", "amazon.titan-embed-text-v2:0"),
        max_tokens=chat_model.get("max_tokens", 4096),
        temperature=chat_model.get("temperature", 0.7),
        top_p=chat_model.get("top_p", 0.9),
    )
    logger.info("NovaLLM ready.")

    # 3. Init AuditLog
    logger.info("[2/9] Initializing AuditLog...")
    from samaritan.security.audit import AuditLog

    audit_cfg = security_cfg.get("audit", {})
    audit = AuditLog(
        persist_path=audit_cfg.get("persist_path", "./audit_log.jsonl"),
        max_memory_entries=audit_cfg.get("max_memory_entries", 10000),
    )
    logger.info("AuditLog ready.")

    # 4. Init Guardian
    logger.info("[3/9] Initializing Guardian (security proxy)...")
    from samaritan.security.guardian import Guardian

    guardian_cfg = security_cfg.get("guardian", {})
    guardian = Guardian(
        block_threshold=guardian_cfg.get("block_threshold", 0.6),
        audit=audit,
    )
    logger.info("Guardian ready.")

    # 5. Init RBAC
    logger.info("[4/9] Initializing RBAC...")
    from samaritan.security.rbac import RBAC

    rbac = RBAC(roles_config=permissions.get("roles"))
    logger.info("RBAC ready | roles: %s", rbac.list_roles())

    # 6. Init Sandbox
    logger.info("[5/9] Initializing Sandbox...")
    from samaritan.security.sandbox import Sandbox

    sandbox_cfg = security_cfg.get("sandbox", {})
    sandbox = Sandbox(
        timeout=sandbox_cfg.get("timeout", 30.0),
        max_output_chars=sandbox_cfg.get("max_output_chars", 10000),
        audit=audit,
    )
    logger.info("Sandbox ready.")

    # 7. Init VectorMemory
    logger.info("[6/9] Initializing VectorMemory...")
    from samaritan.core.memory import VectorMemory

    memory = VectorMemory(
        nova_llm=nova,
        persist_directory=memory_cfg.get("persist_directory", "./chroma_db"),
    )
    logger.info("VectorMemory ready.")

    # 8. Init Skill registry
    logger.info("[7/9] Initializing Skills...")
    from samaritan.skills.case_lookup import CaseLookupSkill
    from samaritan.skills.draft_motion import DraftMotionSkill
    from samaritan.skills.calendar import CalendarSkill
    from samaritan.skills.document_search import DocumentSearchSkill
    from samaritan.skills.billing import BillingSkill
    from samaritan.skills.conflict_check import ConflictCheckSkill

    skills = {
        "case_lookup": CaseLookupSkill(),
        "draft_motion": DraftMotionSkill(),
        "calendar": CalendarSkill(),
        "document_search": DocumentSearchSkill(memory=memory),
        "billing": BillingSkill(),
        "conflict_check": ConflictCheckSkill(),
    }

    # Optional: Web search skill (requires SearXNG)
    try:
        from samaritan.skills.web_search import WebSearchSkill
        searxng_url = settings.get("skills", {}).get("searxng_url", "http://localhost:8080")
        skills["web_search"] = WebSearchSkill(
            searxng_url=searxng_url,
            nova_llm=nova,
            guardian=guardian,
        )
        logger.info("WebSearchSkill registered (SearXNG: %s)", searxng_url)
    except Exception as e:
        logger.warning("WebSearchSkill init failed: %s", e)

    # Optional: Browser automation skill (requires Playwright)
    try:
        from samaritan.skills.browser import BrowserSkill
        skills["browser"] = BrowserSkill(guardian=guardian)
        logger.info("BrowserSkill registered.")
    except Exception as e:
        logger.debug("BrowserSkill not available: %s", e)

    # Optional: MCP runner (admin only)
    try:
        from samaritan.skills.mcp_runner import MCPRunnerSkill
        skills["mcp"] = MCPRunnerSkill(guardian=guardian)
        logger.info("MCPRunnerSkill registered.")
    except Exception as e:
        logger.debug("MCPRunnerSkill not available: %s", e)

    logger.info("Skills registered: %s", list(skills.keys()))

    # 9. Init Agent + Session Manager
    logger.info("[8/9] Initializing SamaritanAgent (ReAct loop)...")
    from samaritan.core.agent import VeritasAgent
    from samaritan.core.session import SessionManager

    samaritan_dir = Path("~/.samaritan").expanduser()
    samaritan_dir.mkdir(parents=True, exist_ok=True)

    session_manager = SessionManager(
        session_ttl=session_cfg.get("ttl_seconds", 3600),
        db_path=str(samaritan_dir / "sessions.db"),
    )

    agent = VeritasAgent(
        nova_llm=nova,
        guardian=guardian,
        memory=memory,
        rbac=rbac,
        skill_registry=skills,
        audit=audit,
    )
    logger.info("VeritasAgent ready.")

    # Init Auth Manager
    auth_manager = None
    try:
        from samaritan.security.auth import AuthManager
        auth_manager = AuthManager(db_path=str(samaritan_dir / "auth.db"))
        logger.info("AuthManager ready.")
    except Exception as e:
        logger.warning("AuthManager init failed: %s", e)

    # Init ProactiveMemory
    proactive_memory = None
    try:
        from samaritan.core.proactive_memory import ProactiveMemory
        proactive_memory = ProactiveMemory(nova_llm=nova, memory=memory)
        logger.info("ProactiveMemory ready.")
    except Exception as e:
        logger.warning("ProactiveMemory init failed: %s", e)

    # Init Scheduler
    scheduler = None
    try:
        from samaritan.core.scheduler import TaskScheduler
        scheduler = TaskScheduler(
            db_path=str(samaritan_dir / "scheduler.db"),
            guardian=guardian,
        )
        # Example: session cleanup every hour
        scheduler.register("session_cleanup", "every 1h", session_manager.cleanup_expired)
        logger.info("TaskScheduler ready.")
    except Exception as e:
        logger.warning("TaskScheduler init failed: %s", e)

    # 10. Init Voice pipeline
    logger.info("[9/9] Initializing Voice pipeline...")

    speaker = None
    listener = None
    wakeword = None

    tts_cfg = model_cfg.get("tts", {})
    stt_cfg = model_cfg.get("stt", {})

    try:
        from samaritan.voice.nova_speaker import NovaSonicSpeaker
        speaker = NovaSonicSpeaker(
            region=aws_cfg.get("region", "us-east-1"),
            model_id=tts_cfg.get("model_id", "amazon.nova-sonic-v1:0"),
            voice_id=tts_cfg.get("voice_id", "matthew"),
            sample_rate=tts_cfg.get("sample_rate", 24000),
        )
        logger.info("NovaSonicSpeaker ready.")
    except Exception as e:
        logger.warning("Speaker init failed (will run in text-only mode): %s", e)

    try:
        from samaritan.voice.listener import Listener
        listener = Listener(
            model_size=stt_cfg.get("whisper_model_size", "base"),
            sample_rate=voice_cfg.get("sample_rate", 16000),
            silence_threshold=voice_cfg.get("silence_threshold", 0.01),
            silence_duration=voice_cfg.get("silence_duration", 1.5),
            max_duration=voice_cfg.get("max_record_duration", 30),
        )
        logger.info("Listener (Whisper STT) ready.")
    except Exception as e:
        logger.warning("Listener init failed: %s", e)

    try:
        from samaritan.voice.wakeword import WakeWordDetector
        wakeword = WakeWordDetector(
            wake_words=voice_cfg.get("wake_words", ["hey samaritan"]),
            model_size=voice_cfg.get("wake_word_model", "tiny"),
        )
        logger.info("WakeWordDetector ready.")
    except Exception as e:
        logger.warning("WakeWord init failed: %s", e)

    logger.info("=" * 60)
    logger.info("SAMARITAN boot complete.")
    logger.info("=" * 60)

    return {
        "nova": nova,
        "guardian": guardian,
        "audit": audit,
        "rbac": rbac,
        "sandbox": sandbox,
        "memory": memory,
        "skills": skills,
        "agent": agent,
        "session_manager": session_manager,
        "auth_manager": auth_manager,
        "proactive_memory": proactive_memory,
        "scheduler": scheduler,
        "speaker": speaker,
        "listener": listener,
        "wakeword": wakeword,
        "config": config,
    }


def main():
    """Entry point."""
    import asyncio

    components = boot()

    # Inject into server
    from samaritan.ui.server import app, init_server
    init_server(
        agent=components["agent"],
        session_manager=components["session_manager"],
        speaker=components["speaker"],
        listener=components["listener"],
        audit_log=components["audit"],
        rbac=components["rbac"],
        nova=components["nova"],
        auth_manager=components.get("auth_manager"),
    )

    # Start server with optional scheduler background task
    import uvicorn
    cfg = components["config"]["settings"].get("server", {})
    host = cfg.get("host", "0.0.0.0")
    port = int(cfg.get("port", 8001))
    log_level = cfg.get("log_level", "info")

    scheduler = components.get("scheduler")

    logger.info("Starting Samaritan server at http://%s:%d", host, port)

    if scheduler:
        # Wire scheduler into uvicorn's startup event
        @app.on_event("startup")
        async def _start_scheduler():
            asyncio.create_task(scheduler.run_loop())
            logger.info("TaskScheduler background loop started.")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        ws_max_size=8 * 1024 * 1024,  # 8 MB — large enough for Polly WAV audio
    )


if __name__ == "__main__":
    main()

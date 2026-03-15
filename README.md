# Samaritan — AI Legal Agent OS

An autonomous multi-domain AI agent for legal professionals, built on Amazon Nova 2 Lite via AWS Bedrock.

## Live Demo

Live demo available — see submission for ngrok URL.

Full instructions: [DEMO_INSTRUCTIONS.md](DEMO_INSTRUCTIONS.md)

## Demo Trigger

```
demo: prepare johnson trial
```

## Features

- Autonomous 5-step agent chain (case lookup → conflict check → calendar → document search → draft motion)
- Guardian security proxy — real-time prompt injection detection
- Role-based access control (Attorney / Paralegal / Clinician / Analyst / Reviewer)
- Voice interface — hold M to speak
- Audit log — click AUDIT in top right

## Stack

- **LLM:** Amazon Nova 2 Lite (AWS Bedrock)
- **Backend:** FastAPI + WebSockets (Python)
- **Voice:** Amazon Nova TTS + OpenAI Whisper STT
- **Memory:** ChromaDB vector store
- **Security:** Custom Guardian proxy (RBAC + injection detection)

## Run Locally

```bash
pip install -r requirements.txt
python -m samaritan.main
# Open http://localhost:8001
```

## Amazon Nova AI Hackathon Submission

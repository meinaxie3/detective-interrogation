"""
main.py — FastAPI application entry point.

Run with:
  cd backend
  .venv/Scripts/uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import game, chat, accuse, history, hint

app = FastAPI(
    title="Detective Interrogation Game",
    description="AI-powered interrogation game — Phase 5",
    version="5.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(game.router)
app.include_router(chat.router)
app.include_router(accuse.router)
app.include_router(history.router)
app.include_router(hint.router)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
async def health():
    """Liveness probe. Returns ok if the server is running."""
    store_type = "redis" if settings.redis_url else "memory"
    return {"status": "ok", "phase": 5, "store": store_type}  # v5.1

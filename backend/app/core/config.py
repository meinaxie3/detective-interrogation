"""
config.py — Application settings loaded from environment / .env file.

All configuration lives here. Nothing else in the codebase should read
os.environ or dotenv directly — import `settings` from this module.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # Ignore unknown env vars
    )

    # Claude API — must be set in .env for any endpoint that calls Claude
    anthropic_api_key: str = ""

    # Model config
    claude_model: str = "claude-sonnet-4-5"
    max_response_tokens: int = 512

    # Game defaults
    default_scenario_id: str = "manor_1920"
    session_ttl_seconds: int = 7200  # 2 hours — TTL applied to every Redis key

    # Phase 2: Redis session store
    # If unset → falls back to the Phase 1 in-memory store (no restart needed).
    # Set in backend/.env:  REDIS_URL=redis://localhost:6379/0
    redis_url: Optional[str] = None

    # Mock mode — returns scripted responses without calling Claude.
    # Set USE_MOCK=true in backend/.env to enable.
    # Useful for UI testing, demos, and CI without spending API credits.
    use_mock: bool = False

    # CORS — allow the Next.js dev server by default
    cors_origins: List[str] = ["http://localhost:3000"]


# Single shared instance — import this everywhere
settings = Settings()

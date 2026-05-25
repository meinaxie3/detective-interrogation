"""
history_store.py — Persistent JSON file store for completed game records.

Phase 5: Records are appended to backend/history.json after each game.
The file is created on first write.  Max 100 records — oldest are
rotated out automatically.

Design: intentionally simple.  No SQLite dependency.  A JSON file is
readable, debuggable, and portable — appropriate for a single-server
deployment.
"""

import json
from pathlib import Path

from app.models.history import GameRecord

# history.json sits in backend/ (one level above the app package)
_HISTORY_FILE = Path(__file__).parent.parent.parent / "history.json"
_MAX_RECORDS  = 100


# ── Public API ────────────────────────────────────────────────────────────────

def append(record: GameRecord) -> None:
    """Prepend a new record (newest-first) and trim to _MAX_RECORDS."""
    records = _load_raw()
    records.insert(0, record.model_dump())
    _save_raw(records[:_MAX_RECORDS])


def get_all() -> list[GameRecord]:
    """Return all records newest-first.  Empty list if none exist."""
    return [GameRecord(**r) for r in _load_raw()]


def clear() -> None:
    """Wipe all records.  Use only in tests."""
    _save_raw([])


# ── Private helpers ───────────────────────────────────────────────────────────

def _load_raw() -> list[dict]:
    if not _HISTORY_FILE.exists():
        return []
    try:
        return json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_raw(records: list[dict]) -> None:
    _HISTORY_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

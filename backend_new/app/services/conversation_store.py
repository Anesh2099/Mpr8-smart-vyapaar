"""
app/services/conversation_store.py — In-memory chat history per session.

Each session stores a list of {role, content, timestamp} messages.
Uses a simple in-memory dict with a max history size per session.
This avoids dependency on Firebase Firestore for chat context.
"""

from datetime import datetime, timezone
from collections import defaultdict

# In-memory store: session_id -> list of {role, content, timestamp}
_store: dict[str, list[dict]] = defaultdict(list)
_MAX_HISTORY = 30  # Keep last 30 messages per session


def get_history(session_id: str, limit: int = 20) -> list[dict]:
    """Return the last `limit` messages for a session, oldest first."""
    return _store[session_id][-limit:]


def append_message(session_id: str, role: str, content: str) -> None:
    """Append a message to a session's chat history."""
    _store[session_id].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc),
    })
    # Trim to prevent memory bloat
    if len(_store[session_id]) > _MAX_HISTORY:
        _store[session_id] = _store[session_id][-_MAX_HISTORY:]


def clear_history(session_id: str) -> None:
    """Delete all messages for a session."""
    _store[session_id] = []


def format_history_for_llm(history: list[dict]) -> list[dict]:
    """Convert stored history to openai-style messages list."""
    return [{"role": h["role"], "content": h["content"]} for h in history]

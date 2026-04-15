"""
app/services/conversation_store.py — Firestore-backed chat history per session.

Each session stores a list of {role, content, timestamp} messages in:
  Firestore: chat_history/{session_id}/messages/{auto_id}
"""

from datetime import datetime, timezone
from app.core.config import db


def get_history(session_id: str, limit: int = 20) -> list[dict]:
    """Return the last `limit` messages for a session, oldest first."""
    try:
        docs = (
            db.collection("chat_history")
            .document(session_id)
            .collection("messages")
            .order_by("timestamp")
            .limit_to_last(limit)
            .get()
        )
        return [d.to_dict() for d in docs]
    except Exception:
        return []


def append_message(session_id: str, role: str, content: str) -> None:
    """Append a message to a session's chat history."""
    try:
        db.collection("chat_history").document(session_id).collection("messages").add({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception:
        pass  # Never crash an agent because of logging failure


def clear_history(session_id: str) -> None:
    """Delete all messages for a session."""
    try:
        ref = db.collection("chat_history").document(session_id).collection("messages")
        for doc in ref.stream():
            doc.reference.delete()
    except Exception:
        pass


def format_history_for_llm(history: list[dict]) -> list[dict]:
    """Convert stored history to openai-style messages list."""
    return [{"role": h["role"], "content": h["content"]} for h in history]

"""SQLite persistence for local Resume Agent sessions."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..database import connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(source_resume_id: str | None, document: dict[str, Any]) -> dict[str, Any]:
    session = {
        "id": str(uuid4()),
        "source_resume_id": source_resume_id,
        "document": document,
        "goal": None,
        "version": 1,
        "messages": [],
        "created_at": _now(),
        "updated_at": _now(),
    }
    with connection() as conn:
        conn.execute(
            "INSERT INTO resume_agent_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session["id"], source_resume_id, json.dumps(document, ensure_ascii=False), None, 1,
             json.dumps([], ensure_ascii=False), session["created_at"], session["updated_at"]),
        )
    return session


def _row(row) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["document"] = json.loads(data["document"])
    data["goal"] = json.loads(data["goal"]) if data["goal"] else None
    data["messages"] = json.loads(data["messages"] or "[]")
    return data


def get_session(session_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        return _row(conn.execute("SELECT * FROM resume_agent_sessions WHERE id = ?", (session_id,)).fetchone())


def update_session(session_id: str, *, document=None, goal=None, version=None, messages=None) -> dict[str, Any] | None:
    current = get_session(session_id)
    if current is None:
        return None
    document = current["document"] if document is None else document
    goal = current["goal"] if goal is None else goal
    version = current["version"] if version is None else version
    messages = current["messages"] if messages is None else messages
    updated_at = _now()
    with connection() as conn:
        conn.execute(
            "UPDATE resume_agent_sessions SET document = ?, goal = ?, version = ?, messages = ?, updated_at = ? WHERE id = ?",
            (json.dumps(document, ensure_ascii=False), json.dumps(goal, ensure_ascii=False) if goal is not None else None,
             version, json.dumps(messages, ensure_ascii=False), updated_at, session_id),
        )
    return get_session(session_id)

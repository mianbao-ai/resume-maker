"""Resume Agent persistence models."""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid4().hex


class ResumeAgentSession(SQLModel, table=True):
    __tablename__ = "resume_agent_sessions"

    id: str = Field(default_factory=_uuid, primary_key=True, index=True)
    user_id: str = Field(index=True)
    source_resume_id: Optional[str] = Field(default=None, index=True)
    mode: str = Field(default="optimization", max_length=40)
    target_role: Optional[str] = Field(default=None, max_length=255)
    audience: str = Field(default="general", max_length=50)
    resume_document_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    document_version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ResumeAgentMessage(SQLModel, table=True):
    __tablename__ = "resume_agent_messages"

    id: str = Field(default_factory=_uuid, primary_key=True, index=True)
    session_id: str = Field(index=True)
    role: str = Field(max_length=20)
    content: str
    intent: Optional[str] = Field(default=None, max_length=40)
    payload_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ResumeAgentProposal(SQLModel, table=True):
    __tablename__ = "resume_agent_proposals"

    id: str = Field(default_factory=_uuid, primary_key=True, index=True)
    session_id: str = Field(index=True)
    message_id: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="pending", max_length=30, index=True)
    title: str = Field(max_length=255)
    rationale: str
    patches_json: list = Field(default_factory=list, sa_column=Column(JSON))
    risk_notes_json: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

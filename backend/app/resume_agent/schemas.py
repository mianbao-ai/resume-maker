from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .core.schemas import ResumeGoalInput, ResumePatch


class AgentSessionCreate(BaseModel):
    source_resume_id: Optional[str] = None
    audience: str = "general"
    target_role: Optional[str] = None


class AgentSessionOut(BaseModel):
    id: str
    source_resume_id: Optional[str] = None
    document: Dict[str, Any]
    goal: Optional[Dict[str, Any]] = None
    version: int
    messages: list[Dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str


class AgentGoalUpdate(BaseModel):
    goal: ResumeGoalInput


class AgentDocumentUpdate(BaseModel):
    base_version: int = Field(ge=1)
    patches: list[ResumePatch]


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)

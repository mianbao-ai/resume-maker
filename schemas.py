"""Schemas for the Resume Agent API."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ResumeAudience = Literal["hr", "graduate_examiner", "internship_recruiter", "general"]
ResumePurpose = Literal[
    "graduate_reexamination",
    "internship",
    "campus_recruitment",
    "social_recruitment",
    "other",
    "undecided",
]


class ResumeGoalInput(BaseModel):
    purpose: ResumePurpose
    target_organization: Optional[str] = Field(default=None, max_length=255)
    target_role: Optional[str] = Field(default=None, max_length=255)
    research_direction: Optional[str] = Field(default=None, max_length=500)
    job_description: Optional[str] = Field(default=None, max_length=20_000)
    additional_context: Optional[str] = Field(default=None, max_length=2_000)


class ResumePatch(BaseModel):
    id: str
    op: Literal["add", "replace", "remove"]
    path: str
    value: Optional[Any] = None
    before: Optional[Any] = None
    after: Optional[Any] = None


class ChangeProposalOut(BaseModel):
    id: str
    status: Literal["pending", "accepted", "rejected", "superseded"]
    title: str
    rationale: str
    patches: List[ResumePatch]
    risk_notes: List[str] = Field(default_factory=list)
    created_at: str


class QuestionOptionOut(BaseModel):
    id: str
    label: str
    description: str = ""
    recommended: bool = False


class ClarifyingQuestionOut(BaseModel):
    id: str
    title: str
    allow_other: bool = False
    options: List[QuestionOptionOut] = Field(default_factory=list)


class AgentActivityOut(BaseModel):
    """Public progress state shown while a Resume Agent run is executing."""

    id: str
    skill_id: Optional[str] = None
    label: str
    state: Literal["running", "completed", "waiting", "error"]
    started_at: str
    completed_at: Optional[str] = None


class AgentMessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    intent: Optional[str] = None
    proposals: List[ChangeProposalOut] = Field(default_factory=list)
    questions: List[ClarifyingQuestionOut] = Field(default_factory=list)
    activity: Optional[AgentActivityOut] = None
    created_at: str


class CreateSessionRequest(BaseModel):
    source_resume_id: Optional[str] = None
    audience: ResumeAudience = "general"
    target_role: Optional[str] = None
    mode: Literal["optimization"] = "optimization"
    force_new: bool = False


class CreateSessionResponse(BaseModel):
    session_id: str
    resume_document: Dict[str, Any]
    messages: List[AgentMessageOut] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str
    audience: Optional[ResumeAudience] = None
    model: Literal["deepseek-v4", "doubao-seed-2.1-pro"] = "deepseek-v4"
    skill_id: Optional[Literal["compress_one_page"]] = None
    page_count: Optional[int] = Field(default=None, ge=1, le=20)


class ApplyProposalRequest(BaseModel):
    patch_ids: Optional[List[str]] = None
    overrides: Optional[Dict[str, Any]] = None
    base_version: Optional[int] = Field(default=None, ge=1)


class ApplyProposalResponse(BaseModel):
    resume_document: Dict[str, Any]
    applied_proposal: ChangeProposalOut


class UpdateDocumentRequest(BaseModel):
    base_version: int
    patches: List[ResumePatch]


class UpdateDocumentResponse(BaseModel):
    resume_document: Dict[str, Any]


class UpdateGoalResponse(BaseModel):
    resume_document: Dict[str, Any]
    messages: List[AgentMessageOut] = Field(default_factory=list)


class RejectProposalResponse(BaseModel):
    proposal: ChangeProposalOut


class ExportPdfRequest(BaseModel):
    html: Optional[str] = Field(default=None, max_length=500_000)
    css: Optional[str] = Field(default=None, max_length=750_000)

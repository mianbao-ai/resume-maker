"""
Resume metadata model stored in SQL database.
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlmodel import SQLModel, Field


def _generate_resume_id() -> str:
    return uuid4().hex


class ResumeFile(SQLModel, table=True):
    """Persisted resume file metadata bound to an authenticated user."""

    __tablename__ = "resume_files"

    id: str = Field(default_factory=_generate_resume_id, primary_key=True, index=True)
    user_id: str = Field(index=True, description="Authenticated user identifier")
    original_filename: str = Field(max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=255)
    stored_filename: str = Field(max_length=255)
    storage_path: str = Field(description="Absolute path to stored file")
    content_type: Optional[str] = Field(default=None, max_length=255)
    file_size: int = Field(ge=0)
    is_interview_default: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

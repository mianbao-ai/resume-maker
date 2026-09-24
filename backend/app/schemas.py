from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PersonalInfo(BaseModel):
    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    website: str = ""
    summary: str = ""


class Experience(BaseModel):
    id: str
    company: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = ""
    current: bool = False
    description: str = ""


class Project(BaseModel):
    id: str
    name: str = ""
    role: str = ""
    link: str = ""
    description: str = ""


class Education(BaseModel):
    id: str
    school: str = ""
    degree: str = ""
    start_date: str = ""
    end_date: str = ""


class Skill(BaseModel):
    id: str
    name: str = ""
    level: Literal["了解", "熟悉", "熟练", "精通"] = "熟练"


class ResumeContent(BaseModel):
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    experiences: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)


class ResumeCreate(BaseModel):
    title: str = Field(default="未命名简历", min_length=1, max_length=120)
    template: Literal["classic", "minimal"] = "classic"
    accent_color: str = Field(default="#176B5B", pattern=r"^#[0-9a-fA-F]{6}$")
    content: ResumeContent = Field(default_factory=ResumeContent)


class ResumeUpdate(ResumeCreate):
    pass


class Resume(ResumeCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class ResumeSummary(BaseModel):
    id: str
    title: str
    template: str
    accent_color: str
    updated_at: datetime

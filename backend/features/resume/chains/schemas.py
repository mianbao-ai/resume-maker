"""Pydantic models for normalized resume facts and scene profiles.

These models are the canonical resume fact schema. Raw LLM output must pass
through a normalization layer before it is validated as ``ResumeFacts``.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResumeFactModel(BaseModel):
    """Shared strict configuration for normalized resume facts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EmploymentType(str, Enum):
    INTERNSHIP = "internship"
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    VOLUNTEER = "volunteer"
    LABORATORY = "laboratory"
    CAMPUS_ROLE = "campus_role"
    OTHER = "other"
    UNKNOWN = "unknown"


class ProjectType(str, Enum):
    ENGINEERING = "engineering"
    RESEARCH = "research"
    COURSE = "course"
    CAPSTONE = "capstone"
    COMPETITION = "competition"
    PERSONAL = "personal"
    OPEN_SOURCE = "open_source"
    PRODUCT = "product"
    OTHER = "other"
    UNKNOWN = "unknown"


class ProjectContext(str, Enum):
    WORK = "work"
    INTERNSHIP = "internship"
    LABORATORY = "laboratory"
    COURSE = "course"
    CAPSTONE = "capstone"
    COMPETITION = "competition"
    PERSONAL = "personal"
    OPEN_SOURCE = "open_source"
    OTHER = "other"
    UNKNOWN = "unknown"


class ResumeScene(str, Enum):
    JOB = "job"
    GRADUATE = "graduate"


class SourceEvidence(ResumeFactModel):
    """Small source reference used to audit an extracted fact."""

    page: int | None = Field(default=None, ge=1)
    excerpt: str = Field(default="", max_length=500)


class BasicInfo(ResumeFactModel):
    name: str = ""
    phone: str = ""
    email: str = ""
    location: str = ""
    headline: str = ""


class Education(ResumeFactModel):
    education_id: str = Field(min_length=1, max_length=100)
    institution_name: str = ""
    school_or_department: str = ""
    major: str = ""
    degree: str = ""
    start_date: str = ""
    end_date: str = ""
    grade: str = ""
    ranking: str = ""
    courses: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    source: SourceEvidence | None = None


class WorkExperience(ResumeFactModel):
    """An organizational relationship, independent from project facts."""

    experience_id: str = Field(min_length=1, max_length=100)
    organization_name: str = ""
    department: str = ""
    position: str = ""
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    start_date: str = ""
    end_date: str = ""
    location: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    source: SourceEvidence | None = None

    @model_validator(mode="after")
    def require_meaningful_content(self) -> "WorkExperience":
        if not (self.organization_name or self.position or self.responsibilities):
            raise ValueError(
                "work experience requires organization_name, position, or responsibilities"
            )
        return self


class ProjectExperience(ResumeFactModel):
    """A bounded project which may optionally relate to work experiences."""

    project_id: str = Field(min_length=1, max_length=100)
    project_name: str = ""
    project_types: list[ProjectType] = Field(default_factory=list)
    project_context: ProjectContext = ProjectContext.UNKNOWN
    start_date: str = ""
    end_date: str = ""
    role: str = ""
    description: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    personal_contribution: list[str] = Field(default_factory=list)
    related_work_experience_ids: list[str] = Field(default_factory=list)
    source: SourceEvidence | None = None

    @field_validator("project_types", "related_work_experience_ids")
    @classmethod
    def deduplicate_values(cls, values: list) -> list:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def require_meaningful_content(self) -> "ProjectExperience":
        if not (self.project_name or self.description):
            raise ValueError("project experience requires project_name or description")
        return self


class Publication(ResumeFactModel):
    publication_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1)
    venue: str = ""
    date: str = ""
    authors: list[str] = Field(default_factory=list)
    related_project_id: str | None = None
    source: SourceEvidence | None = None


class Award(ResumeFactModel):
    award_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1)
    issuer: str = ""
    level: str = ""
    date: str = ""
    related_project_id: str | None = None
    source: SourceEvidence | None = None


class Certification(ResumeFactModel):
    certification_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1)
    issuer: str = ""
    date: str = ""
    credential_id: str = ""
    source: SourceEvidence | None = None


class Achievements(ResumeFactModel):
    publications: list[Publication] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)


class LanguageSkill(ResumeFactModel):
    language: str = Field(min_length=1)
    proficiency: str = ""
    certifications: list[str] = Field(default_factory=list)


class ExtractionWarning(ResumeFactModel):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)
    page: int | None = Field(default=None, ge=1)


class ExtractionMetadata(ResumeFactModel):
    parser_version: str = ""
    extraction_method: str = ""
    source_page_count: int | None = Field(default=None, ge=0)
    extracted_page_count: int | None = Field(default=None, ge=0)
    quality_score: float | None = Field(default=None, ge=0, le=1)
    warnings: list[ExtractionWarning] = Field(default_factory=list)
    @model_validator(mode="after")
    def extracted_pages_cannot_exceed_source(self) -> "ExtractionMetadata":
        if (
            self.source_page_count is not None
            and self.extracted_page_count is not None
            and self.extracted_page_count > self.source_page_count
        ):
            raise ValueError("extracted_page_count cannot exceed source_page_count")
        return self


class ResumeFacts(ResumeFactModel):
    """Normalized, scene-independent resume facts."""

    schema_version: Literal["2.0"] = "2.0"
    resume_id: str = Field(min_length=1, max_length=100)
    basic_info: BasicInfo = Field(default_factory=BasicInfo)
    education: list[Education] = Field(default_factory=list)
    work_experience: list[WorkExperience] = Field(default_factory=list)
    project_experience: list[ProjectExperience] = Field(default_factory=list)
    achievements: Achievements = Field(default_factory=Achievements)
    skills: list[str] = Field(default_factory=list)
    languages: list[LanguageSkill] = Field(default_factory=list)
    extraction_metadata: ExtractionMetadata = Field(default_factory=ExtractionMetadata)

    @field_validator("skills")
    @classmethod
    def deduplicate_skills(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_ids_and_relationships(self) -> "ResumeFacts":
        work_ids = [item.experience_id for item in self.work_experience]
        project_ids = [item.project_id for item in self.project_experience]
        education_ids = [item.education_id for item in self.education]

        self._require_unique_ids("work experience", work_ids)
        self._require_unique_ids("project experience", project_ids)
        self._require_unique_ids("education", education_ids)

        known_work_ids = set(work_ids)
        for project in self.project_experience:
            unknown_work_ids = set(project.related_work_experience_ids) - known_work_ids
            if unknown_work_ids:
                raise ValueError(
                    f"project {project.project_id!r} references unknown work experience "
                    f"IDs: {sorted(unknown_work_ids)}"
                )

        known_project_ids = set(project_ids)
        related_project_ids = [
            item.related_project_id
            for item in (
                *self.achievements.publications,
                *self.achievements.awards,
            )
            if item.related_project_id
        ]
        unknown_project_ids = set(related_project_ids) - known_project_ids
        if unknown_project_ids:
            raise ValueError(
                "achievements reference unknown project IDs: "
                f"{sorted(unknown_project_ids)}"
            )

        return self

    @staticmethod
    def _require_unique_ids(label: str, values: list[str]) -> None:
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {label} IDs are not allowed")


class JobProfile(ResumeFactModel):
    scene: Literal[ResumeScene.JOB] = ResumeScene.JOB
    resume_id: str = Field(min_length=1, max_length=100)
    target_job: str = ""
    job_description_snapshot: str = Field(default="", max_length=20_000)
    priority_work_experience_ids: list[str] = Field(default_factory=list)
    priority_project_ids: list[str] = Field(default_factory=list)
    core_competencies: list[str] = Field(default_factory=list)
    evidence_highlights: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class GraduateProfile(ResumeFactModel):
    scene: Literal[ResumeScene.GRADUATE] = ResumeScene.GRADUATE
    resume_id: str = Field(min_length=1, max_length=100)
    target_program: str = ""
    priority_education_ids: list[str] = Field(default_factory=list)
    priority_project_ids: list[str] = Field(default_factory=list)
    academic_strengths: list[str] = Field(default_factory=list)
    research_interests: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    warnings: list[ExtractionWarning] = Field(default_factory=list)

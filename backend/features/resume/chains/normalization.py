"""Deterministic normalization for raw Resume Facts extraction output."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, TypeVar

from .schemas import (
    Achievements,
    Award,
    BasicInfo,
    Certification,
    Education,
    EmploymentType,
    ExtractionMetadata,
    ExtractionWarning,
    LanguageSkill,
    ProjectContext,
    ProjectExperience,
    ProjectType,
    Publication,
    ResumeFacts,
    SourceEvidence,
    WorkExperience,
)


PARSER_VERSION = "resume-facts-parser-1"
TEnum = TypeVar("TEnum")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        value = value.strip()
        return "" if value.lower() in {"none", "null", "n/a", "未提供", "未知"} else value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "；".join(item for item in (_text(v) for v in value) if item)
    return ""


def _items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _strings(value: Any, *, split: bool = False) -> list[str]:
    if value is None or value == "":
        return []
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        text = _text(item)
        if not text:
            continue
        parts = re.split(r"[,，、;；|]", text) if split else [text]
        result.extend(part.strip() for part in parts if part.strip())
    return list(dict.fromkeys(result))


def _value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def _enum(value: Any, enum_cls: type[TEnum], default: TEnum) -> TEnum:
    normalized = _text(value).lower().replace("-", "_").replace(" ", "_")
    try:
        return enum_cls(normalized)  # type: ignore[call-arg]
    except (TypeError, ValueError):
        return default


def _source(item: dict[str, Any]) -> SourceEvidence | None:
    raw = item.get("source") if isinstance(item.get("source"), dict) else {}
    excerpt = _text(raw.get("excerpt") or item.get("source_excerpt"))[:500]
    page_value = raw.get("page", item.get("source_page"))
    try:
        page = int(page_value) if page_value not in (None, "") else None
        if page is not None and page < 1:
            page = None
    except (TypeError, ValueError):
        page = None
    return SourceEvidence(page=page, excerpt=excerpt) if excerpt or page else None


def _stable_id(prefix: str, values: Iterable[Any]) -> str:
    material = "|".join(_text(value).casefold() for value in values)
    digest = hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _signature(*values: Any) -> tuple[str, ...]:
    return tuple(re.sub(r"\s+", "", _text(value)).casefold() for value in values)


def _infer_employment_type(item: dict[str, Any]) -> EmploymentType:
    explicit = _enum(
        _value(item, "employment_type", "type"),
        EmploymentType,
        EmploymentType.UNKNOWN,
    )
    if explicit != EmploymentType.UNKNOWN:
        return explicit
    text = " ".join(_text(value) for value in item.values()).casefold()
    rules = (
        (EmploymentType.INTERNSHIP, ("实习", "intern")),
        (EmploymentType.PART_TIME, ("兼职", "part-time", "part time")),
        (EmploymentType.VOLUNTEER, ("志愿", "volunteer")),
        (EmploymentType.LABORATORY, ("实验室", "助研", "research assistant", "laboratory")),
        (EmploymentType.CAMPUS_ROLE, ("学生会", "社团", "班长", "校园任职")),
        (EmploymentType.FULL_TIME, ("全职", "full-time", "full time")),
    )
    for employment_type, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return employment_type
    return EmploymentType.UNKNOWN


def _infer_project_types(item: dict[str, Any]) -> list[ProjectType]:
    explicit_values = _strings(_value(item, "project_types", "project_type"), split=True)
    explicit = [
        _enum(value, ProjectType, ProjectType.UNKNOWN)
        for value in explicit_values
    ]
    explicit = [value for value in dict.fromkeys(explicit) if value != ProjectType.UNKNOWN]
    if explicit:
        return explicit

    text = " ".join(_text(value) for value in item.values()).casefold()
    inferred: list[ProjectType] = []
    rules = (
        (ProjectType.COMPETITION, ("竞赛", "比赛", "大赛", "competition", "contest")),
        (ProjectType.CAPSTONE, ("毕业设计", "毕业论文", "capstone", "thesis")),
        (ProjectType.COURSE, ("课程设计", "课程项目", "course project")),
        (ProjectType.OPEN_SOURCE, ("开源", "open source", "github")),
        (ProjectType.RESEARCH, ("科研", "研究", "论文", "实验", "research")),
        (ProjectType.ENGINEERING, ("开发", "系统", "平台", "模型部署", "engineering", "software")),
        (ProjectType.PRODUCT, ("产品", "上线", "用户", "product")),
        (ProjectType.PERSONAL, ("个人项目", "personal project")),
    )
    for project_type, keywords in rules:
        if any(keyword in text for keyword in keywords):
            inferred.append(project_type)
    return inferred or [ProjectType.UNKNOWN]


def _infer_project_context(item: dict[str, Any], types: list[ProjectType]) -> ProjectContext:
    explicit = _enum(
        _value(item, "project_context", "context"),
        ProjectContext,
        ProjectContext.UNKNOWN,
    )
    if explicit != ProjectContext.UNKNOWN:
        return explicit
    text = " ".join(_text(value) for value in item.values()).casefold()
    context_rules = (
        (ProjectContext.INTERNSHIP, ("实习", "intern")),
        (ProjectContext.LABORATORY, ("实验室", "laboratory")),
        (ProjectContext.CAPSTONE, ("毕业设计", "毕业论文", "capstone", "thesis")),
        (ProjectContext.COURSE, ("课程", "course")),
        (ProjectContext.COMPETITION, ("竞赛", "比赛", "competition", "contest")),
        (ProjectContext.OPEN_SOURCE, ("开源", "open source")),
        (ProjectContext.PERSONAL, ("个人项目", "personal project")),
    )
    for context, keywords in context_rules:
        if any(keyword in text for keyword in keywords):
            return context
    if ProjectType.COMPETITION in types:
        return ProjectContext.COMPETITION
    return ProjectContext.UNKNOWN


def _warning(code: str, message: str, item: dict[str, Any] | None = None) -> ExtractionWarning:
    source = _source(item or {})
    return ExtractionWarning(code=code, message=message[:1000], page=source.page if source else None)


def normalize_extraction_output(
    raw_output: dict[str, Any],
    *,
    resume_id: str,
    source_page_count: int | None = None,
) -> ResumeFacts:
    """Normalize permissive section output into strict, linked ResumeFacts."""
    warnings: list[ExtractionWarning] = []
    section_errors = raw_output.get("section_errors")
    section_errors = section_errors if isinstance(section_errors, dict) else {}
    for section, error in section_errors.items():
        warnings.append(_warning("section_extraction_failed", f"{section}: {_text(error)}"))

    basic_section = raw_output.get("basic_education") or raw_output
    basic_raw = basic_section.get("basic_info") if isinstance(basic_section, dict) else {}
    basic_raw = basic_raw if isinstance(basic_raw, dict) else {}
    basic_info = BasicInfo(
        name=_text(_value(basic_raw, "name", "full_name")),
        phone=_text(_value(basic_raw, "phone", "telephone")),
        email=_text(basic_raw.get("email")),
        location=_text(_value(basic_raw, "location", "city")),
        headline=_text(_value(basic_raw, "headline", "summary", "objective")),
    )

    education: list[Education] = []
    seen_education: set[tuple[str, ...]] = set()
    education_raw = _items(basic_section.get("education") if isinstance(basic_section, dict) else None)
    for item in education_raw:
        institution = _text(_value(item, "institution_name", "school", "university"))
        major = _text(_value(item, "major", "Major"))
        degree = _text(_value(item, "degree", "Degree"))
        start_date = _text(_value(item, "start_date", "start"))
        end_date = _text(_value(item, "end_date", "end", "graduation_date"))
        sig = _signature(institution, major, degree, start_date, end_date)
        if not any(sig) or sig in seen_education:
            if sig in seen_education:
                warnings.append(_warning("duplicate_education_dropped", "重复教育经历已合并", item))
            continue
        seen_education.add(sig)
        education.append(Education(
            education_id=_stable_id("edu", sig),
            institution_name=institution,
            school_or_department=_text(_value(item, "school_or_department", "department")),
            major=major,
            degree=degree,
            start_date=start_date,
            end_date=end_date,
            grade=_text(_value(item, "grade", "gpa")),
            ranking=_text(item.get("ranking")),
            courses=_strings(item.get("courses"), split=True),
            highlights=_strings(item.get("highlights")),
            source=_source(item),
        ))

    work_section = raw_output.get("work") or raw_output
    work_raw = _items(work_section.get("work_experience") if isinstance(work_section, dict) else None)
    work_experience: list[WorkExperience] = []
    work_aliases: dict[str, str] = {}
    seen_work: set[tuple[str, ...]] = set()
    for item in work_raw:
        organization = _text(_value(item, "organization_name", "organization", "company_name", "company"))
        position = _text(_value(item, "position", "job_title", "title"))
        start_date = _text(_value(item, "start_date", "start"))
        end_date = _text(_value(item, "end_date", "end"))
        responsibilities = _strings(_value(item, "responsibilities", "duties", "description"))
        sig = _signature(organization, position, start_date, end_date)
        if not (organization or position or responsibilities):
            warnings.append(_warning("empty_work_dropped", "空的任职经历已丢弃", item))
            continue
        if sig in seen_work:
            warnings.append(_warning("duplicate_work_dropped", "重复任职经历已合并", item))
            continue
        seen_work.add(sig)
        experience_id = _stable_id("work", (*sig, *responsibilities))
        work = WorkExperience(
            experience_id=experience_id,
            organization_name=organization,
            department=_text(item.get("department")),
            position=position,
            employment_type=_infer_employment_type(item),
            start_date=start_date,
            end_date=end_date,
            location=_text(item.get("location")),
            responsibilities=responsibilities,
            achievements=_strings(_value(item, "achievements", "results")),
            source=_source(item),
        )
        work_experience.append(work)
        aliases = {
            experience_id,
            _text(item.get("experience_id")),
            _text(item.get("source_key")),
            organization.casefold(),
            f"{organization}|{position}".casefold(),
        }
        for alias in aliases:
            if alias:
                work_aliases[alias] = experience_id

    project_section = raw_output.get("project") or raw_output
    project_raw = _items(project_section.get("project_experience") if isinstance(project_section, dict) else None)
    project_experience: list[ProjectExperience] = []
    project_aliases: dict[str, str] = {}
    seen_project: set[tuple[str, ...]] = set()
    for item in project_raw:
        name = _text(_value(item, "project_name", "name", "Project_name", "Research_topic"))
        description = _text(_value(item, "description", "project_description", "Project_description", "Research_description"))
        if not (name or description):
            warnings.append(_warning("empty_project_dropped", "空的项目经历已丢弃", item))
            continue
        start_date = _text(_value(item, "start_date", "start"))
        end_date = _text(_value(item, "end_date", "end"))
        sig = _signature(
            name,
            description,
            start_date,
            end_date,
            item.get("role"),
            item.get("related_organization_name"),
        )
        if sig in seen_project:
            warnings.append(_warning("duplicate_project_dropped", "重复项目经历已合并", item))
            continue
        seen_project.add(sig)

        related_ids: list[str] = []
        references = _strings(item.get("related_work_experience_ids"))
        related_org = _text(item.get("related_organization_name"))
        related_position = _text(item.get("related_position"))
        if related_org:
            references.extend([related_org, f"{related_org}|{related_position}"])
        for reference in references:
            key = reference.casefold()
            matched = work_aliases.get(key)
            if not matched and related_org:
                for work in work_experience:
                    if related_org.casefold() in work.organization_name.casefold() or work.organization_name.casefold() in related_org.casefold():
                        matched = work.experience_id
                        break
            if matched:
                related_ids.append(matched)
            else:
                warnings.append(_warning("unresolved_work_relation", f"项目关联线索无法匹配任职经历：{reference}", item))

        types = _infer_project_types(item)
        project_id = _stable_id("project", sig)
        project = ProjectExperience(
            project_id=project_id,
            project_name=name,
            project_types=types,
            project_context=_infer_project_context(item, types),
            start_date=start_date,
            end_date=end_date,
            role=_text(item.get("role")),
            description=description,
            responsibilities=_strings(item.get("responsibilities")),
            methods=_strings(item.get("methods")),
            tech_stack=_strings(_value(item, "tech_stack", "Project_tech_stack"), split=True),
            achievements=_strings(_value(item, "achievements", "Project_achievement", "Research_achievement")),
            personal_contribution=_strings(item.get("personal_contribution")),
            related_work_experience_ids=list(dict.fromkeys(related_ids)),
            source=_source(item),
        )
        project_experience.append(project)
        for alias in (_text(item.get("project_id")), _text(item.get("source_key")), name.casefold()):
            if alias:
                project_aliases[alias] = project_id
        project_aliases[project_id] = project_id

    achievement_section = raw_output.get("achievements") or raw_output
    achievement_root = achievement_section.get("achievements") if isinstance(achievement_section, dict) else {}
    if not isinstance(achievement_root, dict) and isinstance(achievement_section, dict):
        achievement_root = achievement_section
    elif not achievement_root and isinstance(achievement_section, dict):
        if any(key in achievement_section for key in ("publications", "awards", "certifications")):
            achievement_root = achievement_section
    achievement_root = achievement_root if isinstance(achievement_root, dict) else {}

    def related_project_id(item: dict[str, Any]) -> str | None:
        reference = _text(_value(item, "related_project_id", "related_project_reference"))
        if not reference:
            return None
        matched = project_aliases.get(reference.casefold())
        if not matched:
            warnings.append(_warning("unresolved_project_relation", f"成果关联线索无法匹配项目：{reference}", item))
        return matched

    publications: list[Publication] = []
    seen_publications: set[tuple[str, ...]] = set()
    for item in _items(achievement_root.get("publications")):
        title = _text(item.get("title"))
        sig = _signature(title, item.get("venue"), item.get("date"))
        if not title or sig in seen_publications:
            continue
        seen_publications.add(sig)
        publications.append(Publication(
            publication_id=_stable_id("publication", sig),
            title=title,
            venue=_text(item.get("venue")),
            date=_text(item.get("date")),
            authors=_strings(item.get("authors"), split=True),
            related_project_id=related_project_id(item),
            source=_source(item),
        ))

    awards: list[Award] = []
    seen_awards: set[tuple[str, ...]] = set()
    for item in _items(achievement_root.get("awards")):
        name = _text(_value(item, "name", "award_name"))
        sig = _signature(name, item.get("issuer"), item.get("level"), item.get("date"))
        if not name or sig in seen_awards:
            continue
        seen_awards.add(sig)
        awards.append(Award(
            award_id=_stable_id("award", sig),
            name=name,
            issuer=_text(item.get("issuer")),
            level=_text(item.get("level")),
            date=_text(item.get("date")),
            related_project_id=related_project_id(item),
            source=_source(item),
        ))

    certifications: list[Certification] = []
    seen_certifications: set[tuple[str, ...]] = set()
    for item in _items(achievement_root.get("certifications")):
        name = _text(item.get("name"))
        sig = _signature(name, item.get("issuer"), item.get("date"))
        if not name or sig in seen_certifications:
            continue
        seen_certifications.add(sig)
        certifications.append(Certification(
            certification_id=_stable_id("certification", sig),
            name=name,
            issuer=_text(item.get("issuer")),
            date=_text(item.get("date")),
            credential_id=_text(item.get("credential_id")),
            source=_source(item),
        ))

    languages: list[LanguageSkill] = []
    for item in _items(basic_section.get("languages") if isinstance(basic_section, dict) else None):
        language = _text(item.get("language"))
        if language:
            languages.append(LanguageSkill(
                language=language,
                proficiency=_text(item.get("proficiency")),
                certifications=_strings(item.get("certifications"), split=True),
            ))

    skills = _strings(basic_section.get("skills") if isinstance(basic_section, dict) else None, split=True)
    completeness = sum((
        bool(basic_info.name),
        bool(education),
        bool(work_experience),
        bool(project_experience),
        bool(skills),
    )) / 5
    quality_score = max(0.0, min(1.0, round(0.5 + completeness * 0.5 - len(warnings) * 0.03, 3)))

    return ResumeFacts(
        resume_id=resume_id,
        basic_info=basic_info,
        education=education,
        work_experience=work_experience,
        project_experience=project_experience,
        achievements=Achievements(
            publications=publications,
            awards=awards,
            certifications=certifications,
        ),
        skills=skills,
        languages=languages,
        extraction_metadata=ExtractionMetadata(
            parser_version=PARSER_VERSION,
            extraction_method="llm-section-extraction+deterministic-normalization",
            source_page_count=source_page_count,
            warnings=warnings,
            quality_score=quality_score,
        ),
    )

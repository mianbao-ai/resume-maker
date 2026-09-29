"""Map normalized StudentInfo onto the canonical ResumeDocument template.

StudentInfo is an extraction intermediate (shared with the interview bot).
ResumeDocument is the template the editor, layout, and exporters render.

Section sources
---------------
basics            ← name, gender, phone, email, location, links
                  ← extras: age / political_status / wechat (user can add more)
education         ← Education, with Graduate_School / Major / GPA / Major_courses fallback
projects          ← Project_experience  (course / product work)
experiences       ← Work_experience     (internships and jobs)
research          ← Research_experience (papers, patents, lab work)
awards            ← Competition_experience + Honor_awards
skills            ← Skills  (language tokens already in Languages are dropped)
languages         ← Languages
volunteering      ← Campus_activities
selfEvaluation    ← Self_evaluation
courses/strengths/interests/industryExpertise/custom stay empty unless source has them

Layout uses DEFAULT_SECTION_ORDERS from patching; this module does not duplicate
those lists. Empty source sections stay empty. Text is copied, never translated.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from .patching import (
    DEFAULT_SECTION_ORDERS,
    VALID_TEMPLATE_IDS,
    collapse_education_item,
    default_contact_order,
    format_coursework_line,
    is_github_profile_link,
    normalize_basics_contacts,
)

DOCUMENT_ROOT_KEYS = (
    "id",
    "userId",
    "sourceResumeId",
    "title",
    "targetRole",
    "audience",
    "locale",
    "templateId",
    "sectionOrder",
    "basics",
    "education",
    "projects",
    "experiences",
    "research",
    "awards",
    "skills",
    "selfEvaluation",
    "languages",
    "courses",
    "strengths",
    "volunteering",
    "interests",
    "industryExpertise",
    "custom",
    "formatting",
    "goal",
    "version",
    "createdAt",
    "updatedAt",
)

AUDIENCE_TEMPLATE_IDS = {
    "graduate_examiner": "postgraduate-interview-v1",
}

PURPOSE_TEMPLATE_IDS = {
    "graduate_reexamination": "postgraduate-interview-v1",
}

KEY_PROFILE_FIELDS = (
    ("gender", "性别"),
    ("phone", "电话"),
    ("email", "邮箱"),
    ("location", "所在地"),
)

_LANGUAGE_TOKEN = re.compile(
    r"(英语|日语|法语|德语|韩语|俄语|西班牙语|普通话|chinese|english|japanese|"
    r"mandarin|ielts|toefl|cet-?\d)",
    re.I,
)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _sid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def template_id_for_audience(audience: str) -> str:
    return AUDIENCE_TEMPLATE_IDS.get(audience, "tech-elegant-v1")


def template_id_for_purpose(purpose: str) -> str:
    return PURPOSE_TEMPLATE_IDS.get(purpose, "tech-elegant-v1")


def section_order_for_template(template_id: str) -> List[str]:
    if template_id not in VALID_TEMPLATE_IDS:
        template_id = "tech-elegant-v1"
    return list(DEFAULT_SECTION_ORDERS[template_id])


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        parts = [_text(item) for item in value]
        return "、".join(part for part in parts if part)
    text = str(value).strip()
    return "" if text in {"未提供", "None", "null"} else text


def _text_list(value: Any) -> list[str]:
    """Keep each value as one item; only explode nested lists, not punctuation."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_text_list(item) if not isinstance(item, str) else [_text(item)])
        return [item for item in items if item]
    text = _text(value)
    return [text] if text else []


def _course_list(value: Any) -> list[str]:
    """Split concatenated course strings such as '数据结构、操作系统'."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_course_list(item))
        return items
    text = re.sub(r"^主修课程[:：]\s*", "", _text(value)).strip()
    if not text:
        return []
    parts = [part.strip() for part in re.split(r"[、,，;；\n]", text) if part.strip()]
    return parts or [text]


def _bullets(*values: Any) -> list[str]:
    items: list[str] = []
    for value in values:
        items.extend(_text_list(value))
    unique: list[str] = []
    for item in items:
        if any(item != other and item in other for other in items):
            continue
        if item not in unique:
            unique.append(item)
    return unique


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _is_pending_admission(degree: str) -> bool:
    return "拟录取" in (degree or "")


def _looks_like_language_skill(skill: str, language_tokens: set[str]) -> bool:
    compact = _compact(skill)
    if compact in language_tokens:
        return True
    return bool(language_tokens and _LANGUAGE_TOKEN.search(skill))


def _filter_skills(skills: Iterable[str], languages: List[Dict[str, str]]) -> list[str]:
    language_tokens = {
        _compact(part)
        for item in languages
        for part in (item.get("name") or "", item.get("level") or "")
        if part
    }
    filtered: list[str] = []
    for skill in skills:
        if _looks_like_language_skill(skill, language_tokens):
            continue
        if skill not in filtered:
            filtered.append(skill)
    return filtered


def _covered_by(text: str, corpus: Iterable[str]) -> bool:
    compact = _compact(text)
    if len(compact) < 4:
        return False
    for other in corpus:
        other_compact = _compact(other)
        if not other_compact:
            continue
        if compact == other_compact or compact in other_compact or other_compact in compact:
            return True
    return False


def _dedup_projects_against_experiences(
    projects: List[Dict[str, Any]],
    experiences: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Internships stay in experiences; drop identical project copies."""
    experience_orgs = {_compact(item.get("company") or "") for item in experiences}
    experience_orgs.discard("")
    experience_bullets = [
        bullet
        for item in experiences
        for bullet in (item.get("bullets") or [])
        if bullet
    ]
    kept: list[Dict[str, Any]] = []
    for project in projects:
        name_key = _compact(project.get("name") or "")
        bullets = [bullet for bullet in (project.get("bullets") or []) if bullet]
        remaining = [bullet for bullet in bullets if not _covered_by(bullet, experience_bullets)]
        name_matches_internship = bool(name_key and name_key in experience_orgs)
        if name_matches_internship and (not bullets or not remaining):
            continue
        if bullets and not remaining:
            continue
        project["bullets"] = remaining or bullets
        kept.append(project)
    return kept


def _map_education(info: Dict[str, Any]) -> list[dict]:
    courses = _course_list(info.get("Major_courses"))
    education: list[dict] = []
    for item in info.get("Education") or []:
        mapped = {
            "id": _sid("edu"),
            "school": item.get("school") or "学校待补充",
            "degree": item.get("degree") or "",
            "major": item.get("major") or "",
            "startDate": item.get("startDate") or "",
            "endDate": item.get("endDate") or "",
            "gpa": item.get("gpa") or "",
            "coursework": "",
            "highlights": _course_list(item.get("highlights")),
        }
        collapse_education_item(mapped)
        education.append(mapped)

    enrolled_school = _text(info.get("Graduate_School"))
    for item in education:
        if not item.get("coursework") and courses and item["school"] == enrolled_school:
            item["coursework"] = format_coursework_line(courses)
        if not item["gpa"] and info.get("GPA") and item["school"] == enrolled_school:
            item["gpa"] = info.get("GPA") or ""

    if not education and (info.get("Graduate_School") or info.get("Major")):
        education.append({
            "id": _sid("edu"),
            "school": info.get("Graduate_School") or "学校待补充",
            "degree": info.get("Degree") or "",
            "major": info.get("Major") or "",
            "startDate": "",
            "endDate": info.get("Graduation_Year") or "",
            "gpa": info.get("GPA") or "",
            "coursework": format_coursework_line(courses),
            "highlights": [],
        })
        return education

    if education and courses and not any(item.get("coursework") for item in education):
        target = next(
            (item for item in education if not _is_pending_admission(item.get("degree") or "")),
            education[0],
        )
        target["coursework"] = format_coursework_line(courses)
    return education


def _map_projects(info: Dict[str, Any]) -> list[dict]:
    projects = []
    for item in info.get("Project_experience") or []:
        name = _text(item.get("Project_name"))
        bullets = _bullets(item.get("Project_description"), item.get("Project_achievement"))
        tech_stack = _course_list(item.get("Project_tech_stack")) or _text_list(item.get("Project_tech_stack"))
        if not name and not bullets:
            continue
        projects.append({
            "id": _sid("project"),
            "name": name or "项目经历",
            "role": _text(item.get("role")),
            "startDate": _text(item.get("startDate")),
            "endDate": _text(item.get("endDate")),
            "techStack": tech_stack,
            "bullets": bullets,
        })
    return projects


def _map_experiences(info: Dict[str, Any]) -> list[dict]:
    experiences = []
    for item in info.get("Work_experience") or []:
        company = _text(item.get("company"))
        bullets = _bullets(item.get("Work_description"), item.get("Work_achievement"))
        if not company and not bullets and not _text(item.get("role")):
            continue
        experiences.append({
            "id": _sid("exp"),
            "company": company or "实习经历",
            "role": _text(item.get("role")),
            "startDate": _text(item.get("startDate")),
            "endDate": _text(item.get("endDate")),
            "bullets": bullets,
        })
    return experiences


def _map_research(info: Dict[str, Any]) -> list[dict]:
    research = []
    for item in info.get("Research_experience") or []:
        title = _text(item.get("Research_topic"))
        bullets = _bullets(item.get("Research_description"), item.get("Research_achievement"))
        if not title and not bullets:
            continue
        research.append({
            "id": _sid("research"),
            "title": title or "科研经历",
            "role": _text(item.get("role")),
            "advisor": _text(item.get("advisor")),
            "startDate": _text(item.get("startDate")),
            "endDate": _text(item.get("endDate")),
            "bullets": bullets,
        })
    return research


def _award_title(name: str, award: str) -> str:
    if name and award and award in name:
        return name
    return " ".join(part for part in (name, award) if part)


def _map_awards(info: Dict[str, Any]) -> list[dict]:
    awards = []
    seen: set[str] = set()
    for item in info.get("Competition_experience") or []:
        title = _award_title(
            _text(item.get("competition_name") or item.get("Competition_name")),
            _text(item.get("award_level")),
        )
        if not title:
            continue
        key = _compact(title)
        if key in seen:
            continue
        seen.add(key)
        awards.append({
            "id": _sid("award"),
            "title": title,
            "date": _text(item.get("date")),
            "issuer": "",
        })
    for item in info.get("Honor_awards") or []:
        title = _text(item.get("title"))
        if not title:
            continue
        key = _compact(title)
        if key in seen:
            continue
        seen.add(key)
        awards.append({
            "id": _sid("award"),
            "title": title,
            "date": _text(item.get("date")),
            "issuer": _text(item.get("issuer")),
        })
    return awards


def _map_languages(info: Dict[str, Any]) -> list[dict]:
    languages = []
    for item in info.get("Languages") or []:
        name = _text(item.get("name"))
        level = _text(item.get("level"))
        if not name and not level:
            continue
        languages.append({
            "id": _sid("lang"),
            "name": name or "英语",
            "level": level,
        })
    return languages


def _format_age(value: Any) -> str:
    text = _text(value)
    if re.fullmatch(r"\d{1,2}", text):
        return f"{text}岁"
    return text


def _map_profile_extras(info: Dict[str, Any]) -> list[dict]:
    extras = []
    age = _format_age(info.get("age"))
    if age:
        extras.append({"id": _sid("profile"), "label": "年龄", "value": age})
    political = _text(info.get("political_status"))
    if political:
        extras.append({"id": _sid("profile"), "label": "政治面貌", "value": political})
    wechat = _text(info.get("wechat"))
    if wechat:
        extras.append({"id": _sid("profile"), "label": "微信", "value": wechat})
    return extras


def _compact_link_text(url: str, label: str = "") -> str:
    compact = re.sub(r"^https?://(www\.)?", "", url, flags=re.I).rstrip("/")
    return compact or label or url


def contact_line_parts(basics: Dict[str, Any], include_github: bool = False) -> List[Tuple[str, str]]:
    """Filled header items as (display_text, json_pointer) for render/export."""
    if not isinstance(basics, dict):
        return []

    extras = [item for item in (basics.get("extras") or []) if isinstance(item, dict)]
    links = [item for item in (basics.get("links") or []) if isinstance(item, dict)]
    extras_by_id = {str(item.get("id") or ""): (index, item) for index, item in enumerate(extras)}
    links_by_id = {str(item.get("id") or ""): (index, item) for index, item in enumerate(links)}
    order = basics.get("contactOrder")
    if not isinstance(order, list) or not order:
        order = default_contact_order(basics)

    parts: List[Tuple[str, str]] = []
    for token in order:
        if token in ("gender", "phone", "email", "location"):
            value = _text(basics.get(token))
            if value:
                parts.append((value, f"/basics/{token}"))
            continue
        if token.startswith("extra:"):
            found = extras_by_id.get(token[6:])
            if not found:
                continue
            index, extra = found
            value = _text(extra.get("value"))
            if value:
                parts.append((value, f"/basics/extras/{index}/value"))
            continue
        if token.startswith("link:"):
            found = links_by_id.get(token[5:])
            if not found:
                continue
            index, link = found
            if is_github_profile_link(link) and not include_github:
                continue
            url = _text(link.get("url"))
            label = _text(link.get("label"))
            text = _compact_link_text(url, label) if url else label
            if text:
                parts.append((text, f"/basics/links/{index}/url" if url else f"/basics/links/{index}/label"))
    if include_github:
        seen = {path for _text_value, path in parts}
        for index, link in enumerate(links):
            if not is_github_profile_link(link):
                continue
            url = _text(link.get("url"))
            label = _text(link.get("label")) or "GitHub"
            text = _compact_link_text(url, label) if url else label
            pointer = f"/basics/links/{index}/url" if url else f"/basics/links/{index}/label"
            if text and pointer not in seen:
                parts.append((text, pointer))
    return parts


def _map_basics(info: Dict[str, Any], target_role: Optional[str]) -> dict:
    links = []
    for item in info.get("links") or []:
        if not isinstance(item, dict):
            continue
        url = _text(item.get("url"))
        label = _text(item.get("label"))
        if not url and not label:
            continue
        links.append({
            "id": _sid("link"),
            "label": label or "主页",
            "url": url,
        })
    basics = {
        "name": info.get("name") or "未命名",
        "headline": _text(target_role),
        "extras": _map_profile_extras(info),
        "links": links,
    }
    for field, _label in KEY_PROFILE_FIELDS:
        basics[field] = _text(info.get(field))
    return normalize_basics_contacts(basics)


def _map_volunteering(info: Dict[str, Any]) -> list[dict]:
    volunteering = []
    for item in info.get("Campus_activities") or []:
        organization = _text(item.get("organization"))
        bullets = _bullets(item.get("description"))
        if not organization and not bullets and not _text(item.get("role")):
            continue
        volunteering.append({
            "id": _sid("vol"),
            "organization": organization or "校园经历",
            "role": _text(item.get("role")),
            "startDate": _text(item.get("startDate")),
            "endDate": _text(item.get("endDate")),
            "bullets": bullets,
        })
    return volunteering


def student_info_to_document(
    *,
    user_id: str,
    source_resume_id: Optional[str],
    student_info: Dict[str, Any],
    audience: str,
    target_role: Optional[str],
) -> Dict[str, Any]:
    """Convert extractor output into a renderable ResumeDocument."""
    info = student_info or {}
    languages = _map_languages(info)
    skill_values = _filter_skills(_text_list(info.get("Skills")), languages)
    skills = [{"id": _sid("skills"), "label": "技能", "skills": skill_values}] if skill_values else []
    experiences = _map_experiences(info)
    projects = _dedup_projects_against_experiences(_map_projects(info), experiences)
    template_id = template_id_for_audience(audience)
    basics = _map_basics(info, target_role)
    return {
        "id": _sid("resume"),
        "userId": user_id,
        "sourceResumeId": source_resume_id,
        "title": f"{basics['name']}的简历",
        "targetRole": target_role or "",
        "audience": audience,
        "locale": "zh-CN",
        "templateId": template_id,
        "sectionOrder": section_order_for_template(template_id),
        "basics": basics,
        "education": _map_education(info),
        "projects": projects,
        "experiences": experiences,
        "research": _map_research(info),
        "awards": _map_awards(info),
        "skills": skills,
        "selfEvaluation": _text(info.get("Self_evaluation")),
        "languages": languages,
        "courses": [],
        "strengths": [],
        "volunteering": _map_volunteering(info),
        "interests": [],
        "industryExpertise": [],
        "custom": [],
        "formatting": {"entries": {}, "inline": {}},
        "version": 1,
        "createdAt": _now_iso(),
        "updatedAt": _now_iso(),
    }

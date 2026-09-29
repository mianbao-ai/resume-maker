"""Adapters between Resume Maker's simple schema and Resume Agent's document."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from .core.patching import DEFAULT_SECTION_ORDERS, normalize_resume_document


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def _bullets(text: str) -> list[str]:
    return [line.strip(" -•\t") for line in (text or "").splitlines() if line.strip(" -•\t")]


def resume_to_document(resume: dict[str, Any] | None) -> dict[str, Any]:
    resume = resume or {}
    content = resume.get("content") or {}
    personal = content.get("personal") or {}
    template_id = "ats-classic-v1" if resume.get("template") == "classic" else "tech-elegant-v1"
    basics: dict[str, Any] = {
        "name": personal.get("name", ""),
        "headline": personal.get("title", ""),
        "email": personal.get("email", ""),
        "phone": personal.get("phone", ""),
        "location": personal.get("location", ""),
        "links": ([{"id": _id("link"), "label": "主页", "url": personal["website"]}]
                  if personal.get("website") else []),
        "extras": [],
    }
    document: dict[str, Any] = {
        "title": resume.get("title") or personal.get("name") or "简历",
        "templateId": template_id,
        "targetRole": personal.get("title", ""),
        "audience": "general",
        "basics": basics,
        "education": [],
        "experiences": [],
        "projects": [],
        "research": [],
        "awards": [],
        "skills": [],
        "languages": [],
        "selfEvaluation": personal.get("summary", ""),
        "sectionOrder": list(DEFAULT_SECTION_ORDERS[template_id]),
        "formatting": {"entries": {}, "inline": {}},
    }
    for item in content.get("experiences", []) or []:
        document["experiences"].append({
            "id": item.get("id") or _id("experience"),
            "company": item.get("company", ""),
            "role": item.get("role", ""),
            "startDate": item.get("start_date", ""),
            "endDate": "至今" if item.get("current") else item.get("end_date", ""),
            "bullets": _bullets(item.get("description", "")),
        })
    for item in content.get("projects", []) or []:
        document["projects"].append({
            "id": item.get("id") or _id("project"),
            "name": item.get("name", ""),
            "role": item.get("role", ""),
            "link": item.get("link", ""),
            "bullets": _bullets(item.get("description", "")),
        })
    for item in content.get("education", []) or []:
        document["education"].append({
            "id": item.get("id") or _id("education"),
            "school": item.get("school", ""),
            "degree": item.get("degree", ""),
            "startDate": item.get("start_date", ""),
            "endDate": item.get("end_date", ""),
            "highlights": [],
        })
    if content.get("skills"):
        document["skills"] = [{
            "id": _id("skills"),
            "label": "技能",
            "skills": [item.get("name", "") for item in content["skills"] if item.get("name")],
        }]
    return normalize_resume_document(document)


def document_to_resume_content(document: dict[str, Any]) -> dict[str, Any]:
    basics = document.get("basics") or {}
    links = basics.get("links") or []
    website = next((item.get("url", "") for item in links if item.get("url")), "")
    experiences = []
    for item in document.get("experiences", []) or []:
        experiences.append({
            "id": item.get("id") or _id("experience"),
            "company": item.get("company", ""),
            "role": item.get("role", ""),
            "start_date": item.get("startDate", ""),
            "end_date": "" if item.get("endDate") == "至今" else item.get("endDate", ""),
            "current": item.get("endDate") == "至今",
            "description": "\n".join(item.get("bullets", []) or []),
        })
    projects = []
    for item in document.get("projects", []) or []:
        projects.append({
            "id": item.get("id") or _id("project"),
            "name": item.get("name", ""),
            "role": item.get("role", ""),
            "link": item.get("link", ""),
            "description": "\n".join(item.get("bullets", []) or []),
        })
    education = []
    for item in document.get("education", []) or []:
        education.append({
            "id": item.get("id") or _id("education"),
            "school": item.get("school", ""),
            "degree": item.get("degree", ""),
            "start_date": item.get("startDate", ""),
            "end_date": item.get("endDate", ""),
        })
    skills = []
    for group in document.get("skills", []) or []:
        for name in group.get("skills", []) or []:
            skills.append({"id": _id("skill"), "name": name, "level": "熟练"})
    return {
        "personal": {
            "name": basics.get("name", ""),
            "title": basics.get("headline", "") or document.get("targetRole", ""),
            "email": basics.get("email", ""),
            "phone": basics.get("phone", ""),
            "location": basics.get("location", ""),
            "website": website,
            "summary": document.get("selfEvaluation", ""),
        },
        "experiences": experiences,
        "projects": projects,
        "education": education,
        "skills": skills,
    }

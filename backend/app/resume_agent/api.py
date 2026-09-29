"""Local Resume Agent API backed by the open-source Resume Agent core."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from ..database import connection
from ..schemas import Resume
from .adapter import document_to_resume_content, resume_to_document
from .core.export_docx import build_docx
from .core.export_pdf import build_pdf
from .core.patching import PatchError, apply_patches, normalize_resume_document
from .schemas import AgentDocumentUpdate, AgentGoalUpdate, AgentSessionCreate, AgentSessionOut
from .store import create_session, get_session, update_session

router = APIRouter(prefix="/api/resume-agent", tags=["resume-agent"])


def _resume(resume_id: str) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    data = dict(row)
    import json
    data["content"] = json.loads(data["content"])
    return data


def _out(session: dict) -> AgentSessionOut:
    return AgentSessionOut(
        id=session["id"], source_resume_id=session["source_resume_id"], document=session["document"],
        goal=session["goal"], version=session["version"], messages=session["messages"],
        created_at=session["created_at"], updated_at=session["updated_at"],
    )


@router.post("/sessions", response_model=AgentSessionOut, status_code=status.HTTP_201_CREATED)
def create_agent_session(payload: AgentSessionCreate) -> AgentSessionOut:
    source = _resume(payload.source_resume_id) if payload.source_resume_id else None
    document = resume_to_document(source)
    document["audience"] = payload.audience
    if payload.target_role:
        document["targetRole"] = payload.target_role
        document["basics"]["headline"] = payload.target_role
    document = normalize_resume_document(document)
    return _out(create_session(payload.source_resume_id, document))


@router.get("/sessions/{session_id}", response_model=AgentSessionOut)
def get_agent_session(session_id: str) -> AgentSessionOut:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return _out(session)


@router.put("/sessions/{session_id}/goal", response_model=AgentSessionOut)
def update_agent_goal(session_id: str, payload: AgentGoalUpdate) -> AgentSessionOut:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent session not found")
    goal = payload.goal.model_dump()
    document = dict(session["document"])
    document["goal"] = goal
    document["targetRole"] = goal.get("target_role") or document.get("targetRole") or ""
    document["basics"] = dict(document.get("basics") or {})
    if goal.get("target_role"):
        document["basics"]["headline"] = goal["target_role"]
    document["audience"] = {"graduate_reexamination": "graduate_examiner", "internship": "internship_recruiter", "campus_recruitment": "internship_recruiter", "social_recruitment": "hr"}.get(goal.get("purpose"), "general")
    return _out(update_session(session_id, document=normalize_resume_document(document), goal=goal))


@router.patch("/sessions/{session_id}/document", response_model=AgentSessionOut)
def update_agent_document(session_id: str, payload: AgentDocumentUpdate) -> AgentSessionOut:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent session not found")
    if payload.base_version != session["version"]:
        raise HTTPException(status_code=409, detail="Document version is stale")
    try:
        document = apply_patches(session["document"], [patch.model_dump() for patch in payload.patches])
    except PatchError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    document = normalize_resume_document(document)
    updated = update_session(session_id, document=document, version=session["version"] + 1)
    if updated and session["source_resume_id"]:
        content = document_to_resume_content(document)
        with connection() as conn:
            conn.execute("UPDATE resumes SET content = ?, updated_at = ? WHERE id = ?", (
                __import__("json").dumps(content, ensure_ascii=False), updated["updated_at"], session["source_resume_id"],
            ))
    return _out(updated)


@router.get("/sessions/{session_id}/export/docx")
def export_agent_docx(session_id: str) -> Response:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return Response(build_docx(session["document"]), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=resume.docx"})


@router.get("/sessions/{session_id}/export/pdf")
def export_agent_pdf(session_id: str) -> Response:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return Response(build_pdf(session["document"]), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=resume.pdf"})

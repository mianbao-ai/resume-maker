"""Resume Agent API."""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from features.auth.dependencies import get_current_active_user
from infrastructure.database.sql import get_session as get_db_session
from models import User

from .export_docx import build_docx
from .export_pdf import build_pdf
from .patching import PatchError
from .schemas import (
    ApplyProposalRequest,
    ApplyProposalResponse,
    ChatRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    ExportPdfRequest,
    RejectProposalResponse,
    ResumeGoalInput,
    UpdateDocumentRequest,
    UpdateDocumentResponse,
    UpdateGoalResponse,
)
from .service import resume_agent_service
from .skills import list_resume_skills

router = APIRouter(prefix="/api/resume-agent", tags=["resume-agent"])


@router.get("/skills")
async def get_skills():
    """Return the resume skills currently available for explicit invocation."""
    return list_resume_skills()


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List all optimization sessions for the current user (most recent first)."""
    from sqlmodel import select as sql_select
    from models.resume_agent import ResumeAgentSession as Session
    result = await db.execute(
        sql_select(Session)
        .where(Session.user_id == str(current_user.id))
        .where(Session.mode == "optimization")
        .order_by(Session.updated_at.desc())
        .limit(20)
    )
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "audience": s.audience,
            "target_role": s.target_role,
            "document_version": s.document_version,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=CreateSessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Load a specific session with its messages."""
    try:
        session = await resume_agent_service.get_session_for_user(db, session_id, str(current_user.id))
    except PermissionError:
        raise HTTPException(status_code=404, detail="Resume agent session not found")

    messages = await resume_agent_service.list_messages(db, session.id)
    proposals_by_message = await resume_agent_service.list_proposals_by_message(db, session.id)
    return CreateSessionResponse(
        session_id=session.id,
        resume_document=session.resume_document_json,
        messages=[
            resume_agent_service.serialize_message(message, proposals_by_message.get(message.id))
            for message in messages
        ],
    )


@router.put("/sessions/{session_id}/goal", response_model=UpdateGoalResponse)
async def update_goal(
    session_id: str,
    body: ResumeGoalInput,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        session = await resume_agent_service.get_session_for_user(db, session_id, str(current_user.id))
    except PermissionError:
        raise HTTPException(status_code=404, detail="Resume agent session not found")

    document, goal_messages = await resume_agent_service.update_goal(
        db,
        session,
        body.model_dump(),
    )
    return UpdateGoalResponse(
        resume_document=document,
        messages=[resume_agent_service.serialize_message(message) for message in goal_messages],
    )


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    session = await resume_agent_service.create_or_load_session(
        db=db,
        user_id=str(current_user.id),
        source_resume_id=body.source_resume_id,
        audience=body.audience,
        target_role=body.target_role,
        force_new=body.force_new,
    )
    messages = await resume_agent_service.list_messages(db, session.id)
    proposals_by_message = await resume_agent_service.list_proposals_by_message(db, session.id)
    return CreateSessionResponse(
        session_id=session.id,
        resume_document=session.resume_document_json,
        messages=[
            resume_agent_service.serialize_message(message, proposals_by_message.get(message.id))
            for message in messages
        ],
    )


@router.patch("/sessions/{session_id}/document", response_model=UpdateDocumentResponse)
async def update_document(
    session_id: str,
    body: UpdateDocumentRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        session = await resume_agent_service.get_session_for_user(db, session_id, str(current_user.id))
        document = await resume_agent_service.update_document(
            db,
            session,
            [patch.model_dump() for patch in body.patches],
            body.base_version,
        )
        return UpdateDocumentResponse(resume_document=document)
    except PermissionError:
        raise HTTPException(status_code=404, detail="Resume agent session not found")
    except PatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/sessions/{session_id}/chat/stream")
async def chat_stream(
    session_id: str,
    body: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        session = await resume_agent_service.get_session_for_user(db, session_id, str(current_user.id))
    except PermissionError:
        raise HTTPException(status_code=404, detail="Resume agent session not found")

    async def event_stream():
        try:
            async for item in resume_agent_service.chat_stream(
                db, session, body.message, body.audience, body.model,
                skill_id=body.skill_id, page_count=body.page_count,
            ):
                yield f"event: {item['event']}\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/sessions/{session_id}/proposals/{proposal_id}/apply", response_model=ApplyProposalResponse)
async def apply_proposal(
    session_id: str,
    proposal_id: str,
    body: ApplyProposalRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        session = await resume_agent_service.get_session_for_user(db, session_id, str(current_user.id))
        document, proposal = await resume_agent_service.apply_proposal(
            db, session, proposal_id, body.patch_ids, body.overrides, body.base_version,
        )
        return ApplyProposalResponse(
            resume_document=document,
            applied_proposal=resume_agent_service.serialize_proposal(proposal),
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="Proposal not found")
    except PatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/sessions/{session_id}/proposals/{proposal_id}/reject", response_model=RejectProposalResponse)
async def reject_proposal(
    session_id: str,
    proposal_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        session = await resume_agent_service.get_session_for_user(db, session_id, str(current_user.id))
        proposal = await resume_agent_service.reject_proposal(db, session, proposal_id)
        return RejectProposalResponse(proposal=resume_agent_service.serialize_proposal(proposal))
    except PermissionError:
        raise HTTPException(status_code=404, detail="Proposal not found")
    except PatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/sessions/{session_id}/export/docx")
async def export_docx(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        session = await resume_agent_service.get_session_for_user(db, session_id, str(current_user.id))
    except PermissionError:
        raise HTTPException(status_code=404, detail="Resume agent session not found")

    if not session.resume_document_json:
        raise HTTPException(status_code=400, detail="当前会话没有可导出的简历")

    content = build_docx(session.resume_document_json)
    filename = f"resume-{datetime.utcnow().strftime('%Y%m%d')}.docx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/sessions/{session_id}/export/pdf")
async def export_pdf(
    session_id: str,
    body: ExportPdfRequest | None = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        session = await resume_agent_service.get_session_for_user(db, session_id, str(current_user.id))
    except PermissionError:
        raise HTTPException(status_code=404, detail="Resume agent session not found")

    if not session.resume_document_json:
        raise HTTPException(status_code=400, detail="当前会话没有可导出的简历")

    content = build_pdf(
        session.resume_document_json,
        html=body.html if body else None,
        css=body.css if body else None,
    )
    filename = f"resume-{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

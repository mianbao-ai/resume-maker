"""Resume Agent service."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from features.profile.storage import get_resume_with_path
from features.resume.chains.schemas import ProjectType, ResumeFacts
from features.resume.parsing_service import get_parsing_service
from models.resume_agent import ResumeAgentMessage, ResumeAgentProposal, ResumeAgentSession
from utils.deepseek_config import (
    get_deepseek_base_url,
    get_deepseek_extra_body,
    get_deepseek_model,
)

from uuid import uuid4

from .mapping import section_order_for_template
from .patching import (
    DEFAULT_SECTION_ORDERS,
    PatchError,
    apply_patches,
    override_proposal_text,
    normalize_resume_document,
)
from .prompts import build_system_prompt


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _sid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


_GOAL_LABELS = {
    "graduate_reexamination": "研究生复试",
    "internship": "实习申请",
    "campus_recruitment": "秋招／校招",
    "social_recruitment": "社招",
    "other": "其他用途",
    "undecided": "暂未确定方向",
}


def _goal_audience(purpose: str) -> str:
    if purpose == "graduate_reexamination":
        return "graduate_examiner"
    if purpose in {"internship", "campus_recruitment"}:
        return "internship_recruiter"
    if purpose == "social_recruitment":
        return "hr"
    return "general"


def _goal_summary(goal: Dict[str, Any]) -> str:
    parts = [_GOAL_LABELS.get(goal.get("purpose"), "其他用途")]
    for key in ("target_organization", "target_role", "research_direction"):
        value = str(goal.get(key) or "").strip()
        if value and value not in parts:
            parts.append(value)
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def _build_llm(model: str = "deepseek-v4", streaming: bool = True) -> ChatOpenAI:
    if model == "deepseek-v4":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")
        return ChatOpenAI(
            model=get_deepseek_model("RESUME_AGENT_MODEL"),
            api_key=api_key,
            base_url=get_deepseek_base_url(),
            extra_body=get_deepseek_extra_body(),
            temperature=0.4,
            streaming=streaming,
            http_async_client=httpx.AsyncClient(timeout=120.0),
        )

    if model == "doubao-seed-2.1-pro":
        api_key = os.getenv("ARK_API_KEY")
        if not api_key:
            raise RuntimeError("ARK_API_KEY is not set")
        return ChatOpenAI(
            model=os.getenv("RESUME_AGENT_DOUBAO_MODEL") or "doubao-seed-2-1-pro-260628",
            api_key=api_key,
            base_url=os.getenv("ARK_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3",
            temperature=0.4,
            streaming=streaming,
            http_async_client=httpx.AsyncClient(timeout=120.0),
        )

    raise ValueError("Unsupported resume agent model")


_PROPOSAL_OPEN = "<resume_proposal>"
_QUESTION_OPEN = "<resume_question>"
_HIDDEN_OPENS = (_PROPOSAL_OPEN, _QUESTION_OPEN)
_PROPOSAL_START_RE = re.compile(
    r"<resume_proposal(?:\s*>|(?=\s*\{)|$)",
    re.IGNORECASE,
)
_QUESTION_START_RE = re.compile(
    r"<resume_question(?:\s*>|(?=\s*\{)|$)",
    re.IGNORECASE,
)


def _unwrap_json_payload(payload_text: str) -> str:
    text = payload_text.lstrip()
    if text.startswith(">"):
        text = text[1:].lstrip()
    if text.startswith("```json"):
        text = text[len("```json"):].lstrip()
    elif text.startswith("```"):
        text = text[3:].lstrip()
    return text


def _extract_tagged_json(text: str, start_re: re.Pattern[str]) -> tuple[str, Optional[Any]]:
    """Split visible copy from a tagged JSON block, tolerating a missing close tag."""
    start_match = start_re.search(text)
    if not start_match:
        return text, None

    clean_prefix = text[: start_match.start()].rstrip()
    payload_text = _unwrap_json_payload(text[start_match.end():])
    try:
        payload, end = json.JSONDecoder().raw_decode(payload_text)
    except (json.JSONDecodeError, ValueError):
        return clean_prefix, None

    remainder = payload_text[end:]
    close_idx = remainder.find("</")
    if close_idx >= 0:
        close_end = remainder.find(">", close_idx)
        if close_end >= 0:
            remainder = remainder[close_end + 1:]
    remainder = remainder.strip()
    if remainder:
        clean_text = f"{clean_prefix}\n{remainder}".strip() if clean_prefix else remainder
    else:
        clean_text = clean_prefix
    return clean_text, payload


def _normalize_questions(raw: Any) -> Optional[List[Dict[str, Any]]]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        items = raw.get("questions")
        if items is None and raw.get("title") and raw.get("options") is not None:
            items = [raw]
        elif items is None:
            return None
    elif isinstance(raw, list):
        items = raw
    else:
        return None
    if not isinstance(items, list):
        return None

    questions: List[Dict[str, Any]] = []
    for index, item in enumerate(items[:3]):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        options_raw = item.get("options") or []
        if not title or not isinstance(options_raw, list):
            continue
        options: List[Dict[str, Any]] = []
        for option_index, option in enumerate(options_raw[:6]):
            if isinstance(option, str):
                label = option.strip()
                if not label:
                    continue
                options.append({
                    "id": f"opt_{option_index + 1}",
                    "label": label,
                    "description": "",
                    "recommended": False,
                })
                continue
            if not isinstance(option, dict):
                continue
            label = str(option.get("label") or option.get("title") or "").strip()
            if not label:
                continue
            options.append({
                "id": str(option.get("id") or f"opt_{option_index + 1}"),
                "label": label,
                "description": str(option.get("description") or "").strip(),
                "recommended": bool(option.get("recommended")),
            })
        if len(options) < 2:
            continue
        questions.append({
            "id": str(item.get("id") or f"q_{index + 1}"),
            "title": title,
            "allow_other": bool(item.get("allow_other", False)),
            "options": options,
        })
    return questions or None


def _extract_structured_output(text: str) -> tuple[str, Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
    remaining, proposal_raw = _extract_tagged_json(text, _PROPOSAL_START_RE)
    remaining, question_raw = _extract_tagged_json(remaining, _QUESTION_START_RE)

    proposal = None
    if isinstance(proposal_raw, dict) and isinstance(proposal_raw.get("patches"), list) and proposal_raw.get("title"):
        proposal = proposal_raw

    questions = _normalize_questions(question_raw)
    return remaining, proposal, questions


def _extract_proposal(text: str) -> tuple[str, Optional[Dict[str, Any]]]:
    """Split model text into visible copy and a proposal, tolerating a missing close tag."""
    clean_text, proposal, _questions = _extract_structured_output(text)
    return clean_text, proposal


def _history_assistant_content(message: ResumeAgentMessage) -> str:
    content = message.content or ""
    payload = message.payload_json or {}
    questions = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(questions, list) or not questions:
        return content
    lines = [content, "", "[已向用户展示选择题]"]
    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            continue
        title = str(question.get("title") or "").strip()
        if title:
            lines.append(f"{index}. {title}")
        for option in question.get("options") or []:
            if not isinstance(option, dict):
                continue
            label = str(option.get("label") or "").strip()
            if not label:
                continue
            recommended = "（推荐）" if option.get("recommended") else ""
            description = str(option.get("description") or "").strip()
            suffix = f"：{description}" if description else ""
            lines.append(f"   - {label}{recommended}{suffix}")
    return "\n".join(line for line in lines if line is not None).strip()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ResumeAgentService:
    """Application service for chat-with-resume optimization."""

    def __init__(self):
        self.parsing_service = get_parsing_service()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def create_or_load_session(
        self,
        db: AsyncSession,
        user_id: str,
        source_resume_id: Optional[str],
        audience: str,
        target_role: Optional[str],
        force_new: bool = False,
    ) -> ResumeAgentSession:
        if not force_new:
            stmt = (
                select(ResumeAgentSession)
                .where(ResumeAgentSession.user_id == user_id)
                .where(ResumeAgentSession.mode == "optimization")
            )
            if source_resume_id:
                stmt = stmt.where(ResumeAgentSession.source_resume_id == source_resume_id)
            stmt = stmt.order_by(ResumeAgentSession.updated_at.desc())
            existing = (await db.execute(stmt)).scalars().first()
        else:
            existing = None

        if existing:
            normalized_document = normalize_resume_document(existing.resume_document_json)
            if normalized_document != existing.resume_document_json:
                existing.resume_document_json = normalized_document
            if not normalized_document.get("goal"):
                existing.audience = audience or existing.audience
                existing.target_role = target_role or existing.target_role
            existing.updated_at = datetime.utcnow()
            db.add(existing)
            await db.commit()
            await db.refresh(existing)
            return existing

        resume_facts = await self._get_or_parse_resume_facts(user_id, source_resume_id)
        document = self._resume_facts_to_document(
            user_id=user_id,
            source_resume_id=source_resume_id,
            resume_facts=resume_facts or ResumeFacts(resume_id=source_resume_id or "empty"),
            audience=audience,
            target_role=target_role,
        )
        session = ResumeAgentSession(
            user_id=user_id,
            source_resume_id=source_resume_id,
            mode="optimization",
            target_role=target_role,
            audience=audience,
            resume_document_json=document,
            document_version=document["version"],
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def list_messages(self, db: AsyncSession, session_id: str) -> List[ResumeAgentMessage]:
        result = await db.execute(
            select(ResumeAgentMessage)
            .where(ResumeAgentMessage.session_id == session_id)
            .order_by(ResumeAgentMessage.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_proposals_by_message(
        self, db: AsyncSession, session_id: str
    ) -> Dict[str, List[ResumeAgentProposal]]:
        """Return {message_id: [proposal, ...]} for all proposals in the session."""
        result = await db.execute(
            select(ResumeAgentProposal)
            .where(ResumeAgentProposal.session_id == session_id)
            .where(ResumeAgentProposal.message_id.isnot(None))
            .order_by(ResumeAgentProposal.created_at.asc())
        )
        proposals = result.scalars().all()
        mapping: Dict[str, List[ResumeAgentProposal]] = {}
        for p in proposals:
            mapping.setdefault(p.message_id, []).append(p)
        return mapping

    async def get_session_for_user(self, db: AsyncSession, session_id: str, user_id: str) -> ResumeAgentSession:
        session = await db.get(ResumeAgentSession, session_id)
        if not session or session.user_id != user_id:
            raise PermissionError("Resume agent session not found")
        normalized_document = normalize_resume_document(session.resume_document_json)
        if normalized_document != session.resume_document_json:
            session.resume_document_json = normalized_document
            session.updated_at = datetime.utcnow()
            db.add(session)
            await db.commit()
            await db.refresh(session)
        return session

    async def update_goal(
        self,
        db: AsyncSession,
        session: ResumeAgentSession,
        goal_input: Dict[str, Any],
    ) -> tuple[Dict[str, Any], List[ResumeAgentMessage]]:
        """Confirm the purpose of this resume version before optimization starts."""
        goal = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in goal_input.items()
            if value is not None
        }
        goal["confirmed_at"] = _now_iso()

        purpose = goal["purpose"]
        audience = _goal_audience(purpose)
        template_id = (
            "postgraduate-interview-v1"
            if purpose == "graduate_reexamination"
            else "tech-elegant-v1"
        )
        target_role = goal.get("target_role") or None

        next_doc = normalize_resume_document(session.resume_document_json)
        next_doc["goal"] = goal
        next_doc["audience"] = audience
        next_doc["targetRole"] = target_role or ""
        next_doc["templateId"] = template_id
        next_doc["sectionOrder"] = section_order_for_template(template_id)
        next_version = int(session.document_version or 1) + 1
        next_doc["version"] = next_version
        next_doc["updatedAt"] = _now_iso()

        session.audience = audience
        session.target_role = target_role
        session.resume_document_json = next_doc
        session.document_version = next_version
        session.updated_at = datetime.utcnow()

        summary = _goal_summary(goal)
        user_message = ResumeAgentMessage(
            session_id=session.id,
            role="user",
            content=f"我想把这份简历用于：{summary}",
            intent="goal_confirmation",
            payload_json={"goal": goal},
        )
        assistant_message = ResumeAgentMessage(
            session_id=session.id,
            role="assistant",
            content=(
                f"好的，这一版简历将用于「{summary}」。"
                "后续诊断和修改都会围绕这个目标展开。"
            ),
            intent="goal_confirmation",
            payload_json={"goal": goal},
        )
        db.add(session)
        db.add(user_message)
        db.add(assistant_message)
        await db.commit()
        await db.refresh(session)
        return session.resume_document_json, [user_message, assistant_message]

    # ------------------------------------------------------------------
    # Chat streaming
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        db: AsyncSession,
        session: ResumeAgentSession,
        message: str,
        audience: Optional[str] = None,
        model: str = "deepseek-v4",
        skill_id: Optional[str] = None,
        page_count: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        goal = (session.resume_document_json or {}).get("goal")
        if not isinstance(goal, dict) or not goal.get("confirmed_at"):
            raise ValueError("请先确认这份简历的使用目标")

        # Detect style prefix from frontend
        style: Optional[str] = None
        clean_message = message
        if message.startswith("[直接优化模式]"):
            style = "optimize"
            clean_message = message.replace("[直接优化模式]", "", 1).strip()
        elif "不要修改简历" in message or "只做诊断" in message:
            style = "chat"

        # Persist user message (without the style prefix)
        user_msg = ResumeAgentMessage(
            session_id=session.id,
            role="user",
            content=clean_message,
            intent=f"skill:{skill_id}" if skill_id else "question",
            payload_json={"page_count": page_count} if skill_id else None,
        )
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)

        session.audience = audience or session.audience
        session.updated_at = datetime.utcnow()
        db.add(session)
        await db.commit()

        # Build conversation history for LLM
        history = await self.list_messages(db, session.id)
        lc_messages = self._build_lc_messages(
            session=session,
            history=history,
            audience=audience or session.audience,
            style="optimize" if skill_id else style,
            skill_id=skill_id,
            page_count=page_count,
        )

        # Stream from LLM; suppress tokens once a structured XML block starts
        full_text = ""
        stream_buffer = ""
        hidden_started = False
        try:
            llm = _build_llm(model=model, streaming=True)
            async for chunk in llm.astream(lc_messages):
                delta = chunk.content or ""
                if not delta:
                    continue
                full_text += delta
                if hidden_started:
                    continue
                stream_buffer += delta
                visible_text, stream_buffer, hidden_started = _split_proposal_stream_buffer(
                    stream_buffer
                )
                if visible_text:
                    yield {"event": "message_delta", "data": {"content": visible_text}}

        except Exception as exc:
            logger.exception("Resume agent LLM error")
            raise RuntimeError(f"AI 服务暂时不可用：{exc}") from exc

        # Flush ordinary trailing text, but never leak an incomplete structured marker.
        if not hidden_started and stream_buffer and not _is_proposal_marker_fragment(stream_buffer):
            yield {"event": "message_delta", "data": {"content": stream_buffer}}

        clean_text, proposal_data, questions = _extract_structured_output(full_text)

        # Persist assistant message
        assistant_msg = ResumeAgentMessage(
            session_id=session.id,
            role="assistant",
            content=clean_text,
            intent="proposal" if proposal_data else "question",
            payload_json={"questions": questions} if questions else None,
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        # Persist proposal if present
        proposal_row = None
        if proposal_data:
            patches = proposal_data.get("patches") or []
            # Assign stable IDs to patches if missing
            for i, patch in enumerate(patches):
                if not patch.get("id"):
                    patch["id"] = f"patch_{i + 1}"
            proposal_row = ResumeAgentProposal(
                session_id=session.id,
                message_id=assistant_msg.id,
                title=proposal_data.get("title", "简历修改提案"),
                rationale=proposal_data.get("rationale", ""),
                patches_json=patches,
                risk_notes_json=proposal_data.get("risk_notes") or [],
            )
            db.add(proposal_row)
            await db.commit()
            await db.refresh(proposal_row)
            yield {"event": "proposal", "data": self.serialize_proposal(proposal_row)}

        if questions:
            yield {"event": "question", "data": {"questions": questions}}

        yield {"event": "done", "data": {}}

    # ------------------------------------------------------------------
    # Proposal actions
    # ------------------------------------------------------------------

    async def update_document(
        self,
        db: AsyncSession,
        session: ResumeAgentSession,
        patches: List[Dict[str, Any]],
        base_version: int,
    ) -> Dict[str, Any]:
        """Persist direct user edits through the same safe patch engine as AI proposals."""
        if int(session.document_version or 1) != base_version:
            raise PatchError("简历已在其他位置更新，请刷新后重试")

        next_doc = apply_patches(session.resume_document_json, patches)
        next_version = base_version + 1
        next_doc["version"] = next_version
        next_doc["updatedAt"] = _now_iso()
        session.resume_document_json = next_doc
        session.document_version = next_version
        session.updated_at = datetime.utcnow()
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session.resume_document_json

    async def apply_proposal(
        self,
        db: AsyncSession,
        session: ResumeAgentSession,
        proposal_id: str,
        patch_ids: Optional[List[str]],
        overrides: Optional[Dict[str, Any]] = None,
        base_version: Optional[int] = None,
    ) -> tuple[Dict[str, Any], ResumeAgentProposal]:
        proposal = await db.get(ResumeAgentProposal, proposal_id)
        if not proposal or proposal.session_id != session.id:
            raise PermissionError("Proposal not found")
        if proposal.status != "pending":
            raise PatchError("Proposal is not pending")

        if base_version is not None and base_version != session.document_version:
            raise PatchError("简历已发生变化，请刷新后重新审阅修改")
        patches = override_proposal_text(proposal.patches_json, overrides, patch_ids)
        next_doc = apply_patches(session.resume_document_json, patches, patch_ids)
        next_version = int(session.document_version or 1) + 1
        next_doc["version"] = next_version
        next_doc["updatedAt"] = _now_iso()
        session.resume_document_json = next_doc
        session.document_version = next_version
        session.updated_at = datetime.utcnow()
        proposal.status = "accepted"
        proposal.patches_json = patches
        proposal.updated_at = datetime.utcnow()
        db.add(session)
        db.add(proposal)
        await db.commit()
        await db.refresh(session)
        await db.refresh(proposal)
        return session.resume_document_json, proposal

    async def reject_proposal(
        self,
        db: AsyncSession,
        session: ResumeAgentSession,
        proposal_id: str,
    ) -> ResumeAgentProposal:
        proposal = await db.get(ResumeAgentProposal, proposal_id)
        if not proposal or proposal.session_id != session.id:
            raise PermissionError("Proposal not found")
        if proposal.status != "pending":
            raise PatchError("Proposal is not pending")
        proposal.status = "rejected"
        proposal.updated_at = datetime.utcnow()
        db.add(proposal)
        db.add(ResumeAgentMessage(
            session_id=session.id,
            role="system",
            content=f"用户拒绝了修改提案：{proposal.title}",
            intent="proposal",
            payload_json={"proposal_id": proposal.id, "status": "rejected"},
        ))
        await db.commit()
        await db.refresh(proposal)
        return proposal

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize_message(
        self,
        message: ResumeAgentMessage,
        proposals: Optional[List[ResumeAgentProposal]] = None,
    ) -> Dict[str, Any]:
        payload = message.payload_json if isinstance(message.payload_json, dict) else {}
        return {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "intent": message.intent,
            "proposals": [self.serialize_proposal(p) for p in (proposals or [])],
            "questions": payload.get("questions") or [],
            "created_at": message.created_at.isoformat(),
        }

    def serialize_proposal(self, proposal: ResumeAgentProposal) -> Dict[str, Any]:
        return {
            "id": proposal.id,
            "status": proposal.status,
            "title": proposal.title,
            "rationale": proposal.rationale,
            "patches": proposal.patches_json or [],
            "risk_notes": proposal.risk_notes_json or [],
            "created_at": proposal.created_at.isoformat(),
        }

    # ------------------------------------------------------------------
    # LangChain message building
    # ------------------------------------------------------------------

    def _build_lc_messages(
        self,
        session: ResumeAgentSession,
        history: List[ResumeAgentMessage],
        audience: str,
        style: Optional[str] = None,
        skill_id: Optional[str] = None,
        page_count: Optional[int] = None,
    ) -> list:
        system_prompt = build_system_prompt(
            audience=audience,
            resume_document=session.resume_document_json or {},
            target_role=session.target_role,
            style=style,
            skill_id=skill_id,
            page_count=page_count,
        )
        messages = [SystemMessage(content=system_prompt)]
        for msg in history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=_history_assistant_content(msg)))
            # skip system messages (they are internal bookkeeping)
        return messages

    # ------------------------------------------------------------------
    # Resume document construction from canonical resume facts
    # ------------------------------------------------------------------

    async def _get_or_parse_resume_facts(
        self,
        user_id: str,
        resume_id: Optional[str],
    ) -> Optional[ResumeFacts]:
        cached = self.parsing_service.get_cached_facts(user_id, resume_id=resume_id)
        if cached:
            return cached

        resume_result = await get_resume_with_path(user_id, resume_id=resume_id)
        if not resume_result:
            return None
        _, path = resume_result
        return await self.parsing_service.parse_and_save(str(path), user_id, resume_id=resume_id)

    def _resume_facts_to_document(
        self,
        user_id: str,
        source_resume_id: Optional[str],
        resume_facts: ResumeFacts,
        audience: str,
        target_role: Optional[str],
    ) -> Dict[str, Any]:
        primary_education = resume_facts.education[0] if resume_facts.education else None
        basics = {
            "name": resume_facts.basic_info.name or "未命名",
            "headline": target_role or resume_facts.basic_info.headline or (primary_education.major if primary_education else ""),
            "gender": "",
            "phone": resume_facts.basic_info.phone,
            "email": resume_facts.basic_info.email,
            "location": resume_facts.basic_info.location,
            "extras": [],
            "links": [],
        }
        education = [{
            "id": item.education_id,
            "school": item.institution_name or "学校待补充",
            "degree": item.degree,
            "major": item.major,
            "startDate": item.start_date,
            "endDate": item.end_date,
            "gpa": item.grade,
            "highlights": [*item.courses, *item.highlights],
        } for item in resume_facts.education]

        experiences = []
        for item in resume_facts.work_experience:
            bullets = [*item.responsibilities, *item.achievements]
            experiences.append({
                "id": item.experience_id,
                "company": item.organization_name or "组织待补充",
                "role": item.position,
                "startDate": item.start_date,
                "endDate": item.end_date,
                "location": item.location,
                "bullets": [str(b) for b in bullets if b and b != "未提供"],
            })

        projects = []
        research = []
        for item in resume_facts.project_experience:
            bullets = [
                item.description,
                *item.responsibilities,
                *item.methods,
                *item.personal_contribution,
                *item.achievements,
            ]
            entry = {
                "id": item.project_id,
                "name": item.project_name or "项目经历",
                "role": item.role,
                "startDate": item.start_date,
                "endDate": item.end_date,
                "techStack": item.tech_stack,
                "bullets": [b for b in bullets if b and b != "未提供"],
            }
            is_research_only = (
                ProjectType.RESEARCH in item.project_types
                and not any(
                    project_type in item.project_types
                    for project_type in (ProjectType.ENGINEERING, ProjectType.PRODUCT)
                )
            )
            if is_research_only:
                research.append({
                    **{key: value for key, value in entry.items() if key != "name"},
                    "title": entry["name"],
                })
            else:
                projects.append(entry)

        for publication in resume_facts.achievements.publications:
            research.append({
                "id": publication.publication_id,
                "title": publication.title,
                "role": "",
                "advisor": "",
                "date": publication.date,
                "bullets": [value for value in (publication.venue, "、".join(publication.authors)) if value],
            })

        awards = [{
            "id": item.award_id,
            "title": item.name,
            "date": item.date,
            "issuer": item.issuer,
            "level": item.level,
        } for item in resume_facts.achievements.awards]
        awards.extend({
            "id": item.certification_id,
            "title": item.name,
            "date": item.date,
            "issuer": item.issuer,
        } for item in resume_facts.achievements.certifications)

        skills = []
        if resume_facts.skills:
            skills.append({"id": _sid("skills"), "label": "技能", "skills": resume_facts.skills})

        languages = [{
            "id": _sid("language"),
            "name": item.language,
            "level": item.proficiency or "、".join(item.certifications),
        } for item in resume_facts.languages]
        courses = [{
            "id": _sid("courses"),
            "label": "主修课程",
            "skills": list(dict.fromkeys(
                course
                for item in resume_facts.education
                for course in item.courses
            )),
        }] if any(item.courses for item in resume_facts.education) else []

        template_id = (
            "postgraduate-interview-v1"
            if audience == "graduate_examiner"
            else "tech-elegant-v1"
        )
        section_order = list(DEFAULT_SECTION_ORDERS[template_id])

        return {
            "id": _sid("resume"),
            "userId": user_id,
            "sourceResumeId": source_resume_id,
            "title": f"{basics['name']}的简历",
            "targetRole": target_role or "",
            "audience": audience,
            "locale": "zh-CN",
            "templateId": template_id,
            "sectionOrder": section_order,
            "basics": basics,
            "education": education,
            "projects": projects,
            "experiences": experiences,
            "research": research,
            "awards": awards,
            "skills": skills,
            "selfEvaluation": "",
            "languages": languages,
            "courses": courses,
            "strengths": [],
            "volunteering": [],
            "interests": [],
            "industryExpertise": [],
            "custom": [],
            "formatting": {"entries": {}, "inline": {}},
            "version": 1,
            "createdAt": _now_iso(),
            "updatedAt": _now_iso(),
        }


# ---------------------------------------------------------------------------
# Streaming text helpers
# ---------------------------------------------------------------------------

def _proposal_marker_suffix_length(text: str) -> int:
    """Return the suffix length that may be the beginning of a hidden XML marker."""
    retained = 0
    for marker in _HIDDEN_OPENS:
        max_length = min(len(text), len(marker) - 1)
        for length in range(max_length, 0, -1):
            if marker.startswith(text[-length:]):
                retained = max(retained, length)
                break
    return retained


def _split_proposal_stream_buffer(buffer: str) -> tuple[str, str, bool]:
    """Expose safe text while retaining a possible split structured marker."""
    marker_index = None
    for marker in _HIDDEN_OPENS:
        found = buffer.find(marker)
        if found >= 0 and (marker_index is None or found < marker_index):
            marker_index = found
    if marker_index is not None:
        return buffer[:marker_index].rstrip(), "", True

    retained_length = _proposal_marker_suffix_length(buffer)
    if retained_length:
        return buffer[:-retained_length], buffer[-retained_length:], False
    return buffer, "", False


def _is_proposal_marker_fragment(text: str) -> bool:
    stripped = text.lstrip()
    if len(stripped) < len("<resume"):
        return False
    return any(marker.startswith(stripped) for marker in _HIDDEN_OPENS)


resume_agent_service = ResumeAgentService()

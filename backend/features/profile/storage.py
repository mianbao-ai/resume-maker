"""
Filesystem helpers for storing and retrieving user resumes.

Canonical layout (relative to DATA_ROOT):
    {environment}/<user_id>/resume/<stored_filename>
Where environment is normalized to one of: development (default), staging, production.
"""
import os
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.sql import async_session
from models.resume import ResumeFile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.getenv("DATA_ROOT", PROJECT_ROOT / "data")).resolve()


def _normalize_env_name(raw_env: Optional[str]) -> str:
    """Map assorted environment labels to a consistent directory name."""
    if not raw_env:
        return "development"

    env = raw_env.lower()
    if env in ("dev", "development", "local"):
        return "development"
    if env in ("prod", "production"):
        return "production"
    if env in ("stage", "staging"):
        return "staging"
    return env


ENV_NAME = _normalize_env_name(os.getenv("ENV") or os.getenv("ENVIRONMENT"))


def get_user_base_dir(user_id: str) -> Path:
    """Base directory for a user's data (resume/info)."""
    base = DATA_ROOT / ENV_NAME / str(user_id)
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_user_directory(user_id: str) -> Path:
    """Return the resume directory for a given user."""
    directory = get_user_base_dir(user_id) / "resume"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def build_storage_path(user_id: str, stored_filename: str) -> Path:
    """Construct absolute path to the stored resume file."""
    return get_user_directory(user_id) / stored_filename


def remove_file_if_exists(path: Path) -> None:
    """Delete the file at path if present."""
    try:
        if path.exists():
            path.unlink()
            logger.info(f"🗑️ 已删除旧简历文件: {path}")
    except Exception as exc:
        logger.warning(f"⚠️ 删除旧简历文件失败 ({path}): {exc}")


async def get_resume_record(
    user_id: str,
    session: Optional[AsyncSession] = None,
    resume_id: Optional[str] = None,
) -> Optional[ResumeFile]:
    """Fetch resume metadata for a user, optionally filtered by resume_id."""
    owns_session = False
    if session is None:
        session = async_session()
        owns_session = True

    try:
        stmt = select(ResumeFile).where(ResumeFile.user_id == str(user_id))
        if resume_id:
            stmt = stmt.where(ResumeFile.id == resume_id)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
        else:
            default_stmt = stmt.where(ResumeFile.is_interview_default == True).order_by(ResumeFile.updated_at.desc())
            result = await session.execute(default_stmt)
            record = result.scalars().first()
            if record is None:
                stmt = stmt.order_by(ResumeFile.updated_at.desc())
                result = await session.execute(stmt)
                record = result.scalars().first()
        return record
    finally:
        if owns_session:
            await session.close()


async def list_resume_records(
    user_id: str,
    session: Optional[AsyncSession] = None,
) -> List[ResumeFile]:
    """List all resumes owned by a user, with the interview default first."""
    owns_session = False
    if session is None:
        session = async_session()
        owns_session = True

    try:
        stmt = (
            select(ResumeFile)
            .where(ResumeFile.user_id == str(user_id))
            .order_by(ResumeFile.is_interview_default.desc(), ResumeFile.updated_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    finally:
        if owns_session:
            await session.close()


async def get_resume_with_path(
    user_id: str,
    resume_id: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> Optional[Tuple[ResumeFile, Path]]:
    """Return resume metadata and ensure the file exists on disk."""
    owns_session = False
    if session is None:
        session = async_session()
        owns_session = True

    try:
        record = await get_resume_record(user_id, session=session, resume_id=resume_id)
        if not record:
            return None

        path = Path(record.storage_path)

        if not path.exists():
            logger.error(f"❌ 简历文件不存在: {path}")

            # Try the canonical storage path (handles legacy env folder names)
            canonical_path = build_storage_path(user_id, record.stored_filename)
            alt_path = None
            if canonical_path.exists():
                alt_path = canonical_path
            else:
                # Last resort: search under data/*/{user_id}/resume/
                for candidate in DATA_ROOT.glob(f"**/{user_id}/resume/{record.stored_filename}"):
                    if candidate.exists():
                        alt_path = candidate
                        break

            if alt_path:
                logger.warning(f"📁 使用规范路径中的简历文件: {alt_path}")
                record.storage_path = str(alt_path)
                session.add(record)
                await session.commit()
                await session.refresh(record)
                path = alt_path
            else:
                logger.error("❌ 规范路径中也未找到简历文件")
                return None

        return record, path
    finally:
        if owns_session:
            await session.close()

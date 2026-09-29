"""Runtime registry for callable Resume Agent skills."""

from typing import Any, Dict, List, Optional

from . import compress_one_page
from .base import ResumeSkillContext, ResumeSkillError, ResumeSkillManifest


_SKILL_MODULES = {
    compress_one_page.MANIFEST.id: compress_one_page,
}


def get_resume_skill(skill_id: str):
    """Return a registered skill module or raise a stable domain error."""
    skill = _SKILL_MODULES.get(skill_id)
    if skill is None:
        raise ResumeSkillError(f"Unsupported resume skill: {skill_id}")
    return skill


def list_resume_skills() -> List[Dict[str, Any]]:
    """Return public manifests for the skills currently available."""
    return [module.MANIFEST.public_dict() for module in _SKILL_MODULES.values()]


def build_skill_instruction(skill_id: Optional[str], page_count: Optional[int]) -> str:
    """Validate a skill id and build its model-facing instruction."""
    if skill_id is None:
        return ""
    skill = get_resume_skill(skill_id)
    return skill.build_instruction(page_count)


def validate_skill_context(skill_id: str, context: ResumeSkillContext) -> ResumeSkillManifest:
    """Validate skill inputs before the orchestration runtime invokes a model."""
    skill = get_resume_skill(skill_id)
    skill.validate_context(context)
    return skill.MANIFEST

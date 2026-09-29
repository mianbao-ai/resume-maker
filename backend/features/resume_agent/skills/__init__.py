"""Callable skills for the Resume Agent.

The package keeps skill contracts separate from prompt text.  A skill may
start as a prompt-backed capability, but it must expose explicit metadata and
validation boundaries before it is allowed to mutate a ResumeDocument.
"""

from .base import ResumeSkillManifest
from .registry import (
    build_skill_instruction,
    get_resume_skill,
    list_resume_skills,
    validate_skill_context,
)

__all__ = [
    "ResumeSkillManifest",
    "build_skill_instruction",
    "get_resume_skill",
    "list_resume_skills",
    "validate_skill_context",
]

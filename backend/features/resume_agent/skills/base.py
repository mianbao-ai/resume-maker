"""Shared contracts for Resume Agent skills."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ResumeSkillManifest:
    """Stable metadata and policy boundaries for one callable skill."""

    id: str
    title: str
    description: str
    version: str = "1.0.0"
    risk_level: str = "medium"
    requires_user_confirmation: bool = True
    max_iterations: int = 1
    required_inputs: List[str] = field(default_factory=list)
    allowed_patch_roots: List[str] = field(default_factory=list)
    validators: List[str] = field(default_factory=list)

    def public_dict(self) -> Dict[str, Any]:
        """Return metadata safe to expose through the skills API."""
        return asdict(self)


@dataclass(frozen=True)
class ResumeSkillContext:
    """Inputs available to a skill during one execution.

    The context is deliberately data-only.  Skills should return proposals;
    persistence and document mutation remain responsibilities of the runtime.
    """

    resume_document: Dict[str, Any]
    goal: Dict[str, Any]
    page_count: Optional[int] = None
    selected_paths: List[str] = field(default_factory=list)


class ResumeSkillError(ValueError):
    """Raised when a skill cannot safely accept its current inputs."""

"""Deterministic routing policy for the Resume Agent.

The LLM or skill runtime is responsible for producing structured observations.
This module decides whether the run can continue or must pause for a user
decision. It deliberately does not inspect raw user text or render UI.
"""

from dataclasses import dataclass
from typing import Literal, Optional


ResumeAgentIntentType = Literal[
    "confirm_goal",
    "request_evidence",
    "propose_rewrite",
    "clarify_request",
]
NextAction = Literal["continue", "wait_for_user", "complete", "error"]


@dataclass(frozen=True)
class RouterContext:
    """Structured observations available to one routing decision."""

    skill_id: Optional[str] = None
    goal_confirmed: bool = False
    evidence_missing: bool = False
    evidence_ambiguous: bool = False
    rewrite_ready: bool = False
    user_request_ambiguous: bool = False
    pending_user_decision: bool = False


@dataclass(frozen=True)
class RouterDecision:
    """A transport-neutral decision consumed by the orchestrator."""

    intent: Optional[ResumeAgentIntentType]
    next_action: NextAction
    activity_label: str
    reason_code: str


def _activity_label(skill_id: Optional[str], *, completed: bool = False) -> str:
    labels = {
        "compress_one_page": "压缩到一页",
        "rewrite_expression": "表达优化",
        "align_with_jd": "岗位 JD 对齐",
        "check_factual_support": "事实核对",
    }
    title = labels.get(skill_id or "", "简历分析")
    return f"已完成「{title}」" if completed else f"正在处理「{title}」"


def route_resume_intent(context: RouterContext) -> RouterDecision:
    """Route structured observations to the next user-facing checkpoint.

    Ordering is intentional: an existing pending decision wins first, then
    goal/evidence gates, and only then can a grounded rewrite be proposed.
    """

    if context.pending_user_decision:
        return RouterDecision(
            intent=None,
            next_action="wait_for_user",
            activity_label="等待你的决定",
            reason_code="pending_user_decision",
        )

    if context.user_request_ambiguous:
        return RouterDecision(
            intent="clarify_request",
            next_action="wait_for_user",
            activity_label="需要你补充优化目标",
            reason_code="ambiguous_user_request",
        )

    if context.skill_id and not context.goal_confirmed:
        return RouterDecision(
            intent="confirm_goal",
            next_action="wait_for_user",
            activity_label="等待确认简历使用目标",
            reason_code="goal_not_confirmed",
        )

    if context.evidence_missing or context.evidence_ambiguous:
        return RouterDecision(
            intent="request_evidence",
            next_action="wait_for_user",
            activity_label="等待你补充真实经历",
            reason_code="evidence_gate",
        )

    if context.rewrite_ready:
        return RouterDecision(
            intent="propose_rewrite",
            next_action="wait_for_user",
            activity_label="修改提案已准备好，等待你确认",
            reason_code="grounded_rewrite_ready",
        )

    if context.skill_id:
        return RouterDecision(
            intent=None,
            next_action="continue",
            activity_label=_activity_label(context.skill_id),
            reason_code="skill_can_continue",
        )

    return RouterDecision(
        intent=None,
        next_action="complete",
        activity_label=_activity_label(context.skill_id, completed=True),
        reason_code="no_user_checkpoint",
    )

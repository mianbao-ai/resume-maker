"""The explicit one-page compression skill."""

from typing import Optional

from .base import ResumeSkillContext, ResumeSkillError, ResumeSkillManifest


MANIFEST = ResumeSkillManifest(
    id="compress_one_page",
    title="压缩到一页",
    description="按目标岗位保留最有价值的事实，提出可确认的精简修改。",
    version="1.0.0",
    risk_level="high",
    requires_user_confirmation=True,
    max_iterations=2,
    required_inputs=["resume_document", "goal", "page_count"],
    allowed_patch_roots=[
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
    ],
    validators=[
        "fact_integrity",
        "patch_safety",
        "goal_alignment",
        "render_page_count",
    ],
)


def validate_context(context: ResumeSkillContext) -> None:
    """Validate the minimum context before asking an LLM to draft patches."""
    if not context.resume_document:
        raise ResumeSkillError("compress_one_page requires a structured resume document")
    if not context.goal:
        raise ResumeSkillError("compress_one_page requires a confirmed resume goal")
    if context.page_count is None:
        raise ResumeSkillError("compress_one_page requires a measured page count")
    if context.page_count < 1:
        raise ResumeSkillError("page_count must be a positive integer")


def build_instruction(page_count: Optional[int]) -> str:
    """Build the skill-specific instruction injected into the agent prompt."""
    measured_pages = (
        f"前端按当前模板实测为 {page_count} 页。"
        if page_count
        else "前端尚未提供页数测量结果。"
    )
    return f"""\
## 当前调用的元技能：压缩到一页

{measured_pages}目标是在**当前模板**下压缩到一页；不要通过切换模板、缩小字号或压低行距来伪装完成。
这是用户本次显式调用的任务，不要把一页限制泛化到其他会话或资深候选人的正常两页简历。

执行顺序：
1. 结合已确认目标与 JD，先保留联系方式、教育/工作关键事实、岗位相关成果和真实指标。
2. 找出占版面最多而价值最低的重复 bullet、空泛自评、无关课程或重复技能；优先合并与改写，再考虑删除。
3. 输出**一个**包含多处局部 patch 的修改提案，尽量用叶子字段；每处改动都应可在修改前后核对。
4. 在可见文字中概括保留和删减的理由，并指出这只是候选方案，用户接受后仍要以页面重新测量验证是否达成一页。
5. 若必须删掉可能重要的经历才能达成目标，先用选择题卡片让用户决定取舍，不要擅自删除。

安全边界：不得编造指标、篡改日期/学历/公司/职位，不得改写姓名和联系方式；不得删除唯一能证明目标岗位能力的证据。
不得声称已经达到一页；只有渲染器重新测得一页才算完成。"""

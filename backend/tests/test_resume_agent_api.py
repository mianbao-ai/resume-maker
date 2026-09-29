import pytest

from features.resume_agent.patching import PatchError, apply_patches


def test_resume_agent_patch_protocol():
    document = {
        "templateId": "ats-classic-v1",
        "sectionOrder": [
            "education", "experiences", "projects", "research", "skills",
            "awards", "selfEvaluation", "languages", "courses", "strengths",
            "volunteering", "industryExpertise", "interests", "custom",
        ],
        "basics": {"name": "测试用户", "headline": "工程师"},
    }
    updated = apply_patches(document, [{
        "id": "headline",
        "op": "replace",
        "path": "/basics/headline",
        "after": "高级工程师",
    }])
    assert updated["basics"]["headline"] == "高级工程师"


def test_resume_agent_rejects_unknown_patch_root():
    with pytest.raises(PatchError):
        apply_patches({}, [{"id": "bad", "op": "replace", "path": "/goal", "after": {}}])

from fastapi.testclient import TestClient

from app.main import app


def payload():
    return {
        "title": "产品经理简历",
        "template": "classic",
        "accent_color": "#176B5B",
        "content": {
            "personal": {
                "name": "测试用户",
                "title": "产品经理",
                "email": "test@example.com",
                "summary": "负责数字产品交付。",
            },
            "experiences": [{
                "id": "exp-1",
                "company": "示例公司",
                "role": "产品经理",
                "start_date": "2022",
                "end_date": "2024",
                "description": "负责路线图\n推动版本发布",
            }],
            "projects": [],
            "education": [],
            "skills": [{"id": "skill-1", "name": "用户研究", "level": "熟练"}],
        },
    }


def test_agent_session_goal_patch_and_export(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_DB_PATH", str(tmp_path / "agent.db"))
    with TestClient(app) as client:
        resume = client.post("/api/resumes", json=payload()).json()
        created = client.post("/api/resume-agent/sessions", json={"source_resume_id": resume["id"]})
        assert created.status_code == 201
        session = created.json()
        assert session["document"]["basics"]["name"] == "测试用户"
        assert session["document"]["templateId"] == "ats-classic-v1"

        goal = client.put(
            f"/api/resume-agent/sessions/{session['id']}/goal",
            json={"goal": {"purpose": "social_recruitment", "target_role": "高级产品经理"}},
        )
        assert goal.status_code == 200
        assert goal.json()["document"]["targetRole"] == "高级产品经理"

        patched = client.patch(
            f"/api/resume-agent/sessions/{session['id']}/document",
            json={
                "base_version": 1,
                "patches": [{
                    "id": "patch-1",
                    "op": "replace",
                    "path": "/basics/headline",
                    "after": "高级产品经理",
                }],
            },
        )
        assert patched.status_code == 200
        assert patched.json()["version"] == 2
        assert patched.json()["document"]["basics"]["headline"] == "高级产品经理"

        stale = client.patch(
            f"/api/resume-agent/sessions/{session['id']}/document",
            json={"base_version": 1, "patches": []},
        )
        assert stale.status_code == 409

        exported = client.get(f"/api/resume-agent/sessions/{session['id']}/export/docx")
        assert exported.status_code == 200
        assert exported.headers["content-type"].startswith("application/vnd.openxmlformats")
        assert exported.content[:2] == b"PK"

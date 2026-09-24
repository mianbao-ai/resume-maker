from fastapi.testclient import TestClient

from app.main import app


def sample_payload():
    return {
        "title": "前端工程师简历",
        "template": "classic",
        "accent_color": "#176B5B",
        "content": {
            "personal": {"name": "测试用户", "email": "test@example.com"},
            "experiences": [],
            "projects": [],
            "education": [],
            "skills": [],
        },
    }


def test_resume_crud(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        created = client.post("/api/resumes", json=sample_payload())
        assert created.status_code == 201
        resume_id = created.json()["id"]

        assert client.get(f"/api/resumes/{resume_id}").status_code == 200
        assert len(client.get("/api/resumes").json()) == 1

        payload = sample_payload()
        payload["title"] = "高级前端工程师简历"
        updated = client.put(f"/api/resumes/{resume_id}", json=payload)
        assert updated.json()["title"] == "高级前端工程师简历"

        assert client.delete(f"/api/resumes/{resume_id}").status_code == 204
        assert client.get(f"/api/resumes/{resume_id}").status_code == 404

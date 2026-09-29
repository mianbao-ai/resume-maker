from fastapi.testclient import TestClient

from main import app


def test_health_and_skills():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        skills = client.get("/api/resume-agent/skills")
        assert skills.status_code == 200
        assert isinstance(skills.json(), list)

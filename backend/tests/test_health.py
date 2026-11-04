from fastapi.testclient import TestClient

from app.main import app


def test_health_check_reports_database_readiness():
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "orchestra-ai"
    assert response.json()["demo_mode"] in {"mock", "real"}

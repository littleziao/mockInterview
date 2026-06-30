from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app import database
from apps.api.app.main import app


def test_health_check_reports_sqlite_status(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        database,
        "DEFAULT_DATABASE_PATH",
        tmp_path / "mock_interview.sqlite3",
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "mock-interview-api",
        "database": {"status": "ok", "migration": "0001_initial"},
    }


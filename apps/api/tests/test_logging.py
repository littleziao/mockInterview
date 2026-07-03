from __future__ import annotations

import logging
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app.logging_config import configure_logging
from apps.api.app.main import app


def _mock_interview_handlers() -> list[logging.Handler]:
    root = logging.getLogger()
    return [h for h in root.handlers if getattr(h, "_mock_interview_logging", False)]


def test_configure_logging_is_idempotent() -> None:
    configure_logging()
    after_first = len(_mock_interview_handlers())
    configure_logging()
    configure_logging()
    after_repeats = len(_mock_interview_handlers())

    assert after_first == 1
    assert after_repeats == 1


def test_configure_logging_defaults_to_info(monkeypatch) -> None:
    monkeypatch.delenv("MOCK_INTERVIEW_LOG_LEVEL", raising=False)
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_configure_logging_respects_env_level(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_LOG_LEVEL", "DEBUG")
    configure_logging()
    assert logging.getLogger().level == logging.DEBUG

    monkeypatch.setenv("MOCK_INTERVIEW_LOG_LEVEL", "WARNING")
    configure_logging()
    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_falls_back_on_invalid_level(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_LOG_LEVEL", "不是级别")
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_configure_logging_silences_noisy_libraries() -> None:
    configure_logging()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


def test_http_exception_handler_logs_and_preserves_response(
    monkeypatch, tmp_path: Path, caplog
) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_DB_PATH", str(tmp_path / "mock.sqlite3"))

    with TestClient(app) as client:
        with caplog.at_level(logging.WARNING):
            response = client.delete("/resume-analysis-records/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "简历分析记录不存在"}

    warning_records = [
        record for record in caplog.records if record.levelno == logging.WARNING
    ]
    assert any("HTTP DELETE" in record.message and "404" in record.message for record in warning_records)

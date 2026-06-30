import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app.main import app


def test_ai_settings_returns_missing_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))

    with TestClient(app) as client:
        response = client.get("/settings/ai-provider")

    assert response.status_code == 200
    assert response.json() == {
        "activeProviderId": "",
        "providers": [],
    }


def test_ai_settings_migrates_legacy_single_provider_config(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "ai-provider.json"
    config_path.write_text(
        json.dumps(
            {
                "baseUrl": "fake://success",
                "apiKey": "secret-key",
                "model": "mock-model",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(config_path))

    with TestClient(app) as client:
        response = client.get("/settings/ai-provider")

    assert response.status_code == 200
    assert response.json() == {
        "activeProviderId": "default",
        "providers": [
            {
                "id": "default",
                "name": "默认供应商",
                "baseUrl": "fake://success",
                "model": "mock-model",
                "hasApiKey": True,
                "isConfigured": True,
            }
        ],
    }


def test_ai_settings_saves_and_reads_multiple_private_providers(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "ai-provider.json"
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(config_path))

    payload = {
        "activeProviderId": "backup",
        "providers": [
            {
                "id": "default",
                "name": "主供应商",
                "baseUrl": "fake://success",
                "apiKey": "primary-key",
                "model": "primary-model",
            },
            {
                "id": "backup",
                "name": "备用供应商",
                "baseUrl": "fake://failure",
                "apiKey": "backup-key",
                "model": "backup-model",
            },
        ],
    }

    with TestClient(app) as client:
        response = client.put("/settings/ai-provider", json=payload)
        read_response = client.get("/settings/ai-provider")

    expected = {
        "activeProviderId": "backup",
        "providers": [
            {
                "id": "default",
                "name": "主供应商",
                "baseUrl": "fake://success",
                "model": "primary-model",
                "hasApiKey": True,
                "isConfigured": True,
            },
            {
                "id": "backup",
                "name": "备用供应商",
                "baseUrl": "fake://failure",
                "model": "backup-model",
                "hasApiKey": True,
                "isConfigured": True,
            },
        ],
    }
    assert response.status_code == 200
    assert response.json() == expected
    assert read_response.status_code == 200
    assert read_response.json() == expected
    assert "primary-key" in config_path.read_text(encoding="utf-8")
    assert "backup-key" in config_path.read_text(encoding="utf-8")


def test_ai_settings_save_keeps_existing_api_key_when_payload_is_blank(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "ai-provider.json"
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(config_path))

    with TestClient(app) as client:
        client.put(
            "/settings/ai-provider",
            json={
                "activeProviderId": "default",
                "providers": [
                    {
                        "id": "default",
                        "name": "主供应商",
                        "baseUrl": "fake://success",
                        "apiKey": "secret-key",
                        "model": "mock-model",
                    }
                ],
            },
        )
        response = client.put(
            "/settings/ai-provider",
            json={
                "activeProviderId": "default",
                "providers": [
                    {
                        "id": "default",
                        "name": "主供应商",
                        "baseUrl": "fake://success",
                        "apiKey": "",
                        "model": "updated-model",
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "activeProviderId": "default",
        "providers": [
            {
                "id": "default",
                "name": "主供应商",
                "baseUrl": "fake://success",
                "model": "updated-model",
                "hasApiKey": True,
                "isConfigured": True,
            }
        ],
    }
    assert "secret-key" in config_path.read_text(encoding="utf-8")


def test_ai_settings_test_connection_uses_active_provider_success(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))

    with TestClient(app) as client:
        client.put(
            "/settings/ai-provider",
            json={
                "activeProviderId": "default",
                "providers": [
                    {
                        "id": "default",
                        "name": "主供应商",
                        "baseUrl": "fake://success",
                        "apiKey": "secret-key",
                        "model": "mock-model",
                    }
                ],
            },
        )
        response = client.post("/settings/ai-provider/test")

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "message": "AI Provider 连接测试成功",
    }


def test_ai_settings_test_connection_uses_active_provider_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))

    with TestClient(app) as client:
        client.put(
            "/settings/ai-provider",
            json={
                "activeProviderId": "backup",
                "providers": [
                    {
                        "id": "default",
                        "name": "主供应商",
                        "baseUrl": "fake://success",
                        "apiKey": "secret-key",
                        "model": "mock-model",
                    },
                    {
                        "id": "backup",
                        "name": "备用供应商",
                        "baseUrl": "fake://failure",
                        "apiKey": "secret-key",
                        "model": "mock-model",
                    },
                ],
            },
        )
        response = client.post("/settings/ai-provider/test")

    assert response.status_code == 200
    assert response.json() == {
        "status": "failure",
        "message": "Fake AI Provider 连接失败",
    }


def test_ai_settings_test_connection_reports_missing_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MOCK_INTERVIEW_AI_CONFIG_PATH", str(tmp_path / "ai-provider.json"))

    with TestClient(app) as client:
        response = client.post("/settings/ai-provider/test")

    assert response.status_code == 200
    assert response.json() == {
        "status": "missing",
        "message": "请先新增并选择一个模型供应商",
    }

from pathlib import Path

from apps.api.app.database import DatabaseSettings, database_health, initialize_database


def test_initialize_database_creates_schema_migration(tmp_path: Path) -> None:
    settings = DatabaseSettings(path=tmp_path / "mock_interview.sqlite3")

    initialize_database(settings)

    health = database_health(settings)
    assert health == {"status": "ok", "migration": "0001_initial"}
    assert settings.path.exists()


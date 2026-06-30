from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DATABASE_PATH = Path("data/mock_interview.sqlite3")


@dataclass(frozen=True)
class DatabaseSettings:
    path: Path


def get_database_settings() -> DatabaseSettings:
    configured_path = os.getenv("MOCK_INTERVIEW_DB_PATH")
    return DatabaseSettings(path=Path(configured_path) if configured_path else DEFAULT_DATABASE_PATH)


def connect(settings: DatabaseSettings | None = None) -> sqlite3.Connection:
    active_settings = settings or get_database_settings()
    active_settings.path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(active_settings.path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(settings: DatabaseSettings | None = None) -> None:
    with connect(settings) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
            ("0001_initial",),
        )


def database_health(settings: DatabaseSettings | None = None) -> dict[str, str]:
    initialize_database(settings)
    with connect(settings) as connection:
        migration = connection.execute(
            "SELECT version FROM schema_migrations WHERE version = ?",
            ("0001_initial",),
        ).fetchone()

    return {
        "status": "ok" if migration else "error",
        "migration": migration["version"] if migration else "missing",
    }


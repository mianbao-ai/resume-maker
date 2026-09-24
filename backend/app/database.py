import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "resumes.db"


def db_path() -> Path:
    return Path(os.getenv("RESUME_DB_PATH", str(DEFAULT_DB)))


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resumes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                template TEXT NOT NULL,
                accent_color TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["content"] = json.loads(data["content"])
    return data

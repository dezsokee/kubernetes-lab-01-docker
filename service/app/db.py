"""SQLite persistence layer.

A single connection is shared between requests and guarded by a lock: FastAPI
runs synchronous endpoints in a thread pool, and a sqlite3 connection opened
with ``check_same_thread=False`` is only safe if access is serialized.
"""

import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_DB_PATH = "/data/snipbox.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snippets (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    language   TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS snippets_created_at ON snippets (created_at DESC);
"""

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def db_path() -> Path:
    return Path(os.environ.get("SNIPBOX_DB_PATH", DEFAULT_DB_PATH))


def connect() -> sqlite3.Connection:
    """Open (once) the shared connection and make sure the schema exists."""
    global _conn
    with _lock:
        if _conn is None:
            path = db_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # WAL survives an unclean container stop better than the default
            # rollback journal, and keeps readers from blocking the writer.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(_SCHEMA)
            conn.commit()
            _conn = conn
        return _conn


def close() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def insert(snippet_id: str, title: str, language: str, content: str) -> dict:
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    conn = connect()
    with _lock, conn:
        conn.execute(
            "INSERT INTO snippets (id, title, language, content, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (snippet_id, title, language, content, created_at),
        )
    return {
        "id": snippet_id,
        "title": title,
        "language": language,
        "content": content,
        "created_at": created_at,
    }


def get(snippet_id: str) -> dict | None:
    conn = connect()
    with _lock:
        row = conn.execute(
            "SELECT * FROM snippets WHERE id = ?", (snippet_id,)
        ).fetchone()
    return dict(row) if row is not None else None


def list_all(limit: int, offset: int) -> list[dict]:
    conn = connect()
    with _lock:
        rows = conn.execute(
            "SELECT * FROM snippets ORDER BY created_at DESC, id"
            " LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]


def delete(snippet_id: str) -> bool:
    conn = connect()
    with _lock, conn:
        cursor = conn.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
    return cursor.rowcount > 0


def count() -> int:
    conn = connect()
    with _lock:
        return conn.execute("SELECT COUNT(*) FROM snippets").fetchone()[0]

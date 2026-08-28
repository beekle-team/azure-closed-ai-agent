from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

from closed_agent.settings import settings

_lock = Lock()
_connections: dict[str, sqlite3.Connection] = {}


def resolve_db_path(path: Path | None = None) -> Path:
    if path is None:
        target = settings.data_dir / "control.sqlite"
    elif path.suffix in {".json", ".jsonl"}:
        target = path.with_suffix(".sqlite")
    elif path.suffix == ".sqlite":
        target = path
    elif path.is_dir() or path.suffix == "":
        target = path / "control.sqlite" if path.suffix == "" else path
    else:
        target = path.with_suffix(".sqlite")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = resolve_db_path(path)
    key = str(target.resolve())
    with _lock:
        existing = _connections.get(key)
        if existing is not None:
            return existing
        conn = sqlite3.connect(target, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _init(conn)
        _connections[key] = conn
        return conn


def _init(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            actor_email TEXT NOT NULL,
            department TEXT NOT NULL,
            question TEXT NOT NULL,
            skill_id TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            decided_at TEXT NOT NULL DEFAULT '',
            decided_by TEXT NOT NULL DEFAULT '',
            result TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            user_id TEXT NOT NULL,
            department TEXT NOT NULL,
            resource TEXT NOT NULL,
            outcome TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            channel TEXT NOT NULL DEFAULT '',
            prev_hash TEXT NOT NULL,
            hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            department TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '',
            approval_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );
        """
    )
    conn.commit()


def close_all() -> None:
    with _lock:
        for conn in _connections.values():
            conn.close()
        _connections.clear()

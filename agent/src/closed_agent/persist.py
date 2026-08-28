from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

from closed_agent.settings import settings

_lock = Lock()
_handles: dict[str, "Handle"] = {}


class Row:
    def __init__(self, data: dict[str, object]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> object:
        return self._data[key]

    def keys(self):
        return self._data.keys()

    def __contains__(self, key: object) -> bool:
        return key in self._data


class Result:
    def __init__(self, rows: list[Row]) -> None:
        self._rows = rows

    def fetchone(self) -> Row | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Row]:
        return list(self._rows)


class Handle:
    def __init__(self, kind: str, raw: object) -> None:
        self.kind = kind
        self._raw = raw

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> Result:
        statement = sql.replace("?", "%s") if self.kind == "postgres" else sql
        if self.kind == "postgres":
            cursor = self._raw.cursor()  # type: ignore[union-attr]
            try:
                cursor.execute(statement, params)
                rows = _pg_rows(cursor)
            finally:
                cursor.close()
            return Result(rows)
        cursor = self._raw.execute(statement, params)  # type: ignore[union-attr]
        if cursor.description is None:
            return Result([])
        columns = [item[0] for item in cursor.description]
        return Result([Row(dict(zip(columns, values))) for values in cursor.fetchall()])

    def commit(self) -> None:
        self._raw.commit()  # type: ignore[union-attr]

    def close(self) -> None:
        self._raw.close()  # type: ignore[union-attr]


def _pg_rows(cursor) -> list[Row]:
    if cursor.description is None:
        return []
    columns = [item.name for item in cursor.description]
    return [Row(dict(zip(columns, values))) for values in cursor.fetchall()]


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


def backend(path: Path | None = None) -> str:
    if path is None and settings.database_url.strip():
        return "postgres"
    return "sqlite"


def connect(path: Path | None = None) -> Handle:
    if path is None and settings.database_url.strip():
        key = f"postgres:{settings.database_url.strip()}"
        with _lock:
            existing = _handles.get(key)
            if existing is not None:
                return existing
            handle = _open_postgres(settings.database_url.strip())
            _handles[key] = handle
            return handle
    target = resolve_db_path(path)
    key = f"sqlite:{target.resolve()}"
    with _lock:
        existing = _handles.get(key)
        if existing is not None:
            return existing
        raw = sqlite3.connect(target, check_same_thread=False)
        raw.execute("PRAGMA journal_mode=WAL")
        raw.execute("PRAGMA foreign_keys=ON")
        handle = Handle("sqlite", raw)
        _init_sqlite(handle)
        _handles[key] = handle
        return handle


def _open_postgres(url: str) -> Handle:
    import psycopg

    raw = psycopg.connect(url)
    handle = Handle("postgres", raw)
    _init_postgres(handle)
    return handle


def _init_sqlite(handle: Handle) -> None:
    handle._raw.executescript(  # type: ignore[union-attr]
        """
        CREATE TABLE IF NOT EXISTS ca_approvals (
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
        CREATE TABLE IF NOT EXISTS ca_audit (
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
        CREATE TABLE IF NOT EXISTS ca_conversations (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            department TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ca_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '',
            approval_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES ca_conversations(id)
        );
        """
    )
    handle.commit()


def _init_postgres(handle: Handle) -> None:
    handle.execute(
        """
        CREATE TABLE IF NOT EXISTS ca_approvals (
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
        )
        """
    )
    handle.execute(
        """
        CREATE TABLE IF NOT EXISTS ca_audit (
            id BIGSERIAL PRIMARY KEY,
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
        )
        """
    )
    handle.execute(
        """
        CREATE TABLE IF NOT EXISTS ca_conversations (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            department TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    handle.execute(
        """
        CREATE TABLE IF NOT EXISTS ca_messages (
            id BIGSERIAL PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES ca_conversations(id),
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '',
            approval_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    handle.commit()


def close_all() -> None:
    with _lock:
        for handle in _handles.values():
            handle.close()
        _handles.clear()

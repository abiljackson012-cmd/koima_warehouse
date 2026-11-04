"""Деректер қоры қабаты.

Әдепкіде SQLite (дайындыққа ыңғайлы), DATABASE_URL=postgresql://... болса PostgreSQL
(Neon / Supabase / Railway). SQL сұраныстарда `?` белгісі қолданылады, PostgreSQL үшін
ол автоматты түрде `%s` болып ауысады.
"""
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g


class ConflictError(Exception):
    """Бірегейлік (UNIQUE) немесе басқа тұтастық шектеуі бұзылды."""


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','manager','admin')),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Басқа',
    price INTEGER NOT NULL CHECK (price >= 0),
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    min_quantity INTEGER NOT NULL DEFAULT 0 CHECK (min_quantity >= 0),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('in','out','init')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,
    expires_at TEXT NOT NULL
)
"""

PG_SCHEMA = SQLITE_SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Conn:
    def __init__(self, raw, kind):
        self.raw = raw
        self.kind = kind  # "sqlite" | "pg"

    def _prep(self, sql):
        return sql.replace("?", "%s") if self.kind == "pg" else sql

    def _cursor(self):
        if self.kind == "pg":
            from psycopg2.extras import RealDictCursor
            return self.raw.cursor(cursor_factory=RealDictCursor)
        return self.raw.cursor()

    def _run(self, sql, params):
        cur = self._cursor()
        try:
            cur.execute(self._prep(sql), tuple(params))
        except Exception as e:  # noqa: BLE001
            if isinstance(e, sqlite3.IntegrityError) or type(e).__name__ in ("IntegrityError", "UniqueViolation"):
                raise ConflictError(str(e)) from e
            raise
        return cur

    def query(self, sql, params=()):
        return [dict(r) for r in self._run(sql, params).fetchall()]

    def one(self, sql, params=()):
        row = self._run(sql, params).fetchone()
        return dict(row) if row else None

    def execute(self, sql, params=()):
        return self._run(sql, params).rowcount

    def insert(self, sql, params=()):
        if self.kind == "pg":
            return self._run(sql + " RETURNING id", params).fetchone()["id"]
        return self._run(sql, params).lastrowid

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


def _connect(url: str) -> Conn:
    if url.startswith("sqlite:///"):
        raw = sqlite3.connect(url[len("sqlite:///"):], timeout=10)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON")
        return Conn(raw, "sqlite")
    if url.startswith(("postgres://", "postgresql://")):
        try:
            import psycopg2
        except ImportError as e:
            raise RuntimeError("PostgreSQL үшін орнатыңыз: pip install psycopg2-binary") from e
        return Conn(psycopg2.connect(url), "pg")
    raise RuntimeError("DATABASE_URL қате. Мысалы: sqlite:///warehouse.db немесе postgresql://user:pass@host/db")


def get_db() -> Conn:
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE_URL"])
    return g.db


def _finish_request(response):
    """Сұраныс сәтті болса (status < 400) транзакцияны сақтайды, әйтпесе болдырмайды."""
    db = g.get("db")
    if db is not None:
        if response.status_code < 400:
            db.commit()
        else:
            db.rollback()
    return response


def _close(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.after_request(_finish_request)
    app.teardown_appcontext(_close)


def init_db():
    db = get_db()
    schema = PG_SCHEMA if db.kind == "pg" else SQLITE_SCHEMA
    for stmt in schema.split(";"):
        if stmt.strip():
            db.execute(stmt)
    db.commit()

"""Engine and session.

Synchronous SQLAlchemy on purpose: the bot has a single user and SQLite is
local, so every operation costs microseconds. Switching to aiosqlite would
require Alembic's async template and would buy nothing here.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def _configure_pragmas(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    # WAL: allows backup/reads while the bot writes.
    cur.execute("PRAGMA journal_mode=WAL")
    # SQLite ignores FKs by default; without this the model's ForeignKeys are
    # decorative.
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


def init_engine(database_url: str) -> Engine:
    global _engine, _Session

    if database_url.startswith("sqlite:///"):
        path = database_url.removeprefix("sqlite:///")
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)

    _engine = create_engine(database_url, future=True)
    event.listen(_engine, "connect", _configure_pragmas)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("init_engine() must be called before get_engine()")
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    if _Session is None:
        raise RuntimeError("init_engine() must be called before session_scope()")
    session = _Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

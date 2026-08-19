"""Engine e sessao.

SQLAlchemy sincrono de proposito: o bot tem um unico usuario e o SQLite e local,
entao cada operacao custa microssegundos. Trocar por aiosqlite exigiria o template
async do Alembic e nao compraria nada aqui.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def _configurar_pragmas(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    # WAL: permite backup/leitura enquanto o bot escreve.
    cur.execute("PRAGMA journal_mode=WAL")
    # SQLite ignora FK por padrao; sem isso as ForeignKey do modelo sao decorativas.
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


def init_engine(database_url: str) -> Engine:
    global _engine, _Session

    if database_url.startswith("sqlite:///"):
        caminho = database_url.removeprefix("sqlite:///")
        pasta = os.path.dirname(caminho)
        if pasta:
            os.makedirs(pasta, exist_ok=True)

    _engine = create_engine(database_url, future=True)
    event.listen(_engine, "connect", _configurar_pragmas)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("init_engine() precisa ser chamado antes de get_engine()")
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    if _Session is None:
        raise RuntimeError("init_engine() precisa ser chamado antes de session_scope()")
    sessao = _Session()
    try:
        yield sessao
        sessao.commit()
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()

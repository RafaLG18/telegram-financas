"""Ambiente do Alembic.

Dois pontos que nao sao opcionais aqui:
- a URL vem do ambiente (DB_PATH), nunca do alembic.ini;
- render_as_batch=True, porque o SQLite quase nao tem ALTER TABLE e o Alembic
  precisa recriar a tabela para alterar coluna/constraint.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from caderneta.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    db_path = os.getenv("DB_PATH", "data/caderneta.db")
    pasta = os.path.dirname(db_path)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    return f"sqlite:///{db_path}"


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    secao = config.get_section(config.config_ini_section, {})
    secao["sqlalchemy.url"] = _url()

    engine = engine_from_config(secao, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with engine.connect() as conexao:
        context.configure(
            connection=conexao,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

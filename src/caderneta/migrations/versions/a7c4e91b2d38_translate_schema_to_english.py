"""translate schema to english

Renames tables, columns and the stored values of `tipo`.

SQLite has almost no ALTER TABLE, and `batch_alter_table` would recreate the
table from the reflected schema - dragging the old CHECKs along, which name the
Portuguese columns. So the new tables are created from scratch and the data is
copied with INSERT ... SELECT: table, column, constraint and value all renamed
in one go.

Revision ID: a7c4e91b2d38
Revises: f86e0739a29f
Create Date: 2026-08-20 20:15:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7c4e91b2d38'
down_revision: Union[str, None] = 'f86e0739a29f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# gasto/entrada/ambos <-> expense/income/both
_TO_ENGLISH = "CASE {col} WHEN 'gasto' THEN 'expense' WHEN 'entrada' THEN 'income' WHEN 'ambos' THEN 'both' ELSE {col} END"
_TO_PORTUGUESE = "CASE {col} WHEN 'expense' THEN 'gasto' WHEN 'income' THEN 'entrada' WHEN 'both' THEN 'ambos' ELSE {col} END"


def upgrade() -> None:
    op.create_table(
        'category',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=40), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.CheckConstraint("kind IN ('expense','income','both')", name='ck_category_kind'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.execute(
        "INSERT INTO category (id, name, kind, active) "
        f"SELECT id, nome, {_TO_ENGLISH.format(col='tipo')}, ativa FROM categoria"
    )

    op.create_table(
        'transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('account_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('source_update_id', sa.Integer(), nullable=True),
        sa.CheckConstraint("kind IN ('expense','income')", name='ck_transaction_kind'),
        sa.CheckConstraint('amount_cents > 0', name='ck_transaction_amount_positive'),
        sa.ForeignKeyConstraint(['category_id'], ['category.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_update_id'),
    )
    op.execute(
        "INSERT INTO \"transaction\" (id, kind, amount_cents, date, category_id, "
        "account_id, description, created_at, source_update_id) "
        f"SELECT id, {_TO_ENGLISH.format(col='tipo')}, valor_centavos, data, categoria_id, "
        "conta_id, descricao, criado_em, origem_update_id FROM transacao"
    )
    op.create_index('idx_transaction_date', 'transaction', ['date'], unique=False)

    op.create_table(
        'draft',
        sa.Column('id', sa.String(length=12), nullable=False),
        sa.Column('state', sa.String(length=20), nullable=False),
        sa.Column('chat_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(length=10), nullable=True),
        sa.Column('amount_cents', sa.Integer(), nullable=True),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['category.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    # A draft is ephemeral state of an in-flight flow, and the state names were
    # renamed too (tipo -> kind, ...). Migrating them is not worth the risk of a
    # half-translated draft: whoever was mid-/registrar just starts over.

    op.drop_index('idx_transacao_data', table_name='transacao')
    op.drop_table('transacao')
    op.drop_table('rascunho')
    op.drop_table('categoria')


def downgrade() -> None:
    op.create_table(
        'categoria',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=40), nullable=False),
        sa.Column('tipo', sa.String(length=10), nullable=False),
        sa.Column('ativa', sa.Boolean(), nullable=False),
        sa.CheckConstraint("tipo IN ('gasto','entrada','ambos')", name='ck_categoria_tipo'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nome'),
    )
    op.execute(
        "INSERT INTO categoria (id, nome, tipo, ativa) "
        f"SELECT id, name, {_TO_PORTUGUESE.format(col='kind')}, active FROM category"
    )

    op.create_table(
        'transacao',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=10), nullable=False),
        sa.Column('valor_centavos', sa.Integer(), nullable=False),
        sa.Column('data', sa.Date(), nullable=False),
        sa.Column('categoria_id', sa.Integer(), nullable=True),
        sa.Column('conta_id', sa.Integer(), nullable=True),
        sa.Column('descricao', sa.String(length=200), nullable=True),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('origem_update_id', sa.Integer(), nullable=True),
        sa.CheckConstraint("tipo IN ('gasto','entrada')", name='ck_transacao_tipo'),
        sa.CheckConstraint('valor_centavos > 0', name='ck_transacao_valor_positivo'),
        sa.ForeignKeyConstraint(['categoria_id'], ['categoria.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('origem_update_id'),
    )
    op.execute(
        "INSERT INTO transacao (id, tipo, valor_centavos, data, categoria_id, "
        "conta_id, descricao, criado_em, origem_update_id) "
        f"SELECT id, {_TO_PORTUGUESE.format(col='kind')}, amount_cents, date, category_id, "
        "account_id, description, created_at, source_update_id FROM \"transaction\""
    )
    op.create_index('idx_transacao_data', 'transacao', ['data'], unique=False)

    op.create_table(
        'rascunho',
        sa.Column('id', sa.String(length=12), nullable=False),
        sa.Column('estado', sa.String(length=20), nullable=False),
        sa.Column('chat_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('tipo', sa.String(length=10), nullable=True),
        sa.Column('valor_centavos', sa.Integer(), nullable=True),
        sa.Column('data', sa.Date(), nullable=True),
        sa.Column('categoria_id', sa.Integer(), nullable=True),
        sa.Column('descricao', sa.String(length=200), nullable=True),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['categoria_id'], ['categoria.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.drop_index('idx_transaction_date', table_name='transaction')
    op.drop_table('transaction')
    op.drop_table('draft')
    op.drop_table('category')

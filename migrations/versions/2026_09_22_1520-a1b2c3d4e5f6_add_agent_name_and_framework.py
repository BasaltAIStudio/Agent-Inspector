"""add agent_name and framework to audits

Revision ID: a1b2c3d4e5f6
Revises: 19fbfbd0d39e
Create Date: 2026-09-22 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '19fbfbd0d39e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("audits") as batch_op:
            batch_op.add_column(sa.Column("agent_name", sa.String(255), nullable=True))
            batch_op.add_column(sa.Column("framework", sa.String(100), nullable=True))
    else:
        op.add_column("audits", sa.Column("agent_name", sa.String(255), nullable=True))
        op.add_column("audits", sa.Column("framework", sa.String(100), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("audits") as batch_op:
            batch_op.drop_column("framework")
            batch_op.drop_column("agent_name")
    else:
        op.drop_column("audits", "framework")
        op.drop_column("audits", "agent_name")

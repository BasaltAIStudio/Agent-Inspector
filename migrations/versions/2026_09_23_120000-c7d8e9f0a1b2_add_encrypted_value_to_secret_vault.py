"""add encrypted_value to secret_vault

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("secret_vault") as batch_op:
            batch_op.add_column(sa.Column("encrypted_value", sa.Text(), nullable=True))
            batch_op.alter_column("value", existing_type=sa.Text(), nullable=True)
    else:
        op.add_column("secret_vault", sa.Column("encrypted_value", sa.Text(), nullable=True))
        op.alter_column("secret_vault", "value", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("secret_vault") as batch_op:
            batch_op.alter_column("value", existing_type=sa.Text(), nullable=False)
            batch_op.drop_column("encrypted_value")
    else:
        op.alter_column("secret_vault", "value", existing_type=sa.Text(), nullable=False)
        op.drop_column("secret_vault", "encrypted_value")
